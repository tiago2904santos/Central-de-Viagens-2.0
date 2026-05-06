from django.urls import reverse

from core.presenters.actions import build_delete_action
from core.presenters.actions import build_edit_action
from core.presenters.actions import build_open_action
from . import roteiro_logic


def _label_cidade_uf(cidade, estado):
    if cidade:
        uf = cidade.estado.sigla if getattr(cidade, "estado", None) else getattr(cidade, "uf", "")
        return f"{cidade.nome}/{uf}"
    if estado:
        return estado.sigla
    return "—"


def _periodo_resumo(roteiro):
    pontos = [
        p
        for p in [
            getattr(roteiro, "saida_dt", None),
            getattr(roteiro, "chegada_dt", None),
            getattr(roteiro, "retorno_saida_dt", None),
            getattr(roteiro, "retorno_chegada_dt", None),
        ]
        if p
    ]
    if not pontos:
        return "Período a definir"
    inicio = min(pontos)
    fim = max(pontos)
    if inicio.date() == fim.date():
        return f"{inicio:%d/%m/%Y %H:%M} – {fim:%H:%M}"
    return f"{inicio:%d/%m/%Y %H:%M} até {fim:%d/%m/%Y %H:%M}"


def apresentar_roteiro_card(roteiro):
    origem_txt = _label_cidade_uf(roteiro.origem_cidade, roteiro.origem_estado)
    destinos_todos = list(roteiro.destinos.all()) if roteiro.pk else []
    destinos = destinos_todos[:3]
    if destinos:
        destino_txt = ", ".join(_label_cidade_uf(d.cidade, d.estado) for d in destinos)
        if len(destinos_todos) > 3:
            destino_txt += "…"
    else:
        destino_txt = "—"

    detail_url = reverse("roteiros:detalhe", args=[roteiro.pk])
    edit_url = reverse("roteiros:editar", args=[roteiro.pk])
    delete_url = reverse("roteiros:excluir", args=[roteiro.pk])
    qtd = getattr(roteiro, "trechos_count", None)
    if qtd is None:
        qtd = roteiro.trechos.count()

    status = roteiro.get_status_display() if hasattr(roteiro, "get_status_display") else roteiro.status
    status_class = (
        "status-chip--active" if roteiro.status == getattr(roteiro, "STATUS_FINALIZADO", "") else "status-chip--draft"
    )

    return {
        "title": origem_txt + " → " + destino_txt if destino_txt != "—" else (origem_txt or "Roteiro"),
        "subtitle": "Roteiro reutilizável (fluxo legacy)",
        "status": status,
        "status_class": status_class,
        "meta": [
            {"label": "Sede", "value": origem_txt},
            {"label": "Destinos", "value": destino_txt},
            {"label": "Período", "value": _periodo_resumo(roteiro)},
            {"label": "Trechos", "value": str(qtd)},
            {"label": "Diárias", "value": roteiro.quantidade_diarias or "—"},
        ],
        "body": (roteiro.observacoes or "").strip() or "Roteiro cadastrado para reutilização nos documentos.",
        "actions": [build_open_action(detail_url), build_edit_action(edit_url), build_delete_action(delete_url)],
    }


def apresentar_contexto_formulario_roteiro_avulso(
    *,
    evento,
    form,
    obj,
    destinos_atuais,
    trechos_list,
    step3_state,
    route_options,
):
    """Contexto do wizard de roteiro avulso (dict para template); sem HTML."""
    return roteiro_logic._build_roteiro_form_context(
        evento=evento,
        form=form,
        obj=obj,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        step3_state=step3_state,
        route_options=route_options,
    )


def apresentar_pagina_detalhe_roteiro(roteiro, trechos):
    pk = roteiro.pk
    destinos = list(roteiro.destinos.all())
    destinos_detalhe = [
        {"ordem": idx + 1, "label": _label_cidade_uf(d.cidade, d.estado)}
        for idx, d in enumerate(destinos)
    ]
    return {
        "page_title": f"Roteiro #{pk}",
        "page_description": "Resumo do roteiro, trechos e diárias calculadas.",
        "roteiro": roteiro,
        "trechos": trechos,
        "destinos_detalhe": destinos_detalhe,
        "edit_url": reverse("roteiros:editar", args=[pk]),
        "delete_url": reverse("roteiros:excluir", args=[pk]),
        "back_url": reverse("roteiros:index"),
    }
