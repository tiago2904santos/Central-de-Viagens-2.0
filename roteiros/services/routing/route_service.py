# -*- coding: utf-8 -*-
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from roteiros.models import Roteiro

from .openrouteservice import get_openrouteservice_provider
from .route_exceptions import RouteConfigurationError, RouteDailyRoundTripBlockedError
from .route_point_builder import build_route_points_for_roteiro
from .route_signature import build_route_signature


def _duration_human(total_minutes: int) -> str:
    h, m = divmod(max(0, int(total_minutes)), 60)
    if h and m:
        return f"{h}h{m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def _format_calculada_em(dt) -> str:
    if not dt:
        return ""
    local = timezone.localtime(dt)
    return local.strftime("%d/%m/%Y %H:%M")


def _points_for_provider(points: List[dict]) -> List[Dict[str, Any]]:
    out = []
    for p in points:
        out.append(
            {
                "id": p.get("id"),
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "label": p.get("label") or "",
            }
        )
    return out


def _infer_point_kind(point_id: str) -> str:
    pid = str(point_id or "")
    if pid.startswith("origem-"):
        return "origem"
    if pid.startswith("destino-"):
        return "destino"
    if pid.startswith("retorno-"):
        return "retorno"
    return ""


def _points_for_frontend(points: List[dict]) -> List[Dict[str, Any]]:
    out = []
    for p in points or []:
        out.append(
            {
                "id": p.get("id"),
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "label": p.get("label") or "",
                "kind": _infer_point_kind(p.get("id")),
            }
        )
    return out


def _effective_distance_km(roteiro: Roteiro) -> float | None:
    if roteiro.rota_distancia_manual_km is not None:
        return float(roteiro.rota_distancia_manual_km)
    if roteiro.rota_distancia_calculada_km is not None:
        return float(roteiro.rota_distancia_calculada_km)
    return None


def _effective_duration_min(roteiro: Roteiro) -> int | None:
    if roteiro.rota_duracao_manual_min is not None:
        return int(roteiro.rota_duracao_manual_min)
    if roteiro.rota_duracao_calculada_min is not None:
        return int(roteiro.rota_duracao_calculada_min)
    return None


def _route_payload_from_roteiro(
    roteiro: Roteiro, *, from_cache: bool, status: str | None = None
) -> Dict[str, Any]:
    dist_auto = (
        float(roteiro.rota_distancia_calculada_km)
        if roteiro.rota_distancia_calculada_km is not None
        else None
    )
    dur_auto = roteiro.rota_duracao_calculada_min
    dist_eff = _effective_distance_km(roteiro)
    dur_eff = _effective_duration_min(roteiro)
    return {
        "provider": roteiro.rota_fonte or "",
        "distance_km": dist_eff,
        "distance_km_auto": dist_auto,
        "duration_minutes": dur_eff,
        "duration_minutes_auto": dur_auto,
        "duration_human": _duration_human(dur_eff) if dur_eff is not None else "",
        "duration_human_auto": _duration_human(dur_auto) if dur_auto is not None else "",
        "geometry": roteiro.rota_geojson,
        "calculated_at": _format_calculada_em(roteiro.rota_calculada_em),
        "from_cache": from_cache,
        "status": status or roteiro.rota_status,
        "assinatura": roteiro.rota_assinatura,
        "distancia_manual_km": float(roteiro.rota_distancia_manual_km)
        if roteiro.rota_distancia_manual_km is not None
        else None,
        "duracao_manual_min": roteiro.rota_duracao_manual_min,
        "ajuste_justificativa": (roteiro.rota_ajuste_justificativa or "").strip(),
    }


@transaction.atomic
def calcular_rota_para_roteiro(
    roteiro: Roteiro, *, force_recalculate: bool = False
) -> Dict[str, Any]:
    """
    Calcula rota consolidada para mapa e campos agregados em `Roteiro`.
    Tempos/distâncias por trecho operacional vêm de `/trechos/estimar/` (par origem→destino), não deste fluxo.
    Respeita cache por assinatura quando `ROUTE_CACHE_ENABLED` e não há `force_recalculate`.
    """
    profile = "driving-car"
    points, bate = build_route_points_for_roteiro(roteiro)
    if bate:
        raise RouteDailyRoundTripBlockedError()

    provider = get_openrouteservice_provider()
    if provider is None:
        raise RouteConfigurationError()

    route_provider = (getattr(settings, "ROUTE_PROVIDER", "openrouteservice") or "").strip().lower()
    if route_provider != "openrouteservice":
        raise RouteConfigurationError("Provedor de rotas não suportado nesta versão.")

    signature = build_route_signature(
        _points_for_provider(points), profile=profile, bate_volta_diario=bate
    )
    cache_on = getattr(settings, "ROUTE_CACHE_ENABLED", True)

    if (
        cache_on
        and not force_recalculate
        and roteiro.rota_assinatura == signature
        and roteiro.rota_status == Roteiro.ROTA_STATUS_CALCULADA
        and roteiro.rota_geojson
    ):
        return {
            "ok": True,
            "route": _route_payload_from_roteiro(roteiro, from_cache=True),
            "points": _points_for_frontend(points),
        }

    payload_points = _points_for_provider(points)
    normalized = provider.calculate_route(payload_points, profile=profile)

    roteiro.rota_distancia_calculada_km = Decimal(str(normalized["distance_km"]))
    roteiro.rota_duracao_calculada_min = int(normalized["duration_minutes"])
    roteiro.rota_geojson = normalized.get("geometry")
    roteiro.rota_fonte = Roteiro.ROTA_FONTE_OPENROUTESERVICE
    roteiro.rota_status = Roteiro.ROTA_STATUS_CALCULADA
    roteiro.rota_assinatura = signature
    roteiro.rota_calculada_em = timezone.now()
    roteiro.save(
        update_fields=[
            "rota_distancia_calculada_km",
            "rota_duracao_calculada_min",
            "rota_geojson",
            "rota_fonte",
            "rota_status",
            "rota_assinatura",
            "rota_calculada_em",
            "updated_at",
        ]
    )

    roteiro.refresh_from_db()
    route_payload = _route_payload_from_roteiro(roteiro, from_cache=False)
    gw = normalized.get("geometry_warning")
    if gw:
        route_payload["geometry_warning"] = gw
    return {
        "ok": True,
        "route": route_payload,
        "points": _points_for_frontend(points),
    }


def serialize_existing_route(roteiro: Roteiro) -> Dict[str, Any] | None:
    """Usado no template para estado inicial do mapa (sem chamar API)."""
    if not roteiro.pk:
        return None
    has_route_data = (
        roteiro.rota_geojson
        or roteiro.rota_distancia_calculada_km is not None
        or roteiro.rota_duracao_calculada_min is not None
        or roteiro.rota_distancia_manual_km is not None
        or roteiro.rota_duracao_manual_min is not None
    )
    points = []
    try:
        built_points, _ = build_route_points_for_roteiro(roteiro)
        points = _points_for_frontend(built_points)
    except Exception:
        points = []
    return {
        "roteiro_id": roteiro.pk,
        "status": roteiro.rota_status,
        "route": _route_payload_from_roteiro(roteiro, from_cache=False) if has_route_data else None,
        "points": points,
    }
