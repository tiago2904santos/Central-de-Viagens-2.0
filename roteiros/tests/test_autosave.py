import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cidade, Estado
from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho


class RoteiroAutosaveTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="autosave_user", password="123")
        self.client.force_login(self.user)
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado2, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(nome="CURITIBA", estado=self.estado, defaults={"uf": "PR"})
        self.cidade_dest, _ = Cidade.objects.get_or_create(nome="FLORIANOPOLIS", estado=self.estado2, defaults={"uf": "SC"})

    def _payload(self, **kwargs):
        base = {
            "object_id": "",
            "form_id": "oficio-step3-form",
            "model": "roteiro",
            "dirty_fields": [],
            "fields": {},
            "snapshots": {},
        }
        base.update(kwargs)
        return base

    def test_autosave_edicao_atualiza_campo_simples(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, observacoes="ANTIGO")
        response = self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(
                self._payload(
                    object_id=str(roteiro.pk),
                    dirty_fields=["observacoes"],
                    fields={"observacoes": "novo texto"},
                )
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.observacoes, "NOVO TEXTO")

    def test_campo_ausente_nao_apaga(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, observacoes="MANTER")
        response = self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(self._payload(object_id=str(roteiro.pk))),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.observacoes, "MANTER")

    def test_dirty_com_vazio_limpa_campo(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, observacoes="LIMPAR")
        response = self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(
                self._payload(
                    object_id=str(roteiro.pk),
                    dirty_fields=["observacoes"],
                    fields={"observacoes": ""},
                )
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.observacoes, "")

    def test_cria_rascunho_com_conteudo_minimo(self):
        response = self.client.post(
            reverse("roteiros:roteiro-autosave-create"),
            data=json.dumps(
                self._payload(
                    dirty_fields=["origem_cidade"],
                    fields={"origem_cidade": str(self.cidade_sede.pk)},
                )
            ),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["created"])
        self.assertTrue(Roteiro.objects.filter(pk=payload["object_id"]).exists())

    def test_nao_cria_rascunho_vazio(self):
        response = self.client.post(
            reverse("roteiros:roteiro-autosave-create"),
            data=json.dumps(self._payload()),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Roteiro.objects.exists())

    def test_salva_geometry_sem_ors_e_nao_apaga_quando_ausente(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO)
        mapa_snapshot = {
            "mapa": {
                "geometry_json": json.dumps({"type": "LineString", "coordinates": [[-49.2, -25.4], [-48.5, -27.6]]}),
                "points_json": "[]",
                "distance_km": "100.10",
                "duration_minutes": "120",
                "provider": "openrouteservice",
                "calculated_at": "2026-05-06T13:40:00-03:00",
            }
        }
        response = self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(self._payload(object_id=str(roteiro.pk), snapshots=mapa_snapshot)),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        roteiro.refresh_from_db()
        self.assertIsNotNone(roteiro.rota_geojson)

        original = roteiro.rota_geojson
        response2 = self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(self._payload(object_id=str(roteiro.pk), dirty_fields=["observacoes"], fields={"observacoes": "x"})),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response2.status_code, 200)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.rota_geojson, original)

    def test_salva_trecho_sem_sobrescrever_nao_enviado(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO, origem_estado=self.estado, origem_cidade=self.cidade_sede)
        RoteiroDestino.objects.create(roteiro=roteiro, estado=self.estado2, cidade=self.cidade_dest, ordem=0)
        trecho1 = RoteiroTrecho.objects.create(
            roteiro=roteiro, ordem=0, tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado, origem_cidade=self.cidade_sede,
            destino_estado=self.estado2, destino_cidade=self.cidade_dest, tempo_adicional_min=0
        )
        trecho2 = RoteiroTrecho.objects.create(
            roteiro=roteiro, ordem=1, tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado2, origem_cidade=self.cidade_dest,
            destino_estado=self.estado, destino_cidade=self.cidade_sede, tempo_adicional_min=0
        )
        state = {
            "roteiro_state": {
                "roteiro_modo": "ROTEIRO_PROPRIO",
                "sede_estado_id": self.estado.pk,
                "sede_cidade_id": self.cidade_sede.pk,
                "destinos_atuais": [{"estado_id": self.estado2.pk, "cidade_id": self.cidade_dest.pk}],
                "trechos": [{
                    "id": trecho1.pk,
                    "ordem": 0,
                    "origem_estado_id": self.estado.pk,
                    "origem_cidade_id": self.cidade_sede.pk,
                    "destino_estado_id": self.estado2.pk,
                    "destino_cidade_id": self.cidade_dest.pk,
                    "origem_nome": "CURITIBA",
                    "destino_nome": "FLORIANOPOLIS",
                    "saida_data": "2026-05-10",
                    "saida_hora": "08:00",
                    "chegada_data": "2026-05-10",
                    "chegada_hora": "10:00",
                    "tempo_cru_estimado_min": 120,
                    "tempo_adicional_min": 10,
                    "duracao_estimada_min": 130
                }],
                "retorno": {
                    "saida_data": "2026-05-10",
                    "saida_hora": "18:00",
                    "chegada_data": "2026-05-10",
                    "chegada_hora": "20:00",
                },
                "bate_volta_diario": {"ativo": False}
            }
        }
        self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(self._payload(object_id=str(roteiro.pk), snapshots=state)),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        trecho1.refresh_from_db()
        trecho2.refresh_from_db()
        self.assertEqual(trecho1.tempo_adicional_min, 10)
        self.assertEqual(trecho2.tempo_adicional_min, 0)

    def test_retorna_json_padrao(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO)
        response = self.client.post(
            reverse("roteiros:roteiro-autosave", args=[roteiro.pk]),
            data=json.dumps(self._payload(object_id=str(roteiro.pk))),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertIn("saved_at", body)
        self.assertIn("saved_at_display", body)
