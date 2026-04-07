"""Máscaras compartilhadas para backend e templates."""

import re


EMPTY_MASK_DISPLAY = '—'
RG_NAO_POSSUI_CANONICAL = 'NAO POSSUI RG'
RG_NAO_POSSUI_DISPLAY = 'NÃO POSSUI RG'


def only_digits(value):
    """Remove tudo que não for dígito."""
    if value is None:
        return ''
    return re.sub(r'\D', '', str(value))


def normalize_protocolo(value):
    """Protocolo canônico: somente dígitos."""
    return only_digits(value)


def format_protocolo(value):
    """Mascara protocolo no formato XX.XXX.XXX-X."""
    text = str(value or '').strip()
    digits = normalize_protocolo(text)
    if not digits:
        return ''
    if len(digits) != 9:
        return text
    return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}-{digits[8]}'


def format_cpf(value):
    """Mascara CPF no formato 000.000.000-00."""
    text = str(value or '').strip()
    digits = only_digits(text)
    if not digits:
        return ''
    if len(digits) != 11:
        return text
    return f'{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}'


def format_telefone(value):
    """Mascara telefone no formato brasileiro."""
    text = str(value or '').strip()
    digits = only_digits(text)
    if not digits:
        return ''
    if len(digits) == 10:
        return f'({digits[:2]}) {digits[2:6]}-{digits[6:]}'
    if len(digits) == 11:
        return f'({digits[:2]}) {digits[2:7]}-{digits[7:]}'
    return text


def format_phone(value):
    """Alias de compatibilidade para telefone."""
    return format_telefone(value)


def format_cep(value):
    """Mascara CEP no formato 00000-000."""
    text = str(value or '').strip()
    digits = only_digits(text)
    if not digits:
        return ''
    if len(digits) != 8:
        return text
    return f'{digits[:5]}-{digits[5:]}'


def format_rg(value):
    """Mascara RG com 7, 8 ou 9 dígitos."""
    text = str(value or '').strip()
    if not text:
        return ''
    if text.upper() in {RG_NAO_POSSUI_CANONICAL, RG_NAO_POSSUI_DISPLAY.upper()}:
        return RG_NAO_POSSUI_DISPLAY
    digits = only_digits(text)
    if not digits:
        return text
    if len(digits) == 7:
        return f'{digits[0]}.{digits[1:4]}.{digits[4:7]}'
    if len(digits) == 8:
        return f'{digits[0]}.{digits[1:4]}.{digits[4:7]}-{digits[7]}'
    if len(digits) == 9:
        return f'{digits[:2]}.{digits[2:5]}.{digits[5:8]}-{digits[8]}'
    return text


def normalize_placa(value):
    """Normaliza placa removendo separadores e aplicando uppercase."""
    if not value:
        return ''
    return re.sub(r'[\s\-]', '', str(value).strip().upper())


def _normalizar_placa(value):
    """Alias de compatibilidade."""
    return normalize_placa(value)


def format_placa(value):
    """Formata placa antiga com hífen e mantém Mercosul sem separador."""
    text = str(value or '').strip()
    placa = normalize_placa(text)
    if not placa:
        return ''
    if re.match(r'^[A-Z]{3}[0-9]{4}$', placa):
        return f'{placa[:3]}-{placa[3:]}'
    if re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', placa):
        return placa
    return text or placa


MASK_FORMATTERS = {
    'cep': format_cep,
    'cpf': format_cpf,
    'phone': format_telefone,
    'placa': format_placa,
    'protocolo': format_protocolo,
    'rg': format_rg,
    'telefone': format_telefone,
}


def apply_mask(mask_name, value):
    """Aplica a máscara pelo nome. Retorna o valor sem formatação se mask_name for inválido."""
    formatter = MASK_FORMATTERS.get(mask_name)
    if not formatter:
        return str(value or '')
    return formatter(value)


def format_masked_display(mask_name, value, *, empty=EMPTY_MASK_DISPLAY):
    """Aplica máscara para exibição com fallback consistente."""
    if mask_name == 'rg' and str(value or '').strip().upper() in {
        RG_NAO_POSSUI_CANONICAL,
        RG_NAO_POSSUI_DISPLAY.upper(),
    }:
        return RG_NAO_POSSUI_DISPLAY

    text = str(value or '').strip()
    if not text:
        return empty

    formatted = apply_mask(mask_name, text)
    formatted = str(formatted or '').strip()
    return formatted or text or empty


def format_rg_display(value, *, sem_rg=False, empty=EMPTY_MASK_DISPLAY):
    """Exibe RG mascarado, respeitando a flag de ausência."""
    if sem_rg:
        return RG_NAO_POSSUI_DISPLAY
    return format_masked_display('rg', value, empty=empty)
