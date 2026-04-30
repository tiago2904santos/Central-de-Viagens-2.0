from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from cadastros.models import Cargo, Estado, Cidade, UnidadeLotacao, Viajante
from eventos.models import Evento, Oficio
from prestacao_contas.models import PrestacaoConta
from prestacao_contas.services.sincronizacao import sincronizar_prestacoes_do_oficio

User = get_user_model()


class PrestacaoAutomaticaPorServidorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="123")
        self.client = Client()
        self.client.login(username="tester", password="123")
        self.estado = Estado.objects.create(nome="Parana", sigla="PR", codigo_ibge="41")
        self.cidade = Cidade.objects.create(
            nome="Curitiba",
            estado=self.estado,
            codigo_ibge="4106902",
            ativo=True,
        )
        self.unidade = UnidadeLotacao.objects.create(nome="Unidade A", sigla="UA")
        self.cargo = Cargo.objects.create(nome="Investigador")
        self.evento = Evento.objects.create(
            titulo="Evento de Teste",
            data_inicio=date(2026, 5, 1),
            data_fim=date(2026, 5, 2),
            cidade_base=self.cidade,
            status=Evento.STATUS_RASCUNHO,
        )
        self.oficio = Oficio.objects.create(
            evento=self.evento,
            numero=5,
            ano=2026,
            protocolo="12345",
            motivo="Missao oficial",
            status=Oficio.STATUS_RASCUNHO,
        )
        self.servidor_1 = self._criar_servidor("Joao", "11111111111", "111111")
        self.servidor_2 = self._criar_servidor("Maria", "22222222222", "222222")
        self.servidor_3 = self._criar_servidor("Pedro", "33333333333", "333333")

    def _criar_servidor(self, nome, cpf, rg):
        return Viajante.objects.create(
            nome=nome,
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf=cpf,
            rg=rg,
            unidade_lotacao=self.unidade,
            telefone="41999990000",
        )

    def _finalizar_oficio_forcando_validacao(self):
        with patch(
            "eventos.views._validate_oficio_for_finalize",
            return_value={
                "ok": True,
                "sections": [],
                "errors": [],
                "justificativa_required": False,
                "justificativa_missing": False,
                "has_non_justificativa_errors": False,
            },
        ):
            return self.client.post(
                reverse("eventos:oficio-step4", kwargs={"pk": self.oficio.pk}),
                data={"finalizar": "1", "gerar_termo_preenchido": "0"},
            )

    def test_finalizar_oficio_cria_uma_prestacao_por_servidor(self):
        self.oficio.viajantes.add(self.servidor_1, self.servidor_2, self.servidor_3)

        response = self._finalizar_oficio_forcando_validacao()

        self.assertEqual(response.status_code, 302)
        self.oficio.refresh_from_db()
        self.assertEqual(self.oficio.status, Oficio.STATUS_FINALIZADO)
        self.assertEqual(
            PrestacaoConta.objects.filter(oficio=self.oficio).count(),
            3,
        )

    def test_finalizar_mesmo_oficio_nao_duplica_prestacoes(self):
        self.oficio.viajantes.add(self.servidor_1, self.servidor_2)

        self._finalizar_oficio_forcando_validacao()
        self._finalizar_oficio_forcando_validacao()

        prestacoes = PrestacaoConta.objects.filter(oficio=self.oficio)
        self.assertEqual(prestacoes.count(), 2)
        self.assertEqual(
            prestacoes.values("oficio_id", "servidor_id").distinct().count(),
            2,
        )

    def test_adicionar_servidor_novo_sincroniza_apenas_novo(self):
        self.oficio.viajantes.add(self.servidor_1, self.servidor_2)
        self._finalizar_oficio_forcando_validacao()
        self.assertEqual(PrestacaoConta.objects.filter(oficio=self.oficio).count(), 2)

        self.oficio.viajantes.add(self.servidor_3)
        sincronizar_prestacoes_do_oficio(self.oficio)

        self.assertEqual(PrestacaoConta.objects.filter(oficio=self.oficio).count(), 3)
        self.assertTrue(
            PrestacaoConta.objects.filter(oficio=self.oficio, servidor=self.servidor_3).exists()
        )

    def test_lista_prestacoes_exibe_itens_criados_automaticamente(self):
        self.oficio.viajantes.add(self.servidor_1, self.servidor_2)
        self._finalizar_oficio_forcando_validacao()

        response = self.client.get(reverse("prestacao_contas:lista"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.servidor_1.nome)
        self.assertContains(response, self.servidor_2.nome)
