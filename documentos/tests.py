from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento
from documentos.services.assinaturas import (
    DadosCarimbo,
    SIGNATURE_LABEL_HEIGHT_PT,
    SIGNATURE_LABEL_QR_PT,
    SIGNATURE_LABEL_WATERMARK_ALPHA,
    SIGNATURE_LABEL_WIDTH_PT,
    assinar_documento_pdf,
    calcular_layout_aparencia_assinatura,
    fit_text_single_or_two_lines,
    diagnosticar_estrutura_assinatura_pdf,
    gerar_url_validacao,
    mascarar_cpf,
    montar_dados_assinatura,
    renderizar_aparencia_assinatura,
    validar_codigo,
    validar_pdf_por_upload,
)
from eventos.models import Oficio


class AssinaturaDocumentoServiceTest(TestCase):
    @staticmethod
    def _pdf(texto='Documento original'):
        stream = BytesIO()
        c = canvas.Canvas(stream)
        c.drawString(72, 740, texto)
        c.showPage()
        c.save()
        return stream.getvalue()

    def test_assinar_documento_gera_pdf_hash_assinatura_real_sem_segunda_pagina(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)
        original = self._pdf()

        assinatura = assinar_documento_pdf(
            oficio,
            pdf_original=original,
            nome_documento='Ofício',
            nome_assinante='Fabiano Rodrigo Teixeira Pinto',
            cpf_assinante='12345678900',
            posicao={'page_index': 0, 'box_x': 0.45, 'box_y': 0.78, 'box_w': 0.5, 'box_h': 0.14},
        )

        self.assertEqual(AssinaturaDocumento.objects.count(), 1)
        self.assertTrue(assinatura.arquivo_pdf_assinado)
        self.assertTrue(assinatura.hash_pdf_original_sha256)
        self.assertTrue(assinatura.hash_pdf_assinado_sha256)
        self.assertNotEqual(assinatura.hash_pdf_original_sha256, assinatura.hash_pdf_assinado_sha256)
        pdf_assinado = assinatura.arquivo_pdf_assinado.read()
        reader = PdfReader(BytesIO(pdf_assinado))
        self.assertEqual(len(reader.pages), 1)
        texto = reader.pages[0].extract_text()
        self.assertNotIn('ASSINADO ELETRONICAMENTE', texto)
        self.assertEqual(reader.metadata.get('/assinatura_codigo'), assinatura.codigo_verificacao)
        diag = diagnosticar_estrutura_assinatura_pdf(pdf_assinado)
        self.assertTrue(diag['has_byterange'])
        self.assertTrue(diag['has_sig'])
        self.assertTrue(diag['has_contents'])
        self.assertTrue(diag['has_acroform'])
        self.assertTrue(diag['has_appearance'])
        self.assertGreaterEqual(diag['embedded_signatures_count'], 1)
        self.assertFalse(diag['page_text_has_signature_visual'])
        self.assertTrue(assinatura.metadata_json['assinatura_visual']['aparencia_vinculada_ao_campo_pdf'])
        self.assertTrue(assinatura.metadata_json['assinatura_visual']['qr_code'])
        self.assertEqual(assinatura.metadata_json['assinatura_visual']['largura_pt'], 160)
        self.assertEqual(assinatura.metadata_json['assinatura_visual']['altura_pt'], 56)
        self.assertEqual(assinatura.metadata_json['assinatura_visual']['qr_tamanho_pt'], 44)
        self.assertEqual(assinatura.metadata_json['assinatura_visual']['marca_dagua'], 'static/img/assinatura/cv-watermark.png')
        self.assertEqual(assinatura.metadata_json['assinatura_visual']['marca_dagua_opacidade'], 0.18)
        box_pdf = assinatura.posicao_carimbo_json['box_pdf']
        self.assertEqual(box_pdf[2] - box_pdf[0], SIGNATURE_LABEL_WIDTH_PT)
        self.assertEqual(box_pdf[3] - box_pdf[1], SIGNATURE_LABEL_HEIGHT_PT)

    def test_aparencia_visual_contem_logo_qr_nome_cpf_data_codigo(self):
        dados = DadosCarimbo(
            nome_assinante='JOAO MARIO DE GOES',
            cpf_mascarado='***.858.369-**',
            data_hora_assinatura=timezone.now(),
            codigo_verificacao='CV-2026-2892A7-326F',
            url_validacao='https://centraldeviagens.local/assinaturas/verificar/CV-2026-2892A7-326F/',
        )
        appearance = renderizar_aparencia_assinatura(dados, 410, 92)
        reader = PdfReader(BytesIO(appearance))
        page = reader.pages[0]
        self.assertEqual(float(page.mediabox.width), SIGNATURE_LABEL_WIDTH_PT)
        self.assertEqual(float(page.mediabox.height), SIGNATURE_LABEL_HEIGHT_PT)
        text = reader.pages[0].extract_text()
        self.assertIn('Documento assinado eletronicamente', text)
        self.assertIn('JOAO MARIO DE GOES', text)
        self.assertIn('***.858.369-**', text)
        self.assertIn('Data:', text)
        self.assertIn('verifique em /assinaturas/verificar', text)
        self.assertIn('/CV-2026-2892', text)
        self.assertNotIn('verificador.iti.br', text)
        self.assertGreater(len(reader.pages[0].get_contents().get_data()), 3000)

    def test_layout_qr_nao_invade_texto_e_fica_dentro_da_area(self):
        layout = calcular_layout_aparencia_assinatura(410, 92)
        text_left, _text_bottom, text_width, _text_height = layout.text_box
        qr_left, _qr_bottom, qr_width, qr_height = layout.qr_box
        self.assertEqual(layout.width, SIGNATURE_LABEL_WIDTH_PT)
        self.assertEqual(layout.height, SIGNATURE_LABEL_HEIGHT_PT)
        self.assertEqual(qr_width, SIGNATURE_LABEL_QR_PT)
        self.assertEqual(qr_height, SIGNATURE_LABEL_QR_PT)
        self.assertEqual(qr_left, 6)
        self.assertGreater(text_left, qr_left + qr_width)
        self.assertLessEqual(text_left + text_width, layout.width - 6 + 0.1)
        self.assertGreaterEqual(qr_left, 0)

    def test_asset_cv_watermark_existe_e_opacidade_configurada(self):
        path = Path(settings.BASE_DIR) / 'static' / 'img' / 'assinatura' / 'cv-watermark.png'
        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 0)
        self.assertEqual(SIGNATURE_LABEL_WATERMARK_ALPHA, 0.18)

    def test_url_validacao_com_request_eh_absoluta_para_qr(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)
        assinatura = AssinaturaDocumento.objects.create(
            content_type=ContentType.objects.get_for_model(oficio, for_concrete_model=False),
            object_id=oficio.pk,
            nome_assinante='Assinante Teste',
            cpf_assinante='12345678900',
            data_hora_assinatura=timezone.now(),
            codigo_verificacao='CV-2026-ABC123-A7F9',
            hash_pdf_original_sha256='abc',
        )
        request = RequestFactory().get('/')

        url = gerar_url_validacao(assinatura, request=request)
        dados = montar_dados_assinatura(assinatura, request=request)

        self.assertEqual(url, 'http://testserver/assinaturas/verificar/CV-2026-ABC123-A7F9/')
        self.assertEqual(dados.url_validacao, url)
        self.assertTrue(dados.url_validacao.startswith('http://testserver/assinaturas/verificar/'))
        self.assertNotIn('verificador.iti.br', dados.url_validacao)

    def test_validacao_por_upload_mesmo_pdf_valido_e_pdf_editado_invalido(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)
        assinatura = assinar_documento_pdf(
            oficio,
            pdf_original=self._pdf(),
            nome_documento='Ofício',
            nome_assinante='Assinante Teste',
            cpf_assinante='12345678900',
        )
        pdf_assinado = assinatura.arquivo_pdf_assinado.read()

        valido = validar_pdf_por_upload(BytesIO(pdf_assinado))
        self.assertTrue(valido['valido'])

        alterado = bytearray(pdf_assinado)
        alterado.append(10)
        invalido = validar_pdf_por_upload(BytesIO(bytes(alterado)), codigo_manual=assinatura.codigo_verificacao)
        self.assertFalse(invalido['valido'])
        self.assertIn(
            invalido['status_assinatura_pdf'],
            ('assinatura_pdf_invalida', 'assinatura_pdf_ausente', 'certificado_nao_confiavel'),
        )
        self.assertEqual(ValidacaoAssinaturaDocumento.objects.count(), 2)

    def test_rota_verificacao_responde_para_codigo_valido_e_invalido(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)
        assinatura = assinar_documento_pdf(
            oficio,
            pdf_original=self._pdf(),
            nome_documento='Oficio',
            nome_assinante='Assinante Teste',
            cpf_assinante='12345678900',
        )

        url = reverse('documentos:assinatura-verificar-codigo', kwargs={'codigo': assinatura.codigo_verificacao})
        valido = self.client.get(url)
        self.assertEqual(valido.status_code, 200)
        self.assertContains(valido, 'Assinante Teste')
        self.assertContains(valido, '***.456.789-**')
        self.assertContains(valido, assinatura.hash_pdf_assinado_sha256)

        invalido = self.client.get(reverse('documentos:assinatura-verificar-codigo', kwargs={'codigo': 'CV-2026-XXXXXX-YYYY'}))
        self.assertEqual(invalido.status_code, 404)
        self.assertIn('encontrado', invalido.content.decode('utf-8').lower())

    def test_pdf_reexportado_com_mesmo_visual_falha_por_hash(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)
        assinatura = assinar_documento_pdf(
            oficio,
            pdf_original=self._pdf('Conteúdo base'),
            nome_documento='Ofício',
            nome_assinante='Assinante Teste',
            cpf_assinante='12345678900',
        )
        pdf_assinado = assinatura.arquivo_pdf_assinado.read()
        reader = PdfReader(BytesIO(pdf_assinado))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        reexportado = BytesIO()
        writer.write(reexportado)

        resultado = validar_pdf_por_upload(BytesIO(reexportado.getvalue()), codigo_manual=assinatura.codigo_verificacao)
        self.assertFalse(resultado['valido'])

    def test_codigo_inexistente_e_arquivo_sem_codigo_tem_resultado_claro(self):
        self.assertIsNone(validar_codigo('CV-2026-XXXXXX-YYYY'))
        resultado = validar_pdf_por_upload(BytesIO(self._pdf('Sem carimbo')))
        self.assertFalse(resultado['valido'])
        self.assertEqual(resultado['resultado'], ValidacaoAssinaturaDocumento.RESULTADO_ARQUIVO_SEM_CODIGO)
        self.assertEqual(ValidacaoAssinaturaDocumento.objects.get().resultado, ValidacaoAssinaturaDocumento.RESULTADO_ARQUIVO_SEM_CODIGO)

    def test_documento_editado_nao_sobrescreve_assinado_anterior_e_permite_nova_versao(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO, motivo='versao 1')
        primeira = assinar_documento_pdf(
            oficio,
            pdf_original=self._pdf('Versão 1'),
            nome_documento='Ofício',
            nome_assinante='Assinante Teste',
            cpf_assinante='12345678900',
        )
        arquivo_primeiro = primeira.arquivo_pdf_assinado.name
        oficio.motivo = 'versao 2'
        oficio.save(update_fields=['motivo'])
        primeira.status = AssinaturaDocumento.STATUS_SUBSTITUIDA
        primeira.motivo_revogacao = 'Documento fonte alterado após a assinatura.'
        primeira.save(update_fields=['status', 'motivo_revogacao', 'updated_at'])

        segunda = assinar_documento_pdf(
            oficio,
            pdf_original=self._pdf('Versão 2'),
            nome_documento='Ofício',
            nome_assinante='Assinante Teste',
            cpf_assinante='12345678900',
        )

        primeira.refresh_from_db()
        self.assertEqual(primeira.status, AssinaturaDocumento.STATUS_SUBSTITUIDA)
        self.assertNotEqual(arquivo_primeiro, segunda.arquivo_pdf_assinado.name)
        self.assertEqual(AssinaturaDocumento.objects.count(), 2)

    def test_mascara_cpf_padrao(self):
        self.assertEqual(mascarar_cpf('123.456.789-00'), '***.456.789-**')

    def test_nome_longo_ajusta_sem_particula_sozinha(self):
        nome = 'JOAO MARIO DE GOES SILVA PEREIRA'
        _, linha_1, linha_2 = fit_text_single_or_two_lines(nome, max_width=150, font_name='Helvetica-Bold')
        if linha_2:
            self.assertNotIn(linha_1.split(' ')[-1].lower(), {'de', 'da', 'do', 'dos', 'das', 'e'})
            self.assertNotIn(linha_2.split(' ')[0].lower(), {'de', 'da', 'do', 'dos', 'das', 'e'})
