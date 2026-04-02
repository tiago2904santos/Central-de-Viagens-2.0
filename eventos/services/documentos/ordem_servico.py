from eventos.services.justificativa import get_primeira_saida_oficio

from .context import build_ordem_servico_document_context, format_document_display, format_document_header_display
from .renderer import (
    add_label_value,
    add_multiline_value,
    add_section_heading,
    create_base_document,
    document_to_bytes,
    get_document_template_path,
    render_docx_template_bytes,
)
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


def _get_primary_signature(context):
    return (context.get('assinaturas') or [{}])[0]


def _format_data_extenso(oficio):
    primeira_saida = get_primeira_saida_oficio(oficio)
    data_inicio = primeira_saida.date() if primeira_saida else None
    data_fim = oficio.retorno_chegada_data or oficio.retorno_saida_data or data_inicio
    if not data_inicio and not data_fim:
        return ''
    data_inicio = data_inicio or data_fim
    data_fim = data_fim or data_inicio
    if data_inicio == data_fim:
        return f'{data_inicio.day} de {MESES_PTBR.get(data_inicio.month, data_inicio.month)} de {data_inicio.year}'
    if data_inicio.year == data_fim.year and data_inicio.month == data_fim.month:
        return f'{data_inicio.day} a {data_fim.day} de {MESES_PTBR.get(data_inicio.month, data_inicio.month)} de {data_inicio.year}'
    return (
        f'{data_inicio.day} de {MESES_PTBR.get(data_inicio.month, data_inicio.month)} '
        f'a {data_fim.day} de {MESES_PTBR.get(data_fim.month, data_fim.month)} de {data_fim.year}'
    )


def _build_ordem_numero(oficio, context):
    if oficio.numero:
        return f'{int(oficio.numero):02d}'
    return context['identificacao']['numero_formatado']


def _build_equipe_deslocamento(context):
    nomes = [viajante['nome'] for viajante in context['viajantes'] if viajante['nome']]
    if not nomes:
        return 'dos servidores designados'
    if len(nomes) == 1:
        return f'do servidor {nomes[0]}'
    return f"dos servidores {', '.join(nomes)}"


def build_ordem_servico_template_context(oficio):
    context = build_ordem_servico_document_context(oficio)
    assinatura = _get_primary_signature(context)
    unidade = context['institucional']['unidade'] or context['institucional']['orgao'] or context['institucional']['sigla_orgao']
    return {
        'cargo_chefia': format_document_display(assinatura.get('cargo', '')),
        'data_extenso': _format_data_extenso(oficio),
        'destino': format_document_display(context['ordem_servico']['destinos_texto']),
        'divisao': format_document_header_display(context['institucional']['divisao'] or unidade),
        'equipe_deslocamento': _build_equipe_deslocamento(context),
        'motivo': context['ordem_servico']['finalidade'].rstrip('.'),
        'nome_chefia': format_document_display(assinatura.get('nome', '')),
        'ordem_de_servico': _build_ordem_numero(oficio, context),
        'sede': format_document_display(context['roteiro']['sede']),
        'unidade': format_document_header_display(unidade),
        'email': context['institucional']['email'],
        'endereco': format_document_display(context['institucional']['endereco']),
        'telefone': context['institucional'].get('telefone', ''),
        'unidade_rodape': format_document_display(unidade),
    }


def render_ordem_servico_docx(oficio):
    template_path = get_document_template_path(DocumentoOficioTipo.ORDEM_SERVICO)
    mapping = build_ordem_servico_template_context(oficio)
    return render_docx_template_bytes(template_path, mapping)


def render_ordem_servico_model_docx(ordem_servico):
    """Renderização DOCX a partir da entidade OrdemServico, sem exigir Ofício/Evento."""
    titulo = f"ORDEM DE SERVIÇO {ordem_servico.numero_formatado or f'#{ordem_servico.pk}'}"
    subtitulo = (
        (ordem_servico.evento.titulo or '').strip()
        if ordem_servico.evento_id and ordem_servico.evento
        else 'Ordem de serviço independente'
    )
    document = create_base_document(titulo, subtitulo)

    add_section_heading(document, 'Identificação')
    add_label_value(document, 'Número', ordem_servico.numero_formatado)
    add_label_value(document, 'Data de criação', ordem_servico.data_criacao.strftime('%d/%m/%Y') if ordem_servico.data_criacao else '')
    add_label_value(document, 'Status', ordem_servico.get_status_display())
    add_label_value(document, 'Evento', (ordem_servico.evento.titulo if ordem_servico.evento_id and ordem_servico.evento else ''))
    add_label_value(document, 'Ofício', (ordem_servico.oficio.numero_formatado if ordem_servico.oficio_id and ordem_servico.oficio else ''))

    add_multiline_value(document, 'Finalidade', ordem_servico.finalidade)
    add_multiline_value(document, 'Responsáveis', ordem_servico.responsaveis)
    add_multiline_value(document, 'Designações', ordem_servico.designacoes)
    add_multiline_value(document, 'Determinações', ordem_servico.determinacoes)
    add_multiline_value(document, 'Observações', ordem_servico.observacoes)

    return document_to_bytes(document)
