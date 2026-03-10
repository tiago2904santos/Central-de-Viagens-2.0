"""Filtros de template para exibição mascarada consistente."""

from django import template

from core.utils.masks import format_masked_display, format_rg_display

register = template.Library()


@register.filter(name='mask')
def mask(value, mask_name):
    """Aplica uma máscara centralizada por nome."""
    if not mask_name:
        return value
    return format_masked_display(str(mask_name), value)


@register.filter(name='cpf_mask')
def cpf_mask(value):
    return format_masked_display('cpf', value)


@register.filter(name='rg_mask')
def rg_mask(value):
    return format_rg_display(value)


@register.filter(name='phone_mask')
def phone_mask(value):
    return format_masked_display('telefone', value)


@register.filter(name='telefone_mask')
def telefone_mask(value):
    return format_masked_display('telefone', value)


@register.filter(name='cep_mask')
def cep_mask(value):
    return format_masked_display('cep', value)


@register.filter(name='placa_mask')
def placa_mask(value):
    return format_masked_display('placa', value)


@register.filter(name='protocolo_mask')
def protocolo_mask(value):
    return format_masked_display('protocolo', value)
