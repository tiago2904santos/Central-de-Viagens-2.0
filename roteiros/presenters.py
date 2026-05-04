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

    return {
        "title": roteiro.nome,
        "subtitle": f"{_format_cidade_uf(roteiro.origem)} → {_format_cidade_uf(roteiro.destino)}",
        "meta": [
            {"label": "Período", "value": _format_periodo(roteiro)},
            {"label": "Trechos", "value": quantidade_trechos},
            {"label": "Atualizado em", "value": roteiro.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": [
            {"label": "Abrir", "href": "#", "variant": "secondary"},
            {"label": "Editar", "href": "#", "variant": "secondary"},
            {"label": "Excluir", "href": "#", "variant": "danger"},
        ],
    }
