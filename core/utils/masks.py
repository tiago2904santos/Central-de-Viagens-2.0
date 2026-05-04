"""Máscaras e normalização para backend (espelha regras úteis do legacy)."""

from __future__ import annotations

import re

EMPTY_MASK_DISPLAY = "—"
RG_NAO_POSSUI_CANONICAL = "NAO POSSUI RG"
RG_NAO_POSSUI_DISPLAY = "NÃO POSSUI RG"


def only_digits(value):
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def normalize_protocolo(value):
    return only_digits(value)


def format_protocolo(value):
    text = str(value or "").strip()
    digits = normalize_protocolo(text)
    if not digits:
        return ""
    if len(digits) != 9:
        return text
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}-{digits[8]}"


def format_cpf(value):
    text = str(value or "").strip()
    digits = only_digits(text)
    if not digits:
        return ""
    if len(digits) != 11:
        return text
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def format_telefone(value):
    text = str(value or "").strip()
    digits = only_digits(text)
    if not digits:
        return ""
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    return text


def format_phone(value):
    return format_telefone(value)


def format_cep(value):
    text = str(value or "").strip()
    digits = only_digits(text)
    if not digits:
        return ""
    if len(digits) != 8:
        return text
    return f"{digits[:5]}-{digits[5:]}"


def format_rg(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if text.upper() in {RG_NAO_POSSUI_CANONICAL, RG_NAO_POSSUI_DISPLAY.upper()}:
        return RG_NAO_POSSUI_DISPLAY
    digits = only_digits(text)
    if not digits:
        return text
    if len(digits) == 7:
        return f"{digits[0]}.{digits[1:4]}.{digits[4:7]}"
    if len(digits) == 8:
        return f"{digits[0]}.{digits[1:4]}.{digits[4:7]}-{digits[7]}"
    if len(digits) == 9:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}-{digits[8]}"
    return text


def normalize_placa(value):
    if not value:
        return ""
    return re.sub(r"[\s\-]", "", str(value).strip().upper())


def format_placa(value):
    text = str(value or "").strip()
    placa = normalize_placa(text)
    if not placa:
        return ""
    if re.match(r"^[A-Z]{3}[0-9]{4}$", placa):
        return f"{placa[:3]}-{placa[3:]}"
    if re.match(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$", placa):
        return placa
    return text or placa


def validar_cpf_digitos(cpf_11: str) -> bool:
    """Valida CPF com dígitos verificadores (mesma lógica do legacy)."""
    if len(cpf_11) != 11 or not cpf_11.isdigit():
        return False
    if cpf_11 == cpf_11[0] * 11:
        return False
    soma = sum(int(cpf_11[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    if int(cpf_11[9]) != d1:
        return False
    soma = sum(int(cpf_11[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    return int(cpf_11[10]) == d2


MASK_FORMATTERS = {
    "cep": format_cep,
    "cpf": format_cpf,
    "phone": format_telefone,
    "placa": format_placa,
    "protocolo": format_protocolo,
    "rg": format_rg,
    "telefone": format_telefone,
}


def apply_mask(mask_name, value):
    formatter = MASK_FORMATTERS.get(mask_name)
    if not formatter:
        return str(value or "")
    return formatter(value)


def format_masked_display(mask_name, value, *, empty=EMPTY_MASK_DISPLAY):
    if mask_name == "rg" and str(value or "").strip().upper() in {
        RG_NAO_POSSUI_CANONICAL,
        RG_NAO_POSSUI_DISPLAY.upper(),
    }:
        return RG_NAO_POSSUI_DISPLAY

    text = str(value or "").strip()
    if not text:
        return empty

    formatted = apply_mask(mask_name, text)
    formatted = str(formatted or "").strip()
    return formatted or text or empty


def format_rg_display(value, *, sem_rg=False, empty=EMPTY_MASK_DISPLAY):
    if sem_rg:
        return RG_NAO_POSSUI_DISPLAY
    return format_masked_display("rg", value, empty=empty)
