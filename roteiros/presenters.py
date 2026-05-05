from django.urls import reverse


def _format_date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def _format_periodo(roteiro):
    if roteiro.data_inicio and roteiro.data_fim:
        return f"{_format_date(roteiro.data_inicio)} a {_format_date(roteiro.data_fim)}"
    if roteiro.data_inicio:
        return f"A partir de {_format_date(roteiro.data_inicio)}"
    if roteiro.data_fim:
        return f"Até {_format_date(roteiro.data_fim)}"
    return "Não informado"


def _format_cidade_uf(cidade):
    if not cidade:
        return "-"
    uf = cidade.estado.sigla if getattr(cidade, "estado", None) else cidade.uf
    return f"{cidade.nome}/{uf}"


def apresentar_roteiro_card(roteiro):
    quantidade_trechos = getattr(roteiro, "trechos_count", None)
    if quantidade_trechos is None:
        quantidade_trechos = roteiro.trechos.count()

    detail_url = reverse("roteiros:detalhe", args=[roteiro.pk])
    edit_url = reverse("roteiros:editar", args=[roteiro.pk])
    delete_url = reverse("roteiros:excluir", args=[roteiro.pk])

    return {
        "title": roteiro.nome,
        "subtitle": "Trajeto oficial reutilizável",
        "status": "Biblioteca",
        "status_class": "status-chip--active",
        "meta": [
            {"label": "Origem", "value": _format_cidade_uf(roteiro.origem)},
            {"label": "Destino principal", "value": _format_cidade_uf(roteiro.destino)},
            {"label": "Período", "value": _format_periodo(roteiro)},
            {"label": "Trechos", "value": quantidade_trechos},
        ],
        "body": roteiro.descricao or "Roteiro disponível para uso administrativo nos fluxos de viagem.",
        "actions": [
            {"label": "Abrir", "href": detail_url, "variant": "secondary"},
            {"label": "Editar", "href": edit_url, "variant": "secondary"},
            {"label": "Excluir", "href": delete_url, "variant": "danger"},
        ],
    }
