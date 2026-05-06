# -*- coding: utf-8 -*-
from __future__ import annotations


def round_trip_minutes_to_15(minutes: int | float | None) -> int:
    """
    Arredonda em blocos de 15 com tolerância operacional:
    - resto <= 5: arredonda para baixo (mantém o bloco atual)
    - resto > 5: arredonda para cima (próximo bloco de 15)

    Exemplos:
    65 -> 60
    66 -> 75
    76 -> 75
    """
    try:
        m = int(minutes or 0)
    except (TypeError, ValueError):
        m = 0
    if m <= 0:
        return 0
    base = (m // 15) * 15
    resto = m - base
    if resto == 0:
        return m
    if resto <= 5:
        return base
    return base + 15


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
