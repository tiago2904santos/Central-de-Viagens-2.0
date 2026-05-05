# -*- coding: utf-8 -*-
"""
Estimativa local de distancia e duracao (route-aware quando OSRM disponivel).

Arquitetura em 3 camadas:
1. ETA tecnico (tempo_viagem_estimado_min): comparavel a um roteador.
2. Buffer operacional (buffer_operacional_sugerido_min): planejamento.
3. Tempo total planejado (duracao_estimada_min) = ETA + buffer.
"""
from __future__ import annotations

from decimal import Decimal
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Union

from . import corredores_pr as corredores
from .routing_provider import RouteResult, get_default_routing_provider

logger = logging.getLogger(__name__)

PERFIL_EIXO_PRINCIPAL = "EIXO_PRINCIPAL"
PERFIL_DIAGONAL_LONGA = "DIAGONAL_LONGA"
PERFIL_LITORAL_SERRA = "LITORAL_SERRA"
PERFIL_URBANA_CURTA = "URBANA_CURTA"
PERFIL_PADRAO = "PADRAO"

CORREDOR_LITORAL_CURTO = "LITORAL_CURTO"
CORREDOR_CAMPOS_GERAIS_CURTO = "CAMPOS_GERAIS_CURTO"
CORREDOR_NORTE_NOROESTE = "NORTE_NOROESTE"
CORREDOR_OESTE_BR277 = "OESTE_BR277"
CORREDOR_PADRAO = "PADRAO"

FATOR_ATE_60_KM = Decimal("1.20")
FATOR_61_120_KM = Decimal("1.18")
FATOR_121_250_KM = Decimal("1.17")
FATOR_251_400_KM = Decimal("1.19")
FATOR_401_700_KM = Decimal("1.22")
FATOR_ACIMA_700_KM = Decimal("1.24")
FATOR_RODOVIARIO = Decimal("1.20")

VELOCIDADE_PISO_KMH = 45
VELOCIDADE_TETO_FINAL_KMH = 85
ARREDONDAMENTO_BLOCO_MIN = 5
VELOCIDADE_MEDIA_BASE_KMH = 64
VELOCIDADE_MEDIA_TETO_KMH = 80
VELOCIDADE_MEDIA_KMH = 64

FATOR_CORREDOR = {
    CORREDOR_LITORAL_CURTO: 0.86,
    CORREDOR_CAMPOS_GERAIS_CURTO: 1.00,
    CORREDOR_NORTE_NOROESTE: 1.12,
    CORREDOR_OESTE_BR277: 1.05,
    CORREDOR_PADRAO: 1.00,
}

BUFFER_POR_CORREDOR = {
    CORREDOR_LITORAL_CURTO: 5,
    CORREDOR_CAMPOS_GERAIS_CURTO: 5,
    CORREDOR_NORTE_NOROESTE: 15,
    CORREDOR_OESTE_BR277: 10,
    CORREDOR_PADRAO: 10,
}

BUFFER_POR_FAIXA_DISTANCIA_KM = (
    (60, 15),
    (120, 20),
    (200, 25),
    (300, 35),
    (450, 45),
    (600, 60),
    (None, 75),
)

ROTA_FONTE_OSRM = "OSRM"
ROTA_FONTE_ESTIMATIVA_LOCAL = "ESTIMATIVA_LOCAL"
ERRO_SEM_COORDENADAS = "Cidade sem coordenadas para estimativa."

CONFIANCA_ALTA = "alta"
CONFIANCA_MEDIA = "media"
CONFIANCA_BAIXA = "baixa"

_CORREDOR_LEGADO_PARA_MACRO = {
    CORREDOR_LITORAL_CURTO: corredores.BR277_LITORAL,
    CORREDOR_CAMPOS_GERAIS_CURTO: corredores.CAMPOS_GERAIS,
    CORREDOR_NORTE_NOROESTE: corredores.NOROESTE_INTERIOR,
    CORREDOR_OESTE_BR277: corredores.BR277_OESTE,
    CORREDOR_PADRAO: corredores.CORREDOR_PADRAO,
}

_MACRO_PARA_CORREDOR_LEGADO = {
    corredores.BR277_LITORAL: CORREDOR_LITORAL_CURTO,
    corredores.CAMPOS_GERAIS: CORREDOR_CAMPOS_GERAIS_CURTO,
    corredores.NORTE_CAFE: CORREDOR_NORTE_NOROESTE,
    corredores.NOROESTE_INTERIOR: CORREDOR_NORTE_NOROESTE,
    corredores.BR277_OESTE: CORREDOR_OESTE_BR277,
    corredores.CORREDOR_PADRAO: CORREDOR_PADRAO,
}

FAIXA_ATE_60 = "ate_60"
FAIXA_61_120 = "61_120"
FAIXA_121_250 = "121_250"
FAIXA_251_400 = "251_400"
FAIXA_401_700 = "401_700"
FAIXA_ACIMA_700 = "acima_700"

_ROOT_DIR = Path(__file__).resolve().parents[2]
_CALIBRACAO_PATH = _ROOT_DIR / "data" / "rotas_pr_calibracao.json"

_DEFAULT_AJUSTE_CORREDOR_MACRO_MIN = {
    corredores.BR277_LITORAL: 0,
    corredores.BR277_OESTE: 0,
    corredores.NORTE_CAFE: 0,
    corredores.NOROESTE_INTERIOR: 0,
    corredores.CAMPOS_GERAIS: 0,
    corredores.CORREDOR_PADRAO: 0,
}
_DEFAULT_AJUSTE_CORREDOR_FINO_MIN = {
    corredores.PONTAL_LITORAL: 0,
    corredores.PARANAGUA: 0,
    corredores.MATINHOS: 0,
    corredores.GUARATUBA: 0,
    corredores.PONTA_GROSSA: 0,
    corredores.CASTRO: 0,
    corredores.TELEMACO_BORBA: 0,
    corredores.IRATI: 0,
    corredores.UNIAO_DA_VITORIA: 0,
    corredores.MARINGA: 0,
    corredores.LONDRINA: 0,
    corredores.APUCARANA: 0,
    corredores.JACAREZINHO: 0,
    corredores.CAMPO_MOURAO: 0,
    corredores.PARANAVAI: 0,
    corredores.CIANORTE: 0,
    corredores.UMUARAMA: 0,
    corredores.CRUZEIRO_DO_SUL: 0,
    corredores.PALOTINA: 0,
    corredores.TOLEDO: 0,
    corredores.CASCAVEL: 0,
    corredores.FOZ_DO_IGUACU: 0,
    corredores.GUARAPUAVA: 0,
    corredores.FRANCISCO_BELTRAO: 0,
    corredores.PATO_BRANCO: 0,
    corredores.CORREDOR_FINO_PADRAO: 0,
}
_DEFAULT_AJUSTE_FAIXA_DISTANCIA_MIN = {
    FAIXA_ATE_60: 0,
    FAIXA_61_120: 0,
    FAIXA_121_250: 0,
    FAIXA_251_400: 0,
    FAIXA_401_700: 0,
    FAIXA_ACIMA_700: 0,
}
_DEFAULT_AJUSTE_ATRIBUTOS_MIN = {
    "serra": 0,
    "travessia_urbana": 0,
    "pedagio": 0,
}
_DEFAULT_AJUSTE_REF_PREDOMINANTE_MIN = {
    "BR-277": 0,
    "BR-376": 0,
    "BR-369": 0,
    "BR-487": 0,
    "BR-373": 0,
    "PR-407": 0,
    "PR-160": 0,
    "PR-323": 0,
    "PR-317": 0,
    "PR-483": 0,
}

AJUSTE_CORREDOR_MACRO_MIN = _DEFAULT_AJUSTE_CORREDOR_MACRO_MIN.copy()
AJUSTE_CORREDOR_FINO_MIN = _DEFAULT_AJUSTE_CORREDOR_FINO_MIN.copy()
AJUSTE_FAIXA_DISTANCIA_MIN = _DEFAULT_AJUSTE_FAIXA_DISTANCIA_MIN.copy()
AJUSTE_ATRIBUTOS_MIN = _DEFAULT_AJUSTE_ATRIBUTOS_MIN.copy()
AJUSTE_REF_PREDOMINANTE_MIN = _DEFAULT_AJUSTE_REF_PREDOMINANTE_MIN.copy()


def _merge_adjustments(target: Dict[str, int], values: Optional[dict]) -> None:
    for key, value in (values or {}).items():
        if key in target:
            target[key] = int(round(float(value)))


def recarregar_calibracao_pr() -> None:
    """Recarrega as tabelas de calibracao a partir de data/rotas_pr_calibracao.json."""
    AJUSTE_CORREDOR_MACRO_MIN.clear()
    AJUSTE_CORREDOR_MACRO_MIN.update(_DEFAULT_AJUSTE_CORREDOR_MACRO_MIN)
    AJUSTE_CORREDOR_FINO_MIN.clear()
    AJUSTE_CORREDOR_FINO_MIN.update(_DEFAULT_AJUSTE_CORREDOR_FINO_MIN)
    AJUSTE_FAIXA_DISTANCIA_MIN.clear()
    AJUSTE_FAIXA_DISTANCIA_MIN.update(_DEFAULT_AJUSTE_FAIXA_DISTANCIA_MIN)
    AJUSTE_ATRIBUTOS_MIN.clear()
    AJUSTE_ATRIBUTOS_MIN.update(_DEFAULT_AJUSTE_ATRIBUTOS_MIN)
    AJUSTE_REF_PREDOMINANTE_MIN.clear()
    AJUSTE_REF_PREDOMINANTE_MIN.update(_DEFAULT_AJUSTE_REF_PREDOMINANTE_MIN)
    if not _CALIBRACAO_PATH.exists():
        return
    try:
        payload = json.loads(_CALIBRACAO_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Falha ao carregar calibracao PR em %s: %s", _CALIBRACAO_PATH, exc)
        return
    _merge_adjustments(AJUSTE_CORREDOR_MACRO_MIN, payload.get("ajuste_corredor_macro_min"))
    _merge_adjustments(AJUSTE_CORREDOR_FINO_MIN, payload.get("ajuste_corredor_fino_min"))
    _merge_adjustments(AJUSTE_FAIXA_DISTANCIA_MIN, payload.get("ajuste_faixa_distancia_min"))
    _merge_adjustments(AJUSTE_ATRIBUTOS_MIN, payload.get("ajuste_atributos_min"))
    _merge_adjustments(AJUSTE_REF_PREDOMINANTE_MIN, payload.get("ajuste_ref_predominante_min"))


recarregar_calibracao_pr()


def _faixa_distancia_key(distancia_rodoviaria_km: float) -> str:
    d = float(distancia_rodoviaria_km)
    if d <= 60:
        return FAIXA_ATE_60
    if d <= 120:
        return FAIXA_61_120
    if d <= 250:
        return FAIXA_121_250
    if d <= 400:
        return FAIXA_251_400
    if d <= 700:
        return FAIXA_401_700
    return FAIXA_ACIMA_700


def get_faixa_distancia_key(distancia_rodoviaria_km: float) -> str:
    return _faixa_distancia_key(distancia_rodoviaria_km)


def arredondar_para_multiplo_5_proximo(minutos: Union[int, float]) -> int:
    if minutos is None or (isinstance(minutos, (int, float)) and minutos <= 0):
        return 0
    return int(round(float(minutos) / ARREDONDAMENTO_BLOCO_MIN) * ARREDONDAMENTO_BLOCO_MIN)


def arredondar_minutos_para_cima_5(minutos: Union[int, float]) -> int:
    if minutos is None or (isinstance(minutos, (int, float)) and minutos <= 0):
        return 0
    return int(math.ceil(float(minutos) / ARREDONDAMENTO_BLOCO_MIN) * ARREDONDAMENTO_BLOCO_MIN)


def minutos_para_hhmm(minutos: Optional[int]) -> str:
    if minutos is None:
        return ""
    try:
        valor = int(minutos)
    except (TypeError, ValueError):
        return ""
    if valor < 0:
        return ""
    horas, mins = divmod(valor, 60)
    return f"{horas:02d}:{mins:02d}"


def _haversine_km(
    lat1: Union[Decimal, float],
    lon1: Union[Decimal, float],
    lat2: Union[Decimal, float],
    lon2: Union[Decimal, float],
) -> float:
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def _fator_rodoviario_por_faixa(linha_reta_km: float) -> Decimal:
    if linha_reta_km <= 60:
        return FATOR_ATE_60_KM
    if linha_reta_km <= 120:
        return FATOR_61_120_KM
    if linha_reta_km <= 250:
        return FATOR_121_250_KM
    if linha_reta_km <= 400:
        return FATOR_251_400_KM
    if linha_reta_km <= 700:
        return FATOR_401_700_KM
    return FATOR_ACIMA_700_KM


def _velocidade_base_por_faixa(distancia_rodoviaria_km: float) -> int:
    if distancia_rodoviaria_km <= 60:
        return 48
    if distancia_rodoviaria_km <= 120:
        return 56
    if distancia_rodoviaria_km <= 250:
        return 64
    if distancia_rodoviaria_km <= 400:
        return 70
    if distancia_rodoviaria_km <= 700:
        return 76
    return 80


def _no_quadrado_litoral_pr(lat: float, lon: float) -> bool:
    return (-26.2 <= lat <= -25.0) and (-48.95 <= lon <= -48.2)


def classificar_corredor(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
    distancia_linha_reta_km: float,
    distancia_rodoviaria_km: float,
) -> str:
    """
    Classificacao legado usada no fallback.
    """
    macro = corredores.classificar_corredor_macro(
        origem_lat,
        origem_lon,
        destino_lat,
        destino_lon,
        distancia_linha_reta_km,
        distancia_rodoviaria_km,
        refs_predominantes=None,
        route_result=None,
    )
    return _MACRO_PARA_CORREDOR_LEGADO.get(macro, CORREDOR_PADRAO)


def classificar_perfil_rota(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
    distancia_linha_reta_km: float,
    distancia_rodoviaria_km: float,
) -> str:
    if distancia_linha_reta_km < 1:
        return PERFIL_PADRAO
    ratio = distancia_rodoviaria_km / distancia_linha_reta_km
    if distancia_linha_reta_km < 60:
        return PERFIL_URBANA_CURTA
    if distancia_linha_reta_km >= 50:
        if _no_quadrado_litoral_pr(float(origem_lat), float(origem_lon)) or _no_quadrado_litoral_pr(float(destino_lat), float(destino_lon)):
            return PERFIL_LITORAL_SERRA
    if distancia_linha_reta_km >= 250 and ratio >= 1.25:
        return PERFIL_DIAGONAL_LONGA
    if distancia_linha_reta_km >= 150 and ratio <= 1.21:
        return PERFIL_EIXO_PRINCIPAL
    return PERFIL_PADRAO


def sugerir_buffer_operacional(corredor_macro: str, distancia_km: float = 0) -> int:
    distancia = float(distancia_km or 0)
    for limite, buffer_min in BUFFER_POR_FAIXA_DISTANCIA_KM:
        if limite is None or distancia <= limite:
            return buffer_min
    return 75


def _aplicar_calibracao_eta(
    eta_base_min: float,
    dist_km: float,
    corredor_macro: str,
    corredor_fino: str,
    serra_presente: bool = False,
    travessia_urbana_presente: bool = False,
    pedagio_presente: bool = False,
    ref_predominante: Optional[str] = None,
) -> float:
    eta = max(0.0, float(eta_base_min))
    eta += AJUSTE_CORREDOR_MACRO_MIN.get(corredor_macro, 0)
    eta += AJUSTE_CORREDOR_FINO_MIN.get(corredor_fino, 0)
    eta += AJUSTE_FAIXA_DISTANCIA_MIN.get(_faixa_distancia_key(dist_km), 0)
    if serra_presente:
        eta += AJUSTE_ATRIBUTOS_MIN.get("serra", 0)
    if travessia_urbana_presente:
        eta += AJUSTE_ATRIBUTOS_MIN.get("travessia_urbana", 0)
    if pedagio_presente:
        eta += AJUSTE_ATRIBUTOS_MIN.get("pedagio", 0)
    if ref_predominante:
        ref_norm = str(ref_predominante).strip().upper()
        eta += AJUSTE_REF_PREDOMINANTE_MIN.get(ref_norm, 0)
    return max(0.0, eta)


def calcular_eta_por_rota(
    route_result: RouteResult,
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
) -> tuple[int, str, str, List[str], dict, int]:
    dist_km = float(route_result.distance_km or 0)
    eta_base = float(route_result.duration_min or 0)
    refs = list(route_result.refs_predominantes or [])
    linha_reta = _haversine_km(origem_lat, origem_lon, destino_lat, destino_lon)
    corredor_macro = corredores.classificar_corredor_macro(
        origem_lat,
        origem_lon,
        destino_lat,
        destino_lon,
        linha_reta,
        dist_km,
        refs_predominantes=refs or None,
        route_result=route_result,
    )
    corredor_fino = corredores.classificar_corredor_fino(
        origem_lat,
        origem_lon,
        destino_lat,
        destino_lon,
        corredor_macro,
        refs_predominantes=refs or None,
        route_result=route_result,
    )
    attrs = corredores.inferir_atributos_rota(route_result, corredor_macro, corredor_fino)
    refs_saida = attrs.get("refs_predominantes") or refs
    ref_predominante = refs_saida[0] if refs_saida else None
    eta_ajustado = _aplicar_calibracao_eta(
        eta_base,
        dist_km,
        corredor_macro,
        corredor_fino,
        serra_presente=attrs.get("serra_presente", False),
        travessia_urbana_presente=attrs.get("travessia_urbana_presente", False),
        pedagio_presente=attrs.get("pedagio_presente", False),
        ref_predominante=ref_predominante,
    )
    eta_min = arredondar_para_multiplo_5_proximo(eta_ajustado)
    correcao_final_min = eta_min - arredondar_para_multiplo_5_proximo(eta_base)
    return eta_min, corredor_macro, corredor_fino, list(refs_saida), attrs, correcao_final_min


def calcular_eta_fallback(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
) -> tuple[float, float, int, str, str, str, str, dict]:
    linha_reta_km = _haversine_km(origem_lat, origem_lon, destino_lat, destino_lon)
    fator = _fator_rodoviario_por_faixa(linha_reta_km)
    dist_rod_km = float(Decimal(str(linha_reta_km)) * fator)
    corredor_macro = corredores.classificar_corredor_macro(
        origem_lat,
        origem_lon,
        destino_lat,
        destino_lon,
        linha_reta_km,
        dist_rod_km,
        refs_predominantes=None,
        route_result=None,
    )
    corredor_fino = corredores.classificar_corredor_fino(
        origem_lat,
        origem_lon,
        destino_lat,
        destino_lon,
        corredor_macro,
        refs_predominantes=None,
        route_result=None,
    )
    corredor_legado = _MACRO_PARA_CORREDOR_LEGADO.get(corredor_macro, CORREDOR_PADRAO)
    velocidade_base = _velocidade_base_por_faixa(dist_rod_km)
    tempo_cru_float = (dist_rod_km / velocidade_base) * 60
    fator_corredor = FATOR_CORREDOR.get(corredor_legado, 1.00)
    tempo_viagem_float = tempo_cru_float * fator_corredor
    tempo_viagem_min = arredondar_para_multiplo_5_proximo(tempo_viagem_float)
    perfil = classificar_perfil_rota(origem_lat, origem_lon, destino_lat, destino_lon, linha_reta_km, dist_rod_km)
    attrs = corredores.inferir_atributos_rota(None, corredor_macro, corredor_fino)
    return linha_reta_km, dist_rod_km, tempo_viagem_min, perfil, corredor_legado, corredor_macro, corredor_fino, attrs


def _build_result(
    ok: bool,
    erro: str,
    distancia_linha_reta_km: Optional[float] = None,
    distancia_rodoviaria_km: Optional[float] = None,
    tempo_viagem_estimado_min: Optional[int] = None,
    buffer_operacional_min: Optional[int] = None,
    perfil_rota: Optional[str] = None,
    corredor_legado: Optional[str] = None,
    corredor_macro: Optional[str] = None,
    corredor_fino: Optional[str] = None,
    rota_fonte: str = ROTA_FONTE_ESTIMATIVA_LOCAL,
    fallback_usado: bool = False,
    confianca_estimativa: str = CONFIANCA_BAIXA,
    refs_predominantes: Optional[List[str]] = None,
    pedagio_presente: bool = False,
    travessia_urbana_presente: bool = False,
    serra_presente: bool = False,
    correcao_final_min: int = 0,
) -> dict:
    duracao = int((tempo_viagem_estimado_min or 0) + (buffer_operacional_min or 0))
    dist_rod = float(distancia_rodoviaria_km or 0)
    tempo = tempo_viagem_estimado_min or 0
    velocidade_media = (dist_rod / (tempo / 60)) if tempo else None
    return {
        "ok": ok,
        "erro": erro,
        "distancia_km": Decimal(str(round(dist_rod, 2))) if distancia_rodoviaria_km is not None else None,
        "distancia_linha_reta_km": round(float(distancia_linha_reta_km), 2) if distancia_linha_reta_km is not None else None,
        "distancia_rodoviaria_km": round(dist_rod, 2) if distancia_rodoviaria_km is not None else None,
        "tempo_viagem_estimado_min": tempo_viagem_estimado_min,
        "tempo_viagem_estimado_hhmm": minutos_para_hhmm(tempo_viagem_estimado_min),
        "buffer_operacional_sugerido_min": buffer_operacional_min,
        "duracao_estimada_min": duracao,
        "duracao_estimada_hhmm": minutos_para_hhmm(duracao),
        "velocidade_media_kmh": round(velocidade_media, 1) if velocidade_media is not None else None,
        "perfil_rota": perfil_rota or PERFIL_PADRAO,
        "corredor": corredor_legado,
        "corredor_macro": corredor_macro,
        "corredor_fino": corredor_fino or corredores.CORREDOR_FINO_PADRAO,
        "rota_fonte": rota_fonte,
        "fallback_usado": fallback_usado,
        "confianca_estimativa": confianca_estimativa,
        "refs_predominantes": refs_predominantes or [],
        "pedagio_presente": pedagio_presente,
        "travessia_urbana_presente": travessia_urbana_presente,
        "serra_presente": serra_presente,
        "tempo_cru_estimado_min": tempo_viagem_estimado_min,
        "tempo_adicional_sugerido_min": buffer_operacional_min,
        "correcao_final_min": correcao_final_min,
    }


def estimar_distancia_duracao(
    origem_lat: Optional[Union[Decimal, float]],
    origem_lon: Optional[Union[Decimal, float]],
    destino_lat: Optional[Union[Decimal, float]],
    destino_lon: Optional[Union[Decimal, float]],
) -> dict:
    result = _build_result(ok=False, erro=ERRO_SEM_COORDENADAS)
    for value in (origem_lat, origem_lon, destino_lat, destino_lon):
        if value is None or value == "" or (isinstance(value, str) and not str(value).strip()):
            return result
        try:
            float(value)
        except (TypeError, ValueError):
            return result

    origem_lat_f = float(origem_lat)
    origem_lon_f = float(origem_lon)
    destino_lat_f = float(destino_lat)
    destino_lon_f = float(destino_lon)
    linha_reta_km = _haversine_km(origem_lat_f, origem_lon_f, destino_lat_f, destino_lon_f)

    provider = get_default_routing_provider()
    route_result = None
    if provider:
        try:
            route_result = provider.route(origem_lat_f, origem_lon_f, destino_lat_f, destino_lon_f)
        except Exception as exc:
            logger.debug("Provider de roteamento falhou: %s", exc)

    if route_result and float(route_result.distance_km or 0) > 0:
        eta_min, corredor_macro, corredor_fino, refs, attrs, correcao_final_min = calcular_eta_por_rota(
            route_result,
            origem_lat_f,
            origem_lon_f,
            destino_lat_f,
            destino_lon_f,
        )
        dist_rod_km = float(route_result.distance_km)
        buffer_min = sugerir_buffer_operacional(corredor_macro, dist_rod_km)
        confianca = CONFIANCA_ALTA if route_result.has_annotations and route_result.geometry else CONFIANCA_MEDIA
        return _build_result(
            ok=True,
            erro="",
            distancia_linha_reta_km=linha_reta_km,
            distancia_rodoviaria_km=dist_rod_km,
            tempo_viagem_estimado_min=eta_min,
            buffer_operacional_min=buffer_min,
            perfil_rota=classificar_perfil_rota(origem_lat_f, origem_lon_f, destino_lat_f, destino_lon_f, linha_reta_km, dist_rod_km),
            corredor_legado=_MACRO_PARA_CORREDOR_LEGADO.get(corredor_macro, corredor_macro),
            corredor_macro=corredor_macro,
            corredor_fino=corredor_fino,
            rota_fonte=ROTA_FONTE_OSRM,
            fallback_usado=False,
            confianca_estimativa=confianca,
            refs_predominantes=refs,
            pedagio_presente=attrs.get("pedagio_presente", False),
            travessia_urbana_presente=attrs.get("travessia_urbana_presente", False),
            serra_presente=attrs.get("serra_presente", False),
            correcao_final_min=correcao_final_min,
        )

    if route_result is None and provider:
        logger.debug("Provider indisponivel; usando fallback.")
    (
        linha_reta_km,
        dist_rod_km,
        tempo_viagem_min,
        perfil,
        corredor_legado,
        corredor_macro,
        corredor_fino,
        attrs,
    ) = calcular_eta_fallback(origem_lat_f, origem_lon_f, destino_lat_f, destino_lon_f)
    buffer_min = sugerir_buffer_operacional(corredor_macro, dist_rod_km)
    return _build_result(
        ok=True,
        erro="",
        distancia_linha_reta_km=linha_reta_km,
        distancia_rodoviaria_km=dist_rod_km,
        tempo_viagem_estimado_min=tempo_viagem_min,
        buffer_operacional_min=buffer_min,
        perfil_rota=perfil,
        corredor_legado=corredor_legado,
        corredor_macro=corredor_macro,
        corredor_fino=corredor_fino,
        rota_fonte=ROTA_FONTE_ESTIMATIVA_LOCAL,
        fallback_usado=True,
        confianca_estimativa=CONFIANCA_BAIXA,
        refs_predominantes=[],
        pedagio_presente=attrs.get("pedagio_presente", False),
        travessia_urbana_presente=attrs.get("travessia_urbana_presente", False),
        serra_presente=attrs.get("serra_presente", False),
        correcao_final_min=0,
    )


def estimar_tempo_por_distancia_rodoviaria(
    distancia_rodoviaria_km: Union[float, Decimal],
    perfil_rota: Optional[str] = None,
    corredor: Optional[str] = None,
) -> dict:
    dist_km = float(distancia_rodoviaria_km)
    corredor_uso = corredor if corredor in FATOR_CORREDOR else CORREDOR_PADRAO
    velocidade_base = _velocidade_base_por_faixa(dist_km)
    tempo_base = arredondar_para_multiplo_5_proximo((dist_km / velocidade_base) * 60)
    tempo_viagem_min = arredondar_para_multiplo_5_proximo(tempo_base * FATOR_CORREDOR[corredor_uso])
    buffer_min = sugerir_buffer_operacional(corredor_uso, dist_km)
    total = tempo_viagem_min + buffer_min
    return {
        "tempo_cru_estimado_min": tempo_viagem_min,
        "tempo_adicional_sugerido_min": buffer_min,
        "tempo_viagem_estimado_min": tempo_viagem_min,
        "tempo_viagem_estimado_hhmm": minutos_para_hhmm(tempo_viagem_min),
        "buffer_operacional_sugerido_min": buffer_min,
        "correcao_final_min": 0,
        "duracao_estimada_min": total,
        "duracao_estimada_hhmm": minutos_para_hhmm(total),
        "velocidade_media_kmh": velocidade_base,
        "perfil_rota": perfil_rota or PERFIL_PADRAO,
        "corredor": corredor_uso,
    }
