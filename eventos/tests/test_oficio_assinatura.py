from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from io import BytesIO
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from cadastros.models import AssinaturaConfiguracao, Cargo, Cidade, ConfiguracaoSistema, Estado, UnidadeLotacao, Viajante
from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento
from documentos.services.assinaturas import diagnosticar_estrutura_assinatura_pdf, validar_pdf_por_upload
from eventos.models import Oficio, OficioAssinaturaPedido
from eventos.services.oficio_assinatura import (
    TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO,
    codigo_validacao_assinatura,
    formatar_cpf_exibicao_auditoria,
    formatar_nome_assinatura,
    hash_conteudo_pdf_bytes,
    status_assinatura_oficio,
)
from eventos.services.pdf_signature import FALLBACK_FONT_NAME, apply_text_signature_on_pdf, resolve_signature_font


class OficioAssinaturaFlowTest(TestCase):
    @staticmethod
    def _build_pdf_with_text(texto: str, *, titulo: str = '') -> bytes:
        stream = BytesIO()
        c = canvas.Canvas(stream)
        if titulo:
            c.setTitle(titulo)
        c.drawString(72, 740, texto)
        c.showPage()
        c.save()
        return stream.getvalue()

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
        self.estado_pr = Estado.objects.create(sigla='PR', nome='Paraná', codigo_ibge='41')
        self.cidade_ctba = Cidade.objects.create(
            nome='Curitiba',
            estado=self.estado_pr,
            codigo_ibge='4106902',
        )
        self.oficio = Oficio.objects.create(
            status=Oficio.STATUS_RASCUNHO,
            cidade_sede=self.cidade_ctba,
            estado_sede=self.estado_pr,
        )

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_gera_pedido_com_pdf_congelado_e_hash(self, _render_mock):
        url = reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_PENDENTE)
        self.assertTrue(bool(pedido.hash_pdf_original))
        self.assertTrue(bool(pedido.pdf_original_congelado))
        self.assertEqual(pedido.criado_por_usuario, self.user)
        self.assertEqual(pedido.criado_por_nome, self.user.username)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_gera_novo_link_invalida_pendente_anterior(self, _render_mock):
        url = reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk})
        self.client.get(url, follow=True)
        pedido_1 = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        response = self.client.get(f'{url}?novo=1', follow=True)
        self.assertEqual(response.status_code, 200)
        pedidos = list(OficioAssinaturaPedido.objects.filter(oficio=self.oficio).order_by('created_at'))
        self.assertEqual(len(pedidos), 2)
        pedidos[0].refresh_from_db()
        self.assertEqual(pedidos[0].status, OficioAssinaturaPedido.STATUS_INVALIDADO)
        self.assertEqual(pedidos[1].status, OficioAssinaturaPedido.STATUS_PENDENTE)
        self.assertNotEqual(pedido_1.token, pedidos[1].token)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_pagina_interna_gestao_assinatura_existe(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        response = self.client.get(reverse('eventos:oficio-assinatura-gestao', kwargs={'pk': self.oficio.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gestão da assinatura')

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_lista_oficios_aponta_para_gestao_assinatura(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        response = self.client.get(reverse('eventos:oficios-global'))
        gestao_url = reverse('eventos:oficio-assinatura-gestao', kwargs={'pk': self.oficio.pk})
        self.assertContains(response, gestao_url)
        self.assertContains(response, 'Gerir assinatura')
        self.assertNotContains(response, 'aria-label="Copiar link de assinatura"', html=False)
        self.assertNotContains(response, 'aria-label="Gerar link de assinatura"', html=False)

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
    @patch('eventos.views_assinatura.apply_text_signature_on_pdf', return_value=(b'PDF_PREVIEW_ASSINADO', {
        'resolved_font_name': 'SignAllura',
        'used_fallback': False,
        'font_detail': 'ok',
        'signature_position': {'box_x': 0.77, 'box_y': 0.33, 'box_w': 0.36, 'box_h': 0.09, 'page_index': 0},
    }))
    def test_preview_pdf_com_fonte_retorna_preview_assinado(self, sign_mock, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.cpf_confirmado_em = pedido.created_at
        pedido.telefone_confirmado_em = pedido.created_at
        pedido.save(update_fields=['cpf_confirmado_em', 'telefone_confirmado_em', 'updated_at'])
        session = self.client.session
        session['oficio_assinatura_confirmada'] = {pedido.token: True}
        session.save()

        preview_url = reverse('eventos:assinatura-oficio-pdf', kwargs={'token': pedido.token})
        response = self.client.get(
            preview_url,
            data={
                'preview_font': OficioAssinaturaPedido.FONTE_ALLURA,
                'sig_x': '0.77',
                'sig_y': '0.33',
                'sig_w': '0.36',
                'sig_h': '0.09',
                'sig_page': '0',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])
        self.assertEqual(response.content, b'PDF_PREVIEW_ASSINADO')
        self.assertEqual(response['X-Assinatura-Fonte'], 'SignAllura')
        self.assertEqual(response['X-Assinatura-Fallback'], 'false')
        self.assertTrue(sign_mock.called)
        self.assertTrue(sign_mock.call_args.kwargs['strict_font'])
        pos = sign_mock.call_args.kwargs['signature_position']
        self.assertEqual(pos['box_x'], 0.77)
        self.assertEqual(pos['box_y'], 0.33)
        self.assertEqual(pos['box_w'], 0.36)
        self.assertEqual(pos['box_h'], 0.09)
        self.assertEqual(pos['page_index'], 0)

    @patch('eventos.views_assinatura.apply_text_signature_on_pdf')
    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_get_tela_assinar_nao_chama_apply_text_signature(self, _render_mock, apply_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.cpf_confirmado_em = pedido.created_at
        pedido.telefone_confirmado_em = pedido.created_at
        pedido.save(update_fields=['cpf_confirmado_em', 'telefone_confirmado_em', 'updated_at'])
        session = self.client.session
        session['oficio_assinatura_confirmada'] = {pedido.token: True}
        session.save()
        self.client.get(reverse('eventos:assinatura-oficio-assinar', kwargs={'token': pedido.token}))
        apply_mock.assert_not_called()

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
        self.assertNotContains(response, 'Documento original (visualização inline)')
        self.assertContains(response, 'data-assinatura-original-pdf')
        self.assertContains(response, 'assinatura-doc-placeholder')
        self.assertContains(response, 'data-testid="assinatura-editor-original-only"')
        self.assertNotContains(response, 'preview_font=')

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_link_publico_assinado_abre_tela_documento_assinado(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.assinado_em = pedido.created_at
        pedido.save(update_fields=['status', 'assinado_em', 'updated_at'])
        identidade_url = reverse('eventos:assinatura-oficio-identidade', kwargs={'token': pedido.token})
        response = self.client.get(identidade_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token}),
            response.url,
        )

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_visualizacao_documento_assinado_inline(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.pdf_assinado_final.save('arquivo-assinado.pdf', ContentFile(b'PDF_ASSINADO'), save=False)
        pedido.save()
        resp = self.client.get(reverse('eventos:assinatura-oficio-pdf-final', kwargs={'token': pedido.token}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertIn('inline;', resp['Content-Disposition'])

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_pagina_verificacao_mostra_dados_estruturados(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.hash_pdf_assinado = 'abc123'
        pedido.assinado_em = pedido.created_at
        pedido.save(update_fields=['status', 'hash_pdf_assinado', 'assinado_em', 'updated_at'])
        resp = self.client.get(reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Código de validação')
        self.assertContains(resp, 'Inserido por')
        self.assertContains(resp, 'Hash do documento')
        self.assertContains(resp, 'Curitiba/PR')
        self.assertContains(resp, TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO)
        self.assertContains(resp, '***.456.789-**')
        self.assertNotContains(resp, '12345678901')
        self.assertContains(resp, 'Visualização inline dos arquivos')
        self.assertContains(resp, 'oficio-lazy-frame')
        self.assertContains(resp, 'data-src=')
        self.assertNotContains(resp, 'title="PDF original" src=')
        self.assertContains(resp, "panel.addEventListener('toggle'")

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_gestao_mostra_botao_copiar_link(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        resp = self.client.get(reverse('eventos:oficio-assinatura-gestao', kwargs={'pk': self.oficio.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Copiar link')
        self.assertContains(resp, 'Criar novo link de assinatura')
        self.assertContains(resp, 'data-testid="criar-novo-link-assinatura"', html=False)
        self.assertContains(resp, 'Abrir link')
        self.assertContains(resp, 'data-testid="abrir-link-assinatura"', html=False)
        self.assertNotContains(resp, 'Abrir fluxo público')
        self.assertContains(resp, '***.456.789-**')
        self.assertContains(resp, 'data-testid="copiar-link-assinatura"', html=False)
        self.assertContains(resp, 'data-testid="oficio-doc-panels-gestao"', html=False)
        self.assertContains(resp, 'oficio-lazy-frame')
        self.assertNotContains(resp, 'title="PDF original" src=')

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_documento_assinado_nao_exibe_abrir_verificacao(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.assinado_em = pedido.created_at
        pedido.save(update_fields=['status', 'assinado_em', 'updated_at'])
        legado = reverse('eventos:assinatura-oficio-documento-assinado', kwargs={'token': pedido.token})
        redir = self.client.get(legado)
        self.assertEqual(redir.status_code, 302)
        self.assertIn(reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token}), redir.url)
        resp = self.client.get(redir.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Visualização inline dos arquivos')
        self.assertContains(resp, 'PDF original')
        self.assertContains(resp, 'PDF assinado')
        self.assertContains(resp, 'data-testid="oficio-doc-panels-publico"', html=False)
        self.assertContains(resp, 'oficio-doc-panel__summary')
        self.assertNotContains(resp, 'Abrir verificação')
        self.assertContains(resp, 'Curitiba/PR')
        self.assertContains(resp, TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_url_documento_assinado_redireciona_para_verificacao(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        url_doc = reverse('eventos:assinatura-oficio-documento-assinado', kwargs={'token': pedido.token})
        resp = self.client.get(url_doc)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token}), resp.url)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio')
    def test_fluxo_publico_confirma_cpf_telefone_e_assina(self, render_mock):
        render_mock.return_value = self._build_pdf_with_text('PDF ORIGINAL')
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

        r3 = self.client.post(
            assinar_url,
            data={
                'fonte_escolhida': OficioAssinaturaPedido.FONTE_GREAT_VIBES,
                'sig_x': '0.81',
                'sig_y': '0.27',
                'sig_w': '0.32',
                'sig_h': '0.10',
                'sig_page': '0',
            },
        )
        self.assertEqual(r3.status_code, 302)
        self.assertIn(reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token}), r3.url)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_ASSINADO)
        self.assertEqual(pedido.fonte_escolhida, OficioAssinaturaPedido.FONTE_GREAT_VIBES)
        self.assertTrue(bool(pedido.hash_pdf_assinado))
        self.assertTrue(bool(pedido.pdf_assinado_final))
        self.assertTrue(AssinaturaDocumento.objects.filter(codigo_verificacao=pedido.auditoria['assinatura_documento_codigo']).exists())
        self.assertEqual(pedido.auditoria.get('fonte_pdf_resolvida'), 'Helvetica')
        self.assertFalse(bool(pedido.auditoria.get('fonte_pdf_fallback')))
        pos = pedido.auditoria.get('assinatura_posicao', {})
        self.assertEqual(pos['box_x'], 0.81)
        self.assertEqual(pos['box_y'], 0.27)
        self.assertEqual(pos['box_w'], 0.4)
        self.assertEqual(pos['box_h'], 0.1)
        self.assertEqual(pos['page_index'], 0)
        self.assertEqual(pos['box_pdf'][2] - pos['box_pdf'][0], 205)
        self.assertEqual(pos['box_pdf'][3] - pos['box_pdf'][1], 70)
        self.assertTrue(pedido.auditoria.get('codigo_validacao', '').startswith('CV-'))
        self.assertIn('/assinaturas/verificar/', pedido.auditoria.get('url_verificacao', ''))
        assinatura = AssinaturaDocumento.objects.get(pk=pedido.auditoria['assinatura_documento_id'])
        self.assertEqual(assinatura.hash_pdf_assinado_sha256, pedido.hash_pdf_assinado)
        pdf_assinado = pedido.pdf_assinado_final.read()
        self.assertEqual(len(PdfReader(BytesIO(pdf_assinado)).pages), 1)
        diagnostico_pdf = diagnosticar_estrutura_assinatura_pdf(pdf_assinado)
        self.assertTrue(diagnostico_pdf['has_byterange'])
        self.assertTrue(diagnostico_pdf['has_acroform'])
        self.assertTrue(diagnostico_pdf['has_appearance'])
        self.assertFalse(diagnostico_pdf['page_text_has_signature_visual'])

        resultado_valido = validar_pdf_por_upload(BytesIO(pdf_assinado))
        self.assertTrue(resultado_valido['valido'])
        alterado = bytearray(pdf_assinado)
        alterado.append(10)
        resultado_invalido = validar_pdf_por_upload(BytesIO(bytes(alterado)), codigo_manual=assinatura.codigo_verificacao)
        self.assertFalse(resultado_invalido['valido'])
        self.assertEqual(ValidacaoAssinaturaDocumento.objects.count(), 2)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio')
    def test_caixa_de_assinatura_usa_etiqueta_compacta_fixa(self, render_mock):
        render_mock.return_value = self._build_pdf_with_text('PDF ORIGINAL')
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        identidade_url = reverse('eventos:assinatura-oficio-identidade', kwargs={'token': pedido.token})
        assinar_url = reverse('eventos:assinatura-oficio-assinar', kwargs={'token': pedido.token})
        self.client.post(identidade_url, data={'etapa': 'cpf', 'cpf_prefixo': '12345'})
        self.client.post(identidade_url, data={'etapa': 'telefone', 'confirmar_telefone': '1'})
        self.client.post(
            assinar_url,
            data={
                'fonte_escolhida': OficioAssinaturaPedido.FONTE_GREAT_VIBES,
                'sig_x': '0.20',
                'sig_y': '0.50',
                'sig_w': '0.44',
                'sig_h': '0.14',
                'sig_page': '0',
            },
        )
        pedido.refresh_from_db()
        pos = pedido.auditoria.get('assinatura_posicao', {})
        self.assertEqual(pos['box_w'], 0.44)
        self.assertEqual(pos['box_h'], 0.14)
        self.assertEqual(pos['box_pdf'][2] - pos['box_pdf'][0], 205)
        self.assertEqual(pos['box_pdf'][3] - pos['box_pdf'][1], 70)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio', return_value=b'PDF_ORIGINAL')
    def test_gestao_assinado_nao_mostra_abrir_link(self, _render_mock):
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.assinado_em = pedido.created_at
        pedido.save(update_fields=['status', 'assinado_em', 'updated_at'])
        resp = self.client.get(reverse('eventos:oficio-assinatura-gestao', kwargs={'pk': self.oficio.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Criar novo link de assinatura')
        self.assertNotContains(resp, 'data-testid="abrir-link-assinatura"', html=False)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio')
    def test_alteracao_real_do_oficio_marca_assinatura_desatualizada(self, render_mock):
        render_mock.return_value = self._build_pdf_with_text('VERSAO A', titulo='A')
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.hash_pdf_original = hash_conteudo_pdf_bytes(render_mock.return_value)
        pedido.save(update_fields=['status', 'hash_pdf_original', 'updated_at'])

        render_mock.return_value = self._build_pdf_with_text('VERSAO B', titulo='B')
        lista_url = reverse('eventos:oficios-global')
        self.client.get(lista_url)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_ASSINADO)
        self.assertEqual(status_assinatura_oficio(self.oficio).key, 'DESATUALIZADA')

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio')
    def test_mesmo_conteudo_documental_nao_invalida_assinatura(self, render_mock):
        pdf_a = self._build_pdf_with_text('CONTEUDO OFICIO ESTAVEL', titulo='v1')
        pdf_b = self._build_pdf_with_text('CONTEUDO OFICIO ESTAVEL', titulo='v2')
        self.assertNotEqual(pdf_a, pdf_b)
        self.assertEqual(hash_conteudo_pdf_bytes(pdf_a), hash_conteudo_pdf_bytes(pdf_b))

        render_mock.return_value = pdf_a
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.hash_pdf_original = hash_conteudo_pdf_bytes(pdf_a)
        pedido.save(update_fields=['status', 'hash_pdf_original', 'updated_at'])

        render_mock.return_value = pdf_b
        status = status_assinatura_oficio(self.oficio)
        pedido.refresh_from_db()
        self.assertEqual(status.key, 'ASSINADO')
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_ASSINADO)

    @patch('eventos.services.oficio_assinatura.gerar_pdf_canonico_oficio')
    def test_validacao_nao_compara_pdf_assinado_final(self, render_mock):
        pdf_canonico = self._build_pdf_with_text('BASE IMUTAVEL', titulo='base')
        render_mock.return_value = pdf_canonico
        self.client.get(reverse('eventos:oficio-assinatura-gerar-link', kwargs={'pk': self.oficio.pk}), follow=True)
        pedido = OficioAssinaturaPedido.objects.get(oficio=self.oficio)
        pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
        pedido.hash_pdf_original = hash_conteudo_pdf_bytes(pdf_canonico)
        pedido.pdf_assinado_final.save('assinado-diferente.pdf', ContentFile(b'PDF_ASSINADO_DIFERENTE'), save=False)
        pedido.save()

        status = status_assinatura_oficio(self.oficio)
        pedido.refresh_from_db()
        self.assertEqual(status.key, 'ASSINADO')
        self.assertEqual(pedido.status, OficioAssinaturaPedido.STATUS_ASSINADO)


class NomeAssinaturaHelperTest(TestCase):
    def test_formatar_cpf_exibicao_auditoria_mascara_centro(self):
        self.assertEqual(formatar_cpf_exibicao_auditoria('123.456.789-01'), '***.456.789-**')
        self.assertEqual(formatar_cpf_exibicao_auditoria(''), '—')

    def test_helper_aplica_capitalizacao_e_particulas(self):
        self.assertEqual(formatar_nome_assinatura('MARIA APARECIDA DOS SANTOS'), 'Maria Aparecida dos Santos')
        self.assertEqual(formatar_nome_assinatura('JOSE CARLOS DA SILVA E SOUZA'), 'Jose Carlos da Silva e Souza')
        self.assertEqual(formatar_nome_assinatura('JOAO MARIO DE GOES'), 'Joao Mario de Goes')

    def test_codigo_validacao_formata_em_grupos(self):
        codigo = codigo_validacao_assinatura('abcde12345fghij67890klmnop')
        self.assertEqual(codigo, 'ABCD-E123-45FG-HIJ6-7890')


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

    @patch('eventos.services.pdf_signature.resolve_signature_font', return_value=('Helvetica', False, 'ok'))
    def test_pdf_final_recebe_carimbo_sem_pagina_extra(self, _font_mock):
        stream = BytesIO()
        c = canvas.Canvas(stream)
        c.drawString(72, 740, 'Oficio base')
        c.showPage()
        c.save()
        original = stream.getvalue()
        validation_payload = {
            'nome_documento': 'Ofício',
            'identificador_oficio': '01/2026',
            'protocolo': '12.345.678-9',
            'nome_assinante': 'Joao Mario de Goes',
            'cpf_mascarado': '***.456.789-**',
            'assinado_em': '22/04/2026 15:00:00',
            'local_assinatura': 'Curitiba/PR',
            'confirmacao_identidade': 'Confirmação por CPF e telefone',
            'criado_por_nome': 'assinatura-admin',
            'pedido_criado_em': '22/04/2026 14:59:00',
            'hash_documento': 'abc123',
            'codigo_validacao': 'CV-2026-ABC123-A7F9',
            'url_verificacao': 'https://exemplo.local/assinaturas/verificar/CV-2026-ABC123-A7F9/',
            'texto_assinatura': 'Documento assinado eletronicamente.',
        }
        final_pdf, meta = apply_text_signature_on_pdf(
            original,
            signer_name='Joao Mario de Goes',
            font_key='great_vibes',
            validation_payload=validation_payload,
            strict_font=True,
        )
        pages = PdfReader(BytesIO(final_pdf)).pages
        self.assertEqual(len(pages), 1)
        self.assertFalse(meta.get('has_validation_page'))
        texto_primeira = pages[0].extract_text()
        self.assertIn('Documento assinado eletronicamente', texto_primeira)
        self.assertIn('verifique em /assinaturas/verificar', texto_primeira)
        self.assertIn('/CV-2026-ABC123-A7F9/', texto_primeira)
        self.assertNotIn('https://verificador.iti.br', texto_primeira)

    @patch('eventos.services.pdf_signature.resolve_signature_font', return_value=('Helvetica', False, 'ok'))
    def test_page_index_menos_um_usa_ultima_pagina(self, _font_mock):
        stream = BytesIO()
        c = canvas.Canvas(stream)
        c.drawString(72, 740, 'Pagina 1')
        c.showPage()
        c.drawString(72, 740, 'Pagina 2')
        c.showPage()
        c.save()
        original = stream.getvalue()

        final_pdf, meta = apply_text_signature_on_pdf(
            original,
            signer_name='Joao Mario de Goes',
            font_key='great_vibes',
            signature_position={'box_x': 0.1, 'box_y': 0.72, 'box_w': 0.55, 'box_h': 0.12, 'page_index': -1},
            strict_font=True,
        )
        pages = PdfReader(BytesIO(final_pdf)).pages
        texto_1 = pages[0].extract_text() or ''
        texto_2 = pages[1].extract_text() or ''
        self.assertNotIn('Joao Mario de Goes', texto_1)
        self.assertIn('Joao Mario de Goes', texto_2)
        self.assertEqual(meta.get('signature_position', {}).get('page_index'), 1)

    @patch('eventos.services.pdf_signature.resolve_signature_font', return_value=('Helvetica', False, 'ok'))
    def test_caixas_distintas_alteram_conteudo_do_pdf(self, _font_mock):
        stream = BytesIO()
        c = canvas.Canvas(stream)
        c.drawString(72, 740, 'Conteudo')
        c.showPage()
        c.save()
        original = stream.getvalue()
        pos_a = {'box_x': 0.1, 'box_y': 0.8, 'box_w': 0.4, 'box_h': 0.1, 'page_index': 0}
        pos_b = {'box_x': 0.5, 'box_y': 0.5, 'box_w': 0.35, 'box_h': 0.12, 'page_index': 0}
        pdf_a, _ = apply_text_signature_on_pdf(
            original,
            signer_name='Joao Mario de Goes',
            font_key='great_vibes',
            signature_position=pos_a,
            strict_font=True,
        )
        pdf_b, _ = apply_text_signature_on_pdf(
            original,
            signer_name='Joao Mario de Goes',
            font_key='great_vibes',
            signature_position=pos_b,
            strict_font=True,
        )
        self.assertNotEqual(pdf_a, pdf_b)
