from io import BytesIO

from django.test import TestCase
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento
from documentos.services.assinaturas import (
    DadosCarimbo,
    assinar_documento_pdf,
    calcular_layout_aparencia_assinatura,
    fit_text_single_or_two_lines,
    diagnosticar_estrutura_assinatura_pdf,
    mascarar_cpf,
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

    def test_aparencia_visual_contem_logo_qr_nome_cpf_data_codigo(self):
        dados = DadosCarimbo(
            nome_assinante='JOAO MARIO DE GOES',
            cpf_mascarado='***.858.369-**',
            data_hora_assinatura=timezone.now(),
            codigo_verificacao='CV-2026-2892A7-326F',
            url_validacao='https://centraldeviagens.local/assinaturas/CV-2026-2892A7-326F',
        )
        appearance = renderizar_aparencia_assinatura(dados, 410, 92)
        reader = PdfReader(BytesIO(appearance))
        text = reader.pages[0].extract_text()
        self.assertIn('DOCUMENTO ASSINADO ELETRONICAMENTE', text)
        self.assertIn('JOAO MARIO DE GOES', text)
        self.assertIn('***.858.369-**', text)
        self.assertIn('CV-2026-2892A7-326F', text)
        self.assertIn('VALIDACAO', text)
        self.assertGreater(len(reader.pages[0].get_contents().get_data()), 3000)

    def test_layout_qr_nao_invade_texto_e_fica_dentro_da_area(self):
        layout = calcular_layout_aparencia_assinatura(410, 92)
        text_left, _text_bottom, text_width, _text_height = layout.text_box
        qr_left, _qr_bottom, qr_width, _qr_height = layout.qr_box
        logo_left, _logo_bottom, logo_width, _logo_height = layout.logo_box
        self.assertGreater(text_left, logo_left + logo_width)
        self.assertLess(text_left + text_width, qr_left)
        self.assertLessEqual(qr_left + qr_width, layout.width - layout.padding + 0.1)
        self.assertGreaterEqual(qr_left, 0)

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
