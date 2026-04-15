from eventos.services.justificativa import get_primeira_saida_oficio
from django.utils import timezone

from .context import (
    build_ordem_servico_document_context,
    format_document_display,
    format_document_header_display,
    get_assinaturas_documento,
)
from .renderer import (
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


def _format_data_single_extenso(value):
    if not value:
        return ''
    return f'{value.day:02d} de {MESES_PTBR.get(value.month, value.month)} de {value.year}'


def _format_data_periodo_extenso(inicio, fim, *, data_unica=False):
    if not inicio and not fim:
        return ''
    inicio = inicio or fim
    fim = fim or inicio
    if data_unica or inicio == fim:
        return _format_data_single_extenso(inicio)
    if inicio.year == fim.year and inicio.month == fim.month:
        return f'{inicio.day} a {fim.day} de {MESES_PTBR.get(inicio.month, inicio.month)} de {inicio.year}'
    return (
        f'{inicio.day} de {MESES_PTBR.get(inicio.month, inicio.month)} '
        f'a {fim.day} de {MESES_PTBR.get(fim.month, fim.month)} de {fim.year}'
    )


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


def _join_pt_br(parts):
    cleaned = [str(part or '').strip() for part in parts if str(part or '').strip()]
    if not cleaned:
        return ''
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f'{cleaned[0]} e {cleaned[1]}'
    return f"{', '.join(cleaned[:-1])} e {cleaned[-1]}"


def _pluralize_pt_br_token(token):
    raw = str(token or '').strip()
    if not raw:
        return raw

    lower = raw.lower()
    irregular = {
        'escrivão': 'escrivães',
        'alemão': 'alemães',
    }
    if lower in irregular:
        plural = irregular[lower]
    elif lower.endswith('ão'):
        plural = lower[:-2] + 'ões'
    elif lower.endswith(('r', 'z', 's')):
        plural = lower + 'es'
    elif lower.endswith('m'):
        plural = lower[:-1] + 'ns'
    elif lower.endswith('al'):
        plural = lower[:-2] + 'ais'
    elif lower.endswith('el'):
        plural = lower[:-2] + 'eis'
    elif lower.endswith('ol'):
        plural = lower[:-2] + 'ois'
    elif lower.endswith('ul'):
        plural = lower[:-2] + 'uis'
    elif lower.endswith('il'):
        plural = lower[:-2] + 'is'
    else:
        plural = lower + 's'

    if raw[:1].isupper():
        return plural[:1].upper() + plural[1:]
    return plural


def _pluralize_cargo_pt_br(cargo_label, quantidade):
    cargo = str(cargo_label or '').strip()
    if quantidade <= 1 or not cargo:
        return cargo
    partes = cargo.split(' ')
    if not partes:
        return cargo
    partes[0] = _pluralize_pt_br_token(partes[0])
    return ' '.join(partes)


def _build_equipe_deslocamento_ordem(ordem_servico):
    viajantes = list(ordem_servico.get_viajantes_relacionados())
    if not viajantes and ordem_servico.responsaveis:
        return format_document_display(ordem_servico.responsaveis)
    if not viajantes:
        return 'dos servidores designados'

    # Agrupa por cargo com ordenação estável para gerar texto documental previsível.
    groups = {}
    for viajante in sorted(
        viajantes,
        key=lambda item: (
            format_document_display(getattr(getattr(item, 'cargo', None), 'nome', '') or 'servidor').casefold(),
            format_document_display(getattr(item, 'nome', '')).casefold(),
        ),
    ):
        cargo_raw = getattr(getattr(viajante, 'cargo', None), 'nome', '') or 'servidor'
        cargo = format_document_display(cargo_raw)
        groups.setdefault(cargo, []).append(format_document_display(viajante.nome))

    descricoes = []
    for cargo, nomes in groups.items():
        prefixo = 'do(a)' if len(nomes) == 1 else 'dos(as)'
        cargo_formatado = _pluralize_cargo_pt_br(cargo, len(nomes))
        descricoes.append(f"{prefixo} {cargo_formatado} {_join_pt_br(nomes)}")
    return _join_pt_br(descricoes)


def _build_destino_ordem(ordem_servico, context=None):
    destinos = []
    for item in ordem_servico.destinos_json or []:
        if not isinstance(item, dict):
            continue
        cidade = format_document_display(item.get('cidade_nome', ''))
        uf = str(item.get('estado_sigla') or '').strip().upper()
        if cidade and uf:
            destinos.append(f'{cidade}/{uf}')
        elif cidade:
            destinos.append(cidade)
    if destinos:
        return ', '.join(destinos)
    if context:
        return format_document_display(context['ordem_servico']['destinos_texto'])
    return ''


def _build_unidade_abreviado(config, unidade):
    sigla = str(getattr(config, 'sigla_orgao', '') or '').strip().upper()
    if sigla:
        return sigla
    unidade_text = str(unidade or '').strip()
    if not unidade_text:
        return ''
    return ''.join(part[0] for part in unidade_text.split() if part).upper()


def build_ordem_servico_model_template_context(ordem_servico):
    oficio = ordem_servico.oficio if ordem_servico.oficio_id else None
    context = build_ordem_servico_document_context(oficio) if oficio else None
    config = None
    assinatura = {}
    if context:
        assinatura = _get_primary_signature(context)
        config = context.get('configuracao')
    if not config:
        from cadastros.models import ConfiguracaoSistema
        config = ConfiguracaoSistema.get_singleton()
    if not assinatura:
        assinatura = _get_primary_signature({'assinaturas': get_assinaturas_documento(DocumentoOficioTipo.ORDEM_SERVICO.value)})

    unidade = (getattr(config, 'unidade', '') or getattr(config, 'nome_orgao', '') or '').strip()
    divisao = (getattr(config, 'divisao', '') or unidade).strip()
    sede_cidade = (
        getattr(getattr(config, 'cidade_sede_padrao', None), 'nome', '')
        or getattr(config, 'cidade_endereco', '')
        or getattr(config, 'sede', '')
    )
    nome_chefia = assinatura.get('nome') or getattr(config, 'nome_chefia', '')
    cargo_chefia = assinatura.get('cargo') or getattr(config, 'cargo_chefia', '')
    motivo = (
        ordem_servico.motivo_texto
        or getattr(getattr(ordem_servico, 'modelo_motivo', None), 'texto', '')
        or ordem_servico.finalidade
        or ''
    ).strip()
    data_deslocamento = ordem_servico.data_deslocamento
    data_deslocamento_fim = getattr(ordem_servico, 'data_deslocamento_fim', None)
    if not data_deslocamento and oficio:
        primeira_saida = get_primeira_saida_oficio(oficio)
        data_deslocamento = primeira_saida.date() if primeira_saida else None
    if ordem_servico.data_unica and data_deslocamento and not data_deslocamento_fim:
        data_deslocamento_fim = data_deslocamento

    endereco = ''
    if context:
        endereco = context['institucional'].get('endereco', '')
    if not endereco:
        endereco_parts = [
            getattr(config, 'logradouro', ''),
            getattr(config, 'numero', ''),
            getattr(config, 'bairro', ''),
        ]
        endereco = ', '.join(str(part).strip() for part in endereco_parts if str(part).strip())

    return {
        'cargo_chefia': format_document_display(cargo_chefia),
        'data_extenso': _format_data_periodo_extenso(data_deslocamento, data_deslocamento_fim, data_unica=ordem_servico.data_unica),
        'data_atual_extenso': _format_data_single_extenso(timezone.localdate()),
        'destino': _build_destino_ordem(ordem_servico, context),
        'divisao': format_document_header_display(divisao),
        'divisao_capitalize': format_document_display(divisao),
        'equipe_deslocamento': _build_equipe_deslocamento_ordem(ordem_servico),
        'motivo': format_document_display(motivo),
        'nome_chefia': format_document_display(nome_chefia),
        'ordem_de_servico': ordem_servico.numero_formatado,
        'sede': format_document_display(sede_cidade),
        'unidade': format_document_header_display(unidade),
        'unidade_abreviado': _build_unidade_abreviado(config, unidade),
        'email': getattr(config, 'email', '') or '',
        'endereco': format_document_display(endereco),
        'telefone': getattr(config, 'telefone', '') or '',
        'unidade_rodape': format_document_header_display(unidade),
    }


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
    """Renderização DOCX a partir da entidade OrdemServico, usando o modelo institucional."""
    template_path = get_document_template_path(DocumentoOficioTipo.ORDEM_SERVICO)
    mapping = build_ordem_servico_model_template_context(ordem_servico)
    return render_docx_template_bytes(template_path, mapping)
