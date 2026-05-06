# -*- coding: utf-8 -*-
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from cadastros.models import Cidade, Estado
from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho
from roteiros.services.routing.openrouteservice import (
    OpenRouteServiceProvider,
    _extract_ors_error_message,
)
from roteiros.services.routing.route_point_builder import build_route_points_for_roteiro
from roteiros.services.routing.route_service import calcular_rota_para_roteiro
from roteiros.services.routing.route_signature import build_route_signature
from roteiros.services.routing.route_preview_service import (
    calculate_route_preview,
)
from roteiros.services.routing.route_exceptions import (
    RouteAuthenticationError,
    RouteProviderUnavailable,
    RouteValidationError,
)
from roteiros.services.routing.route_time_rules import (
    calculate_additional_time_minutes,
    round_trip_minutes_to_15,
)
from roteiros.services.routing.route_stale import mark_stale_when_signature_changed


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost"],
    OPENROUTESERVICE_API_KEY="test-key",
    ROUTE_PROVIDER="openrouteservice",
    ROUTE_CACHE_ENABLED=True,
    ROUTE_REQUEST_TIMEOUT_SECONDS=5,
)
class RoteirosRoutingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="routing_tester", password="teste")
        self.client = Client()
        self.client.force_login(self.user)
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.estado2, _ = Estado.objects.get_or_create(sigla="SC", defaults={"nome": "SANTA CATARINA"})
        self.cidade_sede, _ = Cidade.objects.get_or_create(
            nome="CURITIBA_ROUTING",
            estado=self.estado,
            defaults={"uf": "PR", "latitude": Decimal("-25.4284"), "longitude": Decimal("-49.2733")},
        )
        self.cidade_sede.latitude = Decimal("-25.4284")
        self.cidade_sede.longitude = Decimal("-49.2733")
        self.cidade_sede.save()
        self.cidade_a, _ = Cidade.objects.get_or_create(
            nome="LONDRINA_ROUTING",
            estado=self.estado,
            defaults={"uf": "PR", "latitude": Decimal("-23.3103"), "longitude": Decimal("-51.1628")},
        )
        self.cidade_a.latitude = Decimal("-23.3103")
        self.cidade_a.longitude = Decimal("-51.1628")
        self.cidade_a.save()
        self.cidade_b, _ = Cidade.objects.get_or_create(
            nome="FLORIPA_ROUTING",
            estado=self.estado2,
            defaults={"uf": "SC", "latitude": Decimal("-27.5954"), "longitude": Decimal("-48.5480")},
        )
        self.cidade_b.latitude = Decimal("-27.5954")
        self.cidade_b.longitude = Decimal("-48.5480")
        self.cidade_b.save()

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

    def test_openrouteservice_usa_endpoint_geojson(self):
        provider = OpenRouteServiceProvider("k", timeout_seconds=5)
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-49.0, -25.0], [-48.0, -24.0]],
                    },
                    "properties": {
                        "summary": {"distance": 100000, "duration": 7200},
                        "segments": [{"distance": 100000, "duration": 7200}],
                    },
                }
            ],
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            out = provider.calculate_route(
                [
                    {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                    {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                ],
                profile="driving-car",
            )
        called = post.call_args
        self.assertIn("/geojson", called[0][0])
        body = called[1]["json"]
        self.assertEqual(body["coordinates"][0], [-49.0, -25.0])
        self.assertEqual(out["distance_km"], 100.0)
        self.assertEqual(out["duration_minutes"], 120)
        self.assertEqual(out["geometry"]["type"], "LineString")
        self.assertNotIn("EncodedPolyline", json.dumps(out["geometry"]))

    def test_openrouteservice_resposta_json_legada_ainda_funciona(self):
        provider = OpenRouteServiceProvider("k", timeout_seconds=5)
        mock_resp = {
            "routes": [
                {
                    "summary": {"distance": 100000, "duration": 7200},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-49.0, -25.0], [-48.0, -24.0]],
                    },
                    "segments": [
                        {"distance": 100000, "duration": 7200, "geometry": None},
                    ],
                }
            ]
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_resp
            out = provider.calculate_route(
                [
                    {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                    {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                ],
                profile="driving-car",
            )
        self.assertEqual(out["geometry"]["type"], "LineString")

    def test_openrouteservice_polyline_encoded_nao_vai_no_geometry(self):
        provider = OpenRouteServiceProvider("k", timeout_seconds=5)
        mock_resp = {
            "routes": [
                {
                    "summary": {"distance": 1000, "duration": 120},
                    "geometry": "encoded_polyline_placeholder",
                }
            ]
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_resp
            out = provider.calculate_route(
                [
                    {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                    {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                ],
                profile="driving-car",
            )
        self.assertIsNone(out.get("geometry"))
        self.assertIn("geometry_warning", out)
        blob = json.dumps(out)
        self.assertNotIn("EncodedPolyline", blob)

    def test_openrouteservice_authorization_sem_bearer_e_accept_geojson(self):
        provider = OpenRouteServiceProvider("minha-chave-crua", timeout_seconds=5)
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-49.0, -25.0], [-48.0, -24.0]],
                    },
                    "properties": {
                        "summary": {"distance": 1000, "duration": 60},
                        "segments": [],
                    },
                }
            ],
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.content = b"{}"
            post.return_value.json.return_value = mock_fc
            provider.calculate_route(
                [
                    {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                    {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                ],
                profile="driving-car",
            )
        kwargs = post.call_args[1]
        headers = kwargs["headers"]
        self.assertEqual(headers["Authorization"], "minha-chave-crua")
        self.assertFalse(headers["Authorization"].lower().startswith("bearer "))
        accept = headers.get("Accept", "")
        self.assertIn("application/geo+json", accept)
        self.assertIn("application/json", accept)
        self.assertIn("charset=utf-8", headers.get("Content-Type", "").lower())

    def test_openrouteservice_http401_error_string_nao_quebra(self):
        provider = OpenRouteServiceProvider("k", timeout_seconds=5)
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 401
            post.return_value.content = b"{}"
            post.return_value.json.return_value = {"error": "Access token could not be verified"}
            with self.assertRaises(RouteAuthenticationError):
                provider.calculate_route(
                    [
                        {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                        {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                    ],
                    profile="driving-car",
                )

    def test_openrouteservice_http403_error_dict_nao_quebra(self):
        provider = OpenRouteServiceProvider("k", timeout_seconds=5)
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 403
            post.return_value.content = b"{}"
            post.return_value.json.return_value = {"error": {"message": "Forbidden"}}
            with self.assertRaises(RouteAuthenticationError):
                provider.calculate_route(
                    [
                        {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                        {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                    ],
                    profile="driving-car",
                )

    def test_extract_ors_error_message_varios_formatos(self):
        self.assertEqual(
            _extract_ors_error_message({"error": "Access token could not be verified"}),
            "Access token could not be verified",
        )
        self.assertEqual(
            _extract_ors_error_message({"error": {"message": "Forbidden"}}),
            "Forbidden",
        )
        self.assertEqual(_extract_ors_error_message({"error": [{"x": 1}]}), "[{'x': 1}]")

    def test_openrouteservice_http400_corpo_inesperado_sem_attributeerror(self):
        provider = OpenRouteServiceProvider("k", timeout_seconds=5)
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 400
            post.return_value.content = b"{}"
            post.return_value.json.return_value = {"error": [{"unexpected": True}]}
            with self.assertRaises(RouteProviderUnavailable):
                provider.calculate_route(
                    [
                        {"id": "a", "lat": -25.0, "lng": -49.0, "label": "A"},
                        {"id": "b", "lat": -24.0, "lng": -48.0, "label": "B"},
                    ],
                    profile="driving-car",
                )

    def test_calcular_rota_endpoint_401_retorna_mensagem_amigavel_sem_chave(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        url = reverse("roteiros:calcular_rota")
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 401
            post.return_value.content = b"{}"
            post.return_value.json.return_value = {"error": "Access token could not be verified"}
            resp = self._csrf_post_json(url, {"roteiro_id": roteiro.pk})
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertIn("OPENROUTESERVICE_API_KEY", body["message"])
        self.assertIn("inválida", body["message"].lower())
        blob = json.dumps(body)
        self.assertNotIn("test-key", blob)

    def test_calcular_rota_endpoint_recusa_get(self):
        url = reverse("roteiros:calcular_rota")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 405)

    def test_calcular_rota_endpoint_sem_chave_retorna_mensagem_amigavel(self):
        with override_settings(OPENROUTESERVICE_API_KEY=""):
            url = reverse("roteiros:calcular_rota")
            roteiro = Roteiro.objects.create(
                tipo=Roteiro.TIPO_AVULSO,
                origem_estado=self.estado,
                origem_cidade=self.cidade_sede,
            )
            RoteiroDestino.objects.create(
                roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
            )
            resp = self._csrf_post_json(url, {"roteiro_id": roteiro.pk})
            self.assertEqual(resp.status_code, 503)
            body = resp.json()
            self.assertFalse(body["ok"])
            self.assertIn("OPENROUTESERVICE_API_KEY", body["message"])

    def test_calcular_rota_endpoint_rejeita_api_key_no_payload(self):
        url = reverse("roteiros:calcular_rota")
        resp = self._csrf_post_json(url, {"roteiro_id": 1, "api_key": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_pontos_rota_simples_com_retorno(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        points, bate = build_route_points_for_roteiro(roteiro)
        self.assertFalse(bate)
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0]["cidade_id"], self.cidade_sede.pk)
        self.assertEqual(points[-1]["cidade_id"], self.cidade_sede.pk)

    def test_cache_por_assinatura_sem_chamar_api(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            rota_status=Roteiro.ROTA_STATUS_CALCULADA,
            rota_geojson={"type": "LineString", "coordinates": []},
            rota_distancia_calculada_km=Decimal("10.00"),
            rota_duracao_calculada_min=15,
            rota_fonte=Roteiro.ROTA_FONTE_OPENROUTESERVICE,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        points, bate = build_route_points_for_roteiro(roteiro)
        sig = build_route_signature(
            [{"id": p["id"], "lat": p["lat"], "lng": p["lng"], "label": p["label"]} for p in points],
            profile="driving-car",
            bate_volta_diario=bate,
        )
        roteiro.rota_assinatura = sig
        roteiro.save(update_fields=["rota_assinatura"])

        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            out = calcular_rota_para_roteiro(roteiro, force_recalculate=False)
            post.assert_not_called()
        self.assertTrue(out["ok"])
        self.assertTrue(out["route"]["from_cache"])

    def test_reordenar_destinos_marca_rota_desatualizada(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            rota_status=Roteiro.ROTA_STATUS_CALCULADA,
            rota_geojson={"type": "LineString", "coordinates": []},
            rota_assinatura="",
        )
        d0 = RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        d1 = RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado2, cidade=self.cidade_b, ordem=1
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado2,
            destino_cidade=self.cidade_b,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=2,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado2,
            origem_cidade=self.cidade_b,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        points, bate = build_route_points_for_roteiro(roteiro)
        sig = build_route_signature(
            [{"id": p["id"], "lat": p["lat"], "lng": p["lng"], "label": p["label"]} for p in points],
            profile="driving-car",
            bate_volta_diario=bate,
        )
        roteiro.rota_assinatura = sig
        roteiro.save(update_fields=["rota_assinatura"])

        d0.ordem, d1.ordem = 1, 0
        d0.save(update_fields=["ordem"])
        d1.save(update_fields=["ordem"])

        mark_stale_when_signature_changed(roteiro)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.rota_status, Roteiro.ROTA_STATUS_DESATUALIZADA)

    def test_municipio_sem_coordenada_erro_amigavel(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        sem_coord = Cidade.objects.create(nome="SEM_COORD", estado=self.estado, uf="PR")
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=sem_coord, ordem=0
        )
        url = reverse("roteiros:calcular_rota")
        resp = self._csrf_post_json(url, {"roteiro_id": roteiro.pk})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("latitude", resp.json()["message"].lower())

    def test_falha_provedor_nao_apaga_rota_calculada_anterior(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            rota_status=Roteiro.ROTA_STATUS_CALCULADA,
            rota_geojson={"type": "LineString", "coordinates": [[-49, -25], [-48, -24]]},
            rota_distancia_calculada_km=Decimal("50.00"),
            rota_duracao_calculada_min=60,
            rota_fonte=Roteiro.ROTA_FONTE_OPENROUTESERVICE,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        points, bate = build_route_points_for_roteiro(roteiro)
        sig = build_route_signature(
            [{"id": p["id"], "lat": p["lat"], "lng": p["lng"], "label": p["label"]} for p in points],
            profile="driving-car",
            bate_volta_diario=bate,
        )
        roteiro.rota_assinatura = sig
        roteiro.save(update_fields=["rota_assinatura"])

        with patch("roteiros.services.routing.route_service.get_openrouteservice_provider") as gp:
            mock_p = MagicMock()
            mock_p.calculate_route.side_effect = RouteProviderUnavailable()
            gp.return_value = mock_p
            with self.assertRaises(RouteProviderUnavailable):
                calcular_rota_para_roteiro(roteiro, force_recalculate=True)
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.rota_status, Roteiro.ROTA_STATUS_CALCULADA)
        self.assertIsNotNone(roteiro.rota_geojson)

    def test_calcular_rota_endpoint_sem_roteiro_id(self):
        url = reverse("roteiros:calcular_rota")
        resp = self._csrf_post_json(url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Salve o roteiro", resp.json()["message"])

    def test_calcular_rota_endpoint_retorna_linestring_quando_api_ok(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-49.0, -25.0], [-48.0, -24.0]],
                    },
                    "properties": {
                        "summary": {"distance": 50000, "duration": 3600},
                        "segments": [],
                    },
                }
            ],
        }
        url = reverse("roteiros:calcular_rota")
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            resp = self._csrf_post_json(url, {"roteiro_id": roteiro.pk})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["route"]["geometry"]["type"], "LineString")
        roteiro.refresh_from_db()
        self.assertIsNotNone(roteiro.rota_geojson)
        self.assertEqual(roteiro.rota_geojson.get("type"), "LineString")

    def test_calcular_rota_geometria_invalida_nao_quebra_json(self):
        roteiro = Roteiro.objects.create(
            tipo=Roteiro.TIPO_AVULSO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
        )
        RoteiroDestino.objects.create(
            roteiro=roteiro, estado=self.estado, cidade=self.cidade_a, ordem=0
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_sede,
            destino_estado=self.estado,
            destino_cidade=self.cidade_a,
        )
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=1,
            tipo=RoteiroTrecho.TIPO_RETORNO,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_sede,
        )
        mock_bad = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-49.0, -25.0]},
                    "properties": {
                        "summary": {"distance": 1000, "duration": 60},
                    },
                }
            ],
        }
        url = reverse("roteiros:calcular_rota")
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_bad
            resp = self._csrf_post_json(url, {"roteiro_id": roteiro.pk})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertIn("geometry_warning", body["route"])
        roteiro.refresh_from_db()
        self.assertIsNone(roteiro.rota_geojson)

    def test_novo_roteiro_html_oculta_controles_iniciais_do_mapa(self):
        response = self.client.get(reverse("roteiros:novo"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertRegex(html, r'id="btn-recalcular-rota-mapa"[^>]*hidden')
        self.assertRegex(html, r'id="roteiro-mapa-loading"[^>]*hidden')
        self.assertRegex(html, r'id="roteiro-mapa-stale-hint"[^>]*hidden')
        self.assertNotIn("Selecione a sede e os destinos para calcular a rota.", html)

    def test_round_trip_minutes_to_15_arredonda_para_cima(self):
        cases = [
            (1, 15),
            (14, 15),
            (15, 15),
            (16, 30),
            (29, 30),
            (30, 30),
            (44, 45),
            (45, 45),
            (46, 60),
            (61, 75),
            (98, 105),
        ]
        for raw, expected in cases:
            self.assertEqual(round_trip_minutes_to_15(raw), expected)

    def test_calculate_additional_time_minutes_tabela_operacional(self):
        cases = [
            (20, 0),
            (30, 15),
            (45, 15),
            (60, 15),
            (75, 30),
            (180, 30),
            (181, 45),
            (270, 45),
            (271, 60),
        ]
        for travel, expected in cases:
            self.assertEqual(calculate_additional_time_minutes(travel), expected)

    def test_preview_sem_salvar_retorna_line_string_e_legs(self):
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-49.27, -25.42], [-51.16, -23.31]],
                    },
                    "properties": {
                        "summary": {"distance": 423500, "duration": 18240},
                        "segments": [{"distance": 423500, "duration": 18240}],
                    },
                }
            ],
        }
        payload = {
            "origem_cidade_id": self.cidade_sede.pk,
            "destinos": [{"uuid": "tmp-1", "cidade_id": self.cidade_a.pk}],
            "retorno_cidade_id": self.cidade_sede.pk,
            "incluir_retorno": False,
            "modo": "normal",
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            out = calculate_route_preview(payload)
        self.assertTrue(out["ok"])
        self.assertEqual(out["route"]["geometry"]["type"], "LineString")
        self.assertEqual(len(out["legs"]), 1)
        leg = out["legs"][0]
        self.assertEqual(leg["from_cidade_id"], self.cidade_sede.pk)
        self.assertEqual(leg["to_cidade_id"], self.cidade_a.pk)
        self.assertEqual(leg["distance_km"], 423.5)
        self.assertEqual(leg["raw_duration_minutes"], 304)
        self.assertEqual(leg["travel_minutes"], 315)
        self.assertEqual(leg["travel_hhmm"], "05:15")
        self.assertEqual(leg["additional_minutes"], 60)
        self.assertEqual(leg["additional_hhmm"], "01:00")
        self.assertEqual(leg["total_minutes"], 375)
        self.assertEqual(leg["total_hhmm"], "06:15")
        self.assertEqual(leg["color_index"], 0)
        self.assertIn("points", out)
        self.assertGreaterEqual(len(out["points"]), 2)
        self.assertEqual(out["points"][0]["label"], f"{self.cidade_sede.nome}/{self.estado.sigla}")

    def test_preview_multiplos_destinos_e_retorno(self):
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[-49, -25], [-51, -23], [-48, -27], [-49, -25]]},
                    "properties": {
                        "summary": {"distance": 700000, "duration": 30000},
                        "segments": [
                            {"distance": 100000, "duration": 3600},
                            {"distance": 200000, "duration": 7200},
                            {"distance": 400000, "duration": 14400},
                        ],
                    },
                }
            ],
        }
        payload = {
            "origem_cidade_id": self.cidade_sede.pk,
            "destinos": [
                {"uuid": "tmp-1", "cidade_id": self.cidade_a.pk},
                {"uuid": "tmp-2", "cidade_id": self.cidade_b.pk},
            ],
            "retorno_cidade_id": self.cidade_sede.pk,
            "incluir_retorno": True,
            "modo": "normal",
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            out = calculate_route_preview(payload)
        self.assertEqual(len(out["legs"]), 3)
        self.assertEqual(out["legs"][0]["uuid"], "tmp-1")
        self.assertEqual(out["legs"][1]["uuid"], "tmp-2")
        self.assertEqual(out["legs"][2]["kind"], "retorno")
        self.assertEqual(out["legs"][0]["color_index"], 0)
        self.assertEqual(out["legs"][1]["color_index"], 1)
        self.assertEqual(out["legs"][2]["color_index"], 0)

    def test_preview_fallback_quando_segments_incompativeis(self):
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[-49, -25], [-51, -23], [-48, -27]]},
                    "properties": {
                        "summary": {"distance": 300000, "duration": 10000},
                        "segments": [{"distance": 300000, "duration": 10000}],
                    },
                }
            ],
        }
        payload = {
            "origem_cidade_id": self.cidade_sede.pk,
            "destinos": [
                {"uuid": "tmp-1", "cidade_id": self.cidade_a.pk},
                {"uuid": "tmp-2", "cidade_id": self.cidade_b.pk},
            ],
            "incluir_retorno": False,
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post, patch(
            "roteiros.services.routing.route_preview_service.calcular_rota_trecho"
        ) as trecho_calc:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            trecho_calc.side_effect = [
                {"ok": True, "distancia_km": 100.0, "tempo_cru_estimado_min": 98, "rota_fonte": "openrouteservice"},
                {"ok": True, "distancia_km": 200.0, "tempo_cru_estimado_min": 121, "rota_fonte": "openrouteservice"},
            ]
            out = calculate_route_preview(payload)
        self.assertTrue(out["fallback_per_leg_used"])
        self.assertEqual(trecho_calc.call_count, 2)
        self.assertEqual(out["legs"][0]["travel_minutes"], 105)
        self.assertEqual(out["legs"][1]["travel_minutes"], 135)
        # Confirma que não houve "divisão por 2" no trecho: veio do cálculo por leg.
        self.assertEqual(out["legs"][0]["distance_km"], 100.0)
        self.assertEqual(out["legs"][1]["distance_km"], 200.0)

    def test_preview_endpoint_sem_sede_ou_destino_rejeita(self):
        url = reverse("roteiros:calcular_rota_preview")
        resp = self._csrf_post_json(url, {"origem_cidade_id": self.cidade_sede.pk, "destinos": []})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_preview_endpoint_nao_expoe_api_key(self):
        url = reverse("roteiros:calcular_rota_preview")
        mock_fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[-49, -25], [-51, -23]]},
                    "properties": {
                        "summary": {"distance": 100000, "duration": 3600},
                        "segments": [{"distance": 100000, "duration": 3600}],
                    },
                }
            ],
        }
        with patch("roteiros.services.routing.openrouteservice.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = mock_fc
            resp = self._csrf_post_json(
                url,
                {
                    "origem_cidade_id": self.cidade_sede.pk,
                    "destinos": [{"uuid": "tmp-1", "cidade_id": self.cidade_a.pk}],
                },
            )
        self.assertEqual(resp.status_code, 200)
        blob = json.dumps(resp.json())
        self.assertNotIn("test-key", blob)
