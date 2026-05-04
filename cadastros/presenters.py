def _status_label(is_active):
    return "Ativo" if is_active else "Inativo"


def _actions(edit_url="#", delete_url="#"):
    return [
        {"label": "Editar", "href": edit_url, "variant": "secondary"},
        {"label": "Desativar", "href": delete_url, "variant": "danger"},
    ]


def apresentar_unidade_card(unidade, edit_url="#", delete_url="#"):
    return {
        "title": unidade.nome,
        "subtitle": unidade.sigla or "Sem sigla",
        "status": _status_label(unidade.ativa),
        "meta": [
            {"label": "Sigla", "value": unidade.sigla or "-"},
            {"label": "Atualizado em", "value": unidade.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_cidade_card(cidade, edit_url="#", delete_url="#"):
    return {
        "title": cidade.nome,
        "subtitle": cidade.uf,
        "status": _status_label(cidade.ativa),
        "meta": [
            {"label": "UF", "value": cidade.uf},
            {"label": "Atualizado em", "value": cidade.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_servidor_card(servidor):
    return {
        "title": servidor.nome,
        "subtitle": servidor.cargo or "Cargo nao informado",
        "status": _status_label(servidor.ativo),
        "meta": [
            {"label": "Matricula", "value": servidor.matricula or "-"},
            {"label": "Unidade", "value": servidor.unidade.sigla if servidor.unidade else "-"},
        ],
        "actions": _actions(),
    }


def apresentar_motorista_card(motorista):
    return {
        "title": motorista.servidor.nome,
        "subtitle": f"CNH {motorista.cnh}" if motorista.cnh else "CNH nao informada",
        "status": _status_label(motorista.ativo),
        "meta": [
            {"label": "Categoria", "value": motorista.categoria_cnh or "-"},
            {
                "label": "Unidade",
                "value": motorista.servidor.unidade.sigla
                if motorista.servidor.unidade
                else "-",
            },
        ],
        "actions": _actions(),
    }


def apresentar_viatura_card(viatura):
    return {
        "title": viatura.placa,
        "subtitle": " ".join(filter(None, [viatura.marca, viatura.modelo])) or "Modelo nao informado",
        "status": _status_label(viatura.ativa),
        "meta": [
            {"label": "Tipo", "value": viatura.tipo or "-"},
            {"label": "Unidade", "value": viatura.unidade.sigla if viatura.unidade else "-"},
        ],
        "actions": _actions(),
    }
