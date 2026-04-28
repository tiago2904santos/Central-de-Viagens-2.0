from io import BytesIO

from django.test import TestCase
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento
from documentos.services.assinaturas import (
    assinar_documento_pdf,
    diagnosticar_estrutura_assinatura_pdf,
    mascarar_cpf,
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

    def test_assinar_documento_gera_pdf_hash_carimbo_sem_segunda_pagina(self):
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
        self.assertIn('ASSINADO ELETRONICAMENTE', texto)
        self.assertIn(assinatura.codigo_verificacao, texto)
        self.assertIn('***.456.789-**', texto)
        diag = diagnosticar_estrutura_assinatura_pdf(pdf_assinado)
        self.assertTrue(diag['has_byterange'])
        self.assertTrue(diag['has_sig'])
        self.assertTrue(diag['has_contents'])
        self.assertTrue(diag['has_acroform'])
        self.assertGreaterEqual(diag['embedded_signatures_count'], 1)

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
