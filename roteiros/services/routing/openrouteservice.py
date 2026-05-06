# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import requests
from django.conf import settings

from .providers_base import RouteProvider
from .route_exceptions import (
    RouteNotFoundError,
    RouteProviderUnavailable,
    RouteRateLimitError,
    RouteTimeoutError,
    RouteValidationError,
)

logger = logging.getLogger(__name__)


def _duration_human(total_minutes: int) -> str:
    h, m = divmod(max(0, int(total_minutes)), 60)
    if h and m:
        return f"{h}h{m}min"
    if h:
        return f"{h}h"
    return f"{m}min"


def _flatten_to_linestring(geom: dict | None) -> dict | None:
    """Normaliza para GeoJSON LineString em [lng, lat] (compatível com Leaflet)."""
    if not geom or not isinstance(geom, dict):
        return None
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "LineString" and coords:
        return {"type": "LineString", "coordinates": coords}
    if t == "MultiLineString" and coords:
        merged: list = []
        for line in coords:
            if not line:
                continue
            if not merged:
                merged.extend(line)
            else:
                if merged[-1] == line[0]:
                    merged.extend(line[1:])
                else:
                    merged.extend(line)
        return {"type": "LineString", "coordinates": merged} if merged else None
    return None


def _segments_from_properties(props: dict, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments_out: List[Dict[str, Any]] = []
    segs = (props or {}).get("segments") or []
    for idx, seg in enumerate(segs):
        if idx >= len(points) - 1:
            break
        p0, p1 = points[idx], points[idx + 1]
        dist_seg = float(seg.get("distance") or 0) / 1000.0
        dur_seg_s = float(seg.get("duration") or 0)
        dur_seg_min = max(0, int(round(dur_seg_s / 60.0))) if dur_seg_s else 0
        g = seg.get("geometry")
        seg_geom = _flatten_to_linestring(g) if isinstance(g, dict) else None
        segments_out.append(
            {
                "from_id": str(p0.get("id")),
                "to_id": str(p1.get("id")),
                "from_label": p0.get("label") or "",
                "to_label": p1.get("label") or "",
                "distance_km": round(dist_seg, 2),
                "duration_minutes": dur_seg_min,
                "geometry": seg_geom,
            }
        )
    return segments_out


def _segments_from_legacy_route(route: dict, points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments_out: List[Dict[str, Any]] = []
    segs = route.get("segments") or []
    for idx, seg in enumerate(segs):
        if idx >= len(points) - 1:
            break
        p0, p1 = points[idx], points[idx + 1]
        dist_seg = float(seg.get("distance") or 0) / 1000.0
        dur_seg_s = float(seg.get("duration") or 0)
        dur_seg_min = max(0, int(round(dur_seg_s / 60.0))) if dur_seg_s else 0
        g = seg.get("geometry")
        seg_geom = None
        if isinstance(g, dict):
            seg_geom = _flatten_to_linestring(g)
        segments_out.append(
            {
                "from_id": str(p0.get("id")),
                "to_id": str(p1.get("id")),
                "from_label": p0.get("label") or "",
                "to_label": p1.get("label") or "",
                "distance_km": round(dist_seg, 2),
                "duration_minutes": dur_seg_min,
                "geometry": seg_geom,
            }
        )
    return segments_out


def _parse_geojson_feature_collection(
    data: dict, points: List[Dict[str, Any]]
) -> Tuple[dict | None, dict, List[dict], str | None]:
    """
    Formato preferencial da API `/directions/{profile}/geojson`.
    Retorna (linestring_geometry, summary_dict com distance em metros e duration em segundos, segments, warning).
    """
    warning: str | None = None
    if data.get("type") != "FeatureCollection":
        return None, {}, [], None
    features = data.get("features") or []
    if not features:
        return None, {}, [], None
    feat = features[0] or {}
    geom_raw = feat.get("geometry")
    props = feat.get("properties") or {}
    summary = props.get("summary") or {}
    segments = _segments_from_properties(props, points)

    line = _flatten_to_linestring(geom_raw if isinstance(geom_raw, dict) else None)
    if line is None and geom_raw:
        warning = (
            "Geometria retornada em formato não suportado para desenho no mapa "
            "(esperado LineString ou MultiLineString)."
        )
    return line, summary, segments, warning


def _parse_legacy_routes_json(
    data: dict, points: List[Dict[str, Any]]
) -> Tuple[dict | None, dict, List[dict], str | None]:
    """Formato `/json` legado: `routes[0]` com summary, geometry e segments."""
    warning: str | None = None
    routes = data.get("routes") or []
    if not routes:
        return None, {}, [], None
    route = routes[0]
    summary = route.get("summary") or {}
    raw_geom = route.get("geometry")

    line: dict | None = None
    if isinstance(raw_geom, dict):
        line = _flatten_to_linestring(raw_geom)
        if line is None:
            warning = (
                "Geometria retornada em formato não suportado para desenho no mapa "
                "(esperado LineString ou MultiLineString)."
            )
    elif isinstance(raw_geom, str) and raw_geom.strip():
        warning = (
            "A API retornou geometria codificada (polyline), não convertida nesta versão. "
            "Use o endpoint GeoJSON no servidor."
        )
        logger.info("OpenRouteService: geometria encoded ignorada (sem decoder polyline).")

    segments = _segments_from_legacy_route(route, points)
    return line, summary, segments, warning


def _compute_totals_from_summary(summary: dict) -> Tuple[float, int]:
    distance_m = float(summary.get("distance") or 0)
    duration_s = float(summary.get("duration") or 0)
    distance_km = round(distance_m / 1000.0, 2)
    duration_min = max(1, int(round(duration_s / 60.0))) if duration_s else 0
    return distance_km, duration_min


class OpenRouteServiceProvider(RouteProvider):
    provider_name = "openrouteservice"

    def __init__(self, api_key: str, *, timeout_seconds: int = 12):
        self._api_key = (api_key or "").strip()
        self._timeout = max(1, min(60, int(timeout_seconds)))

    def calculate_route(
        self,
        points: List[Dict[str, Any]],
        *,
        profile: str = "driving-car",
    ) -> Dict[str, Any]:
        if len(points) < 2:
            raise RouteValidationError("Pontos insuficientes para rota.")
        if not self._api_key:
            raise RouteValidationError("API key ausente.")

        coords = [[float(p["lng"]), float(p["lat"])] for p in points]
        url = f"https://api.openrouteservice.org/v2/directions/{profile}/geojson"
        auth = self._api_key
        if not auth.lower().startswith("bearer "):
            auth = f"Bearer {auth}"
        headers = {"Authorization": auth, "Content-Type": "application/json"}
        body: Dict[str, Any] = {
            "coordinates": coords,
            "preference": "recommended",
            "units": "m",
            "geometry": True,
        }

        try:
            resp = requests.post(url, json=body, headers=headers, timeout=self._timeout)
        except requests.Timeout as exc:
            logger.warning("OpenRouteService timeout: %s", exc)
            raise RouteTimeoutError() from exc
        except requests.RequestException as exc:
            logger.warning("OpenRouteService request error: %s", exc)
            raise RouteProviderUnavailable() from exc

        if resp.status_code == 429:
            raise RouteRateLimitError()
        if resp.status_code >= 500:
            raise RouteProviderUnavailable()

        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning("OpenRouteService JSON inválido: %s", exc)
            raise RouteProviderUnavailable() from exc

        if resp.status_code >= 400:
            err = (data.get("error") or {}) if isinstance(data, dict) else {}
            msg = err.get("message") or data.get("message") or ""
            logger.info("OpenRouteService erro HTTP %s: %s", resp.status_code, msg)
            if resp.status_code == 404 or "not found" in str(msg).lower():
                raise RouteNotFoundError()
            raise RouteProviderUnavailable()

        geometry_warning: str | None = None
        line: dict | None = None
        summary: dict = {}
        segments_out: List[Dict[str, Any]] = []

        if not isinstance(data, dict):
            raise RouteNotFoundError()

        if data.get("type") == "FeatureCollection":
            line, summary, segments_out, w = _parse_geojson_feature_collection(data, points)
            geometry_warning = w

        if data.get("routes"):
            lg_line, lg_summary, lg_segs, lg_w = _parse_legacy_routes_json(data, points)
            if lg_summary:
                summary = summary or lg_summary
            if line is None and lg_line is not None:
                line = lg_line
            if not segments_out and lg_segs:
                segments_out = lg_segs
            if lg_w and not geometry_warning:
                geometry_warning = lg_w

        if not summary:
            raise RouteNotFoundError()

        distance_km, duration_min = _compute_totals_from_summary(summary)

        if line is None and not geometry_warning:
            geometry_warning = (
                "Rota calculada, mas nenhuma geometria LineString foi obtida da resposta."
            )

        out = {
            "provider": self.provider_name,
            "distance_km": distance_km,
            "duration_minutes": duration_min,
            "duration_human": _duration_human(duration_min),
            "geometry": line,
            "segments": segments_out,
        }
        if geometry_warning:
            out["geometry_warning"] = geometry_warning
        return out


def get_openrouteservice_provider() -> OpenRouteServiceProvider | None:
    key = getattr(settings, "OPENROUTESERVICE_API_KEY", "") or ""
    if not key.strip():
        return None
    timeout = getattr(settings, "ROUTE_REQUEST_TIMEOUT_SECONDS", 12)
    return OpenRouteServiceProvider(key, timeout_seconds=timeout)
