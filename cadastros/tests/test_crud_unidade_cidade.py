from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Combustivel
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class UnidadeCrudTests(TestCase):
    def test_get_listagem_unidades_retorna_200(self):
        response = self.client.get(reverse("cadastros:unidades_index"))
        self.assertEqual(response.status_code, 200)

    def test_get_criacao_unidade_retorna_200(self):
        response = self.client.get(reverse("cadastros:unidade_create"))
        self.assertEqual(response.status_code, 200)

    def test_post_criacao_unidade_valida_redireciona_e_cria(self):
        response = self.client.post(
            reverse("cadastros:unidade_create"),
            {"nome": " Secretaria ", "sigla": " sec "},
        )
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        unidade = Unidade.objects.get(nome="SECRETARIA", sigla="SEC")
        self.assertEqual(unidade.sigla, "SEC")

    def test_post_exclusao_unidade_com_vinculo_bloqueia_exclusao(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        Servidor.objects.create(nome="SERVIDOR A", unidade=unidade)
        response = self.client.post(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        self.assertTrue(Unidade.objects.filter(pk=unidade.pk).exists())

    def test_post_exclusao_unidade_com_viatura_bloqueia_exclusao(self):
        unidade = Unidade.objects.create(nome="Unidade B", sigla="UB")
        combustivel = Combustivel.objects.create(nome="GASOLINA")
        Viatura.objects.create(placa="ZZZ0001", combustivel=combustivel, tipo=Viatura.TIPO_CARACTERIZADA)
        Servidor.objects.create(nome="SERVIDOR B", unidade=unidade)
        response = self.client.post(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        self.assertTrue(Unidade.objects.filter(pk=unidade.pk).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CidadeCrudTests(TestCase):
    def setUp(self):
        self.estado_pr, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})

    def test_get_listagem_cidades_retorna_200(self):
        response = self.client.get(reverse("cadastros:cidades_index"))
        self.assertEqual(response.status_code, 200)

    def test_get_criacao_cidade_retorna_200(self):
        response = self.client.get(reverse("cadastros:cidade_create"))
        self.assertEqual(response.status_code, 200)

    def test_post_criacao_cidade_valida_redireciona_e_cria(self):
        response = self.client.post(
            reverse("cadastros:cidade_create"),
            {"nome": " Curitiba ", "estado": self.estado_pr.pk},
        )
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        cidade = Cidade.objects.get(nome="CURITIBA", estado=self.estado_pr)
        self.assertEqual(cidade.uf, "PR")

    def test_get_exportar_cidades_csv_retorna_arquivo(self):
        Cidade.objects.create(nome="LONDRINA", estado=self.estado_pr)
        response = self.client.get(reverse("cadastros:cidades_export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        body = response.content.decode("utf-8-sig")
        self.assertIn("LONDRINA", body)
        self.assertIn("PR", body)
