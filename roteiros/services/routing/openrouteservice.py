# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List

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


def _normalize_geometry(raw: Any) -> Dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict) and raw.get("type") and raw.get("coordinates"):
        return raw
    if isinstance(raw, str):
        # polyline encoded — guardar como referência mínima
        return {"type": "EncodedPolyline", "encoded": raw}
    return None


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
        url = f"https://api.openrouteservice.org/v2/directions/{profile}/json"
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

        routes = data.get("routes") or []
        if not routes:
            raise RouteNotFoundError()

        route = routes[0]
        summary = route.get("summary") or {}
        distance_m = float(summary.get("distance") or 0)
        duration_s = float(summary.get("duration") or 0)
        distance_km = round(distance_m / 1000.0, 2)
        duration_min = max(1, int(round(duration_s / 60.0))) if duration_s else 0

        geometry = _normalize_geometry(route.get("geometry"))

        segments_out: List[Dict[str, Any]] = []
        segs = route.get("segments") or []
        for idx, seg in enumerate(segs):
            if idx >= len(points) - 1:
                break
            p0, p1 = points[idx], points[idx + 1]
            dist_seg = float(seg.get("distance") or 0) / 1000.0
            dur_seg_s = float(seg.get("duration") or 0)
            dur_seg_min = max(0, int(round(dur_seg_s / 60.0))) if dur_seg_s else 0
            segments_out.append(
                {
                    "from_id": str(p0.get("id")),
                    "to_id": str(p1.get("id")),
                    "from_label": p0.get("label") or "",
                    "to_label": p1.get("label") or "",
                    "distance_km": round(dist_seg, 2),
                    "duration_minutes": dur_seg_min,
                    "geometry": _normalize_geometry(seg.get("geometry")),
                }
            )

        return {
            "provider": self.provider_name,
            "distance_km": distance_km,
            "duration_minutes": duration_min,
            "duration_human": _duration_human(duration_min),
            "geometry": geometry,
            "segments": segments_out,
        }


def get_openrouteservice_provider() -> OpenRouteServiceProvider | None:
    key = getattr(settings, "OPENROUTESERVICE_API_KEY", "") or ""
    if not key.strip():
        return None
    timeout = getattr(settings, "ROUTE_REQUEST_TIMEOUT_SECONDS", 12)
    return OpenRouteServiceProvider(key, timeout_seconds=timeout)
