from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.models import Roteiro
from roteiros.models import TrechoRoteiro
from roteiros.selectors import listar_trechos_do_roteiro


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class RoteirosBaseTests(TestCase):
    def setUp(self):
        self.estado_origem, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado_destino, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.origem, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado_origem)
        self.destino, _ = Cidade.objects.get_or_create(nome="FLORIANOPOLIS", estado=self.estado_destino)
        self.intermediaria, _ = Cidade.objects.get_or_create(nome="JOINVILLE", estado=self.estado_destino)

    def criar_roteiro(self):
        return Roteiro.objects.create(
            nome="Roteiro litoral sul",
            descricao="Deslocamento institucional",
            origem=self.origem,
            destino=self.destino,
        )

    def test_get_roteiros_retorna_200(self):
        response = self.client.get(reverse("roteiros:index"))
        self.assertEqual(response.status_code, 200)

    def test_listagem_vazia_retorna_200(self):
        response = self.client.get(reverse("roteiros:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum roteiro cadastrado ainda.")

    def test_criar_roteiro_via_model_funciona(self):
        roteiro = self.criar_roteiro()
        self.assertEqual(roteiro.nome, "Roteiro litoral sul")
        self.assertEqual(roteiro.origem, self.origem)
        self.assertEqual(roteiro.destino, self.destino)

    def test_roteiro_aparece_na_listagem(self):
        self.criar_roteiro()
        response = self.client.get(reverse("roteiros:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roteiro litoral sul")

    def test_busca_por_nome_retorna_200(self):
        self.criar_roteiro()
        response = self.client.get(reverse("roteiros:index"), {"q": "litoral"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roteiro litoral sul")

    def test_busca_por_cidade_de_origem_retorna_200(self):
        self.criar_roteiro()
        response = self.client.get(reverse("roteiros:index"), {"q": "Curitiba"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roteiro litoral sul")

    def test_busca_por_cidade_de_destino_retorna_200(self):
        self.criar_roteiro()
        response = self.client.get(reverse("roteiros:index"), {"q": "Florianopolis"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roteiro litoral sul")

    def test_criar_trecho_roteiro_via_model_funciona(self):
        roteiro = self.criar_roteiro()
        trecho = TrechoRoteiro.objects.create(
            roteiro=roteiro,
            ordem=1,
            origem=self.origem,
            destino=self.destino,
        )
        self.assertEqual(trecho.roteiro, roteiro)
        self.assertEqual(trecho.ordem, 1)

    def test_listar_trechos_do_roteiro_retorna_ordenado_por_ordem(self):
        roteiro = self.criar_roteiro()
        segundo = TrechoRoteiro.objects.create(
            roteiro=roteiro,
            ordem=2,
            origem=self.intermediaria,
            destino=self.destino,
        )
        primeiro = TrechoRoteiro.objects.create(
            roteiro=roteiro,
            ordem=1,
            origem=self.origem,
            destino=self.intermediaria,
        )

        trechos = list(listar_trechos_do_roteiro(roteiro))

        self.assertEqual(trechos, [primeiro, segundo])
