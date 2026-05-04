from core.utils.masks import format_cpf as _format_cpf_masked
from core.utils.masks import format_placa as _format_placa_masked
from core.utils.masks import format_rg_display as _format_rg_masked
from core.utils.masks import format_telefone as _format_telefone_masked


def _actions(edit_url="#", delete_url="#"):
    return [
        {"label": "Editar", "href": edit_url, "variant": "secondary"},
        {"label": "Excluir", "href": delete_url, "variant": "danger"},
    ]


def _format_cpf(cpf):
    t = _format_cpf_masked(cpf or "")
    return t if t else "-"


def _format_rg(rg, *, sem_rg=False):
    t = _format_rg_masked(rg or "", sem_rg=sem_rg)
    return t if t else "-"


def _format_placa(placa):
    t = _format_placa_masked(placa or "")
    return t if t else "-"


def _format_telefone(tel):
    t = _format_telefone_masked(tel or "")
    return t if t else "—"


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
            {"label": "RG", "value": _format_rg(servidor.rg, sem_rg=servidor.sem_rg)},
            {"label": "Telefone", "value": _format_telefone(servidor.telefone)},
            {"label": "Unidade", "value": unidade_label},
            {"label": "Atualizado em", "value": servidor.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def _motoristas_label(viatura):
    lista = list(viatura.motoristas.all())
    if not lista:
        return "Nenhum motorista vinculado"
    return ", ".join(s.nome for s in lista)


def apresentar_viatura_card(viatura, edit_url="#", delete_url="#"):
    placa_fmt = _format_placa(viatura.placa)
    modelo = (viatura.modelo or "").strip()
    title = f"{modelo} — {placa_fmt}" if modelo else placa_fmt
    subt = viatura.get_tipo_display() if viatura.tipo else "Tipo não informado"
    return {
        "title": title,
        "subtitle": subt,
        "meta": [
            {"label": "Combustível", "value": viatura.combustivel.nome if viatura.combustivel else "-"},
            {"label": "Tipo", "value": viatura.get_tipo_display() if viatura.tipo else "-"},
            {"label": "Motoristas", "value": _motoristas_label(viatura)},
            {"label": "Atualizado em", "value": viatura.updated_at.strftime("%d/%m/%Y")},
        ],
        "actions": _actions(edit_url, delete_url),
    }


def apresentar_linha_lista_simples_cargo(cargo, edit_url="#", delete_url="#", set_default_url=None):
    row = {
        "title": cargo.nome,
        "badges": [],
        "meta": [
            {"label": "Atualizado em", "value": cargo.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "set_default_url": set_default_url,
    }
    if getattr(cargo, "is_padrao", False):
        row["badges"].append({"text": "Padrão", "variant": "accent"})
        row["set_default_url"] = None
    return row


def apresentar_linha_lista_simples_combustivel(combustivel, edit_url="#", delete_url="#", set_default_url=None):
    row = {
        "title": combustivel.nome,
        "badges": [],
        "meta": [
            {"label": "Atualizado em", "value": combustivel.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
        "set_default_url": set_default_url,
    }
    if getattr(combustivel, "is_padrao", False):
        row["badges"].append({"text": "Padrão", "variant": "accent"})
        row["set_default_url"] = None
    return row


def apresentar_linha_lista_simples_unidade(unidade, edit_url="#", delete_url="#"):
    return {
        "title": unidade.nome,
        "meta": [
            {"label": "Sigla", "value": unidade.sigla or "—"},
            {"label": "Atualizado em", "value": unidade.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
    }


def apresentar_linha_lista_simples_cidade(cidade, edit_url="#", delete_url="#"):
    sigla = cidade.estado.sigla if getattr(cidade, "estado", None) else cidade.uf
    cap = "Sim" if getattr(cidade, "capital", False) else "Não"
    return {
        "title": cidade.nome,
        "meta": [
            {"label": "UF", "value": sigla},
            {"label": "Capital", "value": cap},
            {"label": "Atualizado em", "value": cidade.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
    }


def apresentar_linha_lista_simples_estado(estado, edit_url="#", delete_url="#"):
    cod = str(estado.codigo_ibge) if estado.codigo_ibge is not None else "—"
    return {
        "title": estado.nome,
        "meta": [
            {"label": "Sigla", "value": estado.sigla},
            {"label": "IBGE", "value": cod},
            {"label": "Atualizado em", "value": estado.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
    }


def apresentar_linha_lista_simples_servidor(servidor, edit_url="#", delete_url="#"):
    unidade_label = "—"
    if servidor.unidade:
        unidade_label = servidor.unidade.sigla or servidor.unidade.nome
    cargo_label = servidor.cargo.nome if servidor.cargo else "—"
    return {
        "title": servidor.nome,
        "meta": [
            {"label": "Cargo", "value": cargo_label},
            {"label": "CPF", "value": _format_cpf(servidor.cpf)},
            {"label": "RG", "value": _format_rg(servidor.rg, sem_rg=servidor.sem_rg)},
            {"label": "Telefone", "value": _format_telefone(servidor.telefone)},
            {"label": "Unidade", "value": unidade_label},
            {"label": "Atualizado em", "value": servidor.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
    }


def apresentar_linha_lista_simples_viatura(viatura, edit_url="#", delete_url="#"):
    placa_fmt = _format_placa(viatura.placa)
    modelo = (viatura.modelo or "").strip()
    title = f"{modelo} — {placa_fmt}" if modelo else placa_fmt
    return {
        "title": title,
        "meta": [
            {"label": "Placa", "value": placa_fmt},
            {"label": "Combustível", "value": viatura.combustivel.nome if viatura.combustivel else "—"},
            {"label": "Tipo", "value": viatura.get_tipo_display() if viatura.tipo else "—"},
            {"label": "Motoristas", "value": _motoristas_label(viatura)},
            {"label": "Atualizado em", "value": viatura.updated_at.strftime("%d/%m/%Y")},
        ],
        "edit_url": edit_url,
        "delete_url": delete_url,
    }
