# -*- coding: utf-8 -*-
"""
Estimativa local de distância e duração entre cidades (sem API externa).
Usa coordenadas (latitude/longitude): haversine + fator rodoviário progressivo + velocidade média progressiva.
Tempo cru arredondado para o múltiplo de 5 mais próximo; adicional sugerido por perfil de rota.

Fator rodoviário progressivo (por distância em linha reta):
- até 100 km -> 1.18
- 101 a 250 km -> 1.22
- 251 a 400 km -> 1.27
- acima de 400 km -> 1.34

Velocidade média progressiva:
- base 62 km/h
- +1 km/h a cada 100 km de distância estimada (rodoviária)
- teto máximo 76 km/h

Perfil de rota (heurísticas simples): EIXO_PRINCIPAL, DIAGONAL_LONGA, LITORAL_SERRA, PADRAO.
Usado apenas para sugerir tempo adicional inicial (15/30/45 min).
"""
import math
from decimal import Decimal
from typing import Optional, Union

# Perfis de rota (retorno de classificar_perfil_rota)
PERFIL_EIXO_PRINCIPAL = 'EIXO_PRINCIPAL'
PERFIL_DIAGONAL_LONGA = 'DIAGONAL_LONGA'
PERFIL_LITORAL_SERRA = 'LITORAL_SERRA'
PERFIL_PADRAO = 'PADRAO'

# Constantes de negócio
# Fator rodoviário progressivo por faixa de distância em linha reta (km)
FATOR_ATE_100_KM = Decimal('1.18')
FATOR_101_250_KM = Decimal('1.22')
FATOR_251_400_KM = Decimal('1.27')
FATOR_ACIMA_400_KM = Decimal('1.34')
# Retrocompatibilidade: valor médio (não usar em cálculo novo)
FATOR_RODOVIARIO = Decimal('1.22')

VELOCIDADE_MEDIA_BASE_KMH = 65
VELOCIDADE_MEDIA_TETO_KMH = 78
INCREMENTO_KM = 85  # +1 km/h a cada 90 km
ARREDONDAMENTO_BLOCO_MIN = 5

# Retrocompatibilidade
VELOCIDADE_MEDIA_KMH = VELOCIDADE_MEDIA_BASE_KMH  # 65

ROTA_FONTE_ESTIMATIVA_LOCAL = 'ESTIMATIVA_LOCAL'
ERRO_SEM_COORDENADAS = 'Cidade sem coordenadas para estimativa.'


def arredondar_para_multiplo_5_proximo(minutos: Union[int, float]) -> int:
    """
    Arredonda para o múltiplo de 5 minutos mais próximo (arredondamento neutro).
    Ex.: 362 (6h02) -> 360 (6h00); 363 (6h03) -> 365 (6h05); 367 (6h07) -> 365 (6h05); 368 (6h08) -> 370 (6h10).
    """
    if minutos is None or (isinstance(minutos, (int, float)) and minutos <= 0):
        return 0
    m = float(minutos)
    return int(round(m / ARREDONDAMENTO_BLOCO_MIN) * ARREDONDAMENTO_BLOCO_MIN)


def arredondar_minutos_para_cima_5(minutos: Union[int, float]) -> int:
    """
    Arredonda duração para cima em blocos de 5 minutos.
    Mantido para compatibilidade; o tempo cru usa arredondar_para_multiplo_5_proximo.
    """
    if minutos is None or (isinstance(minutos, (int, float)) and minutos <= 0):
        return 0
    m = float(minutos)
    return int(math.ceil(m / ARREDONDAMENTO_BLOCO_MIN) * ARREDONDAMENTO_BLOCO_MIN)


def minutos_para_hhmm(minutos: Optional[int]) -> str:
    """
    Converte minutos em string HH:MM.
    Ex.: 340 -> '05:40', 65 -> '01:05'.
    """
    if minutos is None:
        return ''
    try:
        n = int(minutos)
    except (TypeError, ValueError):
        return ''
    if n < 0:
        return ''
    h, m = divmod(n, 60)
    return f'{h:02d}:{m:02d}'


def _haversine_km(lat1: Union[Decimal, float], lon1: Union[Decimal, float],
                  lat2: Union[Decimal, float], lon2: Union[Decimal, float]) -> float:
    """
    Distância em linha reta (geodésica) entre dois pontos em km (fórmula de Haversine).
    """
    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)
    R = 6371  # raio da Terra em km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _fator_rodoviario_por_faixa(linha_reta_km: float) -> Decimal:
    """
    Retorna o fator rodoviário conforme a distância em linha reta (km).
    - até 100 km -> 1.18
    - 101 a 250 km -> 1.22
    - 251 a 400 km -> 1.27
    - acima de 400 km -> 1.34
    """
    if linha_reta_km <= 100:
        return FATOR_ATE_100_KM
    if linha_reta_km <= 250:
        return FATOR_101_250_KM
    if linha_reta_km <= 400:
        return FATOR_251_400_KM
    return FATOR_ACIMA_400_KM


def _no_quadrado_litoral_pr(lat: float, lon: float) -> bool:
    """
    Heurística: ponto dentro da região aproximada do litoral/serra paranaense (ex.: Pontal, Paranaguá, Morretes).
    Usado para classificar perfil LITORAL_SERRA.
    """
    return (-26.2 <= lat <= -25.0) and (-48.95 <= lon <= -48.2)


def classificar_perfil_rota(
    origem_lat: float,
    origem_lon: float,
    destino_lat: float,
    destino_lon: float,
    distancia_linha_reta_km: float,
    distancia_rodoviaria_km: float,
) -> str:
    """
    Classifica o perfil da rota com heurísticas simples (sem ML).

    Heurísticas:
    1) Razão rodoviária/linha_reta: alta -> rota mais torta/diagonal.
    2) Rota longa com razão alta -> DIAGONAL_LONGA.
    3) Rota longa com razão baixa -> EIXO_PRINCIPAL (mais reta).
    4) Um dos extremos no litoral/serra PR e distância relevante -> LITORAL_SERRA.
    5) Caso contrário -> PADRAO.

    Retorno: PERFIL_EIXO_PRINCIPAL | PERFIL_DIAGONAL_LONGA | PERFIL_LITORAL_SERRA | PERFIL_PADRAO
    """
    if distancia_linha_reta_km < 1:
        return PERFIL_PADRAO
    ratio = distancia_rodoviaria_km / distancia_linha_reta_km

    # Litoral/serra: um dos pontos na região litoral PR e trecho não muito curto
    if distancia_linha_reta_km >= 50:
        o_lat, o_lon = float(origem_lat), float(origem_lon)
        d_lat, d_lon = float(destino_lat), float(destino_lon)
        if _no_quadrado_litoral_pr(o_lat, o_lon) or _no_quadrado_litoral_pr(d_lat, d_lon):
            return PERFIL_LITORAL_SERRA

    # Longa e razão alta -> diagonal/torta
    if distancia_linha_reta_km >= 250 and ratio >= 1.25:
        return PERFIL_DIAGONAL_LONGA

    # Longa e razão mais baixa -> eixo principal (mais reta)
    if distancia_linha_reta_km >= 150 and ratio <= 1.21:
        return PERFIL_EIXO_PRINCIPAL

    return PERFIL_PADRAO


def _adicional_sugerido_por_perfil(
    perfil: str,
    distancia_rodoviaria_km: float,
) -> int:
    """
    Retorna o tempo adicional sugerido (min) conforme perfil e distância.
    - Trechos curtos (< 100 km rod): 15 min.
    - Trechos médios (100–250 km): 15 min.
    - Trechos longos (>= 250 km) padrão/eixo: 30 min.
    - Trechos longos diagonal/litoral/serra: 45 min.
    """
    if distancia_rodoviaria_km < 250:
        return 15
    if perfil in (PERFIL_DIAGONAL_LONGA, PERFIL_LITORAL_SERRA):
        return 45
    return 30


def estimar_distancia_duracao(
    origem_lat: Optional[Union[Decimal, float]],
    origem_lon: Optional[Union[Decimal, float]],
    destino_lat: Optional[Union[Decimal, float]],
    destino_lon: Optional[Union[Decimal, float]],
) -> dict:
    """
    Calcula distância rodoviária estimada (km) e duração entre duas coordenadas.

    Regras (tempo cru SEM folga; adicional separado):
    - Fator rodoviário progressivo por linha reta: até 100 km 1.18; 101-250 1.22; 251-400 1.27; >400 1.34
    - distancia_rodoviaria_km = linha_reta_km * fator_por_faixa
    - velocidade progressiva: 62 + floor(dist_rod/100), teto 76 km/h
    - tempo_cru = (distância_rod / velocidade) em minutos, arredondado para múltiplo de 5 MAIS PRÓXIMO
    - perfil_rota = classificar_perfil_rota(...); adicional_sugerido = 15/30/45 por perfil e distância (editável com ±15)
    - total = tempo_cru + adicional_sugerido
    """
    result = {
        'ok': False,
        'distancia_km': None,
        'duracao_estimada_min': None,
        'duracao_estimada_hhmm': '',
        'tempo_cru_estimado_min': None,
        'tempo_adicional_sugerido_min': None,
        'perfil_rota': None,
        'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
        'erro': '',
    }
    for val in (origem_lat, origem_lon, destino_lat, destino_lon):
        if val is None or val == '' or (isinstance(val, str) and not str(val).strip()):
            result['erro'] = ERRO_SEM_COORDENADAS
            return result
        try:
            float(val)
        except (TypeError, ValueError):
            result['erro'] = ERRO_SEM_COORDENADAS
            return result

    linha_reta_km = _haversine_km(
        origem_lat, origem_lon,
        destino_lat, destino_lon,
    )
    fator = _fator_rodoviario_por_faixa(linha_reta_km)
    dist_rod_km = float(Decimal(str(linha_reta_km)) * fator)
    result['distancia_km'] = Decimal(str(round(dist_rod_km, 2)))

    # Velocidade progressiva: 62 + floor(dist_rod/100), teto 76 km/h
    vel_kmh = min(
        VELOCIDADE_MEDIA_TETO_KMH,
        VELOCIDADE_MEDIA_BASE_KMH + int(dist_rod_km // INCREMENTO_KM),
    )

    # Tempo cru: SOMENTE distância / velocidade, arredondado para múltiplo de 5 mais próximo.
    duracao_base_float = (dist_rod_km / vel_kmh) * 60
    tempo_cru = arredondar_para_multiplo_5_proximo(duracao_base_float)
    result['tempo_cru_estimado_min'] = tempo_cru

    # Perfil de rota e adicional sugerido (heurísticas; usuário pode alterar com ±15).
    perfil = classificar_perfil_rota(
        float(origem_lat), float(origem_lon),
        float(destino_lat), float(destino_lon),
        linha_reta_km, dist_rod_km,
    )
    result['perfil_rota'] = perfil
    adicional_sugerido = _adicional_sugerido_por_perfil(perfil, dist_rod_km)
    result['tempo_adicional_sugerido_min'] = adicional_sugerido

    # Total = cru + adicional (soma exata).
    duracao_total = tempo_cru + adicional_sugerido
    result['duracao_estimada_min'] = duracao_total
    result['duracao_estimada_hhmm'] = minutos_para_hhmm(duracao_total)
    result['ok'] = True
    return result
