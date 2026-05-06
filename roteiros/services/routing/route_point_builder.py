# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Tuple

from django.db.models import QuerySet

from cadastros.models import Cidade
from roteiros import roteiro_logic
from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho

from .route_exceptions import RouteCoordinateError, RouteValidationError


def _label_cidade(cidade: Cidade) -> str:
    uf = cidade.estado.sigla if cidade.estado_id else ""
    return f"{cidade.nome}/{uf}"


def _coords_cidade(cidade: Cidade) -> Tuple[float, float]:
    if cidade.latitude is None or cidade.longitude is None:
        raise RouteCoordinateError()
    return (float(cidade.latitude), float(cidade.longitude))


def _append_point(
    out: List[dict],
    *,
    point_id: str,
    cidade: Cidade,
) -> None:
    lat, lng = _coords_cidade(cidade)
    if out and out[-1]["cidade_id"] == cidade.pk:
        return
    out.append(
        {
            "id": point_id,
            "lat": lat,
            "lng": lng,
            "label": _label_cidade(cidade),
            "cidade_id": cidade.pk,
        }
    )


def build_route_points_for_roteiro(roteiro: Roteiro) -> Tuple[List[dict], bool]:
    """
    Monta pontos na ordem correta (origem, destinos, retorno à sede quando aplicável).
    Retorna (pontos, bate_volta_diario_ativo).
    """
    if not roteiro.origem_cidade_id:
        raise RouteValidationError("Roteiro sem cidade de origem.")

    state = roteiro_logic._build_step3_state_from_saved_trechos(roteiro)
    if not (state.get("trechos") or []):
        state = roteiro_logic._build_step3_state_from_estrutura(
            roteiro_logic._estrutura_trechos(roteiro),
            roteiro_logic._destinos_roteiro_para_template(roteiro),
            roteiro.origem_estado_id,
            roteiro.origem_cidade_id,
            "",
        )
    bate = bool(roteiro_logic._infer_step3_bate_volta_diario_from_state(state).get("ativo"))

    sede: Cidade = (
        Cidade.objects.select_related("estado")
        .filter(pk=roteiro.origem_cidade_id)
        .first()
    )
    if not sede:
        raise RouteValidationError("Cidade de origem inválida.")

    destinos_qs: QuerySet[RoteiroDestino] = roteiro.destinos.select_related(
        "cidade", "cidade__estado", "estado"
    ).order_by("ordem", "id")

    points: List[dict] = []

    if bate:
        destino = destinos_qs.first()
        if not destino:
            raise RouteValidationError("Modo bate-volta exige um destino.")
        cidade_dest = destino.cidade
        _append_point(points, point_id=f"origem-{roteiro.pk}", cidade=sede)
        _append_point(points, point_id=f"destino-{destino.pk}", cidade=cidade_dest)
        _append_point(points, point_id=f"retorno-{roteiro.pk}", cidade=sede)
        return points, True

    _append_point(points, point_id=f"origem-{roteiro.pk}", cidade=sede)
    for d in destinos_qs:
        _append_point(points, point_id=f"destino-{d.pk}", cidade=d.cidade)

    retorno = (
        roteiro.trechos.filter(tipo=RoteiroTrecho.TIPO_RETORNO).order_by("ordem", "id").first()
    )
    if retorno and retorno.destino_cidade_id:
        dest_cidade = retorno.destino_cidade
        if dest_cidade:
            _append_point(points, point_id=f"retorno-{retorno.pk}", cidade=dest_cidade)

    if len(points) < 2:
        raise RouteValidationError("São necessários pelo menos dois pontos distintos na rota.")

    return points, False
