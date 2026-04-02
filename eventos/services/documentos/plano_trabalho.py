from decimal import Decimal, InvalidOperation
import re

from django.utils import timezone
from utils.valor_extenso import valor_por_extenso_ptbr

from .context import (
    _build_coordenacao_formatada,
    _build_endereco_configuracao,
    _build_sede_configuracao,
    _format_data_extenso,
    _get_configuracao_sistema,
    _text_or_empty,
    build_plano_trabalho_document_context,
    format_document_display,
    format_document_header_display,
    get_assinaturas_documento,
)
from .renderer import (
    add_label_value,
    add_multiline_value,
    add_section_heading,
    add_signature_blocks,
    get_document_template_path,
    replace_paragraph_text,
    render_docx_template_bytes,
)
from .types import DocumentoOficioTipo
from ...models import EfetivoPlanoTrabalho, PlanoTrabalho
from ..plano_trabalho_domain import (
    build_atividades_formatada,
    build_metas_formatada,
    get_unidade_movel_text,
)


_MESES_PT = (
    '', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
)


def _format_periodo_evento_extenso(data_inicio, data_fim):
    if not data_inicio:
        return ''
    if not data_fim or data_fim == data_inicio:
        return _format_data_extenso(data_inicio)

    d1 = f'{data_inicio.day:02d}'
    d2 = f'{data_fim.day:02d}'
    m1 = _MESES_PT[data_inicio.month] if 1 <= data_inicio.month <= 12 else ''
    m2 = _MESES_PT[data_fim.month] if 1 <= data_fim.month <= 12 else ''

    if data_inicio.year == data_fim.year and data_inicio.month == data_fim.month:
        return f'{d1} a {d2} de {m1} de {data_inicio.year}'

    if data_inicio.year == data_fim.year:
        return f'{d1} de {m1} a {d2} de {m2} de {data_inicio.year}'

    return f'{d1} de {m1} de {data_inicio.year} a {d2} de {m2} de {data_fim.year}'


def _to_decimal_br(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    normalized = raw.replace('R$', '').replace(' ', '')
    if ',' in normalized:
        normalized = normalized.replace('.', '').replace(',', '.')
    try:
        return Decimal(normalized)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_decimal_br(value):
    if value is None:
        return ''
    try:
        dec = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return ''
    return f'{dec.quantize(Decimal("0.01")):.2f}'.replace('.', ',')


def _clean_recursos_texto(value):
    linhas = [str(line).strip() for line in str(value or '').replace('\r', '\n').split('\n')]
    ignore_prefixes = (
        'recursos operacionais, materiais de atendimento, equipamentos de apoio e suporte logístico',
        'escopo previsto:',
        'recursos específicos por atividade:',
        'prever unidade móvel institucional e o suporte operacional associado.',
    )
    itens = []
    seen = set()

    for linha in linhas:
        if not linha:
            continue
        lower = linha.lower()
        if any(lower.startswith(prefix) for prefix in ignore_prefixes):
            continue
        cleaned = re.sub(r'^[\-•\u2022]\s*', '', linha).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        itens.append(cleaned)

    return '\n'.join(f'• {item}' for item in itens)


def _build_efetivo_por_cargo_texto(plano_trabalho, evento_relacionado=None):
    composicao = []
    seen = set()

    if plano_trabalho:
        for item in plano_trabalho.efetivos.select_related('cargo').order_by('cargo__nome'):
            if not item.quantidade:
                continue
            cargo_nome = _text_or_empty(item.cargo.nome if item.cargo_id else '') or 'cargo não informado'
            trecho = f'{int(item.quantidade)} {cargo_nome.lower()}'
            if trecho in seen:
                continue
            seen.add(trecho)
            composicao.append(trecho)

    if not composicao and evento_relacionado:
        for item in EfetivoPlanoTrabalho.objects.filter(evento=evento_relacionado).select_related('cargo').order_by('cargo__nome'):
            if not item.quantidade:
                continue
            cargo_nome = _text_or_empty(item.cargo.nome if item.cargo_id else '') or 'cargo não informado'
            trecho = f'{int(item.quantidade)} {cargo_nome.lower()}'
            if trecho in seen:
                continue
            seen.add(trecho)
            composicao.append(trecho)

    if composicao:
        return ', '.join(composicao)

    if plano_trabalho and plano_trabalho.quantidade_servidores:
        return f'{int(plano_trabalho.quantidade_servidores)} servidor(es)'

    return ''


def _resolve_plano_for_oficio(oficio):
    plano = PlanoTrabalho.objects.filter(oficios=oficio).order_by('-updated_at').first()
    if plano:
        return plano
    plano = PlanoTrabalho.objects.filter(oficio=oficio).order_by('-updated_at').first()
    if plano:
        return plano
    if oficio.evento_id:
        return (
            PlanoTrabalho.objects.filter(evento=oficio.evento)
            .order_by('-updated_at')
            .first()
        )
    return None


def _post_process_plano_doc(document):
    for paragraph in document.paragraphs:
        texto = ''.join(run.text for run in paragraph.runs).strip().lower()
        if texto in {'objetivo / finalidade:', 'objetivo/finalidade:'}:
            replace_paragraph_text(paragraph, '')


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
    add_label_value(document, 'Composição (diárias)', context.get('diarias_x', ''))
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
    add_label_value(document, 'Unidade', format_document_header_display(context['institucional'].get('unidade', '')))
    add_label_value(document, 'Unidade (rodapé)', format_document_display(context['institucional'].get('unidade_rodape', '')))
    add_label_value(document, 'Endereço', context['institucional'].get('endereco', ''))
    add_label_value(document, 'Telefone', context['institucional'].get('telefone', ''))
    add_label_value(document, 'Email', context['institucional'].get('email', ''))
    add_label_value(document, 'Sede', context['institucional'].get('sede', ''))
    add_label_value(document, 'Nome da chefia', context['institucional'].get('nome_chefia', ''))
    add_label_value(document, 'Cargo da chefia', context['institucional'].get('cargo_chefia', ''))
    add_signature_blocks(document, context.get('assinaturas') or [])


def render_plano_trabalho_docx(oficio):
    context = build_plano_trabalho_document_context(oficio)
    plano = _resolve_plano_for_oficio(oficio)
    config = _get_configuracao_sistema()

    evento_relacionado = oficio.evento
    data_inicio_evento = plano.evento_data_inicio if plano and plano.evento_data_inicio else (evento_relacionado.data_inicio if evento_relacionado else None)
    data_fim_evento = plano.evento_data_fim if plano and plano.evento_data_fim else (evento_relacionado.data_fim if evento_relacionado else None)
    dias_evento_extenso = _format_periodo_evento_extenso(data_inicio_evento, data_fim_evento) or context.get('dias_evento_extenso', '')

    quantidade_servidores = _build_efetivo_por_cargo_texto(plano, evento_relacionado) or context.get('quantidade_de_servidores', '')

    diarias_x = (plano.diarias_quantidade if plano else '') or context.get('diarias_x', '')
    valor_unitario = (plano.diarias_valor_unitario if plano else '') or context.get('valor_unitario', '')
    valor_total = (plano.diarias_valor_total if plano else '') or context.get('valor_total', '')
    valor_total_extenso = (
        (plano.valor_diarias_extenso if plano else '')
        or (plano.diarias_valor_extenso if plano else '')
        or context.get('valor_total_por_extenso', '')
    )

    if not valor_total and plano and plano.valor_diarias is not None:
        valor_total = _format_decimal_br(plano.valor_diarias)
    if not valor_total_extenso:
        valor_total_extenso = valor_por_extenso_ptbr(valor_total) if valor_total else ''

    if not valor_unitario and plano and plano.valor_diarias is not None and plano.quantidade_servidores:
        try:
            unit = Decimal(plano.valor_diarias) / Decimal(plano.quantidade_servidores)
            valor_unitario = _format_decimal_br(unit)
        except (InvalidOperation, ZeroDivisionError):
            valor_unitario = ''
    valor_unitario_por_extenso = context.get('valor_unitario_por_extenso', '')
    if not valor_unitario_por_extenso and valor_unitario:
        valor_unitario_por_extenso = valor_por_extenso_ptbr(valor_unitario)

    recursos_formatado = _clean_recursos_texto((plano.recursos_texto if plano else '') or context.get('recursos_formatado', ''))
    assinaturas = context.get('assinaturas') or []
    nome_chefia = context['institucional'].get('nome_chefia', '') or format_document_display(getattr(config, 'nome_chefia', '') if config else '')
    cargo_chefia = context['institucional'].get('cargo_chefia', '') or format_document_display(getattr(config, 'cargo_chefia', '') if config else '')
    sede = context['institucional'].get('sede', '') or _build_sede_configuracao(config)
    if not nome_chefia and assinaturas:
        nome_chefia = format_document_display(assinaturas[0].get('nome'))
    if not cargo_chefia and assinaturas:
        cargo_chefia = format_document_display(assinaturas[0].get('cargo'))
    if not sede:
        sede = context['institucional'].get('unidade', '')

    mapping = {
        'numero_plano_trabalho': context.get('numero_plano_trabalho', ''),
        'destino': format_document_display(context.get('destino', '')),
        'solicitante': format_document_display(context.get('solicitante', '')),
        'objetivo': '',
        'metas_formatada': context.get('metas_formatada', ''),
        'atividades_formatada': context.get('atividades_formatada', ''),
        'dias_evento_extenso': dias_evento_extenso,
        'locais_formatado': format_document_display(context.get('locais_formatado', '')),
        'horario_atendimento': context.get('horario_atendimento', ''),
        'quantidade_de_servidores': quantidade_servidores,
        'unidade_movel': context.get('unidade_movel', ''),
        'diarias_x': diarias_x,
        'valor_unitario': valor_unitario,
        'valor_unitario_por_extenso': valor_unitario_por_extenso,
        'valor_total': valor_total,
        'valor_total_por_extenso': valor_total_extenso,
        'recursos_formatado': recursos_formatado,
        'coordenacao_formatada': context.get('coordenacao_formatada', ''),
        'coordenação formatada': context.get('coordenacao_formatada', ''),
        'data_extenso': context.get('data_extenso', ''),
        'divisao': format_document_header_display(context['institucional'].get('divisao', '')),
        'unidade': format_document_header_display(context['institucional'].get('unidade', '')),
        'unidade_rodape': format_document_display(context['institucional'].get('unidade_rodape', '')),
        'endereco': context['institucional'].get('endereco', ''),
        'telefone': context['institucional'].get('telefone', ''),
        'email': context['institucional'].get('email', ''),
        'sede': sede,
        'nome_chefia': nome_chefia,
        'cargo_chefia': cargo_chefia,
    }
    template_path = get_document_template_path(DocumentoOficioTipo.PLANO_TRABALHO)
    return render_docx_template_bytes(template_path, mapping, post_processor=_post_process_plano_doc)


def render_plano_trabalho_model_docx(plano_trabalho):
    """Renderização DOCX a partir da entidade PlanoTrabalho, sem exigir Ofício/Evento."""
    solicitante_texto = ''
    if plano_trabalho.solicitante_id and plano_trabalho.solicitante:
        solicitante_texto = format_document_display(plano_trabalho.solicitante.nome)
    elif plano_trabalho.solicitante_outros:
        solicitante_texto = format_document_display(plano_trabalho.solicitante_outros)

    atividades_fmt = build_atividades_formatada(plano_trabalho.atividades_codigos)
    metas_exibir = plano_trabalho.metas_formatadas or build_metas_formatada(plano_trabalho.atividades_codigos)
    valor_total_extenso = plano_trabalho.valor_diarias_extenso or plano_trabalho.diarias_valor_extenso or ''
    if not valor_total_extenso and plano_trabalho.valor_diarias is not None:
        valor_total_extenso = valor_por_extenso_ptbr(plano_trabalho.valor_diarias)
    valor_unitario_extenso = ''
    if plano_trabalho.diarias_valor_unitario:
        valor_unitario_extenso = valor_por_extenso_ptbr(plano_trabalho.diarias_valor_unitario)

    coordenacao_texto = _build_coordenacao_formatada(plano_trabalho)
    config = _get_configuracao_sistema()
    data_extenso = _format_data_extenso(timezone.localdate())
    evento_relacionado = plano_trabalho.get_evento_relacionado()
    fallback_context = {}
    if evento_relacionado is not None:
        oficio_referencia = evento_relacionado.oficios.order_by('-updated_at').first()
        if oficio_referencia is not None:
            fallback_context = build_plano_trabalho_document_context(oficio_referencia)

    data_inicio_evento = plano_trabalho.evento_data_inicio or (evento_relacionado.data_inicio if evento_relacionado else None)
    data_fim_evento = plano_trabalho.evento_data_fim or (evento_relacionado.data_fim if evento_relacionado else None)
    dias_evento_extenso = _format_periodo_evento_extenso(data_inicio_evento, data_fim_evento)

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
    objetivo_texto = ''

    diarias_x = plano_trabalho.diarias_quantidade or (
        str(plano_trabalho.quantidade_diarias or '').strip() if plano_trabalho.quantidade_diarias is not None else ''
    )
    valor_total = plano_trabalho.diarias_valor_total or (
        str(plano_trabalho.valor_diarias or '').strip() if plano_trabalho.valor_diarias is not None else ''
    )
    valor_unitario = plano_trabalho.diarias_valor_unitario or ''

    if fallback_context:
        diarias_x = diarias_x or fallback_context.get('diarias_x', '')
        valor_total = valor_total or fallback_context.get('valor_total', '')
        valor_unitario = valor_unitario or fallback_context.get('valor_unitario', '')
        valor_total_extenso = valor_total_extenso or fallback_context.get('valor_total_por_extenso', '')
        valor_unitario_extenso = valor_unitario_extenso or fallback_context.get('valor_unitario_por_extenso', '')
    if not valor_unitario and plano_trabalho.valor_diarias is not None and plano_trabalho.quantidade_servidores:
        try:
            unit = Decimal(plano_trabalho.valor_diarias) / Decimal(plano_trabalho.quantidade_servidores)
            valor_unitario = _format_decimal_br(unit)
        except (InvalidOperation, ZeroDivisionError):
            valor_unitario = ''
    if not valor_total and plano_trabalho.valor_diarias is not None:
        valor_total = _format_decimal_br(plano_trabalho.valor_diarias)
    if not diarias_x:
        diarias_x = '0'
    if not valor_unitario:
        valor_unitario = '0,00'
    if not valor_total:
        valor_total = '0,00'
    if not valor_total_extenso:
        valor_total_extenso = valor_por_extenso_ptbr(valor_total)
    if not valor_unitario_extenso:
        valor_unitario_extenso = valor_por_extenso_ptbr(valor_unitario)

    efetivo_texto = _build_efetivo_por_cargo_texto(plano_trabalho, evento_relacionado)
    recursos_formatado = _clean_recursos_texto(plano_trabalho.recursos_texto)

    context = {
        'plano_trabalho': {
            'contexto_operacional': contexto_operacional,
            'objetivo': objetivo_texto,
        },
        'institucional': {
            'divisao': format_document_header_display(config.divisao if config else ''),
            'unidade': format_document_header_display(config.unidade if config else ''),
            'unidade_rodape': format_document_display(config.unidade if config else ''),
            'endereco': _build_endereco_configuracao(config),
            'telefone': _text_or_empty(getattr(config, 'telefone_formatado', '') if config else ''),
            'email': _text_or_empty(config.email if config else ''),
            'sede': _build_sede_configuracao(config),
            'nome_chefia': format_document_display(getattr(config, 'nome_chefia', '') if config else ''),
            'cargo_chefia': format_document_display(getattr(config, 'cargo_chefia', '') if config else ''),
        },
        'numero_plano_trabalho': plano_trabalho.numero_formatado,
        'destino': format_document_display(plano_trabalho.destinos_formatados_display),
        'solicitante': solicitante_texto,
        'objetivo': objetivo_texto,
        'metas_formatada': metas_exibir,
        'atividades_formatada': atividades_fmt,
        'dias_evento_extenso': dias_evento_extenso,
        'locais_formatado': format_document_display(plano_trabalho.destinos_formatados_display),
        'horario_atendimento': plano_trabalho.horario_atendimento,
        'quantidade_de_servidores': efetivo_texto,
        'unidade_movel': get_unidade_movel_text(plano_trabalho.atividades_codigos),
        'valor_total': valor_total,
        'valor_total_por_extenso': '',
        'diarias_x': diarias_x,
        'valor_unitario': valor_unitario,
        'valor_unitario_por_extenso': valor_unitario_extenso,
        'recursos_formatado': recursos_formatado,
        'coordenacao_formatada': coordenacao_texto,
        'data_extenso': data_extenso,
        'assinaturas': get_assinaturas_documento(DocumentoOficioTipo.PLANO_TRABALHO.value),
    }
    nome_chefia = context['institucional'].get('nome_chefia', '')
    cargo_chefia = context['institucional'].get('cargo_chefia', '')
    sede = context['institucional'].get('sede', '') or context['institucional'].get('unidade', '')
    if not nome_chefia and context['assinaturas']:
        nome_chefia = format_document_display(context['assinaturas'][0].get('nome'))
    if not cargo_chefia and context['assinaturas']:
        cargo_chefia = format_document_display(context['assinaturas'][0].get('cargo'))

    mapping = {
        'numero_plano_trabalho': context.get('numero_plano_trabalho', ''),
        'destino': format_document_display(context.get('destino', '')),
        'solicitante': format_document_display(context.get('solicitante', '')),
        'objetivo': '',
        'metas_formatada': context.get('metas_formatada', ''),
        'atividades_formatada': context.get('atividades_formatada', ''),
        'dias_evento_extenso': context.get('dias_evento_extenso', ''),
        'locais_formatado': format_document_display(context.get('locais_formatado', '')),
        'horario_atendimento': context.get('horario_atendimento', ''),
        'quantidade_de_servidores': context.get('quantidade_de_servidores', ''),
        'unidade_movel': context.get('unidade_movel', ''),
        'diarias_x': context.get('diarias_x', ''),
        'valor_unitario': context.get('valor_unitario', ''),
        'valor_unitario_por_extenso': context.get('valor_unitario_por_extenso', ''),
        'valor_total': context.get('valor_total', ''),
        'valor_total_por_extenso': valor_total_extenso or context.get('valor_total_por_extenso', ''),
        'recursos_formatado': _clean_recursos_texto(context.get('recursos_formatado', '')),
        'coordenacao_formatada': context.get('coordenacao_formatada', ''),
        'coordenação formatada': context.get('coordenacao_formatada', ''),
        'data_extenso': context.get('data_extenso', ''),
        'divisao': format_document_header_display(context['institucional'].get('divisao', '')),
        'unidade': format_document_header_display(context['institucional'].get('unidade', '')),
        'unidade_rodape': format_document_display(context['institucional'].get('unidade_rodape', '')),
        'endereco': format_document_display(context['institucional'].get('endereco', '')),
        'telefone': context['institucional'].get('telefone', ''),
        'email': context['institucional'].get('email', ''),
        'sede': format_document_display(sede),
        'nome_chefia': format_document_display(nome_chefia),
        'cargo_chefia': format_document_display(cargo_chefia),
    }
    template_path = get_document_template_path(DocumentoOficioTipo.PLANO_TRABALHO)
    return render_docx_template_bytes(template_path, mapping, post_processor=_post_process_plano_doc)
