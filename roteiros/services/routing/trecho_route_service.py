# -*- coding: utf-8 -*-
"""Cálculo de rota para um único trecho operacional (origem → destino), sem rota consolidada."""
from __future__ import annotations

import logging
from typing import Any, Dict

from django.conf import settings

from cadastros.models import Cidade
from roteiros.models import Roteiro
from roteiros.services.estimativa_local import estimar_distancia_duracao, minutos_para_hhmm

from .openrouteservice import get_openrouteservice_provider
from .route_exceptions import RouteServiceError, RouteValidationError
from .route_time_rules import calculate_additional_time_minutes, round_trip_minutes_to_15

logger = logging.getLogger(__name__)

ROTA_FONTE_TRECHO_ORS = Roteiro.ROTA_FONTE_OPENROUTESERVICE
ROTA_FONTE_TRECHO_LOCAL = "estimativa_local"


def _label_cidade(cidade: Cidade) -> str:
    uf = cidade.estado.sigla if cidade.estado_id else ""
    return f"{cidade.nome}/{uf}"


def _duration_human(total_minutes: int) -> str:
    h, m = divmod(max(0, int(total_minutes)), 60)
    if h and m:
        return f"{h}h{m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def calcular_rota_trecho(origem_cidade_id: int, destino_cidade_id: int) -> Dict[str, Any]:
    """
    Calcula apenas o par origem → destino (dois pontos). Nunca usa rota sede→…→retorno consolidada.
    """
    try:
        oid = int(origem_cidade_id)
        did = int(destino_cidade_id)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "erro": "Identificadores de cidade inválidos.",
            "ors_fallback": False,
        }

    if oid == did:
        return {
            "ok": False,
            "erro": "Origem e destino devem ser cidades diferentes.",
            "ors_fallback": False,
        }

    origem = Cidade.objects.select_related("estado").filter(pk=oid).first()
    destino = Cidade.objects.select_related("estado").filter(pk=did).first()
    if not origem or not destino:
        return {
            "ok": False,
            "erro": "Cidade de origem ou destino não encontrada.",
            "ors_fallback": False,
        }

    if origem.latitude is None or origem.longitude is None:
        return {
            "ok": False,
            "erro": f"Cidade de origem sem coordenadas: {origem.nome}",
            "ors_fallback": False,
        }
    if destino.latitude is None or destino.longitude is None:
        return {
            "ok": False,
            "erro": f"Cidade de destino sem coordenadas: {destino.nome}",
            "ors_fallback": False,
        }

    origem_lat = float(origem.latitude)
    origem_lon = float(origem.longitude)
    destino_lat = float(destino.latitude)
    destino_lon = float(destino.longitude)

    provider = get_openrouteservice_provider()
    route_provider = (getattr(settings, "ROUTE_PROVIDER", "openrouteservice") or "").strip().lower()
    ors_attempted = bool(provider and route_provider == "openrouteservice")

    if ors_attempted:
        try:
            points = [
                {
                    "id": "trecho-origem",
                    "lat": origem_lat,
                    "lng": origem_lon,
                    "label": _label_cidade(origem),
                },
                {
                    "id": "trecho-destino",
                    "lat": destino_lat,
                    "lng": destino_lon,
                    "label": _label_cidade(destino),
                },
            ]
            normalized = provider.calculate_route(points, profile="driving-car")
            cru = int(normalized["duration_minutes"])
            travel_min = round_trip_minutes_to_15(cru)
            additional_min = calculate_additional_time_minutes(travel_min)
            total_min = travel_min + additional_min
            dist = float(normalized["distance_km"])
            hh = minutos_para_hhmm(travel_min)
            return {
                "ok": True,
                "erro": "",
                "origem": _label_cidade(origem),
                "destino": _label_cidade(destino),
                "distancia_km": dist,
                "distancia_linha_reta_km": None,
                "distancia_rodoviaria_km": dist,
                "duracao_estimada_min": total_min,
                "duracao_estimada_hhmm": hh,
                "tempo_viagem_estimado_min": travel_min,
                "tempo_viagem_estimado_hhmm": hh,
                "tempo_cru_estimado_min": travel_min,
                "buffer_operacional_sugerido_min": 0,
                "tempo_adicional_sugerido_min": additional_min,
                "correcao_final_min": 0,
                "velocidade_media_kmh": None,
                "perfil_rota": None,
                "corredor": None,
                "corredor_macro": None,
                "corredor_fino": None,
                "rota_fonte": ROTA_FONTE_TRECHO_ORS,
                "fallback_usado": False,
                "confianca_estimativa": None,
                "refs_predominantes": [],
                "pedagio_presente": False,
                "travessia_urbana_presente": False,
                "serra_presente": False,
                "ors_fallback": False,
                "duration_human": normalized.get("duration_human") or _duration_human(travel_min),
                "raw_duration_minutes": cru,
            }
        except RouteValidationError:
            logger.info("OpenRouteService trecho: validação — usando estimativa local.")
        except RouteServiceError as exc:
            logger.warning(
                "OpenRouteService trecho indisponível (%s); usando estimativa local.",
                exc.__class__.__name__,
            )
        except Exception as exc:
            logger.warning("OpenRouteService trecho falhou: %s; usando estimativa local.", exc)

    out = estimar_distancia_duracao(
        origem_lat=origem_lat,
        origem_lon=origem_lon,
        destino_lat=destino_lat,
        destino_lon=destino_lon,
    )
    merged: Dict[str, Any] = dict(out)
    raw_min = int(merged.get("tempo_viagem_estimado_min") or merged.get("tempo_cru_estimado_min") or 0)
    travel_min = round_trip_minutes_to_15(raw_min)
    additional_min = calculate_additional_time_minutes(travel_min)
    total_min = travel_min + additional_min
    merged["ok"] = bool(out.get("ok"))
    merged["origem"] = _label_cidade(origem)
    merged["destino"] = _label_cidade(destino)
    merged["rota_fonte"] = ROTA_FONTE_TRECHO_LOCAL
    merged["ors_fallback"] = ors_attempted
    merged["raw_duration_minutes"] = raw_min
    merged["tempo_cru_estimado_min"] = travel_min
    merged["tempo_viagem_estimado_min"] = travel_min
    merged["tempo_viagem_estimado_hhmm"] = minutos_para_hhmm(travel_min)
    merged["tempo_adicional_sugerido_min"] = additional_min
    merged["duracao_estimada_min"] = total_min
    merged["duracao_estimada_hhmm"] = minutos_para_hhmm(total_min)
    if merged.get("distancia_km") is not None:
        try:
            merged["distancia_km"] = float(merged["distancia_km"])
        except (TypeError, ValueError):
            pass
    if not merged["ok"]:
        merged["erro"] = out.get("erro") or "Não foi possível estimar o trecho."
    return merged
