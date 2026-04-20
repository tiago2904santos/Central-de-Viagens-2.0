from .context import build_oficio_document_context, format_document_display, format_document_header_display
from .renderer import get_document_template_path, render_docx_template_bytes
from .types import DocumentoOficioTipo


ASSUNTO_AUTORIZACAO = 'Solicitação de autorização e concessão de diárias.'
ASSUNTO_CONVALIDACAO = 'Solicitação de convalidação e concessão de diárias.'

DESTINO_FORA_PARANA = 'SESP'
DESTINO_DENTRO_PARANA = 'Gabinete do Delegado Geral Adjunto'


def _get_primary_signature(context):
    return (context.get('assinaturas') or [{}])[0]


def _join_non_empty(parts, separator=' | '):
    return separator.join([part for part in parts if part])


def _build_motorista_formatado(oficio, context):
    motorista_nome = format_document_display(context['motorista']['nome'])
    if not motorista_nome:
        return ''
    if context['motorista']['carona']:
        linhas = [f'{motorista_nome} (carona)']
        if context['motorista']['oficio_formatado']:
            linhas.append(f"Ofício do motorista: {context['motorista']['oficio_formatado']}")
        if context['motorista']['protocolo_formatado']:
            linhas.append(f"Protocolo do motorista: {context['motorista']['protocolo_formatado']}")
        return '\n'.join(linhas)
    return motorista_nome


def _build_custeio_text(oficio, context):
    labels = {
        oficio.CUSTEIO_UNIDADE: 'UNIDADE - DPC (diárias e combustível custeados pela DPC).',
        oficio.CUSTEIO_OUTRA_INSTITUICAO: 'OUTRA INSTITUIÇÃO',
        oficio.CUSTEIO_ONUS_LIMITADOS: 'ÔNUS LIMITADOS AOS PRÓPRIOS VENCIMENTOS',
    }
    linhas = []
    for choice in [
        oficio.CUSTEIO_UNIDADE,
        oficio.CUSTEIO_OUTRA_INSTITUICAO,
        oficio.CUSTEIO_ONUS_LIMITADOS,
    ]:
        marcador = '( X )' if oficio.custeio_tipo == choice else '(   )'
        label = labels.get(choice, choice)
        if choice == oficio.CUSTEIO_OUTRA_INSTITUICAO and choice == oficio.custeio_tipo and oficio.nome_instituicao_custeio:
            label = f'{label}: {oficio.nome_instituicao_custeio}'
        linhas.append(f'{marcador} {label}')
    return '\n'.join(linhas)


def _build_column_lines(items, blank_lines=1):
    lines = []
    cleaned = [str(item or '').strip() for item in items if str(item or '').strip()]
    for index, item in enumerate(cleaned):
        lines.append(item)
        if index < len(cleaned) - 1:
            lines.extend([''] * blank_lines)
    return '\n'.join(lines)


def _build_col_rgcpf(context):
    linhas = []
    for index, viajante in enumerate(context['viajantes']):
        linhas.append(f"RG: {viajante['rg'] or '-'}")
        linhas.append(f"CPF: {viajante['cpf'] or '-'}")
        if index < len(context['viajantes']) - 1:
            linhas.append('')
    return '\n'.join(linhas)


def _get_assunto_for_oficio(oficio):
    if getattr(oficio, 'assunto_tipo', '') == 'CONVALIDACAO':
        return ASSUNTO_CONVALIDACAO
    return ASSUNTO_AUTORIZACAO


def _get_destino_cabecalho_oficio(oficio):
    fora_do_parana = (
        oficio.trechos
        .filter(destino_estado__isnull=False)
        .exclude(destino_estado__sigla='PR')
        .exists()
    )
    return DESTINO_FORA_PARANA if fora_do_parana else DESTINO_DENTRO_PARANA


def _build_col_solicitacao(context):
    return ''


def _is_sede_route(trecho, sede):
    return bool(sede and trecho.get('destino') and trecho.get('destino') == sede)


def _normalize_route_value(value):
    return str(value or '').strip().lower()


def _route_items_equivalent(left, right):
    keys = ('origem', 'destino', 'saida_data', 'saida_hora', 'chegada_data', 'chegada_hora')
    return all(_normalize_route_value(left.get(key)) == _normalize_route_value(right.get(key)) for key in keys)


def _build_route_columns(items):
    saida_lines = []
    chegada_lines = []
    for idx, trecho in enumerate(items):
        origem = format_document_display(trecho.get('origem') or '—')
        destino = format_document_display(trecho.get('destino') or '—')
        saida_lines.append(f"Saída {origem}: {trecho.get('saida_data', '')} {trecho.get('saida_hora', '')}".strip())
        chegada_lines.append(f"Chegada {destino}: {trecho.get('chegada_data', '')} {trecho.get('chegada_hora', '')}".strip())
        if idx < len(items) - 1:
            saida_lines.append('')
            chegada_lines.append('')
    return '\n'.join(saida_lines), '\n'.join(chegada_lines)


def _build_retorno_fallback(context):
    trechos = context['roteiro'].get('trechos') or []
    sede = context['roteiro'].get('sede') or ''
    if not trechos and not sede:
        return {'origem': '', 'destino': ''}
    return {
        'origem': trechos[-1].get('destino') or '',
        'destino': sede,
    }


def _build_retorno_items(context):
    sede = context['roteiro'].get('sede') or ''
    retorno_items = [
        trecho
        for trecho in context['roteiro']['trechos']
        if _is_sede_route(trecho, sede)
    ]
    retorno = context['roteiro']['retorno']
    retorno_explicit = {
        'origem': retorno.get('origem') or '',
        'destino': retorno.get('destino') or '',
        'saida_data': retorno.get('saida_data') or '',
        'saida_hora': retorno.get('saida_hora') or '',
        'chegada_data': retorno.get('chegada_data') or '',
        'chegada_hora': retorno.get('chegada_hora') or '',
    }
    if any(retorno_explicit.values()):
        if retorno_items:
            # Step 3 can persist retorno dates/hours without city labels; inherit them from
            # the last retorno trecho before deduplicating to avoid duplicate trailing rows.
            retorno_explicit['origem'] = retorno_explicit['origem'] or retorno_items[-1].get('origem') or ''
            retorno_explicit['destino'] = retorno_explicit['destino'] or retorno_items[-1].get('destino') or ''
        else:
            # When the return was saved only in the separate block, reuse the last outbound
            # destination as origin and the configured sede as arrival.
            fallback = _build_retorno_fallback(context)
            retorno_explicit['origem'] = retorno_explicit['origem'] or fallback['origem']
            retorno_explicit['destino'] = retorno_explicit['destino'] or fallback['destino']
        duplicated = bool(retorno_items and _route_items_equivalent(retorno_items[-1], retorno_explicit))
        if not duplicated:
            retorno_items.append(retorno_explicit)
    return retorno_items


def _build_roteiro_ida_cols(context):
    sede = context['roteiro'].get('sede') or ''
    ida_items = [
        trecho
        for trecho in context['roteiro']['trechos']
        if not _is_sede_route(trecho, sede)
    ]
    return _build_route_columns(ida_items)


def _build_retorno_cols(context):
    return _build_route_columns(_build_retorno_items(context))


def build_oficio_template_context(oficio):
    context = build_oficio_document_context(oficio)
    assinatura = _get_primary_signature(context)
    ida_saida, ida_chegada = _build_roteiro_ida_cols(context)
    volta_saida, volta_chegada = _build_retorno_cols(context)
    unidade = context['institucional']['unidade'] or context['institucional']['orgao'] or context['institucional']['sigla_orgao']
    return {
        'oficio': context['identificacao']['numero_formatado'],
        'data_do_oficio': context['identificacao']['data_criacao_br'],
        'protocolo': context['identificacao']['protocolo_formatado'],
        'nome_chefia': format_document_display(assinatura.get('nome', '')),
        'cargo_chefia': format_document_display(assinatura.get('cargo', '')),
        'unidade': format_document_display(unidade),
        'unidade_cabecalho': format_document_header_display(unidade),
        'orgao_destino': format_document_display(_get_destino_cabecalho_oficio(oficio)),
        'placa': context['veiculo']['placa_formatada'],
        'viatura': format_document_display(context['veiculo']['modelo'] or context['veiculo']['descricao']),
        'combustivel': format_document_display(context['veiculo']['combustivel']),
        'tipo_viatura': format_document_display(context['veiculo']['tipo_viatura']),
        'motorista_formatado': _build_motorista_formatado(oficio, context),
        'custo': _build_custeio_text(oficio, context),
        'diarias_x': context['diarias']['quantidade'],
        'diaria': context['diarias']['valor'],
        'valor_extenso': context['diarias']['valor_extenso'],
        'destinos_bloco': format_document_display(context['roteiro']['destinos_texto']),
        'col_servidor': _build_column_lines([format_document_display(viajante['nome']) for viajante in context['viajantes']], blank_lines=2),
        'col_rgcpf': _build_col_rgcpf(context),
        'col_cargo': _build_column_lines([format_document_display(viajante['cargo']) for viajante in context['viajantes']], blank_lines=2),
        'col_ida_saida': ida_saida,
        'col_ida_chegada': ida_chegada,
        'col_volta_saida': volta_saida,
        'col_volta_chegada': volta_chegada,
        'col_solicitacao': _build_col_solicitacao(context),
        'assunto_linha': _get_assunto_for_oficio(oficio),
        'assunto_oficio': '(Convalidação)' if getattr(oficio, 'assunto_tipo', '') == 'CONVALIDACAO' else '(Autorização)',
        'assunto_termo': 'convalidação' if getattr(oficio, 'assunto_tipo', '') == 'CONVALIDACAO' else 'autorização',
        'armamento': context['veiculo']['porte_transporte_armas'],
        'motivo': context['conteudo']['motivo'],
        'divisao': format_document_header_display(context['institucional']['divisao']),
        'email': context['institucional']['email'],
        'endereco': format_document_display(context['institucional']['endereco']),
        'telefone': context['institucional'].get('telefone', ''),
        'unidade_rodape': format_document_display(unidade),
    }


def render_oficio_docx(oficio):
    template_path = get_document_template_path(DocumentoOficioTipo.OFICIO)
    mapping = build_oficio_template_context(oficio)
    return render_docx_template_bytes(template_path, mapping)
