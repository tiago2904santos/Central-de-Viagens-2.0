from django import template

from cadastros.utils.status import get_status_badge_class, get_status_label
from core.utils.masks import format_rg_display

register = template.Library()


@register.filter(name='status_label')
def status_label_filter(status):
    """Retorna o label do status para exibição."""
    return get_status_label(status)


@register.filter(name='status_badge_class')
def status_badge_class_filter(status):
    """Retorna as classes CSS do badge do status."""
    return get_status_badge_class(status)


@register.filter(name='format_rg')
def format_rg_filter(value):
    """Compatibilidade com templates antigos."""
    return format_rg_display(value)
