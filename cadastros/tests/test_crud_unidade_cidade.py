from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Unidade


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
            {"nome": " Secretaria ", "sigla": " sec ", "ativa": "on"},
        )
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        unidade = Unidade.objects.get(nome="Secretaria", sigla="SEC")
        self.assertTrue(unidade.ativa)

    def test_get_edicao_unidade_retorna_200(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.get(reverse("cadastros:unidade_update", args=[unidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_unidade_altera_registro(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.post(
            reverse("cadastros:unidade_update", args=[unidade.pk]),
            {"nome": "Unidade B", "sigla": "ub", "ativa": "on"},
        )
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        unidade.refresh_from_db()
        self.assertEqual(unidade.nome, "Unidade B")
        self.assertEqual(unidade.sigla, "UB")

    def test_get_confirmacao_exclusao_unidade_retorna_200(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.get(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_unidade_desativa_registro(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.post(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        unidade.refresh_from_db()
        self.assertFalse(unidade.ativa)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class CidadeCrudTests(TestCase):
    def test_get_listagem_cidades_retorna_200(self):
        response = self.client.get(reverse("cadastros:cidades_index"))
        self.assertEqual(response.status_code, 200)

    def test_get_criacao_cidade_retorna_200(self):
        response = self.client.get(reverse("cadastros:cidade_create"))
        self.assertEqual(response.status_code, 200)

    def test_post_criacao_cidade_valida_redireciona_e_cria(self):
        response = self.client.post(
            reverse("cadastros:cidade_create"),
            {"nome": " Curitiba ", "uf": " pr ", "ativa": "on"},
        )
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        cidade = Cidade.objects.get(nome="Curitiba", uf="PR")
        self.assertTrue(cidade.ativa)

    def test_get_edicao_cidade_retorna_200(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.get(reverse("cadastros:cidade_update", args=[cidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_cidade_altera_registro(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.post(
            reverse("cadastros:cidade_update", args=[cidade.pk]),
            {"nome": "Londrina", "uf": "pr", "ativa": "on"},
        )
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        cidade.refresh_from_db()
        self.assertEqual(cidade.nome, "Londrina")
        self.assertEqual(cidade.uf, "PR")

    def test_get_confirmacao_exclusao_cidade_retorna_200(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.get(reverse("cadastros:cidade_delete", args=[cidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_cidade_desativa_registro(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.post(reverse("cadastros:cidade_delete", args=[cidade.pk]))
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        cidade.refresh_from_db()
        self.assertFalse(cidade.ativa)
