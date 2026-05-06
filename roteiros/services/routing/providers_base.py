# -*- coding: utf-8 -*-
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class RouteProvider(ABC):
    """Contrato interno para provedores de rota (ORS, OSRM futuro, etc.)."""

    provider_name = "base"

    @abstractmethod
    def calculate_route(
        self,
        points: List[Dict[str, Any]],
        *,
        profile: str = "driving-car",
    ) -> Dict[str, Any]:
        """points: dicts com lat, lng, id, label. Retorno normalizado pelo provedor."""
