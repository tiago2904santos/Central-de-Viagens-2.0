from __future__ import annotations

from datetime import date, datetime, time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cidade, Estado
from eventos.models import Oficio, OficioTrecho, RoteiroEvento, RoteiroEventoTrecho
from prestacao_contas.models import PrestacaoConta

from .models import DiarioBordo, DiarioBordoTrecho
from . import services
from .forms import DiarioTrechoForm
from .services import gerar_diario_bordo_pdf, render_xlsx_diario_bordo


NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _sheet_values(xlsx_bytes):
    with ZipFile(BytesIO(xlsx_bytes)) as zf:
        shared = []
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall("x:si", NS):
            shared.append("".join(t.text or "" for t in si.findall(".//x:t", NS)))
        sheet_name = [name for name in zf.namelist() if name.startswith("xl/worksheets/sheet")][0]
        sheet = ET.fromstring(zf.read(sheet_name))
        rows = []
        for row in sheet.findall(".//x:sheetData/x:row", NS):
            values = []
            for cell in row.findall("x:c", NS):
                value_node = cell.find("x:v", NS)
                if value_node is not None:
                    value = value_node.text or ""
                    if cell.attrib.get("t") == "s":
                        value = shared[int(value)]
                else:
                    value = "".join(t.text or "" for t in cell.findall(".//x:t", NS))
                values.append(value)
            rows.append(values)
        return rows


class DiarioBordoPlaceholderDinamicoTest(TestCase):
    def _diario(self):
        return DiarioBordo.objects.create(
            numero_oficio="12/2026",
            e_protocolo="123.456",
            divisao="DIVISAO TESTE",
            unidade_cabecalho="UNIDADE TESTE",
            tipo_veiculo="DESCARACTERIZADA",
            combustivel="Gasolina",
            placa_oficial="ABC1D23",
            placa_reservada="RES1234",
            nome_responsavel="MOTORISTA TESTE",
            rg_responsavel="1.234.567-8",
        )

    def _trecho(self, diario, ordem, origem, destino, abastecimento=False):
        return DiarioBordoTrecho.objects.create(
            diario=diario,
            ordem=ordem,
            data_saida=date(2026, 4, 30),
            hora_saida=time(8, 15),
            km_inicial=100 + ordem,
            data_chegada=date(2026, 4, 30),
            hora_chegada=time(9, 45),
            km_final=150 + ordem,
            origem=origem,
            destino=destino,
            necessidade_abastecimento=abastecimento,
        )

    def test_diario_com_um_trecho_sem_placeholders(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas", True)
        xlsx = render_xlsx_diario_bordo(diario)
        text = ZipFile(BytesIO(xlsx)).read("xl/worksheets/sheet1.xml").decode("utf-8")
        self.assertNotIn("{{", text)
        rows = _sheet_values(xlsx)
        flat = "\n".join("|".join(row) for row in rows)
        self.assertIn("30/04/2026", flat)
        self.assertIn("08:15", flat)
        self.assertIn("09:45", flat)
        self.assertTrue(any("CURITIBA" in row and "PALMAS" in row for row in rows))

    def test_diario_com_tres_trechos_gera_tres_linhas(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas")
        self._trecho(diario, 1, "Palmas", "Dois Vizinhos")
        self._trecho(diario, 2, "Dois Vizinhos", "Curitiba")
        rows = _sheet_values(render_xlsx_diario_bordo(diario))
        generated = [row for row in rows if any(city in row for city in ["CURITIBA", "PALMAS", "DOIS VIZINHOS"])]
        self.assertEqual(len(generated), 3)

    def test_diario_sem_trecho_gera_linha_unica_de_estado_vazio(self):
        diario = self._diario()
        rows = _sheet_values(render_xlsx_diario_bordo(diario))
        self.assertTrue(any("SEM TRECHOS CADASTRADOS" in row for row in rows))

    def test_abastecimento_sim_e_nao(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas", True)
        self._trecho(diario, 1, "Palmas", "Curitiba", False)
        flat = "\n".join("|".join(row) for row in _sheet_values(render_xlsx_diario_bordo(diario)))
        self.assertIn("(X) Sim ( ) Não", flat)
        self.assertIn("( ) Sim (X) Não", flat)

    def test_trecho_com_abastecimento_sim(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas", True)
        flat = "\n".join("|".join(row) for row in _sheet_values(render_xlsx_diario_bordo(diario)))
        self.assertIn("(X) Sim ( ) Não", flat)

    def test_trecho_com_abastecimento_nao(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas", False)
        flat = "\n".join("|".join(row) for row in _sheet_values(render_xlsx_diario_bordo(diario)))
        self.assertIn("( ) Sim (X) Não", flat)

    def test_documento_final_nao_tem_placeholders_restantes(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas")
        xlsx = render_xlsx_diario_bordo(diario)
        with ZipFile(BytesIO(xlsx)) as zf:
            xml_payload = "\n".join(
                zf.read(name).decode("utf-8", errors="ignore")
                for name in zf.namelist()
                if name.endswith(".xml")
            )
        self.assertNotIn("{{", xml_payload)
        self.assertNotIn("}}", xml_payload)

    def test_xlsx_usa_modelo_oficial(self):
        self.assertEqual(
            services.XLSX_TEMPLATE_PATH,
            Path(services.settings.BASE_DIR) / "documentos" / "templates_xlsx" / "diario_bordo" / "modelo_diario_bordo.xlsx",
        )
        self.assertTrue(services.XLSX_TEMPLATE_PATH.exists())

    def test_pdf_e_gerado_a_partir_do_xlsx_preenchido(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas")
        captured = {}

        def fake_converter(xlsx_path, pdf_path):
            captured["xlsx_bytes"] = Path(xlsx_path).read_bytes()
            Path(pdf_path).write_bytes(b"%PDF-1.4 diario convertido do xlsx")
            return Path(pdf_path)

        with patch("diario_bordo.services.converter_xlsx_para_pdf", side_effect=fake_converter) as converter:
            pdf_bytes, filename = gerar_diario_bordo_pdf(diario)

        self.assertTrue(converter.called)
        self.assertTrue(diario.arquivo_xlsx.name.endswith(".xlsx"))
        self.assertTrue(diario.arquivo_pdf.name.endswith(".pdf"))
        self.assertIn("diario_bordo_oficio_12_2026", filename)
        self.assertEqual(pdf_bytes, b"%PDF-1.4 diario convertido do xlsx")
        with ZipFile(BytesIO(captured["xlsx_bytes"])) as zf:
            xml_payload = "\n".join(
                zf.read(name).decode("utf-8", errors="ignore")
                for name in zf.namelist()
                if name.endswith(".xml")
            )
        self.assertNotIn("{{", xml_payload)

    def test_botao_pdf_chama_fluxo_xlsx_para_pdf(self):
        usuario = get_user_model().objects.create_user("dbuser", password="senha")
        self.client.force_login(usuario)
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas")

        def fake_converter(_xlsx_path, pdf_path):
            Path(pdf_path).write_bytes(b"%PDF-1.4")
            return Path(pdf_path)

        with patch("diario_bordo.services.converter_xlsx_para_pdf", side_effect=fake_converter) as converter:
            response = self.client.post(reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 4}), {"gerar_pdf": "1"})

        self.assertRedirects(response, reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 4}))
        self.assertTrue(converter.called)
        diario.refresh_from_db()
        self.assertTrue(diario.arquivo_xlsx)
        self.assertTrue(diario.arquivo_pdf)

    def test_pdf_nao_tem_fallback_generico(self):
        diario = self._diario()
        self._trecho(diario, 0, "Curitiba", "Palmas")
        with patch("diario_bordo.services._converter_xlsx_com_excel", return_value=False), patch(
            "diario_bordo.services._converter_xlsx_com_libreoffice", return_value=False
        ):
            with self.assertRaises(ValidationError):
                gerar_diario_bordo_pdf(diario)
        diario.refresh_from_db()
        self.assertFalse(diario.arquivo_pdf)

    def test_formulario_de_trecho_renderiza_datas_para_input_date(self):
        diario = self._diario()
        trecho = self._trecho(diario, 0, "Curitiba", "Palmas")
        form = DiarioTrechoForm(instance=trecho)
        self.assertIn('value="2026-04-30"', form["data_saida"].as_widget())
        self.assertIn('value="2026-04-30"', form["data_chegada"].as_widget())


class DiarioBordoStep3ImportacaoTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("step3", password="senha123")
        self.client.force_login(self.user)
        self.estado = Estado.objects.create(nome="Parana", sigla="PR", codigo_ibge="41")
        self.curitiba = Cidade.objects.create(nome="Curitiba", estado=self.estado, codigo_ibge="4106902")
        self.londrina = Cidade.objects.create(nome="Londrina", estado=self.estado, codigo_ibge="4113700")
        self.maringa = Cidade.objects.create(nome="Maringa", estado=self.estado, codigo_ibge="4115200")

    def _create_roteiro(self):
        tz = timezone.get_current_timezone()
        roteiro = RoteiroEvento.objects.create(
            origem_estado=self.estado,
            origem_cidade=self.curitiba,
            saida_dt=timezone.make_aware(datetime(2026, 4, 4, 8, 0), tz),
            chegada_dt=timezone.make_aware(datetime(2026, 4, 10, 18, 0), tz),
            retorno_saida_dt=timezone.make_aware(datetime(2026, 4, 15, 9, 0), tz),
        )
        RoteiroEventoTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.curitiba,
            destino_estado=self.estado,
            destino_cidade=self.londrina,
            saida_dt=timezone.make_aware(datetime(2026, 4, 4, 8, 0), tz),
            chegada_dt=timezone.make_aware(datetime(2026, 4, 4, 11, 0), tz),
        )
        RoteiroEventoTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            origem_estado=self.estado,
            origem_cidade=self.londrina,
            destino_estado=self.estado,
            destino_cidade=self.maringa,
            saida_dt=timezone.make_aware(datetime(2026, 4, 5, 9, 0), tz),
            chegada_dt=timezone.make_aware(datetime(2026, 4, 5, 10, 30), tz),
        )
        return roteiro

    def _create_oficio(self, roteiro=None):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO, cidade_sede=self.curitiba, estado_sede=self.estado)
        if roteiro:
            oficio.roteiro_evento = roteiro
            oficio.save(update_fields=["roteiro_evento", "updated_at"])
        return oficio

    def test_step3_importa_trechos_do_oficio_com_roteiro(self):
        roteiro = self._create_roteiro()
        oficio = self._create_oficio(roteiro=roteiro)
        diario = DiarioBordo.objects.create(oficio=oficio, roteiro=roteiro)

        response = self.client.get(reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(diario.trechos.count(), 2)
        self.assertContains(response, "2026-04-04")
        self.assertContains(response, "Curitiba/PR")
        self.assertContains(response, "Londrina/PR")

    def test_step3_importa_trechos_via_prestacao(self):
        roteiro = self._create_roteiro()
        oficio = self._create_oficio(roteiro=roteiro)
        prestacao = PrestacaoConta.objects.create(oficio=oficio)
        diario = DiarioBordo.objects.create(prestacao=prestacao)

        response = self.client.get(reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(diario.trechos.count(), 2)
        self.assertContains(response, "Maringa/PR")

    def test_reabrir_step3_preserva_km_digitado(self):
        roteiro = self._create_roteiro()
        oficio = self._create_oficio(roteiro=roteiro)
        diario = DiarioBordo.objects.create(oficio=oficio, roteiro=roteiro)
        trecho = DiarioBordoTrecho.objects.create(
            diario=diario,
            ordem=0,
            origem="Curitiba/PR",
            destino="Londrina/PR",
            km_inicial=1234,
            km_final=1300,
        )

        response = self.client.get(reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3}))
        trecho.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(diario.trechos.count(), 1)
        self.assertEqual(trecho.km_inicial, 1234)
        self.assertEqual(trecho.km_final, 1300)

    def test_step3_sem_roteiro_mostra_aviso_e_permite_manual(self):
        diario = DiarioBordo.objects.create()

        response = self.client.get(reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum roteiro/data foi encontrado automaticamente. Preencha os trechos manualmente.")
        self.assertContains(response, "Adicionar trecho")

    def test_botao_reimportar_recria_trechos_somente_quando_acionado(self):
        oficio = self._create_oficio()
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.curitiba,
            destino_estado=self.estado,
            destino_cidade=self.londrina,
            saida_data="2026-04-04",
        )
        diario = DiarioBordo.objects.create(oficio=oficio)
        DiarioBordoTrecho.objects.create(diario=diario, ordem=0, origem="Manual", destino="Manual", km_inicial=10)

        self.client.get(reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3}))
        diario.refresh_from_db()
        self.assertEqual(diario.trechos.first().origem, "Manual")

        response = self.client.post(
            reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3}),
            {"reimportar_trechos": "1"},
            follow=True,
        )
        diario.refresh_from_db()
        trecho = diario.trechos.order_by("ordem", "id").first()
        self.assertContains(response, "Datas e destinos reimportados com sucesso.")
        self.assertEqual(trecho.origem, "Curitiba/PR")
        self.assertEqual(trecho.destino, "Londrina/PR")

    def test_xlsx_exige_trechos_salvos_no_banco(self):
        diario = DiarioBordo.objects.create(numero_oficio="99/2026")
        with self.assertRaises(ValidationError):
            services.gerar_diario_bordo_xlsx(diario)
