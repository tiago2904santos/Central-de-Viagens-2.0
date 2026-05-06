# -*- coding: utf-8 -*-
from __future__ import annotations

from roteiros.models import Roteiro

from .route_signature import build_route_signature_for_roteiro


def mark_stale_when_signature_changed(roteiro: Roteiro, *, profile: str = "driving-car") -> None:
    """
    Após salvar alterações estruturais (destinos, trechos, sede), marca a rota do mapa
    como desatualizada se a assinatura geográfica mudou e havia cálculo válido.
    """
    if not roteiro.pk:
        return
    fresh = Roteiro.objects.get(pk=roteiro.pk)
    try:
        new_sig = build_route_signature_for_roteiro(fresh, profile=profile)
    except Exception:
        return
    if not (fresh.rota_assinatura or "").strip():
        return
    if fresh.rota_assinatura == new_sig:
        return
    if fresh.rota_status not in {
        Roteiro.ROTA_STATUS_CALCULADA,
        Roteiro.ROTA_STATUS_DESATUALIZADA,
        Roteiro.ROTA_STATUS_ERRO,
    }:
        return
    if fresh.rota_status != Roteiro.ROTA_STATUS_DESATUALIZADA:
        fresh.rota_status = Roteiro.ROTA_STATUS_DESATUALIZADA
        fresh.save(update_fields=["rota_status", "updated_at"])
