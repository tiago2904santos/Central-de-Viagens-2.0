from .context import build_plano_trabalho_document_context, _build_coordenacao_formatada, get_assinaturas_documento
from .renderer import (
    add_bullet_list,
    add_label_value,
    add_multiline_value,
    add_section_heading,
    add_signature_blocks,
    add_simple_table,
    create_base_document,
    document_to_bytes,
)
from .types import DocumentoOficioTipo
from ..plano_trabalho_domain import build_atividades_formatada, build_metas_formatada


def render_plano_trabalho_docx(oficio):
    context = build_plano_trabalho_document_context(oficio)
    titulo = (
        f"PLANO DE TRABALHO Nº {context.get('numero_plano_trabalho') or '—'} - "
        f"OFÍCIO Nº {context['identificacao']['numero_formatado'] or 'RASCUNHO'}"
    )
    subtitulo = context['institucional']['orgao'] or context['institucional']['sigla_orgao']
    document = create_base_document(titulo, subtitulo)

    add_section_heading(document, 'Identificação')
    add_label_value(document, 'Número do plano', context.get('numero_plano_trabalho', ''))
    add_label_value(document, 'Evento', context['evento']['titulo'])
    add_label_value(document, 'Protocolo', context['identificacao']['protocolo_formatado'])
    add_label_value(document, 'Período da viagem', context['roteiro']['periodo_viagem']['resumo'])
    add_label_value(document, 'Destino(s)', context.get('destino') or context['roteiro']['destinos_texto'])
    add_label_value(document, 'Solicitante', context.get('solicitante', ''))

    add_multiline_value(document, 'Objetivo / finalidade', context['plano_trabalho']['objetivo'])
    add_label_value(document, 'Local e período', context['plano_trabalho']['local_periodo'])
    add_label_value(document, 'Dias do evento (extenso)', context.get('dias_evento_extenso', ''))
    add_label_value(document, 'Locais', context.get('locais_formatado', '') or context['roteiro']['destinos_texto'])
    add_label_value(document, 'Horário de atendimento', context.get('horario_atendimento', ''))

    if context.get('atividades_formatada'):
        add_multiline_value(document, 'Atividades', context['atividades_formatada'])
    if context.get('metas_formatada'):
        add_multiline_value(document, 'Metas', context['metas_formatada'])
    if context.get('unidade_movel'):
        add_label_value(document, 'Unidade móvel', context['unidade_movel'])

    add_label_value(document, 'Quantidade de servidores', context.get('quantidade_de_servidores', ''))

    participantes_rows = [
        [viajante['nome'], viajante['cargo'], viajante['rg'], viajante['cpf']]
        for viajante in context['viajantes']
    ]
    if participantes_rows:
        add_section_heading(document, 'Participantes / servidores')
        add_simple_table(document, ['Nome', 'Cargo', 'RG', 'CPF'], participantes_rows)

    add_bullet_list(
        document,
        'Roteiro resumido',
        context['plano_trabalho']['roteiro_resumo'],
        empty_text='Roteiro ainda não informado.',
    )

    if context.get('coordenacao_formatada'):
        add_multiline_value(document, 'Coordenação', context['coordenacao_formatada'])

    add_section_heading(document, 'Transporte')
    add_label_value(document, 'Veículo', context['veiculo']['descricao'])
    add_label_value(document, 'Motorista', context['motorista']['descricao'])
    add_label_value(document, 'Sede', context['roteiro']['sede'])

    add_section_heading(document, 'Diárias e custeio')
    add_label_value(document, 'Composição (diárias)', context.get('diarias_x') or context['plano_trabalho']['diarias_resumo'])
    add_label_value(document, 'Valor unitário (1 servidor)', context.get('valor_unitario', ''))
    add_label_value(document, 'Valor unitário por extenso', context.get('valor_unitario_por_extenso', ''))
    add_label_value(document, 'Valor total', context.get('valor_total', '') or context['diarias']['valor'])
    add_label_value(document, 'Valor total por extenso', context.get('valor_total_por_extenso') or context['diarias']['valor_extenso'])
    add_label_value(document, 'Custeio', context['plano_trabalho']['custeio_resumo'])

    if context.get('recursos_formatado'):
        add_multiline_value(document, 'Recursos', context['recursos_formatado'])

    add_section_heading(document, 'Informações institucionais')
    add_label_value(document, 'Data (extenso)', context.get('data_extenso', ''))
    add_label_value(document, 'Órgão', context['institucional']['orgao'] or context['institucional']['sigla_orgao'])
    add_label_value(document, 'Unidade', context['institucional']['unidade'])
    add_label_value(document, 'Divisão', context['institucional']['divisao'])
    add_label_value(document, 'Sede', context['institucional'].get('sede', ''))
    add_label_value(document, 'Endereço', context['institucional']['endereco'])
    add_label_value(document, 'Nome da chefia', context['institucional'].get('nome_chefia', ''))
    add_label_value(document, 'Cargo da chefia', context['institucional'].get('cargo_chefia', ''))

    if context['justificativa']['exigida'] and context['conteudo']['justificativa_texto']:
        add_multiline_value(document, 'Justificativa registrada', context['conteudo']['justificativa_texto'])

    add_signature_blocks(document, context['assinaturas'])
    return document_to_bytes(document)


def render_plano_trabalho_model_docx(plano_trabalho):
    """Renderização DOCX a partir da entidade PlanoTrabalho, sem exigir Ofício/Evento."""
    titulo = f"PLANO DE TRABALHO {plano_trabalho.numero_formatado or f'#{plano_trabalho.pk}'}"
    subtitulo = (
        (plano_trabalho.evento.titulo or '').strip()
        if plano_trabalho.evento_id and plano_trabalho.evento
        else 'Plano de trabalho independente'
    )
    document = create_base_document(titulo, subtitulo)

    add_section_heading(document, 'Identificação')
    add_label_value(document, 'Número', plano_trabalho.numero_formatado)
    add_label_value(document, 'Data de criação', plano_trabalho.data_criacao.strftime('%d/%m/%Y') if plano_trabalho.data_criacao else '')
    add_label_value(document, 'Status', plano_trabalho.get_status_display())
    add_label_value(document, 'Evento', (plano_trabalho.evento.titulo if plano_trabalho.evento_id and plano_trabalho.evento else ''))
    add_label_value(document, 'Ofício', (plano_trabalho.oficio.numero_formatado if plano_trabalho.oficio_id and plano_trabalho.oficio else ''))

    # Solicitante
    solicitante_texto = ''
    if plano_trabalho.solicitante_id and plano_trabalho.solicitante:
        solicitante_texto = plano_trabalho.solicitante.nome
    elif plano_trabalho.solicitante_outros:
        solicitante_texto = plano_trabalho.solicitante_outros
    if solicitante_texto:
        add_label_value(document, 'Solicitante', solicitante_texto)

    add_multiline_value(document, 'Objetivo / finalidade', plano_trabalho.objetivo)
    add_multiline_value(document, 'Locais', plano_trabalho.locais)
    add_label_value(document, 'Horário de atendimento', plano_trabalho.horario_atendimento)
    add_label_value(document, 'Quantidade de servidores', str(plano_trabalho.quantidade_servidores or ''))

    # Atividades formatadas (fallback para string bruta)
    atividades_fmt = build_atividades_formatada(plano_trabalho.atividades_codigos)
    if atividades_fmt:
        add_multiline_value(document, 'Atividades', atividades_fmt)

    # Metas formatadas (preferencia pelo campo armazenado; fallback por catálogo)
    metas_exibir = plano_trabalho.metas_formatadas or build_metas_formatada(plano_trabalho.atividades_codigos)
    if metas_exibir:
        add_multiline_value(document, 'Metas', metas_exibir)

    if plano_trabalho.efetivo_resumo:
        add_multiline_value(document, 'Efetivo', plano_trabalho.efetivo_resumo)
    if plano_trabalho.recursos_texto:
        add_multiline_value(document, 'Recursos', plano_trabalho.recursos_texto)

    # Coordenação
    coordenacao_texto = _build_coordenacao_formatada(plano_trabalho)
    if coordenacao_texto:
        add_multiline_value(document, 'Coordenação', coordenacao_texto)

    if plano_trabalho.observacoes:
        add_multiline_value(document, 'Observações', plano_trabalho.observacoes)

    # Assinaturas configuradas para Plano de Trabalho
    assinaturas = get_assinaturas_documento(DocumentoOficioTipo.PLANO_TRABALHO.value)
    if assinaturas:
        add_signature_blocks(document, assinaturas)

    return document_to_bytes(document)
