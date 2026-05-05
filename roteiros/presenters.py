from django.urls import reverse


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
    destinos = list(roteiro.destinos.all()[:3]) if roteiro.pk else []
    if destinos:
        destino_txt = ", ".join(_label_cidade_uf(d.cidade, d.estado) for d in destinos)
        if roteiro.destinos.count() > 3:
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
        "actions": [
            {"label": "Abrir", "href": detail_url, "variant": "secondary"},
            {"label": "Editar", "href": edit_url, "variant": "secondary"},
            {"label": "Excluir", "href": delete_url, "variant": "danger"},
        ],
    }
