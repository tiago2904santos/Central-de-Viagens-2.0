from django.utils import timezone

from .context import (
    _build_coordenacao_formatada,
    _build_endereco_configuracao,
    _format_data_extenso,
    _get_configuracao_sistema,
    _text_or_empty,
    build_plano_trabalho_document_context,
    get_assinaturas_documento,
)
from .renderer import (
    get_document_template_path,
    render_docx_template_bytes,
)
from .types import DocumentoOficioTipo
from ..plano_trabalho_domain import build_atividades_formatada, build_metas_formatada


def _render_from_context(document, context):
    add_section_heading(document, '1. BREVE CONTEXTUALIZAÇÃO')
    add_multiline_value(document, 'Contexto operacional', context['plano_trabalho']['contexto_operacional'])
    add_label_value(document, 'Número do plano', context.get('numero_plano_trabalho', ''))
    add_label_value(document, 'Destino', context.get('destino', ''))
    add_label_value(document, 'Solicitante', context.get('solicitante', ''))

    add_section_heading(document, '2. METAS ESTABELECIDAS')
    add_multiline_value(document, 'Metas', context.get('metas_formatada', ''))

    add_section_heading(document, '3. ATIVIDADES A SEREM DESENVOLVIDAS')
    add_multiline_value(document, 'Atividades', context.get('atividades_formatada', ''))

    add_section_heading(document, '4. ATUAÇÃO')
    add_label_value(document, 'Dias do evento (extenso)', context.get('dias_evento_extenso', ''))
    add_label_value(document, 'Locais', context.get('locais_formatado', ''))
    add_label_value(document, 'Horário de atendimento', context.get('horario_atendimento', ''))
    add_multiline_value(document, 'Quantidade de servidores', context.get('quantidade_de_servidores', ''))
    if context.get('unidade_movel'):
        add_label_value(document, 'Unidade móvel', context['unidade_movel'])

    add_section_heading(document, '5. VALOR TOTAL DO PLANO')
    add_label_value(document, 'Valor unitário', context.get('valor_unitario', ''))
    add_label_value(document, 'Valor unitário por extenso', context.get('valor_unitario_por_extenso', ''))
    add_label_value(document, 'Valor total', context.get('valor_total', ''))
    add_label_value(document, 'Valor total por extenso', context.get('valor_total_por_extenso', ''))

    add_section_heading(document, '6. RECURSOS NECESSÁRIOS')
    add_multiline_value(document, 'Recursos', context.get('recursos_formatado', ''))

    add_section_heading(document, '7. COORDENADOR DO EVENTO')
    add_multiline_value(document, 'Coordenação', context.get('coordenacao_formatada', ''))

    add_section_heading(document, '8. CONSIDERAÇÕES FINAIS')
    add_label_value(document, 'Data (extenso)', context.get('data_extenso', ''))
    add_label_value(document, 'Divisão', context['institucional'].get('divisao', ''))
    add_label_value(document, 'Unidade', context['institucional'].get('unidade', ''))
    add_label_value(document, 'Unidade (rodapé)', context['institucional'].get('unidade_rodape', ''))
    add_label_value(document, 'Endereço', context['institucional'].get('endereco', ''))
    add_label_value(document, 'Telefone', context['institucional'].get('telefone', ''))
    add_label_value(document, 'Email', context['institucional'].get('email', ''))
    add_label_value(document, 'Sede', context['institucional'].get('sede', ''))
    add_label_value(document, 'Nome da chefia', context['institucional'].get('nome_chefia', ''))
    add_label_value(document, 'Cargo da chefia', context['institucional'].get('cargo_chefia', ''))
    add_signature_blocks(document, context.get('assinaturas') or [])


def render_plano_trabalho_docx(oficio):
    context = build_plano_trabalho_document_context(oficio)

    mapping = {
        'numero_plano_trabalho': context.get('numero_plano_trabalho', ''),
        'destino': context.get('destino', ''),
        'solicitante': context.get('solicitante', ''),
            'objetivo': context.get('plano_trabalho', {}).get('objetivo', ''),
        'metas_formatada': context.get('metas_formatada', ''),
        'atividades_formatada': context.get('atividades_formatada', ''),
        'dias_evento_extenso': context.get('dias_evento_extenso', ''),
        'locais_formatado': context.get('locais_formatado', ''),
        'horario_atendimento': context.get('horario_atendimento', ''),
        'quantidade_de_servidores': context.get('quantidade_de_servidores', ''),
        'unidade_movel': context.get('unidade_movel', ''),
        'valor_unitario': context.get('valor_unitario', ''),
        'valor_unitario_por_extenso': context.get('valor_unitario_por_extenso', ''),
        'valor_total': context.get('valor_total', ''),
        'valor_total_por_extenso': context.get('valor_total_por_extenso', ''),
        'recursos_formatado': context.get('recursos_formatado', ''),
        'coordenacao_formatada': context.get('coordenacao_formatada', ''),
        'coordenação formatada': context.get('coordenacao_formatada', ''),
        'data_extenso': context.get('data_extenso', ''),
        'divisao': context['institucional'].get('divisao', ''),
        'unidade': context['institucional'].get('unidade', ''),
        'unidade_rodape': context['institucional'].get('unidade_rodape', ''),
        'endereco': context['institucional'].get('endereco', ''),
        'telefone': context['institucional'].get('telefone', ''),
        'email': context['institucional'].get('email', ''),
        'sede': context['institucional'].get('sede', ''),
        'nome_chefia': context['institucional'].get('nome_chefia', ''),
        'cargo_chefia': context['institucional'].get('cargo_chefia', ''),
    }
    template_path = get_document_template_path(DocumentoOficioTipo.PLANO_TRABALHO)
    return render_docx_template_bytes(template_path, mapping)


def render_plano_trabalho_model_docx(plano_trabalho):
    """Renderização DOCX a partir da entidade PlanoTrabalho, sem exigir Ofício/Evento."""
    solicitante_texto = ''
    if plano_trabalho.solicitante_id and plano_trabalho.solicitante:
        solicitante_texto = plano_trabalho.solicitante.nome
    elif plano_trabalho.solicitante_outros:
        solicitante_texto = plano_trabalho.solicitante_outros

    atividades_fmt = build_atividades_formatada(plano_trabalho.atividades_codigos)
    metas_exibir = plano_trabalho.metas_formatadas or build_metas_formatada(plano_trabalho.atividades_codigos)
    coordenacao_texto = _build_coordenacao_formatada(plano_trabalho)
    config = _get_configuracao_sistema()
    data_extenso = _format_data_extenso(timezone.localdate())
    evento_relacionado = plano_trabalho.get_evento_relacionado()
    contexto_operacional = ' | '.join(
        [
            part
            for part in [
                _text_or_empty(evento_relacionado.titulo if evento_relacionado else ''),
                _text_or_empty(plano_trabalho.oficios_relacionados_display),
                _text_or_empty(plano_trabalho.destinos_formatados_display),
            ]
            if part
        ]
    )

    context = {
        'plano_trabalho': {
            'contexto_operacional': contexto_operacional,
        },
        'institucional': {
            'divisao': _text_or_empty(config.divisao if config else ''),
            'unidade': _text_or_empty(config.unidade if config else ''),
            'unidade_rodape': _text_or_empty(config.unidade if config else ''),
            'endereco': _build_endereco_configuracao(config),
            'telefone': _text_or_empty(getattr(config, 'telefone_formatado', '') if config else ''),
            'email': _text_or_empty(config.email if config else ''),
            'sede': _text_or_empty(getattr(config, 'sede', '') if config else ''),
            'nome_chefia': _text_or_empty(getattr(config, 'nome_chefia', '') if config else ''),
            'cargo_chefia': _text_or_empty(getattr(config, 'cargo_chefia', '') if config else ''),
        },
        'numero_plano_trabalho': plano_trabalho.numero_formatado,
        'destino': plano_trabalho.destinos_formatados_display,
        'solicitante': solicitante_texto,
        'metas_formatada': metas_exibir,
        'atividades_formatada': atividades_fmt,
        'dias_evento_extenso': '',
        'locais_formatado': plano_trabalho.destinos_formatados_display,
        'horario_atendimento': plano_trabalho.horario_atendimento,
        'quantidade_de_servidores': str(plano_trabalho.quantidade_servidores or ''),
        'unidade_movel': '',
        'valor_total': '',
        'valor_total_por_extenso': '',
        'valor_unitario': '',
        'valor_unitario_por_extenso': '',
        'recursos_formatado': plano_trabalho.recursos_texto,
        'coordenacao_formatada': coordenacao_texto,
        'data_extenso': data_extenso,
        'assinaturas': get_assinaturas_documento(DocumentoOficioTipo.PLANO_TRABALHO.value),
    }
    mapping = {
        'numero_plano_trabalho': context.get('numero_plano_trabalho', ''),
        'destino': context.get('destino', ''),
        'solicitante': context.get('solicitante', ''),
        'metas_formatada': context.get('metas_formatada', ''),
        'atividades_formatada': context.get('atividades_formatada', ''),
        'dias_evento_extenso': context.get('dias_evento_extenso', ''),
        'locais_formatado': context.get('locais_formatado', ''),
        'horario_atendimento': context.get('horario_atendimento', ''),
        'quantidade_de_servidores': context.get('quantidade_de_servidores', ''),
        'unidade_movel': context.get('unidade_movel', ''),
        'valor_unitario': context.get('valor_unitario', ''),
        'valor_unitario_por_extenso': context.get('valor_unitario_por_extenso', ''),
        'valor_total': context.get('valor_total', ''),
        'valor_total_por_extenso': context.get('valor_total_por_extenso', ''),
        'recursos_formatado': context.get('recursos_formatado', ''),
        'coordenacao_formatada': context.get('coordenacao_formatada', ''),
        'coordenação formatada': context.get('coordenacao_formatada', ''),
        'data_extenso': context.get('data_extenso', ''),
        'divisao': context['institucional'].get('divisao', ''),
        'unidade': context['institucional'].get('unidade', ''),
        'unidade_rodape': context['institucional'].get('unidade_rodape', ''),
        'endereco': context['institucional'].get('endereco', ''),
        'telefone': context['institucional'].get('telefone', ''),
        'email': context['institucional'].get('email', ''),
        'sede': context['institucional'].get('sede', ''),
        'nome_chefia': context['institucional'].get('nome_chefia', ''),
        'cargo_chefia': context['institucional'].get('cargo_chefia', ''),
    }
    template_path = get_document_template_path(DocumentoOficioTipo.PLANO_TRABALHO)
    return render_docx_template_bytes(template_path, mapping)
