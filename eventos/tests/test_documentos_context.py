from django.test import TestCase

from cadastros.models import ConfiguracaoSistema
from documentos.services.context import _build_common_context


class DocumentosContextTests(TestCase):
    def _build_config(self, **kwargs):
        config = ConfiguracaoSistema.get_singleton()
        defaults = {
            "logradouro": "RUA X",
            "numero": "123",
            "bairro": "BAIRRO Y",
            "cidade_endereco": "CURITIBA",
            "uf": "PR",
            "cep": "80000000",
            "telefone": "41999999999",
            "email": "exemplo@pc.pr.gov.br",
            "divisao": "DIV",
            "unidade": "UNIDADE",
        }
        defaults.update(kwargs)
        for key, value in defaults.items():
            setattr(config, key, value)
        return config

    def test_institucional_endereco_montado(self):
        context = _build_common_context(self._build_config())
        self.assertEqual(
            context["institucional"]["endereco"],
            "RUA X, 123, BAIRRO Y, CURITIBA / PR, CEP 80000-000",
        )

    def test_institucional_telefone_mascarado(self):
        context = _build_common_context(self._build_config(telefone="4133334444"))
        self.assertEqual(context["institucional"]["telefone"], "(41) 3333-4444")

    def test_institucional_email_preenchido(self):
        context = _build_common_context(self._build_config(email="contato@pc.pr.gov.br"))
        self.assertEqual(context["institucional"]["email"], "contato@pc.pr.gov.br")

    def test_rodape_sem_telefone(self):
        context = _build_common_context(self._build_config(telefone=""))
        self.assertEqual(
            context["rodape_linha"],
            "RUA X, 123, BAIRRO Y, CURITIBA / PR, CEP 80000-000 | E-mail: exemplo@pc.pr.gov.br",
        )

    def test_rodape_sem_email(self):
        context = _build_common_context(self._build_config(email=""))
        self.assertEqual(
            context["rodape_linha"],
            "RUA X, 123, BAIRRO Y, CURITIBA / PR, CEP 80000-000 | Telefone: (41) 99999-9999",
        )

    def test_rodape_sem_telefone_e_email(self):
        context = _build_common_context(self._build_config(telefone="", email=""))
        self.assertEqual(context["rodape_linha"], "RUA X, 123, BAIRRO Y, CURITIBA / PR, CEP 80000-000")
