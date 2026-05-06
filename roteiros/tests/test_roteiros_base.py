import json
from datetime import date
from datetime import time

from django.contrib.auth import get_user_model
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho
from roteiros import step3_logic


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
        self.cidade_dest_2, _ = Cidade.objects.get_or_create(
            nome="LONDRINA", estado=self.estado, defaults={"uf": "PR"}
        )
        self.cidade_dest_3, _ = Cidade.objects.get_or_create(
            nome="MARINGA", estado=self.estado, defaults={"uf": "PR"}
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

    def test_calculo_diarias_com_roteiro_salvo_sem_evento_id(self):
        r = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_FINALIZADO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=r,
            estado=self.estado_destino,
            cidade=self.cidade_dest,
            ordem=0,
        )
        request = RequestFactory().post(
            reverse("roteiros:novo"),
            data={
                "roteiro_modo": step3_logic.ROTEIRO_MODO_EVENTO,
                "roteiro_id": str(r.pk),
                "origem_estado": str(self.estado.pk),
                "origem_cidade": str(self.cidade_sede.pk),
                "destino_estado_0": str(self.estado_destino.pk),
                "destino_cidade_0": str(self.cidade_dest.pk),
            },
        )

        route_options, _, _, _ = step3_logic._build_roteiro_diarias_from_request(
            request,
            roteiro=r,
        )

        self.assertIn(r.pk, [option["id"] for option in route_options])

    def test_salvar_reordenacao_preserva_dados_dos_trechos_existentes(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        destinos = [self.cidade_dest, self.cidade_dest_2, self.cidade_dest_3]
        for ordem, cidade in enumerate(destinos):
            RoteiroDestino.objects.create(
                roteiro=roteiro,
                estado=cidade.estado,
                cidade=cidade,
                ordem=ordem,
            )
        trecho_1 = RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.cidade_dest.estado,
            destino_cidade=self.cidade_dest,
            saida_dt="2026-05-01 08:00",
            chegada_dt="2026-05-01 10:00",
            tempo_cru_estimado_min=120,
            tempo_adicional_min=30,
            duracao_estimada_min=150,
        )
        trecho_2 = RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.cidade_dest.estado,
            origem_cidade=self.cidade_dest,
            destino_estado=self.cidade_dest_2.estado,
            destino_cidade=self.cidade_dest_2,
            saida_dt="2026-05-02 09:00",
            chegada_dt="2026-05-02 11:00",
            tempo_cru_estimado_min=90,
            tempo_adicional_min=45,
            duracao_estimada_min=135,
        )

        step3_logic._salvar_roteiro_avulso_from_step3_state(
            roteiro,
            {
                "destinos_atuais": [
                    {"estado_id": self.cidade_dest_2.estado_id, "cidade_id": self.cidade_dest_2.pk},
                    {"estado_id": self.cidade_dest.estado_id, "cidade_id": self.cidade_dest.pk},
                ],
                "retorno": {
                    "saida_data": "2026-05-03",
                    "saida_hora": "18:00",
                    "chegada_data": "2026-05-03",
                    "chegada_hora": "20:00",
                    "tempo_cru_estimado_min": "120",
                    "tempo_adicional_min": "15",
                    "duracao_estimada_min": "135",
                },
            },
            {
                "trechos": [
                    {
                        "id": trecho_2.pk,
                        "origem_estado_id": self.estado.pk,
                        "origem_cidade_id": self.cidade_sede.pk,
                        "destino_estado_id": self.cidade_dest_2.estado_id,
                        "destino_cidade_id": self.cidade_dest_2.pk,
                        "saida_data": date(2026, 5, 2),
                        "saida_hora": time(9, 0),
                        "chegada_data": date(2026, 5, 2),
                        "chegada_hora": time(11, 0),
                        "tempo_cru_estimado_min": 90,
                        "tempo_adicional_min": 45,
                        "duracao_estimada_min": 135,
                    },
                    {
                        "id": trecho_1.pk,
                        "origem_estado_id": self.cidade_dest_2.estado_id,
                        "origem_cidade_id": self.cidade_dest_2.pk,
                        "destino_estado_id": self.cidade_dest.estado_id,
                        "destino_cidade_id": self.cidade_dest.pk,
                        "saida_data": date(2026, 5, 1),
                        "saida_hora": time(8, 0),
                        "chegada_data": date(2026, 5, 1),
                        "chegada_hora": time(10, 0),
                        "tempo_cru_estimado_min": 120,
                        "tempo_adicional_min": 30,
                        "duracao_estimada_min": 150,
                    },
                ],
                "retorno_saida_data": date(2026, 5, 3),
                "retorno_saida_hora": time(18, 0),
                "retorno_chegada_data": date(2026, 5, 3),
                "retorno_chegada_hora": time(20, 0),
            },
        )

        trecho_1.refresh_from_db()
        trecho_2.refresh_from_db()
        self.assertEqual(trecho_2.ordem, 0)
        self.assertEqual(trecho_1.ordem, 1)
        self.assertEqual(trecho_1.tempo_cru_estimado_min, 120)
        self.assertEqual(trecho_1.tempo_adicional_min, 30)
        self.assertEqual(trecho_1.duracao_estimada_min, 150)
        self.assertEqual(trecho_2.tempo_cru_estimado_min, 90)
        self.assertEqual(trecho_2.tempo_adicional_min, 45)
        self.assertEqual(trecho_2.duracao_estimada_min, 135)
        self.assertEqual(roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_IDA).count(), 2)

    def test_salvar_trecho_existente_nao_sobrescreve_campos_ausentes(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro,
            estado=self.estado_destino,
            cidade=self.cidade_dest,
            ordem=0,
        )
        trecho = RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado_destino,
            destino_cidade=self.cidade_dest,
            saida_dt="2026-05-04 07:30",
            chegada_dt="2026-05-04 09:45",
            tempo_cru_estimado_min=135,
            tempo_adicional_min=60,
            duracao_estimada_min=195,
        )

        step3_logic._salvar_roteiro_avulso_from_step3_state(
            roteiro,
            {
                "destinos_atuais": [
                    {"estado_id": self.estado_destino.pk, "cidade_id": self.cidade_dest.pk},
                ],
                "retorno": {},
            },
            {
                "trechos": [
                    {
                        "id": trecho.pk,
                        "origem_estado_id": self.estado.pk,
                        "origem_cidade_id": self.cidade_sede.pk,
                        "destino_estado_id": self.estado_destino.pk,
                        "destino_cidade_id": self.cidade_dest.pk,
                    }
                ],
            },
        )

        trecho.refresh_from_db()
        self.assertEqual(trecho.tempo_cru_estimado_min, 135)
        self.assertEqual(trecho.tempo_adicional_min, 60)
        self.assertEqual(trecho.duracao_estimada_min, 195)
        self.assertIsNotNone(trecho.saida_dt)
        self.assertIsNotNone(trecho.chegada_dt)

    def test_bate_volta_diario_remove_retorno_final_duplicado_do_post(self):
        request = RequestFactory().post(
            reverse("roteiros:novo"),
            data=self._loop_diario_post_data(),
        )

        state = step3_logic._build_avulso_step3_state_from_post(request)
        validated = step3_logic._validate_step3_state(state)

        self.assertTrue(validated["ok"], validated["errors"])
        self.assertEqual(len(state["trechos"]), 5)
        self.assertEqual(len(validated["trechos"]), 5)
        self.assertEqual(state["retorno"]["saida_data"], "2026-05-07")
        self.assertEqual(state["retorno"]["saida_hora"], "18:00")
        ultimo = validated["trechos"][-1]
        self.assertEqual(ultimo["origem_cidade_id"], self.cidade_sede.pk)
        self.assertEqual(ultimo["destino_cidade_id"], self.cidade_dest.pk)

    def test_salvar_bate_volta_diario_nao_persiste_retorno_final_como_ida(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro,
            estado=self.estado_destino,
            cidade=self.cidade_dest,
            ordem=0,
        )
        request = RequestFactory().post(
            reverse("roteiros:novo"),
            data=self._loop_diario_post_data(),
        )
        state = step3_logic._build_avulso_step3_state_from_post(request)
        validated = step3_logic._validate_step3_state(state)

        step3_logic._salvar_roteiro_avulso_from_step3_state(roteiro, state, validated)

        self.assertEqual(roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_IDA).count(), 5)
        self.assertEqual(roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).count(), 1)
        retorno = roteiro.trechos.get(tipo=RoteiroTrecho.TIPO_RETORNO)
        self.assertEqual(retorno.origem_cidade_id, self.cidade_dest.pk)
        self.assertEqual(retorno.destino_cidade_id, self.cidade_sede.pk)
        self.assertFalse(
            roteiro.trechos.filter(
                tipo=RoteiroTrecho.TIPO_IDA,
                origem_cidade=self.cidade_dest,
                destino_cidade=self.cidade_sede,
                saida_dt=retorno.saida_dt,
                chegada_dt=retorno.chegada_dt,
            ).exists()
        )

    def test_reabrir_bate_volta_diario_mantem_retorno_separado(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro,
            estado=self.estado_destino,
            cidade=self.cidade_dest,
            ordem=0,
        )
        request = RequestFactory().post(
            reverse("roteiros:novo"),
            data=self._loop_diario_post_data(),
        )
        state = step3_logic._build_avulso_step3_state_from_post(request)
        validated = step3_logic._validate_step3_state(state)
        step3_logic._salvar_roteiro_avulso_from_step3_state(roteiro, state, validated)

        reopened = step3_logic._build_step3_state_from_roteiro_evento(roteiro)

        self.assertEqual(len(reopened["trechos"]), 5)
        self.assertTrue(reopened["bate_volta_diario"]["ativo"])
        self.assertEqual(reopened["bate_volta_diario"]["data_inicio"], "2026-05-05")
        self.assertEqual(reopened["bate_volta_diario"]["data_fim"], "2026-05-07")
        self.assertEqual(reopened["retorno"]["saida_data"], "2026-05-07")
        self.assertEqual(reopened["retorno"]["saida_hora"], "18:00")

    def test_calculo_diarias_ignora_retorno_final_duplicado_no_loop_diario(self):
        base_state = self._loop_diario_state_com_retorno_duplicado()
        deduped_state = step3_logic._dedupe_step3_loop_retorno_final(dict(base_state))

        markers_com_duplicado, _, chegada_com_duplicado, _, _ = step3_logic._collect_step3_markers_payload(base_state)
        markers_sem_duplicado, _, chegada_sem_duplicado, _, _ = step3_logic._collect_step3_markers_payload(deduped_state)

        self.assertEqual(len(markers_com_duplicado), len(markers_sem_duplicado))
        self.assertEqual(len(markers_com_duplicado), 5)
        self.assertEqual(chegada_com_duplicado, chegada_sem_duplicado)

    def _loop_diario_post_data(self):
        state = self._loop_diario_state_com_retorno_duplicado()
        data = {
            "roteiro_modo": step3_logic.ROTEIRO_MODO_PROPRIO,
            "origem_estado": str(self.estado.pk),
            "origem_cidade": str(self.cidade_sede.pk),
            "destino_estado_0": str(self.estado_destino.pk),
            "destino_cidade_0": str(self.cidade_dest.pk),
            "bate_volta_diario_ativo": "on",
            "bate_volta_data_inicio": "2026-05-05",
            "bate_volta_data_fim": "2026-05-07",
            "bate_volta_ida_saida_hora": "08:00",
            "bate_volta_ida_tempo_min": "45",
            "bate_volta_volta_saida_hora": "18:00",
            "bate_volta_volta_tempo_min": "45",
            "retorno_saida_data": "2026-05-07",
            "retorno_saida_hora": "18:00",
            "retorno_chegada_data": "2026-05-07",
            "retorno_chegada_hora": "18:45",
            "retorno_tempo_cru_estimado_min": "45",
            "retorno_tempo_adicional_min": "0",
            "retorno_duracao_estimada_min": "45",
        }
        for idx, trecho in enumerate(state["trechos"]):
            for key, value in trecho.items():
                data[f"trecho_{idx}_{key}"] = str(value)
        return data

    def _loop_diario_state_com_retorno_duplicado(self):
        trechos = []
        dias = ["2026-05-05", "2026-05-06", "2026-05-07"]
        for dia in dias:
            trechos.append(
                {
                    "origem_nome": "CURITIBA",
                    "destino_nome": "FLORIANOPOLIS",
                    "origem_estado_id": self.estado.pk,
                    "origem_cidade_id": self.cidade_sede.pk,
                    "destino_estado_id": self.estado_destino.pk,
                    "destino_cidade_id": self.cidade_dest.pk,
                    "saida_data": dia,
                    "saida_hora": "08:00",
                    "chegada_data": dia,
                    "chegada_hora": "08:45",
                    "tempo_cru_estimado_min": "45",
                    "tempo_adicional_min": "0",
                    "duracao_estimada_min": "45",
                }
            )
            trechos.append(
                {
                    "origem_nome": "FLORIANOPOLIS",
                    "destino_nome": "CURITIBA",
                    "origem_estado_id": self.estado_destino.pk,
                    "origem_cidade_id": self.cidade_dest.pk,
                    "destino_estado_id": self.estado.pk,
                    "destino_cidade_id": self.cidade_sede.pk,
                    "saida_data": dia,
                    "saida_hora": "18:00",
                    "chegada_data": dia,
                    "chegada_hora": "18:45",
                    "tempo_cru_estimado_min": "45",
                    "tempo_adicional_min": "0",
                    "duracao_estimada_min": "45",
                }
            )
        return {
            "roteiro_modo": step3_logic.ROTEIRO_MODO_PROPRIO,
            "sede_estado_id": self.estado.pk,
            "sede_cidade_id": self.cidade_sede.pk,
            "destinos_atuais": [
                {"estado_id": self.estado_destino.pk, "cidade_id": self.cidade_dest.pk},
            ],
            "bate_volta_diario": {
                "ativo": True,
                "data_inicio": "2026-05-05",
                "data_fim": "2026-05-07",
                "ida_saida_hora": "08:00",
                "ida_tempo_min": "45",
                "volta_saida_hora": "18:00",
                "volta_tempo_min": "45",
            },
            "trechos": trechos,
            "retorno": {
                "saida_cidade": "FLORIANOPOLIS",
                "chegada_cidade": "CURITIBA",
                "saida_data": "2026-05-07",
                "saida_hora": "18:00",
                "chegada_data": "2026-05-07",
                "chegada_hora": "18:45",
                "tempo_cru_estimado_min": "45",
                "tempo_adicional_min": "0",
                "duracao_estimada_min": "45",
            },
        }


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class RoteirosApiAuthTests(TestCase):
    def test_endpoint_ajax_sem_login_retorna_json_401(self):
        client = Client()
        response = client.post(
            reverse("roteiros:trechos_estimar"),
            data=json.dumps({"origem_cidade_id": 1, "destino_cidade_id": 2}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = response.json()
        self.assertEqual(payload["ok"], False)
        self.assertIn("Sessao expirada", payload["error"])
