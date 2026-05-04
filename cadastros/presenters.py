def _actions(edit_url="#", delete_url="#"):
    return [
        {"label": "Editar", "href": edit_url, "variant": "secondary"},
        {"label": "Excluir", "href": delete_url, "variant": "danger"},
    ]


def apresentar_unidade_card(unidade, edit_url="#", delete_url="#"):
    return {
        "title": unidade.nome,
        "subtitle": unidade.sigla or "Sem sigla",
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
        "meta": [
            {"label": "UF", "value": cidade.uf},
            {"label": "Atualizado em", "value": cidade.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_servidor_card(servidor, edit_url="#", delete_url="#"):
    unidade_label = "-"
    if servidor.unidade:
        unidade_label = servidor.unidade.sigla or servidor.unidade.nome
    return {
        "title": servidor.nome,
        "subtitle": servidor.cargo or "Cargo não informado",
        "meta": [
            {"label": "Matrícula", "value": servidor.matricula or "-"},
            {"label": "Unidade", "value": unidade_label},
            {"label": "Atualizado em", "value": servidor.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_motorista_card(motorista, edit_url="#", delete_url="#"):
    subtitle = f"CNH {motorista.cnh}" if motorista.cnh else "CNH não informada"
    unidade_label = "-"
    if motorista.servidor.unidade:
        unidade_label = motorista.servidor.unidade.sigla or motorista.servidor.unidade.nome
    return {
        "title": motorista.servidor.nome,
        "subtitle": subtitle,
        "meta": [
            {"label": "Categoria", "value": motorista.categoria_cnh or "-"},
            {"label": "Unidade", "value": unidade_label},
            {"label": "Atualizado em", "value": motorista.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def _placa_exibicao(placa):
    if not placa:
        return ""
    s = "".join(c for c in str(placa).upper() if c.isalnum())
    if len(s) == 7:
        return f"{s[:3]}-{s[3:]}"
    return str(placa).strip().upper()


def apresentar_viatura_card(viatura, edit_url="#", delete_url="#"):
    marca_modelo = " ".join(filter(None, [viatura.marca, viatura.modelo])) or "Modelo não informado"
    unidade_label = "-"
    if viatura.unidade:
        unidade_label = viatura.unidade.sigla or viatura.unidade.nome
    return {
        "title": _placa_exibicao(viatura.placa),
        "subtitle": marca_modelo,
        "meta": [
            {"label": "Tipo", "value": viatura.tipo or "-"},
            {"label": "Unidade", "value": unidade_label},
            {"label": "Atualizado em", "value": viatura.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }
