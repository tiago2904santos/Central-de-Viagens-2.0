# -*- coding: utf-8 -*-
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from cadastros.models import Cidade, Estado
from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho
from roteiros.services.routing.trecho_route_service import ROTA_FONTE_TRECHO_ORS, calcular_rota_trecho
from roteiros.services.routing.route_service import calcular_rota_para_roteiro


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost"],
    OPENROUTESERVICE_API_KEY="test-key",
    ROUTE_PROVIDER="openrouteservice",
    ROUTE_CACHE_ENABLED=True,
    ROUTE_REQUEST_TIMEOUT_SECONDS=5,
)
class TrechoRouteServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="trecho_route", password="x")
        self.client = Client()
        self.client.force_login(self.user)
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PR"})
        self.c_sede, _ = Cidade.objects.get_or_create(
            nome="TRECHO_SEDE",
            estado=self.estado,
            defaults={"uf": "PR", "latitude": Decimal("-25.4284"), "longitude": Decimal("-49.2733")},
        )
        self.c_sede.latitude = Decimal("-25.4284")
        self.c_sede.longitude = Decimal("-49.2733")
        self.c_sede.save()
        self.c_a, _ = Cidade.objects.get_or_create(
            nome="TRECHO_A",
            estado=self.estado,
            defaults={"uf": "PR", "latitude": Decimal("-23.3103"), "longitude": Decimal("-51.1628")},
        )
        self.c_a.latitude = Decimal("-23.3103")
        self.c_a.longitude = Decimal("-51.1628")
        self.c_a.save()
        self.c_b, _ = Cidade.objects.get_or_create(
            nome="TRECHO_B",
            estado=self.estado,
            defaults={"uf": "PR", "latitude": Decimal("-24.0"), "longitude": Decimal("-50.0")},
        )
        self.c_b.latitude = Decimal("-24.0")
        self.c_b.longitude = Decimal("-50.0")
        self.c_b.save()

    def _csrf_post_json(self, url, data):
        self.client.get(reverse("roteiros:index"))
        token = self.client.cookies.get("csrftoken")
        csrf = token.value if token else ""
        return self.client.post(
            url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )

    def test_calcular_rota_trecho_ors_envia_apenas_dois_pontos(self):
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.content = b"{}"
            post.return_value.json.return_value = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[-49.0, -25.0], [-48.0, -24.0]],
                        },
                        "properties": {
                            "summary": {"distance": 100000, "duration": 6000},
                            "segments": [],
                        },
                    }
                ],
            }
            out = calcular_rota_trecho(self.c_sede.pk, self.c_a.pk)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("rota_fonte"), ROTA_FONTE_TRECHO_ORS)
        body = post.call_args[1]["json"]
        self.assertEqual(len(body["coordinates"]), 2)
        self.assertEqual(out.get("tempo_cru_estimado_min"), 100)

    def test_calcular_rota_consolidada_nao_atualiza_distancia_trecho_ida(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.c_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.c_a, ordem=0
        )
        t_ida = RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.c_sede,
            destino_estado=self.estado,
            destino_cidade=self.c_a,
            distancia_km=Decimal("50.00"),
            tempo_cru_estimado_min=60,
            duracao_estimada_min=60,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.c_a,
            destino_estado=self.estado,
            destino_cidade=self.c_sede,
            distancia_km=Decimal("50.00"),
            tempo_cru_estimado_min=60,
            duracao_estimada_min=60,
        )
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-49.0, -25.0], [-48.0, -24.0], [-49.0, -25.0]],
                    },
                    "properties": {
                        "summary": {"distance": 200000, "duration": 14400},
                        "segments": [
                            {"distance": 100000, "duration": 7200},
                            {"distance": 100000, "duration": 7200},
                        ],
                    },
                }
            ],
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            calcular_rota_para_roteiro(roteiro, force_recalculate=True)
        t_ida.refresh_from_db()
        self.assertEqual(float(t_ida.distancia_km), 50.0)
        self.assertEqual(t_ida.tempo_cru_estimado_min, 60)

    def test_trechos_estimar_endpoint_retorna_openrouteservice(self):
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": [[-49.0, -25.0], [-48.0, -24.0]]},
                        "properties": {
                            "summary": {"distance": 117410, "duration": 5880},
                            "segments": [],
                        },
                    }
                ],
            }
            resp = self._csrf_post_json(
                reverse("roteiros:trechos_estimar"),
                {"origem_cidade_id": self.c_sede.pk, "destino_cidade_id": self.c_a.pk},
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["rota_fonte"], "openrouteservice")
        self.assertAlmostEqual(data["distancia_km"], 117.41, places=1)

    @override_settings(OPENROUTESERVICE_API_KEY="")
    def test_trechos_estimar_fallback_estimativa_local(self):
        resp = self._csrf_post_json(
            reverse("roteiros:trechos_estimar"),
            {"origem_cidade_id": self.c_sede.pk, "destino_cidade_id": self.c_a.pk},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["rota_fonte"], "estimativa_local")
