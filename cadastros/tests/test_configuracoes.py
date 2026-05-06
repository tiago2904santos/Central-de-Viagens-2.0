from unittest.mock import Mock
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.forms import ConfiguracaoSistemaForm
from cadastros.models import ConfiguracaoSistema


class ConfiguracaoSistemaFormTests(TestCase):
    def setUp(self):
        self.instance = ConfiguracaoSistema.get_singleton()

    def _build_valid_data(self):
        return {
            "divisao": "DIV",
            "unidade": "UNI",
            "cep": "80000-000",
            "logradouro": "RUA TESTE",
            "numero": "123",
            "bairro": "CENTRO",
            "cidade_endereco": "CURITIBA",
            "uf": "pr",
            "telefone": "(41) 3333-4444",
            "email": "teste@pc.pr.gov.br",
        }

    def test_salva_cep_valido(self):
        form = ConfiguracaoSistemaForm(data=self._build_valid_data(), instance=self.instance)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.cep, "80000000")

    def test_exibe_cep_e_telefone_mascarados_ao_editar(self):
        self.instance.cep = "80000000"
        self.instance.telefone = "41999998888"
        self.instance.save()
        form = ConfiguracaoSistemaForm(instance=self.instance)
        self.assertEqual(form.initial["cep"], "80000-000")
        self.assertEqual(form.initial["telefone"], "(41) 99999-8888")

    def test_telefone_10_digitos_aceito(self):
        data = self._build_valid_data()
        data["telefone"] = "(41) 3333-4444"
        form = ConfiguracaoSistemaForm(data=data, instance=self.instance)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["telefone"], "4133334444")

    def test_telefone_11_digitos_aceito(self):
        data = self._build_valid_data()
        data["telefone"] = "(41) 99999-8888"
        form = ConfiguracaoSistemaForm(data=data, instance=self.instance)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["telefone"], "41999998888")

    def test_telefone_invalido_rejeitado(self):
        data = self._build_valid_data()
        data["telefone"] = "12345"
        form = ConfiguracaoSistemaForm(data=data, instance=self.instance)
        self.assertFalse(form.is_valid())
        self.assertIn("telefone", form.errors)

    def test_email_valido_aceito(self):
        form = ConfiguracaoSistemaForm(data=self._build_valid_data(), instance=self.instance)
        self.assertTrue(form.is_valid(), form.errors)

    def test_email_invalido_rejeitado(self):
        data = self._build_valid_data()
        data["email"] = "invalido@"
        form = ConfiguracaoSistemaForm(data=data, instance=self.instance)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class ApiConsultaCepTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="123456")

    def test_exige_login(self):
        url = reverse("cadastros:api_consulta_cep", kwargs={"cep": "80000000"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_retorna_400_para_cep_invalido(self):
        self.client.force_login(self.user)
        url = reverse("cadastros:api_consulta_cep", kwargs={"cep": "123"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    @patch("cadastros.views.requests.get")
    def test_retorna_404_para_cep_nao_encontrado(self, mock_get):
        self.client.force_login(self.user)
        api_response = Mock()
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = {"erro": True}
        mock_get.return_value = api_response

        url = reverse("cadastros:api_consulta_cep", kwargs={"cep": "99999999"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @patch("cadastros.views.requests.get")
    def test_retorna_200_com_campos_esperados(self, mock_get):
        self.client.force_login(self.user)
        api_response = Mock()
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = {
            "cep": "80000-000",
            "logradouro": "RUA TESTE",
            "bairro": "CENTRO",
            "localidade": "CURITIBA",
            "uf": "PR",
        }
        mock_get.return_value = api_response

        url = reverse("cadastros:api_consulta_cep", kwargs={"cep": "80000000"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["logradouro"], "RUA TESTE")
        self.assertEqual(response.json()["bairro"], "CENTRO")
        self.assertEqual(response.json()["cidade"], "CURITIBA")
        self.assertEqual(response.json()["uf"], "PR")
