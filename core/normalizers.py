import re
import unicodedata


def normalize_spaces(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_upper(value: str) -> str:
    return normalize_spaces(value).upper()


def normalize_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def normalize_plate(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def remove_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", (value or ""))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
