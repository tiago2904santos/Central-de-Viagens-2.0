from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from cadastros.models import Cargo, UnidadeLotacao, Viajante
from eventos.models import Oficio
from prestacao_contas.models import PrestacaoConta, TextoPadraoDocumento
from prestacao_contas.services.relatorio_tecnico import (
    obter_ou_criar_rt,
    obter_valor_diaria_individual,
)

User = get_user_model()


class RelatorioTecnicoPrestacaoTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rt-user", password="123")
        self.client = Client()
        self.client.login(username="rt-user", password="123")
        self.cargo = Cargo.objects.create(nome="Investigador")
        self.unidade = UnidadeLotacao.objects.create(nome="Unidade RT")
        self.servidor = Viajante.objects.create(
            nome="Servidor RT",
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf="12312312312",
            rg="1234567",
            unidade_lotacao=self.unidade,
            telefone="41999998888",
        )
        self.outro_servidor = Viajante.objects.create(
            nome="Servidor 2",
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf="99988877766",
            rg="7654321",
            unidade_lotacao=self.unidade,
            telefone="41999997777",
        )
        self.oficio = Oficio.objects.create(
            protocolo="123",
            numero=5,
            ano=2026,
            motivo="Missao tecnica",
            valor_diarias=Decimal("1750.00"),
            status=Oficio.STATUS_FINALIZADO,
        )
        self.oficio.viajantes.add(self.servidor, self.outro_servidor)
        self.prestacao = PrestacaoConta.objects.create(
            oficio=self.oficio,
            servidor=self.servidor,
            nome_servidor=self.servidor.nome,
            rg_servidor=self.servidor.rg,
            cpf_servidor=self.servidor.cpf,
            cargo_servidor=self.cargo.nome,
            dados_db={"valor_diaria_individual": "500,00"},
            status=PrestacaoConta.STATUS_EM_ANDAMENTO,
        )

    def test_diaria_do_rt_usa_valor_individual_da_prestacao(self):
        valor_individual = obter_valor_diaria_individual(self.prestacao)
        rt = obter_ou_criar_rt(self.prestacao, usuario=self.user)
        self.assertEqual(valor_individual, Decimal("500.00"))
        self.assertEqual(rt.diaria, "R$ 500,00")
        self.assertNotEqual(rt.diaria, "R$ 1.750,00")

    def test_autosave_rt_atualiza_apenas_campos_enviados(self):
        rt = obter_ou_criar_rt(self.prestacao, usuario=self.user)
        rt.conclusao = "Conclusao original"
        rt.medidas = "Medidas originais"
        rt.informacoes_complementares = "Info original"
        rt.save()

        response = self.client.post(
            reverse("prestacao_contas:relatorio-tecnico-autosave", kwargs={"prestacao_id": self.prestacao.pk}),
            data={
                "autosave": "1",
                "teve_translado": "1",
                "valor_translado": "88,90",
            },
        )
        self.assertEqual(response.status_code, 200)
        rt.refresh_from_db()
        self.assertTrue(rt.teve_translado)
        self.assertEqual(rt.translado, "R$ 88,90")
        self.assertEqual(rt.conclusao, "Conclusao original")
        self.assertEqual(rt.medidas, "Medidas originais")
        self.assertEqual(rt.informacoes_complementares, "Info original")
        self.assertEqual(rt.status, rt.STATUS_RASCUNHO)

    def test_autosave_modelo_preenche_texto_e_persiste(self):
        rt = obter_ou_criar_rt(self.prestacao, usuario=self.user)
        modelo = TextoPadraoDocumento.objects.create(
            categoria=TextoPadraoDocumento.CATEGORIA_RT_CONCLUSAO,
            titulo="Modelo de conclusao",
            texto="Texto padrao de conclusao",
        )

        response = self.client.post(
            reverse("prestacao_contas:relatorio-tecnico-autosave", kwargs={"prestacao_id": self.prestacao.pk}),
            data={"autosave": "1", "conclusao_modelo": str(modelo.pk)},
        )
        self.assertEqual(response.status_code, 200)
        rt.refresh_from_db()
        self.assertEqual(rt.conclusao, "Texto padrao de conclusao")
