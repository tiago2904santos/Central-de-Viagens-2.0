from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import AssinaturaConfiguracao, Cargo, ConfiguracaoSistema, UnidadeLotacao, Viajante
from eventos.models import Oficio, OficioAssinaturaPedido
from eventos.services.oficio_assinatura import formatar_nome_assinatura
from eventos.services.pdf_signature import FALLBACK_FONT_NAME, resolve_signature_font


class OficioAssinaturaFlowTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='assinatura-admin', password='senha123')
        self.client.force_login(self.user)

        cargo = Cargo.objects.create(nome='DELEGADO')
        lotacao = UnidadeLotacao.objects.create(nome='DPC')
        self.assinante = Viajante.objects.create(
            nome='JOAO MARIO DE GOES',
            cargo=cargo,
            unidade_lotacao=lotacao,
            cpf='12345678901',
            telefone='41999991234',
            rg='998877',
            status=Viajante.STATUS_FINALIZADO,
        )
        config = ConfiguracaoSistema.get_singleton()
        AssinaturaConfiguracao.objects.create(
            configuracao=config,
            tipo=AssinaturaConfiguracao.TIPO_OFICIO,
            ordem=1,
            viajante=self.assinante,
            ativo=True,
        )
        self.oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_gera_pedido_com_pdf_congelado_e_hash(self, _render_mock):
        url = reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_PENDENTE)
        self.assertTrue(bool(pedido.hash_pdf_original))
        self.assertTrue(bool(pedido.pdf_original_congelado))

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_preview_pdf_responde_com_arquivo_congelado(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        preview_url = reverse('eventos:assinatura-oficio-pdf', kwargs={'token': pedido.token})
        response = self.client.get(preview_url)
        payload = b''.join(response.streaming_content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertEqual(payload, b'PDF_ORIGINAL')

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_nome_na_tela_publica_nao_fica_em_caixa_alta_bruta(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.cpf_confirmado_em = pedido.created_at
        pedido.telefone_confirmado_em = pedido.created_at
        pedido.save(update_fields=['cpf_confirmado_em', 'telefone_confirmado_em', 'updated_at'])
        session = self.client.session
        session['oficio_assinatura_confirmada'] = {pedido.token: True}
        session.save()
        response = self.client.get(reverse('eventos:assinatura-oficio-assinar', kwargs={'token': pedido.token}))
        body = response.content.decode('utf-8')
        self.assertContains(response, 'Joao Mario de Goes')
        self.assertNotIn('JOAO MARIO DE GOES', body)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    @patch('eventos.views_assinatura.apply_text_signature_on_pdf', return_value=(b'PDF_ASSINADO', {
        'resolved_font_name': 'SignGreatVibes',
        'used_fallback': False,
        'font_detail': 'ok',
    }))
    def test_fluxo_publico_confirma_cpf_telefone_e_assina(self, sign_mock, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        identidade_url = reverse('eventos:assinatura-oficio-identidade', kwargs={'token': pedido.token})
        assinar_url = reverse('eventos:assinatura-oficio-assinar', kwargs={'token': pedido.token})

        r1 = self.client.post(identidade_url, data={'etapa': 'cpf', 'cpf_prefixo': '12345'})
        self.assertEqual(r1.status_code, 200)
        pedido.refresh_from_db()
        self.assertEqual(pedido.cpf_prefixo_confirmado, '12345')

        r2 = self.client.post(identidade_url, data={'etapa': 'telefone', 'confirmar_telefone': '1'})
        self.assertEqual(r2.status_code, 302)
        self.assertIn(assinar_url, r2.url)

        r3 = self.client.post(assinar_url, data={'fonte_escolhida': OficioAssinaturaPedido.FONTE_GREAT_VIBES})
        self.assertEqual(r3.status_code, 302)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_ASSINADO)
        self.assertEqual(pedido.fonte_escolhida, OficioAssinaturaPedido.FONTE_GREAT_VIBES)
        self.assertTrue(bool(pedido.hash_pdf_assinado))
        self.assertTrue(bool(pedido.pdf_assinado_final))
        self.assertEqual(pedido.auditoria.get('fonte_pdf_resolvida'), 'SignGreatVibes')
        self.assertFalse(bool(pedido.auditoria.get('fonte_pdf_fallback')))
        sign_mock.assert_called_once()
        self.assertEqual(sign_mock.call_args.kwargs['signer_name'], 'Joao Mario de Goes')

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio')
    def test_alteracao_real_do_oficio_invalida_assinatura(self, render_mock):
        render_mock.return_value = b'PDF_A'
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.hash_pdf_original = 'a' * 64
        pedido.save(update_fields=['status', 'hash_pdf_original', 'updated_at'])

        render_mock.return_value = b'PDF_B'
        lista_url = reverse('eventos:oficios-global')
        self.client.get(lista_url)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_INVALIDADO)


class NomeAssinaturaHelperTest(TestCase):
    def test_helper_aplica_capitalizacao_e_particulas(self):
        self.assertEqual(formatar_nome_assinatura('MARIA APARECIDA DOS SANTOS'), 'Maria Aparecida dos Santos')
        self.assertEqual(formatar_nome_assinatura('JOSE CARLOS DA SILVA E SOUZA'), 'Jose Carlos da Silva e Souza')
        self.assertEqual(formatar_nome_assinatura('JOAO MARIO DE GOES'), 'Joao Mario de Goes')


class PdfSignatureFontResolutionTest(TestCase):
    @patch('eventos.services.pdf_signature.TTFont')
    @patch('eventos.services.pdf_signature.pdfmetrics.registerFont')
    @patch('eventos.services.pdf_signature.pdfmetrics.getRegisteredFontNames', return_value=[])
    @patch('eventos.services.pdf_signature.requests.get')
    def test_resolve_signature_font_registra_fonte_real(self, get_mock, _registered_mock, register_mock, ttfont_mock):
        response = Mock()
        response.content = b'FAKE_FONT_BYTES'
        response.raise_for_status = Mock()
        get_mock.return_value = response
        ttfont_mock.return_value = Mock()

        font_name, used_fallback, _detail = resolve_signature_font('great_vibes')
        self.assertEqual(font_name, 'SignGreatVibes')
        self.assertFalse(used_fallback)
        register_mock.assert_called_once()

    def test_resolve_signature_font_fallback_para_chave_invalida(self):
        font_name, used_fallback, detail = resolve_signature_font('fonte_invalida')
        self.assertEqual(font_name, FALLBACK_FONT_NAME)
        self.assertTrue(used_fallback)
        self.assertIn('fonte desconhecida', detail)
