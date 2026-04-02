from django.utils import timezone

from .context import build_justificativa_document_context, format_document_display, format_document_header_display
from .renderer import get_document_template_path, render_docx_template_bytes
from .types import DocumentoOficioTipo


MESES_PTBR = {
    1: 'janeiro',
    2: 'fevereiro',
    3: 'março',
    4: 'abril',
    5: 'maio',
    6: 'junho',
    7: 'julho',
    8: 'agosto',
    9: 'setembro',
    10: 'outubro',
    11: 'novembro',
    12: 'dezembro',
}


def _format_data_extenso(value):
    mes = MESES_PTBR.get(value.month, str(value.month))
    return f'{value.day} de {mes} de {value.year}'


def _get_primary_signature(context):
    return (context.get('assinaturas') or [{}])[0]


def build_justificativa_template_context(oficio):
    context = build_justificativa_document_context(oficio)
    assinatura = _get_primary_signature(context)
    unidade = context['institucional']['unidade'] or context['institucional']['orgao'] or context['institucional']['sigla_orgao']
    return {
        'sede': format_document_display(context['roteiro']['sede']),
        'data_extenso': _format_data_extenso(timezone.localdate()),
        'justificativa': context['conteudo']['justificativa_texto'],
        'assinante_justificativa': format_document_display(assinatura.get('nome', '')),
        'cargo_assinante_justificativa': format_document_display(assinatura.get('cargo', '')),
        'divisao': format_document_header_display(context['institucional']['divisao']),
        'unidade': format_document_header_display(unidade),
        'unidade_rodape': format_document_display(unidade),
        'endereco': format_document_display(context['institucional']['endereco']),
        'email': context['institucional']['email'],
        'telefone': context['institucional'].get('telefone', ''),
    }


def render_justificativa_docx(oficio):
    template_path = get_document_template_path(DocumentoOficioTipo.JUSTIFICATIVA)
    mapping = build_justificativa_template_context(oficio)
    return render_docx_template_bytes(template_path, mapping)
