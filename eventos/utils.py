# -*- coding: utf-8 -*-
"""Utilitários do app eventos."""

import re

from core.utils.masks import format_protocolo, normalize_protocolo, only_digits


def hhmm_to_minutes(value):
    """
    Converte string HH:MM em minutos.
    Ex.: "03:30" -> 210, "01:05" -> 65, "00:45" -> 45.
    Aceita HH de 0 a 99, MM de 0 a 59.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    s = str(value).strip()
    match = re.match(r'^(\d{1,2}):([0-5]?\d)$', s)
    if not match:
        raise ValueError('Use o formato HH:MM (ex.: 03:30).')
    horas, minutos = int(match.group(1)), int(match.group(2))
    if horas < 0 or minutos < 0 or minutos > 59:
        raise ValueError('Minutos devem ser 00 a 59.')
    return horas * 60 + minutos


def minutes_to_hhmm(minutes):
    """
    Converte minutos em string HH:MM.
    Ex.: 210 -> "03:30", 65 -> "01:05".
    """
    if minutes is None:
        return ''
    try:
        total = int(minutes)
    except (TypeError, ValueError):
        return ''
    if total < 0:
        return ''
    horas, minutos = divmod(total, 60)
    return f'{horas:02d}:{minutos:02d}'
