"""Validação e normalização de CPF (apenas dígitos verificadores brasileiros)."""
from __future__ import annotations


def normalizar_cpf(valor: str | None) -> str:
    """Devolve 11 dígitos ou string vazia se não houver 11 dígitos."""
    if not valor:
        return ""
    d = "".join(ch for ch in str(valor) if ch.isdigit())
    return d if len(d) == 11 else ""


def validar_cpf_digitos(cpf11: str) -> bool:
    if len(cpf11) != 11 or not cpf11.isdigit():
        return False
    if cpf11 == cpf11[0] * 11:
        return False

    def dv_9_primeiros(nove: str) -> int:
        s = sum(int(nove[i]) * (10 - i) for i in range(9))
        m = s % 11
        return 0 if m < 2 else 11 - m

    def dv_10_primeiros(dez: str) -> int:
        s = sum(int(dez[i]) * (11 - i) for i in range(10))
        m = s % 11
        return 0 if m < 2 else 11 - m

    if int(cpf11[9]) != dv_9_primeiros(cpf11[:9]):
        return False
    return int(cpf11[10]) == dv_10_primeiros(cpf11[:10])


def validar_e_normalizar_cpf_digitado(valor: str | None) -> str:
    """
    Valor digitado pelo utilizador → 11 dígitos válidos ou levanta ValueError.
    """
    n = normalizar_cpf(valor)
    if len(n) != 11:
        raise ValueError("Indique um CPF com 11 dígitos.")
    if not validar_cpf_digitos(n):
        raise ValueError("CPF inválido (dígitos verificadores).")
    return n


def cpf_mascarado(cpf11: str) -> str:
    """Ex.: ***.***.***-12 (nunca expõe o CPF completo em UI pública)."""
    n = normalizar_cpf(cpf11)
    if len(n) != 11:
        return ""
    return f"***.***.*{n[6:9]}-{n[9:11]}"


def cpf_confere(esperado: str, informado: str) -> bool:
    e = normalizar_cpf(esperado)
    i = normalizar_cpf(informado)
    if not e or not i:
        return False
    return e == i
