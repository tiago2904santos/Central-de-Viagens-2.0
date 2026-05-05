from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class RoteirosBaseTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="roteiros_tester", password="teste")
        self.client.force_login(self.user)
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado_destino, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})
        self.cidade_dest, _ = Cidade.objects.get_or_create(
            nome="FLORIANOPOLIS", estado=self.estado_destino, defaults={"uf": "SC"}
        )

    def test_get_roteiros_retorna_200(self):
        response = self.client.get(reverse("roteiros:index"))
        self.assertEqual(response.status_code, 200)

    def test_get_novo_roteiro_retorna_200(self):
        response = self.client.get(reverse("roteiros:novo"))
        self.assertEqual(response.status_code, 200)

    def test_criar_roteiro_minimo_e_destino(self):
        r = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=r,
            estado=self.estado_destino,
            cidade=self.cidade_dest,
            ordem=0,
        )
        self.assertEqual(r.destinos.count(), 1)

    def test_trecho_ida(self):
        r = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        t = RoteiroTrecho.objects.create(
            roteiro=r,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado_destino,
            destino_cidade=self.cidade_dest,
        )
        self.assertEqual(t.roteiro, r)
