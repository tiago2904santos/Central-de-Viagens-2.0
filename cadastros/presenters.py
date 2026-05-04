def _actions(edit_url="#", delete_url="#"):
    return [
        {"label": "Editar", "href": edit_url, "variant": "secondary"},
        {"label": "Excluir", "href": delete_url, "variant": "danger"},
    ]


def _format_cpf(cpf):
    digits = "".join(c for c in (cpf or "") if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return digits or "-"


def _format_rg(rg):
    raw = "".join(c for c in (rg or "").upper() if c.isalnum())
    if len(raw) >= 8:
        base = raw[:8]
        suffix = raw[8:9]
        masked = f"{base[:2]}.{base[2:5]}.{base[5:8]}"
        return f"{masked}-{suffix}" if suffix else masked
    return raw or "-"


def _format_placa(placa):
    raw = "".join(c for c in (placa or "").upper() if c.isalnum())
    if len(raw) == 7 and raw[3:].isdigit():
        return f"{raw[:3]}-{raw[3:]}"
    return raw


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


def apresentar_cargo_card(cargo, edit_url="#", delete_url="#"):
    return {
        "title": cargo.nome,
        "subtitle": "Cadastro de cargo",
        "meta": [
            {"label": "Atualizado em", "value": cargo.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_combustivel_card(combustivel, edit_url="#", delete_url="#"):
    return {
        "title": combustivel.nome,
        "subtitle": "Cadastro de combustível",
        "meta": [
            {"label": "Atualizado em", "value": combustivel.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_servidor_card(servidor, edit_url="#", delete_url="#"):
    unidade_label = "-"
    if servidor.unidade:
        unidade_label = servidor.unidade.sigla or servidor.unidade.nome
    return {
        "title": servidor.nome,
        "subtitle": servidor.cargo.nome if servidor.cargo else "Cargo não informado",
        "meta": [
            {"label": "CPF", "value": _format_cpf(servidor.cpf)},
            {"label": "RG", "value": _format_rg(servidor.rg)},
            {"label": "Unidade", "value": unidade_label},
            {"label": "Atualizado em", "value": servidor.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_viatura_card(viatura, edit_url="#", delete_url="#"):
    return {
        "title": _format_placa(viatura.placa),
        "subtitle": viatura.modelo or "Modelo não informado",
        "meta": [
            {"label": "Combustível", "value": viatura.combustivel.nome if viatura.combustivel else "-"},
            {"label": "Tipo", "value": viatura.get_tipo_display() if viatura.tipo else "-"},
            {"label": "Atualizado em", "value": viatura.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }
