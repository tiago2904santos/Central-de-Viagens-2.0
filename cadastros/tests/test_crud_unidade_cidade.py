from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
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
        unidade = Unidade.objects.get(nome="Secretaria", sigla="SEC")
        self.assertEqual(unidade.sigla, "SEC")

    def test_get_edicao_unidade_retorna_200(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.get(reverse("cadastros:unidade_update", args=[unidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_unidade_altera_registro(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.post(
            reverse("cadastros:unidade_update", args=[unidade.pk]),
            {"nome": "Unidade B", "sigla": "ub"},
        )
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        unidade.refresh_from_db()
        self.assertEqual(unidade.nome, "Unidade B")
        self.assertEqual(unidade.sigla, "UB")

    def test_get_confirmacao_exclusao_unidade_retorna_200(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.get(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_unidade_remove_registro(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        response = self.client.post(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        self.assertFalse(Unidade.objects.filter(pk=unidade.pk).exists())

    def test_post_exclusao_unidade_com_vinculo_bloqueia_exclusao(self):
        unidade = Unidade.objects.create(nome="Unidade A", sigla="UA")
        Servidor.objects.create(nome="Servidor A", unidade=unidade)
        response = self.client.post(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        self.assertTrue(Unidade.objects.filter(pk=unidade.pk).exists())

    def test_post_exclusao_unidade_com_viatura_bloqueia_exclusao(self):
        unidade = Unidade.objects.create(nome="Unidade B", sigla="UB")
        Viatura.objects.create(placa="ZZZ0001", unidade=unidade)
        response = self.client.post(reverse("cadastros:unidade_delete", args=[unidade.pk]))
        self.assertRedirects(response, reverse("cadastros:unidades_index"))
        self.assertTrue(Unidade.objects.filter(pk=unidade.pk).exists())


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
            {"nome": " Curitiba ", "uf": " pr "},
        )
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        cidade = Cidade.objects.get(nome="Curitiba", uf="PR")
        self.assertEqual(cidade.uf, "PR")

    def test_get_edicao_cidade_retorna_200(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.get(reverse("cadastros:cidade_update", args=[cidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_cidade_altera_registro(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.post(
            reverse("cadastros:cidade_update", args=[cidade.pk]),
            {"nome": "Londrina", "uf": "pr"},
        )
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        cidade.refresh_from_db()
        self.assertEqual(cidade.nome, "Londrina")
        self.assertEqual(cidade.uf, "PR")

    def test_get_confirmacao_exclusao_cidade_retorna_200(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.get(reverse("cadastros:cidade_delete", args=[cidade.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_cidade_remove_registro(self):
        cidade = Cidade.objects.create(nome="Curitiba", uf="PR")
        response = self.client.post(reverse("cadastros:cidade_delete", args=[cidade.pk]))
        self.assertRedirects(response, reverse("cadastros:cidades_index"))
        self.assertFalse(Cidade.objects.filter(pk=cidade.pk).exists())
