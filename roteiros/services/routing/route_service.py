# -*- coding: utf-8 -*-
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from roteiros.models import Roteiro, RoteiroTrecho

from .openrouteservice import get_openrouteservice_provider
from .route_exceptions import RouteConfigurationError
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
        "status": status or roteiro.rota_status,
    }


def _apply_segments_to_trechos(
    roteiro: Roteiro, segments: List[dict], *, bate_volta_diario: bool
) -> None:
    if bate_volta_diario or not segments:
        return
    ida = list(roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_IDA).order_by("ordem", "id"))
    retorno = (
        roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).order_by("ordem", "id").first()
    )
    ordered = ida + ([retorno] if retorno else [])
    now = timezone.now()
    for idx, seg in enumerate(segments):
        if idx >= len(ordered):
            break
        trecho = ordered[idx]
        if (trecho.rota_fonte or "").strip().lower() == "manual":
            continue
        cru = int(seg.get("duration_minutes") or 0)
        adic = trecho.tempo_adicional_min or 0
        if adic < 0:
            adic = 0
        dist = seg.get("distance_km")
        trecho.tempo_cru_estimado_min = cru
        trecho.duracao_estimada_min = cru + adic
        if dist is not None:
            trecho.distancia_km = Decimal(str(round(float(dist), 2)))
        trecho.rota_fonte = Roteiro.ROTA_FONTE_OPENROUTESERVICE
        trecho.rota_calculada_em = now
        trecho.save(
            update_fields=[
                "tempo_cru_estimado_min",
                "duracao_estimada_min",
                "distancia_km",
                "rota_fonte",
                "rota_calculada_em",
                "updated_at",
            ]
        )


@transaction.atomic
def calcular_rota_para_roteiro(
    roteiro: Roteiro, *, force_recalculate: bool = False
) -> Dict[str, Any]:
    """
    Calcula rota consolidada, persiste em `Roteiro` e opcionalmente reparte tempos nos trechos.
    Respeita cache por assinatura quando `ROUTE_CACHE_ENABLED` e não há `force_recalculate`.
    """
    profile = "driving-car"
    provider = get_openrouteservice_provider()
    if provider is None:
        raise RouteConfigurationError()

    route_provider = (getattr(settings, "ROUTE_PROVIDER", "openrouteservice") or "").strip().lower()
    if route_provider != "openrouteservice":
        raise RouteConfigurationError("Provedor de rotas não suportado nesta versão.")

    points, bate = build_route_points_for_roteiro(roteiro)
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

    _apply_segments_to_trechos(roteiro, normalized.get("segments") or [], bate_volta_diario=bate)

    roteiro.refresh_from_db()
    return {
        "ok": True,
        "route": _route_payload_from_roteiro(roteiro, from_cache=False),
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
    return {
        "roteiro_id": roteiro.pk,
        "status": roteiro.rota_status,
        "route": _route_payload_from_roteiro(roteiro, from_cache=False) if has_route_data else None,
    }
