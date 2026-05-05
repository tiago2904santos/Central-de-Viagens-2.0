# -*- coding: utf-8 -*-
"""
Modelagem de corredores rodoviarios do Parana para estimativa de viagem.
Classificacao macro e fina; inferencia de atributos (serra, pedagio, urbano).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import csv
import math
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence

# --- Corredores macro ---
BR277_LITORAL = "BR277_LITORAL"
BR277_OESTE = "BR277_OESTE"
NORTE_CAFE = "NORTE_CAFE"
NOROESTE_INTERIOR = "NOROESTE_INTERIOR"
CAMPOS_GERAIS = "CAMPOS_GERAIS"
CORREDOR_PADRAO = "PADRAO"

CORREDORES_MACRO = (
    BR277_LITORAL,
    BR277_OESTE,
    NORTE_CAFE,
    NOROESTE_INTERIOR,
    CAMPOS_GERAIS,
    CORREDOR_PADRAO,
)

BUFFER_POR_CORREDOR_MACRO = {
    BR277_LITORAL: 5,
    BR277_OESTE: 10,
    NORTE_CAFE: 15,
    NOROESTE_INTERIOR: 15,
    CAMPOS_GERAIS: 10,
    CORREDOR_PADRAO: 10,
}

# --- Corredores finos ---
PONTAL_LITORAL = "PONTAL_LITORAL"
PARANAGUA = "PARANAGUA"
MATINHOS = "MATINHOS"
GUARATUBA = "GUARATUBA"
PONTA_GROSSA = "PONTA_GROSSA"
CASTRO = "CASTRO"
TELEMACO_BORBA = "TELEMACO_BORBA"
IRATI = "IRATI"
UNIAO_DA_VITORIA = "UNIAO_DA_VITORIA"
MARINGA = "MARINGA"
LONDRINA = "LONDRINA"
APUCARANA = "APUCARANA"
JACAREZINHO = "JACAREZINHO"
CAMPO_MOURAO = "CAMPO_MOURAO"
PARANAVAI = "PARANAVAI"
CIANORTE = "CIANORTE"
UMUARAMA = "UMUARAMA"
CRUZEIRO_DO_SUL = "CRUZEIRO_DO_SUL"
PALOTINA = "PALOTINA"
TOLEDO = "TOLEDO"
CASCAVEL = "CASCAVEL"
FOZ_DO_IGUACU = "FOZ_DO_IGUACU"
GUARAPUAVA = "GUARAPUAVA"
FRANCISCO_BELTRAO = "FRANCISCO_BELTRAO"
PATO_BRANCO = "PATO_BRANCO"
CORREDOR_FINO_PADRAO = "PADRAO"

REF_BR277 = "BR-277"
REF_BR376 = "BR-376"
REF_BR369 = "BR-369"
REF_BR487 = "BR-487"
REF_BR373 = "BR-373"
REF_BR153 = "BR-153"

_ROAD_REF_RE = re.compile(r"\b(?:BR|PRC|PR)-?\d{2,3}\b", re.IGNORECASE)
_URBAN_NAME_HINTS = ("AVENIDA", "RUA", "MARGINAL", "ALAMEDA", "TRAVESSA", "PRACA")
_ROOT_DIR = Path(__file__).resolve().parents[2]
_MUNICIPIO_CODE_PATH = _ROOT_DIR / "data" / "geografia" / "municipio_code.csv"


def _normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Z0-9 ]+", " ", ascii_text.upper())
    return re.sub(r"\s+", " ", cleaned).strip()


def _normalize_refs(values: Optional[Iterable[str]]) -> List[str]:
    refs: List[str] = []
    for value in values or []:
        if not value:
            continue
        normalized = (
            str(value).upper()
            .replace(" ", "")
            .replace("–", "-")
            .replace("—", "-")
        )
        for match in _ROAD_REF_RE.findall(normalized):
            ref = match.upper()
            if "-" not in ref:
                prefix = ref[:3] if ref.startswith("PRC") else ref[:2]
                number = ref[len(prefix):]
                ref = f"{prefix}-{number}"
            if ref not in refs:
                refs.append(ref)
    return refs


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


@dataclass(frozen=True)
class MunicipioInfo:
    nome: str
    nome_norm: str
    latitude: float
    longitude: float
    codigo_ibge: str


@dataclass(frozen=True)
class FineCorridorSpec:
    fino: str
    macro: str
    municipios: Sequence[str]
    refs: Sequence[str] = ()
    radius_km: float = 32.0
    serra: bool = False


FINE_SPECS: List[FineCorridorSpec] = [
    FineCorridorSpec(PONTAL_LITORAL, BR277_LITORAL, ("PONTAL DO PARANA",), ("PR-407", REF_BR277), radius_km=28.0, serra=True),
    FineCorridorSpec(PARANAGUA, BR277_LITORAL, ("PARANAGUA",), (REF_BR277,), radius_km=24.0, serra=True),
    FineCorridorSpec(MATINHOS, BR277_LITORAL, ("MATINHOS",), ("PR-508", "PR-412", REF_BR277), radius_km=24.0, serra=True),
    FineCorridorSpec(GUARATUBA, BR277_LITORAL, ("GUARATUBA",), ("PR-412", REF_BR277), radius_km=28.0, serra=True),
    FineCorridorSpec(PONTA_GROSSA, CAMPOS_GERAIS, ("PONTA GROSSA",), (REF_BR277, REF_BR376, "PR-151"), radius_km=22.0),
    FineCorridorSpec(CASTRO, CAMPOS_GERAIS, ("CASTRO",), ("PR-151", "PR-340"), radius_km=20.0),
    FineCorridorSpec(TELEMACO_BORBA, CAMPOS_GERAIS, ("TELEMACO BORBA",), ("PR-160", REF_BR376), radius_km=24.0),
    FineCorridorSpec(IRATI, CAMPOS_GERAIS, ("IRATI",), (REF_BR277, REF_BR153, REF_BR373), radius_km=20.0),
    FineCorridorSpec(UNIAO_DA_VITORIA, CAMPOS_GERAIS, ("UNIAO DA VITORIA",), (REF_BR153, REF_BR373), radius_km=24.0),
    FineCorridorSpec(LONDRINA, NORTE_CAFE, ("LONDRINA",), (REF_BR376, REF_BR369, "PR-445"), radius_km=22.0),
    FineCorridorSpec(APUCARANA, NORTE_CAFE, ("APUCARANA",), (REF_BR376, REF_BR369, "PR-444"), radius_km=22.0),
    FineCorridorSpec(MARINGA, NORTE_CAFE, ("MARINGA",), (REF_BR376, "PR-317", "PR-897"), radius_km=22.0),
    FineCorridorSpec(JACAREZINHO, NORTE_CAFE, ("JACAREZINHO",), (REF_BR153, REF_BR369), radius_km=22.0),
    FineCorridorSpec(CAMPO_MOURAO, NOROESTE_INTERIOR, ("CAMPO MOURAO",), (REF_BR487, "PR-317"), radius_km=22.0),
    FineCorridorSpec(PARANAVAI, NOROESTE_INTERIOR, ("PARANAVAI",), ("PR-323", "PR-492"), radius_km=22.0),
    FineCorridorSpec(CIANORTE, NOROESTE_INTERIOR, ("CIANORTE",), ("PR-323", "PR-317"), radius_km=22.0),
    FineCorridorSpec(UMUARAMA, NOROESTE_INTERIOR, ("UMUARAMA",), ("PR-323", "PR-482"), radius_km=22.0),
    FineCorridorSpec(CRUZEIRO_DO_SUL, NOROESTE_INTERIOR, ("CRUZEIRO DO SUL",), ("PR-323", "PR-082"), radius_km=28.0),
    FineCorridorSpec(CASCAVEL, BR277_OESTE, ("CASCAVEL",), (REF_BR277, "BR-467", "PRC-467"), radius_km=22.0),
    FineCorridorSpec(TOLEDO, BR277_OESTE, ("TOLEDO",), ("PR-317", "PR-239", "BR-163"), radius_km=22.0),
    FineCorridorSpec(PALOTINA, BR277_OESTE, ("PALOTINA",), ("PR-182", "PR-317"), radius_km=22.0),
    FineCorridorSpec(FOZ_DO_IGUACU, BR277_OESTE, ("FOZ DO IGUACU",), (REF_BR277, "BR-469"), radius_km=24.0),
    FineCorridorSpec(GUARAPUAVA, BR277_OESTE, ("GUARAPUAVA",), (REF_BR277, REF_BR373), radius_km=24.0),
    FineCorridorSpec(FRANCISCO_BELTRAO, BR277_OESTE, ("FRANCISCO BELTRAO",), ("PR-483", "PR-180", REF_BR277), radius_km=24.0),
    FineCorridorSpec(PATO_BRANCO, BR277_OESTE, ("PATO BRANCO",), ("PR-280", "BR-158"), radius_km=24.0),
]

_FINE_BY_NAME: Dict[str, FineCorridorSpec] = {}
for _spec in FINE_SPECS:
    for _municipio_name in _spec.municipios:
        _FINE_BY_NAME[_normalize_text(_municipio_name)] = _spec

_MACRO_MUNICIPIOS: Dict[str, set[str]] = {
    BR277_LITORAL: {"PONTAL DO PARANA", "PARANAGUA", "MATINHOS", "GUARATUBA", "MORRETES", "ANTONINA", "GUARAQUECABA"},
    CAMPOS_GERAIS: {"PONTA GROSSA", "CASTRO", "TELEMACO BORBA", "IRATI", "UNIAO DA VITORIA"},
    NORTE_CAFE: {"LONDRINA", "APUCARANA", "MARINGA", "JACAREZINHO", "ARAPONGAS"},
    NOROESTE_INTERIOR: {"CAMPO MOURAO", "PARANAVAI", "CIANORTE", "UMUARAMA", "CRUZEIRO DO SUL"},
    BR277_OESTE: {"GUARAPUAVA", "CASCAVEL", "TOLEDO", "PALOTINA", "FOZ DO IGUACU", "FRANCISCO BELTRAO", "PATO BRANCO"},
}

_LITORAL_REFS = {REF_BR277, "PR-407", "PR-508", "PR-412"}
_CAMPOS_REFS = {REF_BR277, REF_BR376, REF_BR373, "PR-151", "PR-160", "PR-092"}
_NORTE_REFS = {REF_BR376, REF_BR369, "PR-445", "PR-444"}
_NOROESTE_REFS = {REF_BR487, "PR-323", "PR-317", "PR-492", "PR-082", "PR-463"}
_OESTE_REFS = {REF_BR277, "BR-467", "PRC-467", "PR-182", "PR-483", "PR-280", "BR-163"}
_FINE_SERRA = {PONTAL_LITORAL, PARANAGUA, MATINHOS, GUARATUBA}
_FINE_URBANO = {
    PARANAGUA,
    PONTA_GROSSA,
    LONDRINA,
    APUCARANA,
    MARINGA,
    CASCAVEL,
    FOZ_DO_IGUACU,
}
_MACRO_PEDAGIO = {BR277_LITORAL, BR277_OESTE, NORTE_CAFE, CAMPOS_GERAIS}


@lru_cache(maxsize=1)
def _load_pr_municipios() -> List[MunicipioInfo]:
    municipios: List[MunicipioInfo] = []
    if not _MUNICIPIO_CODE_PATH.exists():
        return municipios
    with _MUNICIPIO_CODE_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            if (row.get("uf") or "").upper() != "PR":
                continue
            nome = row.get("municipio") or ""
            municipios.append(
                MunicipioInfo(
                    nome=nome,
                    nome_norm=_normalize_text(nome),
                    latitude=float(row.get("latitude") or 0),
                    longitude=float(row.get("longitude") or 0),
                    codigo_ibge=str(row.get("id_municipio") or ""),
                )
            )
    return municipios


def inferir_municipio_por_coordenada(
    lat: float,
    lon: float,
    raio_max_km: float = 38.0,
) -> Optional[MunicipioInfo]:
    """Retorna o municipio PR mais proximo ao ponto, se estiver no raio tolerado."""
    melhor: Optional[MunicipioInfo] = None
    menor_distancia = float("inf")
    for municipio in _load_pr_municipios():
        distancia = _haversine_km(lat, lon, municipio.latitude, municipio.longitude)
        if distancia < menor_distancia:
            melhor = municipio
            menor_distancia = distancia
    if melhor and menor_distancia <= raio_max_km:
        return melhor
    return None


def _municipio_macro(nome_norm: str) -> Optional[str]:
    for macro, municipios in _MACRO_MUNICIPIOS.items():
        if nome_norm in municipios:
            return macro
    return None


def _coord_no_litoral(lat: float, lon: float) -> bool:
    return -26.6 <= float(lat) <= -25.0 and -49.2 <= float(lon) <= -48.2


def _coord_em_campos_gerais(lat: float, lon: float) -> bool:
    return -26.3 <= float(lat) <= -24.0 and -51.2 <= float(lon) <= -49.2


def _coord_em_norte_cafe(lat: float, lon: float) -> bool:
    return -24.4 <= float(lat) <= -22.6 and -52.0 <= float(lon) <= -50.5


def _coord_em_noroeste(lat: float, lon: float) -> bool:
    return -24.8 <= float(lat) <= -22.4 and -54.2 <= float(lon) <= -51.7


def _coord_em_oeste(lat: float, lon: float) -> bool:
    return -26.7 <= float(lat) <= -24.0 and -54.8 <= float(lon) <= -51.0


def _route_touches_bbox(route_result: Optional[Any], *, min_lon: float, max_lon: float, min_lat: float, max_lat: float, min_points: int = 3) -> bool:
    if not route_result or not getattr(route_result, "geometry", None):
        return False
    hits = 0
    for lon, lat in route_result.geometry:
        if min_lon <= float(lon) <= max_lon and min_lat <= float(lat) <= max_lat:
            hits += 1
            if hits >= min_points:
                return True
    return False


def _route_has_serra_segment(route_result: Optional[Any]) -> bool:
    return _route_touches_bbox(
        route_result,
        min_lon=-49.20,
        max_lon=-48.45,
        min_lat=-25.78,
        max_lat=-25.15,
        min_points=4,
    )


def _route_reaches_west(route_result: Optional[Any]) -> bool:
    if not route_result or not getattr(route_result, "geometry", None):
        return False
    return any(float(lon) <= -52.20 for lon, _lat in route_result.geometry)


def _route_reaches_north(route_result: Optional[Any]) -> bool:
    if not route_result or not getattr(route_result, "geometry", None):
        return False
    return any(float(lat) >= -24.20 for _lon, lat in route_result.geometry)


def _near_spec(lat: float, lon: float, spec: FineCorridorSpec) -> bool:
    for municipio_name in spec.municipios:
        municipio = _find_municipio_by_name(_normalize_text(municipio_name))
        if not municipio:
            continue
        if _haversine_km(lat, lon, municipio.latitude, municipio.longitude) <= spec.radius_km:
            return True
    return False


@lru_cache(maxsize=None)
def _find_municipio_by_name(nome_norm: str) -> Optional[MunicipioInfo]:
    for municipio in _load_pr_municipios():
        if municipio.nome_norm == nome_norm:
            return municipio
    return None


def classificar_corredor_macro(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
    distancia_linha_reta_km: float,
    distancia_rodoviaria_km: float,
    refs_predominantes: Optional[List[str]] = None,
    route_result: Optional[Any] = None,
) -> str:
    """
    Classifica o corredor macro da rota.
    Prioridade: refs predominantes -> geometria/segmentos -> municipio destino -> bbox.
    """
    refs = _normalize_refs(refs_predominantes or getattr(route_result, "refs_predominantes", None))
    destino_municipio = inferir_municipio_por_coordenada(destino_lat, destino_lon)
    origem_municipio = inferir_municipio_por_coordenada(origem_lat, origem_lon)
    destino_nome = destino_municipio.nome_norm if destino_municipio else ""
    origem_nome = origem_municipio.nome_norm if origem_municipio else ""

    if refs:
        ref_set = set(refs)
        if (REF_BR277 in ref_set and _route_has_serra_segment(route_result)) or (
            ref_set.intersection(_LITORAL_REFS)
            and (destino_nome in _MACRO_MUNICIPIOS[BR277_LITORAL] or origem_nome in _MACRO_MUNICIPIOS[BR277_LITORAL])
        ):
            return BR277_LITORAL
        if destino_nome:
            municipio_macro = _municipio_macro(destino_nome)
            if municipio_macro == NOROESTE_INTERIOR and (
                ref_set.intersection(_NOROESTE_REFS)
                or _route_reaches_north(route_result)
                or float(destino_lon) <= -51.9
            ):
                return NOROESTE_INTERIOR
            if municipio_macro == NORTE_CAFE and (
                ref_set.intersection(_NORTE_REFS)
                or _route_reaches_north(route_result)
            ):
                return NORTE_CAFE
            if municipio_macro == BR277_OESTE and (
                ref_set.intersection(_OESTE_REFS)
                or float(destino_lon) <= -51.1
                or _route_reaches_west(route_result)
            ):
                return BR277_OESTE
            if municipio_macro == CAMPOS_GERAIS and ref_set.intersection(_CAMPOS_REFS):
                return CAMPOS_GERAIS
        if ref_set.intersection(_NORTE_REFS) and (
            destino_nome in _MACRO_MUNICIPIOS[NORTE_CAFE]
            or origem_nome in _MACRO_MUNICIPIOS[NORTE_CAFE]
            or _route_reaches_north(route_result)
        ):
            return NORTE_CAFE
        if ref_set.intersection(_NOROESTE_REFS) and (
            destino_nome in _MACRO_MUNICIPIOS[NOROESTE_INTERIOR]
            or origem_nome in _MACRO_MUNICIPIOS[NOROESTE_INTERIOR]
            or float(destino_lon) <= -51.9
        ):
            return NOROESTE_INTERIOR
        if ref_set.intersection(_OESTE_REFS) and (
            destino_nome in _MACRO_MUNICIPIOS[BR277_OESTE]
            or origem_nome in _MACRO_MUNICIPIOS[BR277_OESTE]
            or _route_reaches_west(route_result)
            or float(destino_lon) <= -51.1
        ):
            return BR277_OESTE
        if ref_set.intersection(_CAMPOS_REFS) and (
            destino_nome in _MACRO_MUNICIPIOS[CAMPOS_GERAIS]
            or origem_nome in _MACRO_MUNICIPIOS[CAMPOS_GERAIS]
            or float(destino_lon) <= -49.4
        ):
            return CAMPOS_GERAIS

    if _route_has_serra_segment(route_result):
        return BR277_LITORAL

    if destino_nome:
        municipio_macro = _municipio_macro(destino_nome)
        if municipio_macro:
            return municipio_macro
    if origem_nome and distancia_linha_reta_km <= 120:
        municipio_macro = _municipio_macro(origem_nome)
        if municipio_macro:
            return municipio_macro

    if _coord_no_litoral(destino_lat, destino_lon) or _coord_no_litoral(origem_lat, origem_lon):
        return BR277_LITORAL
    if _coord_em_norte_cafe(destino_lat, destino_lon):
        return NORTE_CAFE
    if _coord_em_noroeste(destino_lat, destino_lon):
        return NOROESTE_INTERIOR
    if _coord_em_oeste(destino_lat, destino_lon):
        return BR277_OESTE
    if _coord_em_campos_gerais(destino_lat, destino_lon) or _coord_em_campos_gerais(origem_lat, origem_lon):
        return CAMPOS_GERAIS

    if distancia_rodoviaria_km >= 180 and float(destino_lon) <= -51.0:
        return BR277_OESTE
    return CORREDOR_PADRAO


def classificar_corredor_fino(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
    corredor_macro: str,
    refs_predominantes: Optional[List[str]] = None,
    route_result: Optional[Any] = None,
) -> str:
    """
    Classifica o corredor fino quando a rota justifica.
    Prioridade: refs predominantes -> geometria/segmentos -> municipio destino -> bbox/radius.
    """
    refs = _normalize_refs(refs_predominantes or getattr(route_result, "refs_predominantes", None))
    ref_set = set(refs)
    destino_municipio = inferir_municipio_por_coordenada(destino_lat, destino_lon, raio_max_km=42.0)
    origem_municipio = inferir_municipio_por_coordenada(origem_lat, origem_lon, raio_max_km=42.0)
    destino_nome = destino_municipio.nome_norm if destino_municipio else ""
    origem_nome = origem_municipio.nome_norm if origem_municipio else ""

    if ref_set:
        for spec in FINE_SPECS:
            if spec.macro != corredor_macro:
                continue
            if not set(spec.refs).intersection(ref_set):
                continue
            if destino_nome in spec.municipios or origem_nome in spec.municipios:
                return spec.fino
        for spec in FINE_SPECS:
            if spec.macro != corredor_macro:
                continue
            if not set(spec.refs).intersection(ref_set):
                continue
            if _near_spec(destino_lat, destino_lon, spec) or _near_spec(origem_lat, origem_lon, spec):
                return spec.fino

    if corredor_macro == BR277_LITORAL and _route_has_serra_segment(route_result):
        for spec in FINE_SPECS:
            if spec.macro == BR277_LITORAL and (destino_nome in spec.municipios or _near_spec(destino_lat, destino_lon, spec)):
                return spec.fino

    if destino_nome in _FINE_BY_NAME:
        return _FINE_BY_NAME[destino_nome].fino
    if origem_nome in _FINE_BY_NAME and corredor_macro == _FINE_BY_NAME[origem_nome].macro:
        return _FINE_BY_NAME[origem_nome].fino

    for spec in FINE_SPECS:
        if spec.macro != corredor_macro:
            continue
        if _near_spec(destino_lat, destino_lon, spec) or _near_spec(origem_lat, origem_lon, spec):
            return spec.fino

    return CORREDOR_FINO_PADRAO


def inferir_atributos_rota(
    route_result: Optional[Any],
    corredor_macro: str,
    corredor_fino: str,
) -> dict:
    """
    Infere atributos da rota que influenciam a estimativa: serra, pedagio e urbano.
    """
    refs = _normalize_refs(getattr(route_result, "refs_predominantes", None))
    out = {
        "pedagio_presente": False,
        "travessia_urbana_presente": False,
        "serra_presente": False,
        "refs_predominantes": refs,
    }

    if corredor_fino in _FINE_SERRA:
        out["serra_presente"] = True
    elif corredor_macro == BR277_LITORAL and _route_has_serra_segment(route_result):
        out["serra_presente"] = True

    if corredor_macro in _MACRO_PEDAGIO or refs and any(ref in _LITORAL_REFS | _NORTE_REFS | _OESTE_REFS for ref in refs):
        out["pedagio_presente"] = True

    urban_distance_km = 0.0
    if route_result:
        for step in getattr(route_result, "steps", []) or []:
            step_refs = _normalize_refs(step.get("road_refs") or [step.get("ref"), step.get("name")])
            if step_refs:
                continue
            name_norm = _normalize_text(step.get("name"))
            if any(token in name_norm for token in _URBAN_NAME_HINTS):
                urban_distance_km += float(step.get("distance") or 0) / 1000.0
    if corredor_fino in _FINE_URBANO or urban_distance_km >= 8.0 or (route_result and float(getattr(route_result, "distance_km", 0) or 0) <= 70.0):
        out["travessia_urbana_presente"] = True

    return out
