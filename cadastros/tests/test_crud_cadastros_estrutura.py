import re

from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CargoCrudTests(TestCase):
    def test_crud_cargo_e_normalizacao(self):
        self.assertEqual(self.client.get(reverse("cadastros:cargos_index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:cargo_create")).status_code, 200)

        response = self.client.post(reverse("cadastros:cargo_create"), {"nome": " analista "})
        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        cargo = Cargo.objects.get(nome="ANALISTA")

        response = self.client.post(reverse("cadastros:cargo_update", args=[cargo.pk]), {"nome": " gerente "})
        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        cargo.refresh_from_db()
        self.assertEqual(cargo.nome, "GERENTE")

        self.client.post(reverse("cadastros:cargo_create"), {"nome": "gerente"})
        self.assertEqual(Cargo.objects.filter(nome="GERENTE").count(), 1)

        response = self.client.post(reverse("cadastros:cargo_delete", args=[cargo.pk]))
        self.assertRedirects(response, reverse("cadastros:cargos_index"))
        self.assertFalse(Cargo.objects.filter(pk=cargo.pk).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CombustivelCrudTests(TestCase):
    def test_crud_combustivel_e_normalizacao(self):
        self.assertEqual(self.client.get(reverse("cadastros:combustiveis_index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:combustivel_create")).status_code, 200)

        response = self.client.post(reverse("cadastros:combustivel_create"), {"nome": " gasolina "})
        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        combustivel = Combustivel.objects.get(nome="GASOLINA")

        response = self.client.post(
            reverse("cadastros:combustivel_update", args=[combustivel.pk]),
            {"nome": " etanol "},
        )
        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        combustivel.refresh_from_db()
        self.assertEqual(combustivel.nome, "ETANOL")

        self.client.post(reverse("cadastros:combustivel_create"), {"nome": "etanol"})
        self.assertEqual(Combustivel.objects.filter(nome="ETANOL").count(), 1)

        response = self.client.post(reverse("cadastros:combustivel_delete", args=[combustivel.pk]))
        self.assertRedirects(response, reverse("cadastros:combustiveis_index"))
        self.assertFalse(Combustivel.objects.filter(pk=combustivel.pk).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class SimpleListCsrfTests(TestCase):
    def test_acao_inline_de_cargo_renderiza_csrf_e_aceita_post(self):
        Cargo.objects.create(nome="ANALISTA", is_padrao=True)
        cargo = Cargo.objects.create(nome="GERENTE")
        client = Client(enforce_csrf_checks=True)

        response = client.get(reverse("cadastros:cargos_index"))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode()
        self.assertIn('name="csrfmiddlewaretoken"', html)
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
        self.assertIsNotNone(match)

        response = client.post(
            reverse("cadastros:cargo_set_default", args=[cargo.pk]),
            {"csrfmiddlewaretoken": match.group(1)},
        )
        self.assertRedirects(response, reverse("cadastros:cargos_index"))


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ServidorCrudTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Secretaria", sigla="SEC")
        self.cargo = Cargo.objects.create(nome="ANALISTA")

    def test_servidor_fluxo_busca_e_regras(self):
        create_page = self.client.get(reverse("cadastros:servidor_create"))
        self.assertEqual(create_page.status_code, 200)
        self.assertNotContains(create_page, 'name="matricula"')

        response = self.client.post(
            reverse("cadastros:servidor_create"),
            {
                "nome": " joao silva ",
                "cargo": str(self.cargo.pk),
                "cpf": "111.444.777-35",
                "rg": "12.345.678-9",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor = Servidor.objects.get(nome="JOAO SILVA")
        self.assertEqual(servidor.cpf, "11144477735")
        self.assertEqual(servidor.rg, "123456789")

        response = self.client.post(
            reverse("cadastros:servidor_update", args=[servidor.pk]),
            {
                "nome": "joao silva",
                "cargo": str(self.cargo.pk),
                "cpf": "11144477735",
                "rg": "",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))

        self.client.post(
            reverse("cadastros:servidor_create"),
            {
                "nome": "JOAO SILVA",
                "cargo": str(self.cargo.pk),
                "cpf": "",
                "rg": "",
                "unidade": "",
            },
        )
        self.assertEqual(Servidor.objects.filter(nome="JOAO SILVA").count(), 1)

        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "JOAO"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "11144477735"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "123456789"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:servidores_index"), {"q": "ANALISTA"}).status_code, 200)

        response = self.client.post(reverse("cadastros:servidor_delete", args=[servidor.pk]))
        self.assertRedirects(response, reverse("cadastros:servidores_index"))


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ViaturaCrudTests(TestCase):
    def setUp(self):
        self.combustivel = Combustivel.objects.create(nome="GASOLINA")

    def test_viatura_fluxo_busca_e_validacoes(self):
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viatura_create")).status_code, 200)

        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "aaa1234",
                "modelo": "Onix",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura = Viatura.objects.get(placa="AAA1234")

        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "aaa1a23",
                "modelo": "Tracker",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_DESCARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        self.assertTrue(Viatura.objects.filter(placa="AAA1A23").exists())

        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "12ABC34",
                "modelo": "Invalida",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Placa deve estar no formato")

        self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": "AAA1234",
                "modelo": "Duplicada",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertEqual(Viatura.objects.filter(placa="AAA1234").count(), 1)

        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "AAA"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "Onix"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "GASOLINA"}).status_code, 200)
        self.assertEqual(self.client.get(reverse("cadastros:viaturas_index"), {"q": "CARACTERIZADA"}).status_code, 200)

        response = self.client.post(
            reverse("cadastros:viatura_update", args=[viatura.pk]),
            {
                "placa": "aaa1234",
                "modelo": "Onix Plus",
                "combustivel": str(self.combustivel.pk),
                "tipo": Viatura.TIPO_CARACTERIZADA,
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))

        response = self.client.post(reverse("cadastros:viatura_delete", args=[viatura.pk]))
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class MotoristaRemovidoTests(TestCase):
    def test_rota_motoristas_nao_existe(self):
        response = self.client.get("/cadastros/motoristas/")
        self.assertEqual(response.status_code, 404)
