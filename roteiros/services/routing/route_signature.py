# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from typing import Any, List


def _round_coord(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.5f}"
    except (TypeError, ValueError):
        return ""


def build_route_signature(
    points: List[dict],
    *,
    profile: str,
    bate_volta_diario: bool,
) -> str:
    """
    Assinatura estável da rota: ordem, perfil, modo e coordenadas (não só nomes).
    """
    payload = {
        "profile": profile,
        "loop": bool(bate_volta_diario),
        "pts": [
            {
                "id": str(p.get("id") or ""),
                "lat": _round_coord(p.get("lat")),
                "lng": _round_coord(p.get("lng")),
            }
            for p in points
        ],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_route_signature_for_roteiro(roteiro, *, profile: str = "driving-car") -> str:
    from .route_point_builder import build_route_points_for_roteiro

    points, bate = build_route_points_for_roteiro(roteiro)
    return build_route_signature(points, profile=profile, bate_volta_diario=bate)
