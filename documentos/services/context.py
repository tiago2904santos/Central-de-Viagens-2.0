from core.utils.masks import format_cep
from core.utils.masks import format_telefone


def _build_endereco_configuracao(config):
    partes = []
    if config.logradouro:
        partes.append(config.logradouro)
    if config.numero:
        partes.append(config.numero)
    if config.bairro:
        partes.append(config.bairro)

    cidade_uf = ""
    if config.cidade_endereco and config.uf:
        cidade_uf = f"{config.cidade_endereco} / {config.uf}"
    else:
        cidade_uf = config.cidade_endereco or config.uf or ""
    if cidade_uf:
        partes.append(cidade_uf)

    cep_formatado = format_cep(config.cep)
    if cep_formatado:
        partes.append(f"CEP {cep_formatado}")
    return ", ".join(partes)


def _build_common_context(config):
    endereco = _build_endereco_configuracao(config)
    telefone = format_telefone(config.telefone)
    email = (config.email or "").strip()

    contatos = []
    if telefone:
        contatos.append(f"Telefone: {telefone}")
    if email:
        contatos.append(f"E-mail: {email}")

    rodape_contato = " | ".join(contatos)
    unidade_rodape = " - ".join(
        [item for item in [config.divisao, config.unidade] if (item or "").strip()],
    ).strip()

    institucional = {
        "endereco": endereco,
        "telefone": telefone,
        "email": email,
        "sede": config.cidade_endereco or "",
        "unidade_rodape": unidade_rodape,
    }

    return {
        "institucional": institucional,
        "rodape_endereco": endereco,
        "rodape_telefone": telefone,
        "rodape_email": email,
        "rodape_contato": rodape_contato,
        "rodape_linha": " | ".join([item for item in [endereco, rodape_contato] if item]),
    }
