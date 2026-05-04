from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Motorista
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.models import Viatura


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ServidorCrudTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Secretaria", sigla="SEC")

    def test_get_listagem_servidores_retorna_200(self):
        response = self.client.get(reverse("cadastros:servidores_index"))
        self.assertEqual(response.status_code, 200)

    def test_get_criacao_servidor_retorna_200(self):
        response = self.client.get(reverse("cadastros:servidor_create"))
        self.assertEqual(response.status_code, 200)

    def test_post_criacao_servidor_valida_redireciona_e_cria(self):
        response = self.client.post(
            reverse("cadastros:servidor_create"),
            {
                "nome": " João  Silva ",
                "matricula": " 123 ",
                "cargo": " Analista ",
                "cpf": " 111.444.777-35 ",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor = Servidor.objects.get(nome="João Silva")
        self.assertEqual(servidor.matricula, "123")
        self.assertEqual(servidor.cargo, "Analista")
        self.assertEqual(servidor.cpf, "11144477735")

    def test_get_edicao_servidor_retorna_200(self):
        servidor = Servidor.objects.create(nome="Ana", unidade=self.unidade)
        response = self.client.get(reverse("cadastros:servidor_update", args=[servidor.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_servidor_altera_registro(self):
        servidor = Servidor.objects.create(nome="Ana", unidade=self.unidade)
        response = self.client.post(
            reverse("cadastros:servidor_update", args=[servidor.pk]),
            {
                "nome": "Ana Maria",
                "matricula": "99",
                "cargo": "Cargo",
                "cpf": "",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        servidor.refresh_from_db()
        self.assertEqual(servidor.nome, "Ana Maria")

    def test_get_confirmacao_exclusao_servidor_retorna_200(self):
        servidor = Servidor.objects.create(nome="Ana", unidade=self.unidade)
        response = self.client.get(reverse("cadastros:servidor_delete", args=[servidor.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_servidor_remove_registro(self):
        servidor = Servidor.objects.create(nome="Ana", unidade=self.unidade)
        response = self.client.post(reverse("cadastros:servidor_delete", args=[servidor.pk]))
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        self.assertFalse(Servidor.objects.filter(pk=servidor.pk).exists())

    def test_busca_por_nome_ou_matricula_retorna_200(self):
        Servidor.objects.create(nome="Bruno", matricula="M1", unidade=self.unidade)
        r1 = self.client.get(reverse("cadastros:servidores_index"), {"q": "Bruno"})
        r2 = self.client.get(reverse("cadastros:servidores_index"), {"q": "M1"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

    def test_post_exclusao_servidor_com_motorista_bloqueia(self):
        servidor = Servidor.objects.create(nome="Carlos", unidade=self.unidade)
        Motorista.objects.create(servidor=servidor)
        response = self.client.post(reverse("cadastros:servidor_delete", args=[servidor.pk]))
        self.assertRedirects(response, reverse("cadastros:servidores_index"))
        self.assertTrue(Servidor.objects.filter(pk=servidor.pk).exists())


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class MotoristaCrudTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Secretaria", sigla="SEC")
        self.servidor = Servidor.objects.create(nome="Diana", unidade=self.unidade)

    def test_get_listagem_motoristas_retorna_200(self):
        response = self.client.get(reverse("cadastros:motoristas_index"))
        self.assertEqual(response.status_code, 200)

    def test_get_criacao_motorista_retorna_200(self):
        response = self.client.get(reverse("cadastros:motorista_create"))
        self.assertEqual(response.status_code, 200)

    def test_post_criacao_motorista_valida_redireciona_e_cria(self):
        response = self.client.post(
            reverse("cadastros:motorista_create"),
            {
                "servidor": str(self.servidor.pk),
                "cnh": " 12345 ",
                "categoria_cnh": " b ",
            },
        )
        self.assertRedirects(response, reverse("cadastros:motoristas_index"))
        motorista = Motorista.objects.get(servidor=self.servidor)
        self.assertEqual(motorista.cnh, "12345")
        self.assertEqual(motorista.categoria_cnh, "B")

    def test_get_edicao_motorista_retorna_200(self):
        motorista = Motorista.objects.create(servidor=self.servidor)
        response = self.client.get(reverse("cadastros:motorista_update", args=[motorista.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_motorista_altera_registro(self):
        motorista = Motorista.objects.create(servidor=self.servidor, cnh="1")
        response = self.client.post(
            reverse("cadastros:motorista_update", args=[motorista.pk]),
            {
                "servidor": str(self.servidor.pk),
                "cnh": "999",
                "categoria_cnh": "d",
            },
        )
        self.assertRedirects(response, reverse("cadastros:motoristas_index"))
        motorista.refresh_from_db()
        self.assertEqual(motorista.cnh, "999")
        self.assertEqual(motorista.categoria_cnh, "D")

    def test_get_confirmacao_exclusao_motorista_retorna_200(self):
        motorista = Motorista.objects.create(servidor=self.servidor)
        response = self.client.get(reverse("cadastros:motorista_delete", args=[motorista.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_motorista_remove_registro(self):
        motorista = Motorista.objects.create(servidor=self.servidor)
        response = self.client.post(reverse("cadastros:motorista_delete", args=[motorista.pk]))
        self.assertRedirects(response, reverse("cadastros:motoristas_index"))
        self.assertFalse(Motorista.objects.filter(pk=motorista.pk).exists())

    def test_busca_por_nome_servidor_ou_cnh_retorna_200(self):
        Motorista.objects.create(servidor=self.servidor, cnh="XYZ")
        r1 = self.client.get(reverse("cadastros:motoristas_index"), {"q": "Diana"})
        r2 = self.client.get(reverse("cadastros:motoristas_index"), {"q": "XYZ"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ViaturaCrudTests(TestCase):
    def setUp(self):
        self.unidade = Unidade.objects.create(nome="Secretaria", sigla="SEC")

    def test_get_listagem_viaturas_retorna_200(self):
        response = self.client.get(reverse("cadastros:viaturas_index"))
        self.assertEqual(response.status_code, 200)

    def test_get_criacao_viatura_retorna_200(self):
        response = self.client.get(reverse("cadastros:viatura_create"))
        self.assertEqual(response.status_code, 200)

    def test_post_criacao_viatura_valida_redireciona_e_cria(self):
        response = self.client.post(
            reverse("cadastros:viatura_create"),
            {
                "placa": " abc1d23 ",
                "modelo": " Onix ",
                "marca": " GM ",
                "tipo": " Sedan ",
                "combustivel": " Flex ",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura = Viatura.objects.get(placa="ABC1D23")
        self.assertEqual(viatura.modelo, "Onix")

    def test_get_edicao_viatura_retorna_200(self):
        viatura = Viatura.objects.create(placa="AAA1111", unidade=self.unidade)
        response = self.client.get(reverse("cadastros:viatura_update", args=[viatura.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_edicao_viatura_altera_registro(self):
        viatura = Viatura.objects.create(placa="AAA1111", modelo="A", unidade=self.unidade)
        response = self.client.post(
            reverse("cadastros:viatura_update", args=[viatura.pk]),
            {
                "placa": "aaa1111",
                "modelo": "B",
                "marca": "",
                "tipo": "",
                "combustivel": "",
                "unidade": str(self.unidade.pk),
            },
        )
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        viatura.refresh_from_db()
        self.assertEqual(viatura.modelo, "B")
        self.assertEqual(viatura.placa, "AAA1111")

    def test_get_confirmacao_exclusao_viatura_retorna_200(self):
        viatura = Viatura.objects.create(placa="AAA2222", unidade=self.unidade)
        response = self.client.get(reverse("cadastros:viatura_delete", args=[viatura.pk]))
        self.assertEqual(response.status_code, 200)

    def test_post_exclusao_viatura_remove_registro(self):
        viatura = Viatura.objects.create(placa="AAA3333", unidade=self.unidade)
        response = self.client.post(reverse("cadastros:viatura_delete", args=[viatura.pk]))
        self.assertRedirects(response, reverse("cadastros:viaturas_index"))
        self.assertFalse(Viatura.objects.filter(pk=viatura.pk).exists())

    def test_busca_por_placa_ou_modelo_retorna_200(self):
        Viatura.objects.create(placa="BBB1234", modelo="Tracker", unidade=self.unidade)
        r1 = self.client.get(reverse("cadastros:viaturas_index"), {"q": "BBB"})
        r2 = self.client.get(reverse("cadastros:viaturas_index"), {"q": "Tracker"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
