import base64
import hashlib
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas as rl_canvas

from assinaturas.models import AssinaturaDocumento, AssinaturaEtapa
from assinaturas.services.assinatura_estado import EstadoLinkAssinatura, estado_etapa_assinatura, estado_pedido_assinatura
from assinaturas.services.assinatura_flow import (
    criar_pedido_assinatura,
    processar_assinatura,
    processar_assinatura_etapa,
    validar_e_normalizar_nome,
)
from assinaturas.services.documento_bloqueio import assinatura_concluida_para, garantir_documento_editavel
from assinaturas.services.pdf_assinatura import aplicar_assinatura_data_url
from cadastros.models import AssinaturaConfiguracao, ConfiguracaoSistema, Viajante
from eventos.models import Evento, Justificativa, Oficio, OrdemServico, PlanoTrabalho, TermoAutorizacao


def _minimal_pdf_bytes() -> bytes:
    buf = BytesIO()
    c = rl_canvas.Canvas(buf)
    c.drawString(72, 720, "Teste assinatura")
    c.save()
    return buf.getvalue()


def _signature_data_url() -> str:
    img = Image.new("RGBA", (220, 90), color=(255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.line((15, 70, 80, 25), fill=(20, 20, 120, 255), width=5)
    draw.line((80, 25, 140, 60), fill=(20, 20, 120, 255), width=5)
    draw.line((140, 60, 205, 30), fill=(20, 20, 120, 255), width=5)
    b = BytesIO()
    img.save(b, format="PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode("ascii")


def _signature_data_url_vazia() -> str:
    img = Image.new("RGBA", (180, 70), color=(255, 255, 255, 0))
    b = BytesIO()
    img.save(b, format="PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode("ascii")


def _setup_config_assinatura(viajante: Viajante) -> None:
    cfg = ConfiguracaoSistema.get_singleton()
    for tipo in (
        AssinaturaConfiguracao.TIPO_OFICIO,
        AssinaturaConfiguracao.TIPO_JUSTIFICATIVA,
        AssinaturaConfiguracao.TIPO_PLANO_TRABALHO,
        AssinaturaConfiguracao.TIPO_ORDEM_SERVICO,
    ):
        AssinaturaConfiguracao.objects.update_or_create(
            configuracao=cfg,
            tipo=tipo,
            ordem=1,
            defaults={"viajante": viajante, "ativo": True},
        )


@patch("assinaturas.services.assinatura_flow.gerar_pdf_bytes_para_assinatura", return_value=_minimal_pdf_bytes())
class AssinaturaFlowTests(TestCase):
    def setUp(self):
        self.evento = Evento.objects.create(
            titulo="Evento teste assinatura",
            data_inicio=date(2026, 3, 1),
            data_fim=date(2026, 3, 2),
            status=Evento.STATUS_RASCUNHO,
        )
        self.cpf_padrao = "52998224725"
        self.cpf_termo = "39053344705"
        self.cpf_chefia = "86288366757"
        self.viaj = Viajante.objects.create(nome="Servidor Padrao Assinatura", cpf=self.cpf_padrao)
        self.viaj_termo = Viajante.objects.create(nome="Servidor Do Termo Silva", cpf=self.cpf_termo)
        _setup_config_assinatura(self.viaj)
        self.oficio = Oficio.objects.create(tipo_origem=Oficio.ORIGEM_EVENTO)
        self.oficio.eventos.add(self.evento)
        self.justificativa = Justificativa.objects.create(oficio=self.oficio, texto="Texto justificativa teste.")
        self.plano = PlanoTrabalho.objects.create(evento=self.evento)
        self.os = OrdemServico.objects.create(evento=self.evento)
        cfg = ConfiguracaoSistema.get_singleton()
        cfg.nome_chefia = "Chefia Externa Teste"
        cfg.email = "chefia@example.org"
        cfg.cpf_chefia_assinatura = ""
        cfg.save(update_fields=["nome_chefia", "email", "cpf_chefia_assinatura"])
        self.termo = TermoAutorizacao.objects.create(
            evento=self.evento,
            viajante=self.viaj_termo,
            status=TermoAutorizacao.STATUS_GERADO,
        )

    def test_convite_upload_nao_entra_em_assinatura(self, _mock_pdf):
        from eventos.models import EventoAnexoSolicitante

        anexo = EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original="doc.pdf",
        )
        anexo.arquivo.save("doc.pdf", ContentFile(_minimal_pdf_bytes()), save=True)
        with self.assertRaises(ValueError):
            criar_pedido_assinatura(
                documento_tipo="eventos.EventoAnexoSolicitante",
                documento_id=anexo.pk,
            )

    def test_pdf_congelado_hash_original(self, _mock_pdf):
        assin, _, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        self.assertTrue(assin.arquivo_original.name)
        self.assertEqual(len(assin.arquivo_original_sha256), 64)
        with assin.arquivo_original.open("rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(), assin.arquivo_original_sha256)

    def test_oficio_cria_pedido_com_verificacao_token(self, _mock_pdf):
        assin, et1, rel = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        self.assertTrue(assin.verificacao_token)
        self.assertEqual(et1.cpf_esperado_normalizado, self.cpf_padrao)
        self.assertIn("/assinar/", rel)

    def test_cpf_incorreto_bloqueia(self, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        with self.assertRaises(ValueError):
            processar_assinatura_etapa(
                etapa=et1,
                nome_assinante="Maria Silva Santos",
                cpf_digitado="11111111111",
                signature_data_url=_signature_data_url(),
                ip="127.0.0.1",
                user_agent="ua",
            )
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.PENDENTE)

    def test_cpf_correto_auditoria_e_hash_assinado(self, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua-test",
        )
        et1.refresh_from_db()
        assin.refresh_from_db()
        self.assertTrue(et1.cpf_confere)
        self.assertTrue(et1.cpf_informado)
        self.assertEqual(et1.cpf_normalizado, self.cpf_padrao)
        self.assertEqual(assin.status, AssinaturaDocumento.Status.CONCLUIDO)
        self.assertEqual(len(assin.arquivo_assinado_sha256), 64)

    @patch("assinaturas.services.documento_bloqueio.gerar_pdf_bytes_para_assinatura")
    def test_documento_editavel_invalida_assinatura_apos_alteracao(self, mock_doc_pdf, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        self.assertTrue(assinatura_concluida_para("eventos.oficio", self.oficio.pk))
        mock_doc_pdf.side_effect = [_minimal_pdf_bytes(), _minimal_pdf_bytes() + b"\n%mudanca-real"]
        garantir_documento_editavel("eventos.oficio", self.oficio.pk)
        self.oficio.motivo = "Motivo alterado apos assinatura"
        self.oficio.save(update_fields=["motivo"])
        garantir_documento_editavel("eventos.oficio", self.oficio.pk)
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.INVALIDADO_ALTERACAO)
        self.assertTrue(assin.invalidado_em)

    @patch("assinaturas.services.documento_bloqueio.gerar_pdf_bytes_para_assinatura", return_value=_minimal_pdf_bytes())
    def test_abrir_cadastro_nao_invalida_assinatura(self, _mock_doc_pdf, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        with assin.arquivo_original.open("rb") as fh:
            _mock_doc_pdf.return_value = fh.read()
        garantir_documento_editavel("eventos.oficio", self.oficio.pk)
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.CONCLUIDO)

    @patch("assinaturas.services.documento_bloqueio.gerar_pdf_bytes_para_assinatura", return_value=_minimal_pdf_bytes())
    def test_salvar_sem_mudar_pdf_nao_invalida(self, _mock_doc_pdf, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        with assin.arquivo_original.open("rb") as fh:
            _mock_doc_pdf.return_value = fh.read()
        garantir_documento_editavel("eventos.oficio", self.oficio.pk)
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.CONCLUIDO)

    @patch("assinaturas.services.documento_bloqueio.gerar_pdf_bytes_para_assinatura")
    def test_alterar_conteudo_que_muda_pdf_invalida(self, mock_doc_pdf, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        mock_doc_pdf.return_value = _minimal_pdf_bytes() + b"\n%alterado"
        garantir_documento_editavel("eventos.oficio", self.oficio.pk)
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.INVALIDADO_ALTERACAO)

    def test_verificacao_get(self, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        c = Client()
        url = reverse("assinaturas:verificar", kwargs={"token": str(assin.verificacao_token)})
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Concluído")
        pdf_url = reverse("assinaturas:verificar_pdf", kwargs={"token": str(assin.verificacao_token)})
        r2 = c.get(pdf_url)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2["Content-Type"], "application/pdf")

    def test_termo_segunda_etapa_so_apos_primeira(self, _mock_pdf):
        assin, _, _ = criar_pedido_assinatura(
            documento_tipo="eventos.termoautorizacao",
            documento_id=self.termo.pk,
            cpf_esperado_chefia=self.cpf_chefia,
        )
        e2 = assin.etapas.order_by("ordem").last()
        self.assertEqual(estado_etapa_assinatura(e2), EstadoLinkAssinatura.INVALIDO)
        e1 = assin.etapas.order_by("ordem").first()
        processar_assinatura_etapa(
            etapa=e1,
            nome_assinante="Servidor Do Termo Silva",
            cpf_digitado=self.cpf_termo,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        self.assertEqual(estado_etapa_assinatura(e2), EstadoLinkAssinatura.VALIDO)

    @patch("assinaturas.services.assinatura_flow._sync_drive_replace", side_effect=RuntimeError("drive down"))
    def test_falha_drive_nao_desfaz_assinatura_local(self, _mock_drive, _mock_pdf):
        User = get_user_model()
        u = User.objects.create_user(username="driveuser", password="x")
        assin, _, _ = criar_pedido_assinatura(
            documento_tipo="eventos.oficio",
            documento_id=self.oficio.pk,
            usuario_drive=u,
            drive_parent_folder_id="folder123",
            drive_target_filename="doc.pdf",
        )
        processar_assinatura(
            assin=assin,
            nome_assinante="Carlos Teste Silva",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.CONCLUIDO)
        self.assertTrue(assin.arquivo_assinado_sha256)
        self.assertIn("drive", (assin.drive_sync_error or "").lower())

    def test_estado_pedido_valido_e_expirado(self, _mock_pdf):
        assin, _, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        self.assertEqual(estado_pedido_assinatura(assin), EstadoLinkAssinatura.VALIDO)
        AssinaturaDocumento.objects.filter(pk=assin.pk).update(expires_at=timezone.now() - timedelta(hours=1))
        assin.refresh_from_db()
        self.assertEqual(estado_pedido_assinatura(assin), EstadoLinkAssinatura.EXPIRADO)

    def test_nome_invalido(self, _mock_pdf):
        with self.assertRaises(ValueError):
            validar_e_normalizar_nome("ab")

    def test_aplicar_assinatura_gera_pdf(self, _mock_pdf):
        pdf = _minimal_pdf_bytes()
        out = aplicar_assinatura_data_url(pdf, _signature_data_url(), documento_tipo="eventos.oficio")
        self.assertTrue(out.startswith(b"%PDF"))
        reader = PdfReader(BytesIO(out))
        page = reader.pages[-1]
        xobj = page.get("/Resources", {}).get("/XObject")
        self.assertTrue(xobj)
        image_names = [k for k, v in xobj.items() if v.get_object().get("/Subtype") == "/Image"]
        self.assertTrue(image_names)

    def test_assinatura_vazia_e_rejeitada(self, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        with self.assertRaises(ValueError):
            processar_assinatura_etapa(
                etapa=et1,
                nome_assinante="Maria Silva Santos",
                cpf_digitado=self.cpf_padrao,
                signature_data_url=_signature_data_url_vazia(),
                ip="127.0.0.1",
                user_agent="ua",
            )
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.PENDENTE)

    def test_status_assinado_somente_com_pdf_assinado_valido(self, _mock_pdf):
        assin, et1, _ = criar_pedido_assinatura(documento_tipo="eventos.oficio", documento_id=self.oficio.pk)
        processar_assinatura_etapa(
            etapa=et1,
            nome_assinante="Maria Silva Santos",
            cpf_digitado=self.cpf_padrao,
            signature_data_url=_signature_data_url(),
            ip="127.0.0.1",
            user_agent="ua",
        )
        assin.refresh_from_db()
        self.assertEqual(assin.status, AssinaturaDocumento.Status.CONCLUIDO)
        self.assertTrue(assin.arquivo_assinado.name)
        self.assertTrue(assin.arquivo_assinado_sha256)

    def test_lista_oficios_exibe_status_e_acao_de_link(self, _mock_pdf):
        User = get_user_model()
        user = User.objects.create_user(username="gestor", password="x")
        c = Client()
        c.force_login(user)
        r = c.get(reverse("eventos:oficios-global"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "SEM ASSINATURA")
        self.assertContains(r, "Gerar link")

    def test_gera_novo_link_apos_invalidacao(self, _mock_pdf):
        User = get_user_model()
        user = User.objects.create_user(username="gestor2", password="x")
        c = Client()
        c.force_login(user)
        post_url = reverse("assinaturas:pedido_criar")
        payload = {
            "documento_tipo": "eventos.oficio",
            "documento_id": self.oficio.pk,
            "next": reverse("eventos:oficios-global"),
        }
        r1 = c.post(post_url, payload, follow=True)
        self.assertEqual(r1.status_code, 200)
        pedido1 = AssinaturaDocumento.objects.filter(documento_tipo__iexact="eventos.oficio", documento_id=self.oficio.pk).latest("id")
        self.oficio.motivo = "Forca invalidacao para novo link"
        self.oficio.save(update_fields=["motivo"])
        r2 = c.post(post_url, payload, follow=True)
        self.assertEqual(r2.status_code, 200)
        pedido1.refresh_from_db()
        self.assertEqual(pedido1.status, AssinaturaDocumento.Status.INVALIDADO_ALTERACAO)
        pedido2 = AssinaturaDocumento.objects.filter(documento_tipo__iexact="eventos.oficio", documento_id=self.oficio.pk).latest("id")
        self.assertNotEqual(pedido1.pk, pedido2.pk)
