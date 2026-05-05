# -*- coding: utf-8 -*-
"""
Provider de roteamento para estimativa de viagem (route-aware).
Interface abstrata + implementacao OSRM local.
Sem dependencia de API externa em producao; OSRM roda localmente.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 5
_ROAD_REF_RE = re.compile(r"\b(?:BR|PRC|PR)-?\d{2,3}\b", re.IGNORECASE)


def _normalize_road_refs(value: Optional[str]) -> List[str]:
    """Extrai refs rodoviarias normalizadas do texto informado."""
    if not value or not isinstance(value, str):
        return []
    normalized = (
        value.upper()
        .replace(" ", "")
        .replace("–", "-")
        .replace("—", "-")
    )
    refs: List[str] = []
    for match in _ROAD_REF_RE.findall(normalized):
        ref = match.upper()
        if "-" not in ref:
            prefix = ref[:3] if ref.startswith("PRC") else ref[:2]
            number = ref[len(prefix):]
            ref = f"{prefix}-{number}"
        if ref not in refs:
            refs.append(ref)
    return refs


@dataclass
class RouteResult:
    """Resultado de uma rota obtida do motor de roteamento."""

    distance_km: float
    duration_min: float
    refs_predominantes: List[str] = field(default_factory=list)
    steps: List[dict] = field(default_factory=list)
    geometry: Optional[List] = None
    ref_distance_km: Dict[str, float] = field(default_factory=dict)
    raw: Optional[dict] = None

    @property
    def has_annotations(self) -> bool:
        return bool(self.steps or self.refs_predominantes)


class RoutingProvider(ABC):
    """Interface para provedor de roteamento (OSRM, GraphHopper, etc.)."""

    @abstractmethod
    def route(
        self,
        origem_lat: float,
        origem_lon: float,
        destino_lat: float,
        destino_lon: float,
    ) -> Optional[RouteResult]:
        """Obtem rota entre dois pontos."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome do provider (ex: 'osrm')."""


class OSRMRoutingProvider(RoutingProvider):
    """
    Provider para OSRM local (route service).
    URL base e timeout configuraveis (env: OSRM_BASE_URL, OSRM_TIMEOUT_SECONDS).
    Le distance (m), duration (s), steps com ref/name quando disponivel.
    Timeout/erro HTTP/sem rota retornam None sem quebrar o sistema.
    """

    def __init__(self, base_url: str, timeout_seconds: int = _DEFAULT_TIMEOUT):
        self._base_url = (base_url or "").rstrip("/")
        self._timeout = max(1, min(30, int(timeout_seconds)))

    @property
    def name(self) -> str:
        return "osrm"

    def route(
        self,
        origem_lat: float,
        origem_lon: float,
        destino_lat: float,
        destino_lon: float,
    ) -> Optional[RouteResult]:
        if not self._base_url:
            return None
        try:
            import requests
        except ImportError:
            logger.warning("requests nao disponivel; OSRM provider inativo.")
            return None

        coords = f"{origem_lon},{origem_lat};{destino_lon},{destino_lat}"
        url = f"{self._base_url}/route/v1/driving/{coords}"
        params = {
            "overview": "full",
            "annotations": "true",
            "steps": "true",
            "geometries": "geojson",
        }

        data = None
        for attempt in range(2):
            try:
                response = requests.get(url, params=params, timeout=self._timeout)
                response.raise_for_status()
                data = response.json()
                break
            except Exception as exc:
                if attempt == 1:
                    logger.debug("OSRM route falhou: %s", exc)
                    return None

        routes = data.get("routes") or []
        if not routes:
            return None

        route = routes[0]
        distance_km = float(route.get("distance") or 0) / 1000.0
        duration_min = float(route.get("duration") or 0) / 60.0

        steps: List[dict] = []
        ref_distance_km: Dict[str, float] = defaultdict(float)
        named_distance_km: Dict[str, float] = defaultdict(float)
        for leg in route.get("legs") or []:
            for step in leg.get("steps") or []:
                road_refs = _normalize_road_refs(step.get("ref"))
                if not road_refs:
                    road_refs = _normalize_road_refs(step.get("name"))
                step_km = float(step.get("distance") or 0) / 1000.0
                if road_refs:
                    for road_ref in road_refs:
                        ref_distance_km[road_ref] += step_km
                else:
                    step_name = (step.get("name") or "").strip()
                    if step_name:
                        named_distance_km[step_name] += step_km
                steps.append(
                    {
                        "distance": step.get("distance"),
                        "duration": step.get("duration"),
                        "name": step.get("name"),
                        "ref": step.get("ref"),
                        "road_refs": road_refs,
                    }
                )

        geometry = None
        route_geometry = route.get("geometry") or {}
        if route_geometry.get("coordinates"):
            geometry = route_geometry["coordinates"]

        if ref_distance_km:
            refs_predominantes = [
                ref
                for ref, _distance in sorted(
                    ref_distance_km.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]
        else:
            refs_predominantes = [
                name
                for name, _distance in sorted(
                    named_distance_km.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]

        return RouteResult(
            distance_km=distance_km,
            duration_min=duration_min,
            refs_predominantes=refs_predominantes[:20],
            steps=steps,
            geometry=geometry,
            ref_distance_km=dict(ref_distance_km),
            raw=route,
        )


def get_default_routing_provider(
    base_url: Optional[str] = None,
    enabled: Optional[bool] = None,
    timeout_seconds: Optional[int] = None,
) -> Optional[RoutingProvider]:
    """
    Retorna o provider OSRM se OSRM_ENABLED e OSRM_BASE_URL estiverem configurados.
    Caso contrario retorna None (aplicacao usa fallback Haversine/corredor).
    """
    try:
        from django.conf import settings

        is_enabled = enabled if enabled is not None else getattr(settings, "OSRM_ENABLED", False)
        url = base_url if base_url else (getattr(settings, "OSRM_BASE_URL", "") or "")
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "OSRM_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT)
        )
    except Exception:
        is_enabled = False
        url = ""
        timeout = _DEFAULT_TIMEOUT
    if not is_enabled or not (url or "").strip():
        return None
    return OSRMRoutingProvider(url.strip(), timeout_seconds=timeout)
