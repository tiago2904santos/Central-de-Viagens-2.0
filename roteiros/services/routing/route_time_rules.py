# -*- coding: utf-8 -*-
from __future__ import annotations


def round_trip_minutes_to_15(minutes: int | float | None) -> int:
    """
    Arredonda SEMPRE para cima no próximo múltiplo de 15 minutos.
    """
    try:
        m = int(minutes or 0)
    except (TypeError, ValueError):
        m = 0
    if m <= 0:
        return 0
    return ((m + 14) // 15) * 15


def calculate_additional_time_minutes(rounded_travel_minutes: int | float | None) -> int:
    """
    Regras operacionais de tempo adicional:
    - até 29 min: 0
    - 30..60 min: 15
    - 61..180 min: 30
    - >180 min: 30 + 15 a cada bloco de 90 min excedente (arredondando para cima)
    """
    try:
        m = int(rounded_travel_minutes or 0)
    except (TypeError, ValueError):
        m = 0

    if m < 30:
        return 0
    if m <= 60:
        return 15
    if m <= 180:
        return 30

    excesso = m - 180
    blocos_90 = (excesso + 89) // 90
    return 30 + (blocos_90 * 15)
