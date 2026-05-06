# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from cadastros.models import Cidade

from .openrouteservice import get_openrouteservice_provider
from .route_exceptions import RouteServiceError, RouteValidationError
from .route_time_rules import calculate_additional_time_minutes, round_trip_minutes_to_15
from .trecho_route_service import calcular_rota_trecho


@dataclass
class PreviewPoint:
    idx: int
    kind: str
    key: str
    cidade_id: int
    label: str
    lat: float
    lng: float


def _duration_human(total_minutes: int) -> str:
    h, m = divmod(max(0, int(total_minutes)), 60)
    if h and m:
        return f"{h}h{m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def _hhmm(minutes: int) -> str:
    m = max(0, int(minutes or 0))
    h, mm = divmod(m, 60)
    return f"{h:02d}:{mm:02d}"


def _label_cidade(cidade: Cidade) -> str:
    uf = cidade.estado.sigla if cidade.estado_id else ""
    return f"{cidade.nome}/{uf}"


def build_preview_points(payload: Dict[str, Any]) -> List[PreviewPoint]:
    origem_id = payload.get("origem_cidade_id")
    destinos = payload.get("destinos") or []
    incluir_retorno = bool(payload.get("incluir_retorno"))
    retorno_id = payload.get("retorno_cidade_id")

    try:
        oid = int(origem_id)
    except (TypeError, ValueError):
        raise RouteValidationError("Informe cidade de origem.")

    if not isinstance(destinos, list) or not destinos:
        raise RouteValidationError("Informe ao menos um destino.")

    cidades_ids: List[int] = [oid]
    destinos_norm: List[dict] = []
    for idx, item in enumerate(destinos):
        if not isinstance(item, dict):
            raise RouteValidationError(f"Destino #{idx + 1} inválido.")
        try:
            cid = int(item.get("cidade_id"))
        except (TypeError, ValueError):
            raise RouteValidationError(f"Destino #{idx + 1} sem cidade válida.")
        uuid = str(item.get("uuid") or f"tmp-{idx + 1}")
        destinos_norm.append({"uuid": uuid, "cidade_id": cid})
        cidades_ids.append(cid)

    rid = None
    if incluir_retorno:
        try:
            rid = int(retorno_id)
            cidades_ids.append(rid)
        except (TypeError, ValueError):
            raise RouteValidationError("Retorno inválido.")

    cidades_map = {
        c.pk: c
        for c in Cidade.objects.select_related("estado").filter(pk__in=list(dict.fromkeys(cidades_ids)))
    }
    if oid not in cidades_map:
        raise RouteValidationError("Cidade de origem não encontrada.")
    for d in destinos_norm:
        if d["cidade_id"] not in cidades_map:
            raise RouteValidationError("Cidade de destino não encontrada.")
    if incluir_retorno and rid not in cidades_map:
        raise RouteValidationError("Cidade de retorno não encontrada.")

    points: List[PreviewPoint] = []
    origem = cidades_map[oid]
    if origem.latitude is None or origem.longitude is None:
        raise RouteValidationError(f"Cidade sem coordenadas: {origem.nome}")
    points.append(
        PreviewPoint(
            idx=0,
            kind="origem",
            key="origem",
            cidade_id=oid,
            label=_label_cidade(origem),
            lat=float(origem.latitude),
            lng=float(origem.longitude),
        )
    )
    for i, d in enumerate(destinos_norm, start=1):
        c = cidades_map[d["cidade_id"]]
        if c.latitude is None or c.longitude is None:
            raise RouteValidationError(f"Cidade sem coordenadas: {c.nome}")
        points.append(
            PreviewPoint(
                idx=i,
                kind="destino",
                key=d["uuid"],
                cidade_id=c.pk,
                label=_label_cidade(c),
                lat=float(c.latitude),
                lng=float(c.longitude),
            )
        )

    if incluir_retorno and rid is not None:
        r = cidades_map[rid]
        if r.latitude is None or r.longitude is None:
            raise RouteValidationError(f"Cidade sem coordenadas: {r.nome}")
        points.append(
            PreviewPoint(
                idx=len(points),
                kind="retorno",
                key="retorno",
                cidade_id=r.pk,
                label=_label_cidade(r),
                lat=float(r.latitude),
                lng=float(r.longitude),
            )
        )
    return points


def build_operational_legs(points: List[PreviewPoint]) -> List[dict]:
    legs: List[dict] = []
    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        legs.append(
            {
                "index": i,
                "kind": "retorno" if p1.kind == "retorno" else "trecho",
                "uuid": p1.key if p1.kind == "destino" else "retorno",
                "from_cidade_id": p0.cidade_id,
                "to_cidade_id": p1.cidade_id,
                "from_label": p0.label,
                "to_label": p1.label,
            }
        )
    return legs


def _build_leg_payload(base_leg: dict, distance_km: float, raw_minutes: int, provider: str) -> dict:
    travel_minutes = round_trip_minutes_to_15(raw_minutes)
    additional_minutes = calculate_additional_time_minutes(travel_minutes)
    total_minutes = travel_minutes + additional_minutes
    out = dict(base_leg)
    out.update(
        {
            "distance_km": round(float(distance_km), 2),
            "raw_duration_minutes": int(raw_minutes),
            "travel_minutes": travel_minutes,
            "travel_hhmm": _hhmm(travel_minutes),
            "additional_minutes": additional_minutes,
            "additional_hhmm": _hhmm(additional_minutes),
            "total_minutes": total_minutes,
            "total_hhmm": _hhmm(total_minutes),
            "provider": provider,
        }
    )
    return out


def calculate_route_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    points = build_preview_points(payload)
    legs_base = build_operational_legs(points)
    provider = get_openrouteservice_provider()
    if provider is None:
        raise RouteValidationError("API de rotas não configurada.")

    ors_points = [
        {"id": p.key, "lat": p.lat, "lng": p.lng, "label": p.label}
        for p in points
    ]
    normalized = provider.calculate_route(ors_points, profile="driving-car")
    segments = normalized.get("segments") or []

    route_raw_minutes = int(normalized.get("duration_minutes") or 0)
    route_rounded = round_trip_minutes_to_15(route_raw_minutes)
    route_payload = {
        "provider": normalized.get("provider") or "openrouteservice",
        "distance_km": normalized.get("distance_km"),
        "duration_minutes": route_rounded,
        "duration_human": _duration_human(route_rounded),
        "geometry": normalized.get("geometry"),
        "status": "calculada",
    }
    if normalized.get("geometry_warning"):
        route_payload["geometry_warning"] = normalized.get("geometry_warning")

    legs_payload: List[dict] = []
    fallback_used = False
    if len(segments) == len(legs_base):
        for idx, leg_base in enumerate(legs_base):
            seg = segments[idx] or {}
            legs_payload.append(
                _build_leg_payload(
                    leg_base,
                    float(seg.get("distance_km") or 0.0),
                    int(seg.get("duration_minutes") or 0),
                    str(normalized.get("provider") or "openrouteservice"),
                )
            )
    else:
        fallback_used = True
        for leg_base in legs_base:
            trecho = calcular_rota_trecho(leg_base["from_cidade_id"], leg_base["to_cidade_id"])
            if not trecho.get("ok"):
                raise RouteServiceError(
                    user_message=trecho.get("erro")
                    or "Não foi possível estimar um dos trechos da rota."
                )
            legs_payload.append(
                _build_leg_payload(
                    leg_base,
                    float(trecho.get("distancia_km") or 0.0),
                    int(trecho.get("tempo_cru_estimado_min") or 0),
                    str(trecho.get("rota_fonte") or "estimativa_local"),
                )
            )

    return {
        "ok": True,
        "route": route_payload,
        "legs": legs_payload,
        "fallback_per_leg_used": fallback_used,
    }
