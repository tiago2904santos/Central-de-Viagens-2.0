from __future__ import annotations

from datetime import datetime, time
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from .forms import (
    JustificativaForm,
    OrdemServicoForm,
    PlanoTrabalhoForm,
    TermoAutorizacaoEdicaoForm,
    TermoAutorizacaoForm,
)
from .models import (
    Evento,
    EventoTermoParticipante,
    Justificativa,
    ModeloJustificativa,
    OrdemServico,
    Oficio,
    OficioTrecho,
    PlanoTrabalho,
    RoteiroEvento,
    TermoAutorizacao,
)
from .services.diarias import PeriodMarker, TABELA_DIARIAS, calculate_periodized_diarias, formatar_valor_diarias
from .services.documentos import (
    DocumentoFormato,
    DocumentoOficioTipo,
    DocumentGenerationError,
    DocumentRendererUnavailable,
    get_document_generation_status,
    get_document_type_meta,
)
from .services.documentos.renderer import (
    convert_docx_bytes_to_pdf_bytes,
    get_termo_autorizacao_template_path,
)
from .services.documentos.ordem_servico import render_ordem_servico_docx, render_ordem_servico_model_docx
from .services.documentos.plano_trabalho import render_plano_trabalho_docx, render_plano_trabalho_model_docx
from .services.documentos.termo_autorizacao import render_saved_termo_autorizacao_docx
from .termos import TERMO_TEMPLATE_NAMES, build_termo_context, build_termo_preview_payload
from .utils import serializar_viajante_para_autocomplete, serializar_veiculo_para_oficio
from .views import _build_oficio_justificativa_info


SIMULACAO_SESSION_KEY = 'global_simulacao_diarias_last'
STATUS_LABELS = {
    'available': 'Disponivel',
    'pending': 'Pendente',
    'unavailable': 'Indisponivel',
    'not_applicable': 'Nao aplicavel',
    'preenchida': 'Preenchida',
    'nao_exigida': 'Nao exigida',
    'indefinida': 'Aguardando roteiro',
    'indisponivel': 'Indisponivel',
}

OFICIO_STATUS_CARD_META = {
    Oficio.STATUS_RASCUNHO: {'label': 'Rascunho', 'css_class': 'is-rascunho'},
    'ASSINADO': {'label': 'Assinado', 'css_class': 'is-assinado'},
    Oficio.STATUS_FINALIZADO: {'label': 'Finalizado', 'css_class': 'is-finalizado'},
}

DOCUMENT_STATUS_CARD_META = {
    'available': {'label': 'Disponivel', 'css_class': 'is-ready'},
    'pending': {'label': 'Pendente', 'css_class': 'is-pending'},
    'unavailable': {'label': 'Indisponivel', 'css_class': 'is-unavailable'},
    'not_applicable': {'label': 'Nao aplicavel', 'css_class': 'is-muted'},
    'preenchida': {'label': 'Preenchida', 'css_class': 'is-info'},
    'nao_exigida': {'label': 'Nao exigida', 'css_class': 'is-muted'},
    'indefinida': {'label': 'Aguardando roteiro', 'css_class': 'is-muted'},
    'indisponivel': {'label': 'Indisponivel', 'css_class': 'is-unavailable'},
    'pendente': {'label': 'Pendente', 'css_class': 'is-pending'},
}

TERMO_STATUS_CARD_META = {
    TermoAutorizacao.STATUS_RASCUNHO: {'label': 'Rascunho', 'css_class': 'is-rascunho'},
    TermoAutorizacao.STATUS_GERADO: {'label': 'Gerado', 'css_class': 'is-finalizado'},
}

EMPTY_DISPLAY = '-'
OFICIO_CONTEXT_CHOICES = [
    ('EVENTO', 'Com evento'),
    ('AVULSO', 'Sem evento'),
]
OFICIO_VIAGEM_STATUS_CHOICES = [
    ('FUTURA', 'Viagem futura'),
    ('EM_ANDAMENTO', 'Em andamento'),
    ('CONCLUIDA', 'Concluida'),
]
OFICIO_PRESENCE_CHOICES = [
    ('COM', 'Com'),
    ('SEM', 'Sem'),
]
OFICIO_ORDER_BY_CHOICES = [
    ('numero', 'Numero do oficio'),
    ('protocolo', 'Numero do protocolo'),
    ('data_criacao', 'Data de criacao'),
    ('updated_at', 'Data de atualizacao'),
    ('data_evento', 'Data do evento'),
]
OFICIO_ORDER_DIR_CHOICES = [
    ('desc', 'Decrescente'),
    ('asc', 'Crescente'),
]
OFICIO_ORDER_BY_DEFAULT = 'updated_at'
OFICIO_ORDER_DIR_DEFAULT = 'desc'
VIAGEM_STATUS_CARD_META = {
    'FUTURA': {'label': 'Vai acontecer', 'css_class': 'is-trip-future'},
    'EM_ANDAMENTO': {'label': 'Em andamento', 'css_class': 'is-trip-ongoing'},
    'CONCLUIDA': {'label': 'Ja aconteceu', 'css_class': 'is-trip-past'},
    'INDEFINIDA': {'label': 'Sem periodo', 'css_class': 'is-trip-muted'},
}
OFICIO_CARD_THEME_META = {
    'green': {
        'label': 'Concluido',
        'css_class': 'is-tone-green',
        'status_css_class': 'is-finalizado',
    },
    'orange': {
        'label': 'Em andamento',
        'css_class': 'is-tone-orange',
        'status_css_class': 'is-warning',
    },
    'blue': {
        'label': 'Programado',
        'css_class': 'is-tone-blue',
        'status_css_class': 'is-info',
    },
    'yellow': {
        'label': 'Atencao',
        'css_class': 'is-tone-yellow',
        'status_css_class': 'is-pending',
    },
    'red': {
        'label': 'Critico',
        'css_class': 'is-tone-red',
        'status_css_class': 'is-rascunho',
    },
    'gray': {
        'label': 'Rascunho',
        'css_class': 'is-tone-gray',
        'status_css_class': 'is-muted',
    },
}


def _clean(value):
    return str(value or '').strip()


def _parse_int_list(values):
    items = []
    seen = set()
    for value in values or []:
        item = str(value or '').strip()
        if not item.isdigit():
            continue
        number = int(item)
        if number in seen:
            continue
        seen.add(number)
        items.append(number)
    return items


def _parse_choice_list(values, allowed_values):
    items = []
    seen = set()
    allowed = set(allowed_values)
    for value in values or []:
        item = _clean(value).upper()
        if not item or item not in allowed or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _parse_single_choice(value, allowed_values, default):
    item = _clean(value)
    return item if item in set(allowed_values) else default


def _full_route_name(request):
    resolver = request.resolver_match
    if not resolver:
        return ''
    namespace = getattr(resolver, 'namespace', '') or ''
    url_name = getattr(resolver, 'url_name', '') or ''
    return f'{namespace}:{url_name}' if namespace else url_name


def _query_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def _paginate(sequence, page_number, per_page=20):
    paginator = Paginator(sequence, per_page)
    return paginator.get_page(page_number)


def _eventos_choices():
    return Evento.objects.order_by('-data_inicio', 'titulo')


def _append_next(url, next_url):
    if not next_url:
        return url
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}{urlencode({"next": next_url})}'


def _get_safe_return_to(request, default_url=''):
    candidate = _clean(request.POST.get('return_to') or request.GET.get('return_to'))
    if candidate and candidate.startswith('/'):
        return candidate
    return default_url


def _get_context_source(request):
    value = _clean(request.GET.get('context_source') or request.POST.get('context_source')).lower()
    return value if value in {'evento', 'oficio', 'global'} else ''


def _parse_int(value):
    raw = _clean(value)
    if raw.isdigit():
        return int(raw)
    return None


def _label_local(cidade, estado):
    if cidade and estado:
        return f'{cidade.nome}/{estado.sigla}'
    if cidade:
        return cidade.nome
    if estado:
        return estado.sigla
    return '—'


def _oficio_destinos_display(oficio):
    labels = []
    seen = set()
    for trecho in oficio.trechos.all():
        label = _label_local(
            getattr(trecho, 'destino_cidade', None),
            getattr(trecho, 'destino_estado', None),
        )
        if label == '—' or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    if labels:
        return ', '.join(labels)
    return oficio.get_tipo_destino_display() or '—'


def _roteiro_destinos_display(roteiro):
    labels = []
    for destino in roteiro.destinos.all():
        labels.append(_label_local(destino.cidade, destino.estado))
    return ', '.join(labels) if labels else '—'


def _combine_date_time(date_value, time_value, fallback_time):
    if not date_value:
        return None
    return datetime.combine(date_value, time_value or fallback_time)


def _oficio_periodo_display(oficio):
    pontos = []
    for trecho in oficio.trechos.all():
        saida = _combine_date_time(trecho.saida_data, trecho.saida_hora, time.min)
        chegada = _combine_date_time(trecho.chegada_data, trecho.chegada_hora, time.max)
        if saida:
            pontos.append(saida)
        if chegada:
            pontos.append(chegada)
    retorno_saida = _combine_date_time(oficio.retorno_saida_data, oficio.retorno_saida_hora, time.min)
    retorno_chegada = _combine_date_time(oficio.retorno_chegada_data, oficio.retorno_chegada_hora, time.max)
    if retorno_saida:
        pontos.append(retorno_saida)
    if retorno_chegada:
        pontos.append(retorno_chegada)
    if not pontos:
        return 'â€”'
    inicio = min(pontos)
    fim = max(pontos)
    if inicio.date() == fim.date():
        return f'{inicio:%d/%m/%Y} {inicio:%H:%M} - {fim:%H:%M}'
    return f'{inicio:%d/%m/%Y %H:%M} at\u00e9 {fim:%d/%m/%Y %H:%M}'


def _oficio_viajantes_display(oficio):
    viajantes = list(oficio.viajantes.all())
    if not viajantes:
        return 'Nenhum'
    if len(viajantes) == 1:
        return viajantes[0].nome
    if len(viajantes) == 2:
        return f'{viajantes[0].nome} e {viajantes[1].nome}'
    return f'{len(viajantes)} viajantes'


def _oficio_process_status_meta(oficio):
    default_label = getattr(oficio, 'get_status_display', lambda: oficio.status)() or oficio.status or 'â€”'
    meta = OFICIO_STATUS_CARD_META.get(oficio.status, {})
    return {
        'label': meta.get('label', default_label),
        'css_class': meta.get('css_class', 'is-muted'),
    }


def _document_card_status_meta(status_key, fallback_label='â€”'):
    meta = DOCUMENT_STATUS_CARD_META.get(status_key, {})
    return {
        'label': meta.get('label', fallback_label),
        'css_class': meta.get('css_class', 'is-muted'),
    }


def _build_oficio_document_actions(oficio, tipo_documento):
    meta = get_document_type_meta(tipo_documento)
    actions = []
    errors = []
    statuses = []
    for formato in (DocumentoFormato.PDF, DocumentoFormato.DOCX):
        if not meta.supports(formato):
            continue
        status_info = get_document_generation_status(oficio, meta.tipo, formato)
        statuses.append(status_info['status'])
        actions.append(
            {
                'label': formato.value.upper(),
                'url': reverse(
                    'eventos:oficio-documento-download',
                    kwargs={'pk': oficio.pk, 'tipo_documento': meta.slug, 'formato': formato.value},
                ),
                'available': status_info['status'] == 'available',
                'status': status_info['status'],
                'errors': status_info.get('errors') or [],
            }
        )
        if status_info['status'] != 'available':
            errors.extend(status_info.get('errors') or [])

    if any(status == 'available' for status in statuses):
        status_key = 'available'
        detail = 'Documento pronto para download.'
    elif any(status == 'pending' for status in statuses):
        status_key = 'pending'
        detail = (errors or ['Documento com pendencias de preenchimento.'])[0]
    elif statuses:
        status_key = 'unavailable'
        detail = (errors or ['Documento indisponivel no momento.'])[0]
    else:
        status_key = 'not_applicable'
        detail = 'Documento nao suportado neste fluxo.'

    status_meta = _document_card_status_meta(status_key, STATUS_LABELS.get(status_key, 'â€”'))
    return {
        'status_key': status_key,
        'status_label': status_meta['label'],
        'status_css_class': status_meta['css_class'],
        'detail': detail,
        'actions': actions,
        'available': any(action['available'] for action in actions),
    }


def _build_oficio_document_cards(oficio):
    common_items = [
        {'label': 'Destino', 'value': oficio.destinos_display},
        {'label': 'Per\u00edodo', 'value': oficio.periodo_display},
        {'label': 'Viajantes', 'value': oficio.viajantes_display},
        {'label': 'Protocolo', 'value': oficio.protocolo_formatado or 'â€”'},
    ]
    cards = []

    oficio_document = _build_oficio_document_actions(oficio, DocumentoOficioTipo.OFICIO)
    cards.append(
        {
            'key': 'oficio',
            'title': 'Of\u00edcio',
            'status_key': oficio_document['status_key'],
            'status_label': oficio_document['status_label'],
            'status_css_class': oficio_document['status_css_class'],
            'detail': oficio_document['detail'],
            'summary_items': common_items,
            'edit_url': reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk}),
            'actions': oficio_document['actions'],
        }
    )

    justificativa_info = oficio.justificativa_info
    justificativa_exists = justificativa_info['required'] or justificativa_info['filled']
    if justificativa_exists:
        justificativa_document = _build_oficio_document_actions(oficio, DocumentoOficioTipo.JUSTIFICATIVA)
        justificativa_status = _document_card_status_meta(
            justificativa_info['status_key'],
            justificativa_info['status_label'],
        )
        cards.append(
            {
                'key': 'justificativa',
                'title': 'Justificativa',
                'status_key': justificativa_info['status_key'],
                'status_label': justificativa_status['label'],
                'status_css_class': justificativa_status['css_class'],
                'detail': (
                    'Texto da justificativa preenchido.'
                    if justificativa_info['filled']
                    else justificativa_document['detail']
                ),
                'summary_items': [
                    {'label': 'Destino', 'value': oficio.destinos_display},
                    {'label': 'Per\u00edodo', 'value': oficio.periodo_display},
                    {'label': 'Primeira sa\u00edda', 'value': justificativa_info['primeira_saida_display'] or 'â€”'},
                    {'label': 'Protocolo', 'value': oficio.protocolo_formatado or 'â€”'},
                ],
                'edit_url': reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
                'actions': justificativa_document['actions'],
            }
        )

    termo_document = _build_oficio_document_actions(oficio, DocumentoOficioTipo.TERMO_AUTORIZACAO)
    termo_exists = oficio.gerar_termo_preenchido or termo_document['available']
    if termo_exists:
        cards.append(
            {
                'key': 'termo-autorizacao',
                'title': 'Termo de autoriza\u00e7\u00e3o',
                'status_key': termo_document['status_key'],
                'status_label': termo_document['status_label'],
                'status_css_class': termo_document['status_css_class'],
                'detail': (
                    'Marcado no resumo para geraÃ§Ã£o do termo preenchido.'
                    if oficio.gerar_termo_preenchido and termo_document['status_key'] != 'available'
                    else termo_document['detail']
                ),
                'summary_items': common_items,
                'edit_url': reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
                'actions': termo_document['actions'],
            }
        )

    return cards


def _build_oficio_filters(request):
    return {
        'q': _clean(request.GET.get('q')),
        'status': _clean(request.GET.get('status')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'ano': _clean(request.GET.get('ano')),
        'numero': _clean(request.GET.get('numero')),
        'protocolo': _clean(request.GET.get('protocolo')),
        'destino': _clean(request.GET.get('destino')),
    }


def _build_oficio_list_filters(request):
    return {
        'q': _clean(request.GET.get('q') or request.GET.get('protocolo')),
        'status': _parse_choice_list(request.GET.getlist('status'), dict(Oficio.STATUS_CHOICES).keys()),
        'contexto': _parse_choice_list(request.GET.getlist('contexto'), dict(OFICIO_CONTEXT_CHOICES).keys()),
        'viagem_status': _parse_choice_list(
            request.GET.getlist('viagem_status'),
            dict(OFICIO_VIAGEM_STATUS_CHOICES).keys(),
        ),
        'justificativa': _parse_choice_list(
            request.GET.getlist('justificativa'),
            dict(OFICIO_PRESENCE_CHOICES).keys(),
        ),
        'termo': _parse_choice_list(request.GET.getlist('termo'), dict(OFICIO_PRESENCE_CHOICES).keys()),
        'order_by': _parse_single_choice(
            request.GET.get('order_by'),
            dict(OFICIO_ORDER_BY_CHOICES).keys(),
            OFICIO_ORDER_BY_DEFAULT,
        ),
        'order_dir': _parse_single_choice(
            request.GET.get('order_dir'),
            dict(OFICIO_ORDER_DIR_CHOICES).keys(),
            OFICIO_ORDER_DIR_DEFAULT,
        ),
    }


def _oficio_list_ordered_unique_strings(values):
    items = []
    seen = set()
    for value in values or []:
        item = _clean(value)
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _oficio_list_viajante_names(oficio):
    return _oficio_list_ordered_unique_strings(
        oficio.viajantes.order_by('pk').values_list('nome', flat=True)
    )


def _oficio_list_summarize_labels(labels, limit=2):
    items = _oficio_list_ordered_unique_strings(labels)
    if not items:
        return EMPTY_DISPLAY
    if len(items) <= limit:
        return ', '.join(items)
    return f"{', '.join(items[:limit])} +{len(items) - limit}"


def _oficio_list_format_datetime(value):
    if not value:
        return EMPTY_DISPLAY
    return timezone.localtime(value).strftime('%d/%m/%Y %H:%M')


def _oficio_list_shorten_text(value, limit=220):
    text = ' '.join(str(value or '').split())
    if len(text) <= limit:
        return text
    return f"{text[: max(1, limit - 3)].rstrip()}..."


def _oficio_list_destino_labels(oficio):
    labels = []
    for trecho in oficio.trechos.all():
        label = _label_local(
            getattr(trecho, 'destino_cidade', None),
            getattr(trecho, 'destino_estado', None),
        )
        if label and label != EMPTY_DISPLAY:
            labels.append(label)
    labels = _oficio_list_ordered_unique_strings(labels)
    if labels:
        return labels
    fallback = _clean(oficio.get_tipo_destino_display())
    return [fallback] if fallback else []


def _oficio_list_destinos_display(oficio):
    return _oficio_list_summarize_labels(_oficio_list_destino_labels(oficio), limit=2)


def _oficio_list_period_bounds(oficio):
    datas = []
    for trecho in oficio.trechos.all():
        if trecho.saida_data:
            datas.append(trecho.saida_data)
        if trecho.chegada_data:
            datas.append(trecho.chegada_data)
    if oficio.retorno_saida_data:
        datas.append(oficio.retorno_saida_data)
    if oficio.retorno_chegada_data:
        datas.append(oficio.retorno_chegada_data)
    if not datas:
        return None, None
    return min(datas), max(datas)


def _oficio_list_period_display(oficio):
    inicio, fim = _oficio_list_period_bounds(oficio)
    if not inicio:
        return EMPTY_DISPLAY
    if fim and fim != inicio:
        return f'{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}'
    return f'{inicio:%d/%m/%Y}'


def _oficio_list_viajantes_display(oficio):
    viajantes = _oficio_list_viajante_names(oficio)
    if not viajantes:
        return 'Nenhum'
    if len(viajantes) <= 2:
        return ', '.join(viajantes)
    return f"{', '.join(viajantes[:2])} +{len(viajantes) - 2}"


def _oficio_list_basic_viajantes_summary(oficio):
    viajantes = _oficio_list_viajante_names(oficio)
    if not viajantes:
        return 'Nenhum viajante'
    primeiro = viajantes[0]
    restante = len(viajantes) - 1
    return primeiro if restante <= 0 else f'{primeiro} +{restante}'


def _oficio_list_chip(label, value, css_class=''):
    text = _clean(value)
    if not text or text == EMPTY_DISPLAY:
        return None
    return {
        'label': label,
        'value': text,
        'css_class': css_class,
    }


def _oficio_list_display_or_default(value, fallback):
    text = _clean(value)
    if not text or text == EMPTY_DISPLAY:
        return fallback
    return text


def _oficio_list_header_chips(oficio, destinos_display, periodo_display):
    return [
        _oficio_list_chip('Oficio', _oficio_list_display_or_default(oficio.numero_formatado, 'A definir'), 'is-key'),
        _oficio_list_chip('Protocolo', _oficio_list_display_or_default(oficio.protocolo_formatado, 'Nao informado')),
        _oficio_list_chip('Destino', _oficio_list_display_or_default(destinos_display, 'Nao definido')),
        _oficio_list_chip('Data do evento', _oficio_list_display_or_default(periodo_display, 'A definir'), 'is-date'),
    ]


def _oficio_list_basic_fields(oficio, destinos_display, periodo_display):
    return [
        {
            'label': 'Oficio',
            'value': _oficio_list_display_or_default(oficio.numero_formatado, 'A definir'),
            'css_class': 'is-key',
        },
        {
            'label': 'Protocolo',
            'value': _oficio_list_display_or_default(oficio.protocolo_formatado, 'Nao informado'),
            'css_class': '',
        },
        {
            'label': 'Destino',
            'value': _oficio_list_display_or_default(destinos_display, 'Nao definido'),
            'css_class': '',
        },
        {
            'label': 'Data',
            'value': _oficio_list_display_or_default(periodo_display, 'A definir'),
            'css_class': 'is-date',
        },
        {
            'label': 'Viajantes',
            'value': _oficio_list_basic_viajantes_summary(oficio),
            'css_class': 'is-viajantes',
        },
    ]


def _oficio_list_corner_badges(oficio, viagem_status):
    oficio_status = _oficio_process_status_meta(oficio)
    badges = []
    seen = set()

    def append_badge(value, css_class):
        text = _clean(value)
        if not text or text == EMPTY_DISPLAY:
            return
        normalized = text.lower()
        if normalized in seen:
            return
        seen.add(normalized)
        badges.append({'value': text, 'css_class': css_class})

    append_badge(oficio_status['label'], oficio_status['css_class'])
    relative_label = _clean(viagem_status.get('relative_label'))
    if relative_label.lower() == 'termina hoje':
        append_badge(relative_label, viagem_status['css_class'])
    return badges


def _oficio_list_initials(value):
    parts = [part for part in _clean(value).split() if part]
    if not parts:
        return '--'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return ''.join(part[0] for part in parts[:2]).upper()


def _oficio_list_viajantes_block(oficio, limit=3):
    viajantes = _oficio_list_viajante_names(oficio)
    if not viajantes:
        return {
            'count_label': '0 viajante',
            'items': [{'name': 'Nenhum viajante vinculado', 'initials': '--', 'css_class': 'is-empty'}],
        }

    items = [
        {'name': nome, 'initials': _oficio_list_initials(nome), 'css_class': ''}
        for nome in viajantes[:limit]
    ]
    restante = len(viajantes) - limit
    if restante > 0:
        items.append(
            {
                'name': f'+{restante} viajante(s)',
                'initials': f'+{restante}',
                'css_class': 'is-counter',
            }
        )
    return {
        'count_label': f'{len(viajantes)} viajante(s)',
        'items': items,
    }


def _oficio_list_vehicle_display(oficio):
    placa = _clean(getattr(oficio, 'placa_formatada', ''))
    modelo = _clean(oficio.modelo)
    if placa == EMPTY_DISPLAY:
        placa = ''
    parts = [item for item in [placa, modelo] if item]
    return ' - '.join(parts) if parts else 'Nao informado'


def _oficio_list_driver_display(oficio):
    if getattr(oficio, 'motorista_viajante_id', None):
        motorista_nome = _clean(getattr(getattr(oficio, 'motorista_viajante', None), 'nome', ''))
        if motorista_nome:
            return motorista_nome
    return _clean(oficio.motorista) or 'Nao informado'


def _oficio_list_protocol_sort_value(oficio):
    raw_value = _clean(oficio.protocolo)
    digits = ''.join(char for char in raw_value if char.isdigit())
    return digits or raw_value


def _oficio_list_transport_block(oficio):
    placa = _clean(getattr(oficio, 'placa_formatada', ''))
    modelo = _clean(oficio.modelo)
    if placa == EMPTY_DISPLAY:
        placa = ''
    vehicle_display = _oficio_list_vehicle_display(oficio)
    driver_display = _oficio_list_driver_display(oficio)

    vehicle_secondary = modelo if placa and modelo and modelo != placa else ''
    if not vehicle_secondary and placa and not modelo:
        vehicle_secondary = 'Placa da viagem'

    driver_secondary = ''
    if driver_display != 'Nao informado':
        driver_secondary = 'Servidor cadastrado' if getattr(oficio, 'motorista_viajante_id', None) else 'Informado manualmente'

    return {
        'title': 'Veiculo e motorista',
        'vehicle_primary': vehicle_display,
        'vehicle_secondary': vehicle_secondary,
        'driver_primary': driver_display,
        'driver_secondary': driver_secondary,
    }


def _oficio_list_trip_status(oficio, today=None):
    inicio, fim = _oficio_list_period_bounds(oficio)
    if not inicio:
        meta = VIAGEM_STATUS_CARD_META['INDEFINIDA']
        return {
            'key': 'INDEFINIDA',
            'label': meta['label'],
            'css_class': meta['css_class'],
            'relative_label': '',
        }

    hoje = today or timezone.localdate()
    fim = fim or inicio
    if hoje < inicio:
        delta = (inicio - hoje).days
        meta = VIAGEM_STATUS_CARD_META['FUTURA']
        return {
            'key': 'FUTURA',
            'label': meta['label'],
            'css_class': meta['css_class'],
            'relative_label': 'Comeca hoje' if delta == 0 else f'Faltam {delta} dia(s)',
        }
    if hoje > fim:
        delta = (hoje - fim).days
        meta = VIAGEM_STATUS_CARD_META['CONCLUIDA']
        return {
            'key': 'CONCLUIDA',
            'label': meta['label'],
            'css_class': meta['css_class'],
            'relative_label': 'Aconteceu hoje' if delta == 0 else f'Aconteceu ha {delta} dia(s)',
        }

    meta = VIAGEM_STATUS_CARD_META['EM_ANDAMENTO']
    if inicio == fim == hoje:
        relative_label = 'Acontece hoje'
    elif hoje == inicio:
        relative_label = 'Comecou hoje'
    elif hoje == fim:
        relative_label = 'Termina hoje'
    else:
        relative_label = 'Em andamento'
    return {
        'key': 'EM_ANDAMENTO',
        'label': meta['label'],
        'css_class': meta['css_class'],
        'relative_label': relative_label,
    }


def _oficio_list_theme(oficio, viagem_status, today=None):
    inicio, fim = _oficio_list_period_bounds(oficio)
    hoje = today or timezone.localdate()
    theme_key = 'gray'
    reason = 'Rascunho aguardando programacao.'

    if not inicio:
        if oficio.status == Oficio.STATUS_FINALIZADO:
            theme_key = 'blue'
            reason = 'Oficio finalizado sem periodo definido.'
        meta = OFICIO_CARD_THEME_META[theme_key]
        return {
            'key': theme_key,
            'label': meta['label'],
            'css_class': meta['css_class'],
            'status_css_class': meta['status_css_class'],
            'reason': reason,
        }

    fim = fim or inicio
    days_until = (inicio - hoje).days
    if hoje > fim:
        if oficio.status == Oficio.STATUS_FINALIZADO:
            theme_key = 'green'
            reason = 'Evento concluido com oficio finalizado.'
        else:
            theme_key = 'red'
            reason = 'Evento ja passou e o oficio segue pendente.'
    elif inicio <= hoje <= fim:
        if oficio.status == Oficio.STATUS_FINALIZADO:
            theme_key = 'orange'
            reason = 'Evento em andamento com oficio finalizado.'
        else:
            theme_key = 'red'
            reason = 'Evento em andamento e o oficio ainda exige atencao.'
    elif days_until == 1:
        theme_key = 'yellow'
        reason = 'Evento acontece amanha.'
    elif oficio.status == Oficio.STATUS_FINALIZADO:
        theme_key = 'blue'
        reason = 'Oficio finalizado para evento futuro.'

    meta = OFICIO_CARD_THEME_META[theme_key]
    return {
        'key': theme_key,
        'label': meta['label'],
        'css_class': meta['css_class'],
        'status_css_class': meta['status_css_class'],
        'reason': reason,
    }


def _oficio_list_justificativa_block(oficio, justificativa_info):
    try:
        justificativa = oficio.justificativa
    except Justificativa.DoesNotExist:
        justificativa = None

    if not justificativa_info['required'] and not justificativa_info['filled'] and not justificativa:
        return None

    document = _build_oficio_document_actions(oficio, DocumentoOficioTipo.JUSTIFICATIVA)
    status_meta = _document_card_status_meta(
        justificativa_info['status_key'],
        justificativa_info['status_label'],
    )
    texto = _clean(justificativa_info.get('texto'))
    return {
        'status_label': status_meta['label'],
        'status_css_class': status_meta['css_class'],
        'texto_resumido': _oficio_list_shorten_text(texto, limit=220) if texto else 'Justificativa ainda nao preenchida.',
        'created_at_display': _oficio_list_format_datetime(getattr(justificativa, 'created_at', None)),
        'detail_url': (
            reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': justificativa.pk})
            if getattr(justificativa, 'pk', None)
            else reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk})
        ),
        'edit_url': reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
        'downloads': document['actions'],
        'has_text': bool(texto),
    }


def _oficio_list_saved_term_card(termo):
    return {
        'traveler_name': _clean(termo.servidor_display) or 'Termo geral',
        'open_url': reverse('eventos:documentos-termos-detalhe', kwargs={'pk': termo.pk}),
        'download_docx_url': reverse(
            'eventos:documentos-termos-download',
            kwargs={'pk': termo.pk, 'formato': DocumentoFormato.DOCX.value},
        ),
        'download_pdf_url': reverse(
            'eventos:documentos-termos-download',
            kwargs={'pk': termo.pk, 'formato': DocumentoFormato.PDF.value},
        ),
        'is_saved': True,
    }


def _oficio_list_pending_term_card(oficio, viajante):
    return {
        'traveler_name': _clean(getattr(viajante, 'nome', '')) or 'Termo geral',
        'open_url': reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
        'download_docx_url': '',
        'download_pdf_url': '',
        'is_saved': False,
    }


def _oficio_list_term_block(oficio):
    termos_map = {}
    for termo in list(oficio.termos_autorizacao.all()) + list(oficio.termos_autorizacao_relacionados.all()):
        if termo.pk:
            termos_map[termo.pk] = termo

    saved_terms = sorted(termos_map.values(), key=lambda item: (item.created_at, item.pk))
    if not saved_terms and not oficio.gerar_termo_preenchido:
        return None

    subcards = []
    saved_viajante_ids = set()
    for termo in saved_terms:
        if termo.viajante_id:
            saved_viajante_ids.add(termo.viajante_id)
        subcards.append(_oficio_list_saved_term_card(termo))

    if oficio.gerar_termo_preenchido:
        for viajante in oficio.viajantes.all():
            if viajante.pk in saved_viajante_ids:
                continue
            subcards.append(_oficio_list_pending_term_card(oficio, viajante))

    saved_count = len([card for card in subcards if card['is_saved']])
    pending_count = len(subcards) - saved_count
    summary = []
    if saved_count:
        summary.append(f'{saved_count} salvo(s)')
    if pending_count:
        summary.append(f'{pending_count} pendente(s)')
    return {
        'summary': ', '.join(summary) if summary else 'Termos vinculados',
        'count_label': f'{len(subcards)} servidor(es)',
        'items': subcards,
    }


def _oficio_list_card(oficio):
    justificativa_info = _build_oficio_justificativa_info(oficio)
    viagem_status = _oficio_list_trip_status(oficio)
    theme = _oficio_list_theme(oficio, viagem_status)
    oficio_downloads = _build_oficio_document_actions(oficio, DocumentoOficioTipo.OFICIO)
    justificativa = _oficio_list_justificativa_block(oficio, justificativa_info)
    termos = _oficio_list_term_block(oficio)
    destinos_display = _oficio_list_destinos_display(oficio)
    periodo_display = _oficio_list_period_display(oficio)
    data_evento_inicio, data_evento_fim = _oficio_list_period_bounds(oficio)
    context_label = 'Com evento' if oficio.evento_id else 'Avulso'
    vehicle_display = _oficio_list_vehicle_display(oficio)
    driver_display = _oficio_list_driver_display(oficio)
    return {
        'pk': oficio.pk,
        'numero_formatado': oficio.numero_formatado,
        'protocolo_formatado': oficio.protocolo_formatado or EMPTY_DISPLAY,
        'evento_titulo': _clean(getattr(getattr(oficio, 'evento', None), 'titulo', '')),
        'evento_url': reverse('eventos:guiado-painel', kwargs={'pk': oficio.evento_id}) if oficio.evento_id else '',
        'destinos_display': destinos_display,
        'periodo_display': periodo_display,
        'theme': theme,
        'basic_fields': _oficio_list_basic_fields(oficio, destinos_display, periodo_display),
        'header_chips': [chip for chip in _oficio_list_header_chips(oficio, destinos_display, periodo_display) if chip],
        'corner_badges': _oficio_list_corner_badges(oficio, viagem_status),
        'viajantes_block': _oficio_list_viajantes_block(oficio),
        'transport_block': _oficio_list_transport_block(oficio),
        'oficio_status': _oficio_process_status_meta(oficio),
        'viagem_status': viagem_status,
        'justificativa': justificativa,
        'termos': termos,
        'downloads': oficio_downloads['actions'],
        'summary_url': reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
        'wizard_url': reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk}),
        'excluir_url': reverse('eventos:oficio-excluir', kwargs={'pk': oficio.pk}),
        'search_blob': ' '.join(
            value
            for value in [
                oficio.numero_formatado,
                oficio.protocolo_formatado or '',
                _clean(oficio.protocolo),
                _clean(getattr(getattr(oficio, 'evento', None), 'titulo', '')),
                _clean(oficio.motivo),
                destinos_display,
                _oficio_list_viajantes_display(oficio),
                vehicle_display,
                driver_display,
                context_label,
            ]
            if value
        ).lower(),
        'filter_meta': {
            'status': oficio.status,
            'contexto': 'EVENTO' if oficio.evento_id else 'AVULSO',
            'viagem_status': viagem_status['key'],
            'has_justificativa': justificativa_info['filled'],
            'has_termo': bool(termos),
        },
        'sort_meta': {
            'numero': (
                int(oficio.ano) if oficio.ano is not None else None,
                int(oficio.numero) if oficio.numero is not None else None,
            ),
            'protocolo': _oficio_list_protocol_sort_value(oficio),
            'data_criacao': oficio.data_criacao,
            'updated_at': getattr(oficio, 'updated_at', None),
            'data_evento': data_evento_inicio,
            'data_evento_fim': data_evento_fim,
        },
    }


def _matches_oficio_list_choice(selected_values, current_value, all_values):
    if not selected_values or set(selected_values) == set(all_values):
        return True
    return current_value in selected_values


def _matches_oficio_list_presence(selected_values, present):
    if not selected_values or set(selected_values) == {'COM', 'SEM'}:
        return True
    return ('COM' if present else 'SEM') in selected_values


def _is_missing_oficio_sort_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, tuple):
        return all(_is_missing_oficio_sort_value(item) for item in value)
    return False


def _normalize_oficio_sort_value(value):
    if isinstance(value, tuple):
        return tuple(_normalize_oficio_sort_value(item) for item in value)
    if isinstance(value, str):
        return value.lower()
    return value


def _oficio_list_sort_value(card, order_by):
    return card['sort_meta'].get(order_by)


def _sort_oficio_list_cards(cards, order_by, order_dir):
    present_cards = []
    missing_cards = []
    for card in cards:
        sort_value = _oficio_list_sort_value(card, order_by)
        if _is_missing_oficio_sort_value(sort_value):
            missing_cards.append(card)
        else:
            present_cards.append(card)

    present_cards.sort(
        key=lambda card: (_normalize_oficio_sort_value(_oficio_list_sort_value(card, order_by)), card['pk']),
        reverse=order_dir == 'desc',
    )
    return present_cards + missing_cards


def oficio_global_lista(request):
    filters = _build_oficio_list_filters(request)
    queryset = (
        Oficio.objects.select_related(
            'evento',
            'cidade_sede',
            'estado_sede',
            'roteiro_evento',
            'veiculo',
            'motorista_viajante',
            'justificativa',
        )
        .prefetch_related(
            Prefetch(
                'trechos',
                queryset=OficioTrecho.objects.select_related(
                    'origem_estado',
                    'origem_cidade',
                    'destino_estado',
                    'destino_cidade',
                ),
            ),
            'viajantes',
            Prefetch(
                'termos_autorizacao',
                queryset=TermoAutorizacao.objects.select_related('viajante', 'veiculo').order_by('created_at', 'pk'),
            ),
            Prefetch(
                'termos_autorizacao_relacionados',
                queryset=TermoAutorizacao.objects.select_related('viajante', 'veiculo').order_by('created_at', 'pk'),
            ),
        )
        .all()
    )

    if filters['status'] and set(filters['status']) != set(dict(Oficio.STATUS_CHOICES).keys()):
        queryset = queryset.filter(status__in=filters['status'])

    if filters['contexto'] and set(filters['contexto']) != set(dict(OFICIO_CONTEXT_CHOICES).keys()):
        if filters['contexto'] == ['EVENTO']:
            queryset = queryset.filter(evento_id__isnull=False)
        elif filters['contexto'] == ['AVULSO']:
            queryset = queryset.filter(evento_id__isnull=True)

    cards = []
    query_text = filters['q'].lower()
    for oficio in queryset.distinct().order_by('-updated_at', '-created_at'):
        card = _oficio_list_card(oficio)
        if query_text and query_text not in card['search_blob']:
            continue
        if not _matches_oficio_list_choice(
            filters['viagem_status'],
            card['filter_meta']['viagem_status'],
            dict(OFICIO_VIAGEM_STATUS_CHOICES).keys(),
        ):
            continue
        if not _matches_oficio_list_presence(filters['justificativa'], card['filter_meta']['has_justificativa']):
            continue
        if not _matches_oficio_list_presence(filters['termo'], card['filter_meta']['has_termo']):
            continue
        cards.append(card)

    cards = _sort_oficio_list_cards(cards, filters['order_by'], filters['order_dir'])
    page_obj = _paginate(cards, request.GET.get('page'))
    return render(
        request,
        'eventos/global/oficios_lista.html',
        {
            'object_list': list(page_obj.object_list),
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'status_filter_options': Oficio.STATUS_CHOICES,
            'context_filter_options': OFICIO_CONTEXT_CHOICES,
            'viagem_filter_options': OFICIO_VIAGEM_STATUS_CHOICES,
            'presence_filter_options': OFICIO_PRESENCE_CHOICES,
            'order_by_options': OFICIO_ORDER_BY_CHOICES,
            'order_dir_options': OFICIO_ORDER_DIR_CHOICES,
            'hide_page_header': True,
        },
    )


def roteiro_global_lista(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'status': _clean(request.GET.get('status')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'tipo': _clean(request.GET.get('tipo')).upper(),
    }
    queryset = (
        RoteiroEvento.objects.select_related('evento', 'origem_estado', 'origem_cidade')
        .prefetch_related('destinos__estado', 'destinos__cidade')
        .annotate(oficios_count=Count('oficios', distinct=True))
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(evento__titulo__icontains=filters['q'])
            | Q(origem_cidade__nome__icontains=filters['q'])
            | Q(origem_estado__sigla__icontains=filters['q'])
            | Q(destinos__cidade__nome__icontains=filters['q'])
            | Q(destinos__estado__sigla__icontains=filters['q'])
        )
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])
    if filters['tipo'] == RoteiroEvento.TIPO_AVULSO:
        queryset = queryset.filter(tipo=RoteiroEvento.TIPO_AVULSO)
    elif filters['tipo'] == RoteiroEvento.TIPO_EVENTO:
        queryset = queryset.filter(tipo=RoteiroEvento.TIPO_EVENTO)
    if filters['evento_id'].isdigit():
        queryset = queryset.filter(evento_id=int(filters['evento_id']))

    page_obj = _paginate(
        queryset.distinct().order_by('-updated_at', '-created_at'),
        request.GET.get('page'),
    )
    object_list = list(page_obj.object_list)
    for roteiro in object_list:
        roteiro.destinos_display = _roteiro_destinos_display(roteiro)
        roteiro.is_avulso = roteiro.tipo == RoteiroEvento.TIPO_AVULSO or not roteiro.evento_id
        if roteiro.is_avulso:
            roteiro.editar_url = reverse('eventos:roteiro-avulso-editar', kwargs={'pk': roteiro.pk})
            roteiro.evento_url = ''
            roteiro.etapa_url = ''
            roteiro.oficios_url = ''
        else:
            roteiro.editar_url = reverse(
                'eventos:guiado-etapa-2-editar',
                kwargs={'evento_id': roteiro.evento_id, 'pk': roteiro.pk},
            )
            roteiro.evento_url = reverse('eventos:guiado-painel', kwargs={'pk': roteiro.evento_id})
            roteiro.etapa_url = reverse('eventos:guiado-etapa-2', kwargs={'evento_id': roteiro.evento_id})
            roteiro.oficios_url = reverse('eventos:guiado-etapa-5', kwargs={'evento_id': roteiro.evento_id})

    selected_event = None
    if filters['evento_id'].isdigit():
        selected_event = Evento.objects.filter(pk=int(filters['evento_id'])).first()

    return render(
        request,
        'eventos/global/roteiros_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'status_choices': RoteiroEvento.STATUS_CHOICES,
            'tipo_choices': [
                ('', 'Todos'),
                (RoteiroEvento.TIPO_AVULSO, 'Avulsos'),
                (RoteiroEvento.TIPO_EVENTO, 'Vinculados a evento'),
            ],
            'novo_roteiro_url': (
                reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': selected_event.pk})
                if selected_event
                else ''
            ),
            'novo_roteiro_avulso_url': reverse('eventos:roteiro-avulso-cadastrar'),
            'selected_event': selected_event,
        },
    )


def _base_documento_filters(request):
    return {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'oficio_id': _clean(request.GET.get('oficio_id')),
        'status': _clean(request.GET.get('status')),
    }


def _resolve_preselected_context(request):
    preselected_event_id = _parse_int(request.GET.get('preselected_event_id') or request.POST.get('preselected_event_id'))
    preselected_oficio_id = _parse_int(request.GET.get('preselected_oficio_id') or request.POST.get('preselected_oficio_id'))
    preselected_event = Evento.objects.filter(pk=preselected_event_id).first() if preselected_event_id else None
    preselected_oficio = Oficio.objects.filter(pk=preselected_oficio_id).first() if preselected_oficio_id else None
    return preselected_event, preselected_oficio


def planos_trabalho_global(request):
    filters = _base_documento_filters(request)
    queryset = PlanoTrabalho.objects.select_related('evento', 'oficio', 'solicitante').all()
    if filters['q']:
        queryset = queryset.filter(
            Q(objetivo__icontains=filters['q'])
            | Q(observacoes__icontains=filters['q'])
            | Q(evento__titulo__icontains=filters['q'])
            | Q(oficio__motivo__icontains=filters['q'])
        )
    if filters['evento_id'].isdigit():
        queryset = queryset.filter(evento_id=int(filters['evento_id']))
    if filters['oficio_id'].isdigit():
        queryset = queryset.filter(oficio_id=int(filters['oficio_id']))
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])

    page_obj = _paginate(queryset.order_by('-updated_at', '-created_at'), request.GET.get('page'))
    return render(
        request,
        'eventos/documentos/planos_trabalho_lista.html',
        {
            'object_list': list(page_obj.object_list),
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficios_choices': Oficio.objects.order_by('-updated_at')[:200],
            'status_choices': PlanoTrabalho.STATUS_CHOICES,
        },
    )


@require_http_methods(['GET', 'POST'])
def plano_trabalho_novo(request):
    return_to_default = reverse('eventos:documentos-planos-trabalho')
    return_to = _get_safe_return_to(request, return_to_default)
    context_source = _get_context_source(request)
    preselected_event, preselected_oficio = _resolve_preselected_context(request)

    initial = {}
    if preselected_event:
        initial['evento'] = preselected_event.pk
    if preselected_oficio:
        initial['oficio'] = preselected_oficio.pk

    form = PlanoTrabalhoForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, 'Plano de trabalho criado com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-planos-trabalho-detalhe', kwargs={'pk': obj.pk}))

    return render(
        request,
        'eventos/documentos/planos_trabalho_form.html',
        {
            'form': form,
            'object': None,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': preselected_event.pk if preselected_event else '',
            'preselected_oficio_id': preselected_oficio.pk if preselected_oficio else '',
        },
    )


@require_http_methods(['GET', 'POST'])
def plano_trabalho_editar(request, pk):
    obj = get_object_or_404(PlanoTrabalho.objects.select_related('evento', 'oficio'), pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-planos-trabalho'))
    context_source = _get_context_source(request)
    form = PlanoTrabalhoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Plano de trabalho atualizado.')
        return redirect(return_to or reverse('eventos:documentos-planos-trabalho-detalhe', kwargs={'pk': obj.pk}))
    return render(
        request,
        'eventos/documentos/planos_trabalho_form.html',
        {
            'form': form,
            'object': obj,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': obj.evento_id or '',
            'preselected_oficio_id': obj.oficio_id or '',
        },
    )


@require_http_methods(['GET'])
def plano_trabalho_detalhe(request, pk):
    obj = get_object_or_404(PlanoTrabalho.objects.select_related('evento', 'oficio', 'solicitante'), pk=pk)
    return render(request, 'eventos/documentos/planos_trabalho_detalhe.html', {'object': obj})


@require_http_methods(['GET', 'POST'])
def plano_trabalho_excluir(request, pk):
    obj = get_object_or_404(PlanoTrabalho, pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-planos-trabalho'))
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Plano de trabalho excluído.')
        return redirect(return_to)
    return render(
        request,
        'eventos/documentos/planos_trabalho_excluir.html',
        {'object': obj, 'return_to': return_to},
    )


@require_http_methods(['GET'])
def plano_trabalho_download(request, pk, formato):
    obj = get_object_or_404(PlanoTrabalho.objects.select_related('oficio'), pk=pk)
    formato = _clean(formato).lower()
    if formato not in {DocumentoFormato.DOCX.value, DocumentoFormato.PDF.value}:
        raise Http404('Formato inválido.')
    docx_bytes = (
        render_plano_trabalho_docx(obj.oficio)
        if obj.oficio_id
        else render_plano_trabalho_model_docx(obj)
    )
    payload = docx_bytes
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if formato == DocumentoFormato.PDF.value:
        payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
        content_type = 'application/pdf'
    response = HttpResponse(payload, content_type=content_type)
    ext = 'docx' if formato == DocumentoFormato.DOCX.value else 'pdf'
    response['Content-Disposition'] = f'attachment; filename="plano_trabalho_{obj.pk}.{ext}"'
    return response


def ordens_servico_global(request):
    filters = _base_documento_filters(request)
    queryset = OrdemServico.objects.select_related('evento', 'oficio').all()
    if filters['q']:
        queryset = queryset.filter(
            Q(finalidade__icontains=filters['q'])
            | Q(observacoes__icontains=filters['q'])
            | Q(evento__titulo__icontains=filters['q'])
            | Q(oficio__motivo__icontains=filters['q'])
        )
    if filters['evento_id'].isdigit():
        queryset = queryset.filter(evento_id=int(filters['evento_id']))
    if filters['oficio_id'].isdigit():
        queryset = queryset.filter(oficio_id=int(filters['oficio_id']))
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])

    page_obj = _paginate(queryset.order_by('-updated_at', '-created_at'), request.GET.get('page'))
    return render(
        request,
        'eventos/documentos/ordens_servico_lista.html',
        {
            'object_list': list(page_obj.object_list),
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficios_choices': Oficio.objects.order_by('-updated_at')[:200],
            'status_choices': OrdemServico.STATUS_CHOICES,
        },
    )


@require_http_methods(['GET', 'POST'])
def ordem_servico_novo(request):
    return_to_default = reverse('eventos:documentos-ordens-servico')
    return_to = _get_safe_return_to(request, return_to_default)
    context_source = _get_context_source(request)
    preselected_event, preselected_oficio = _resolve_preselected_context(request)

    initial = {}
    if preselected_event:
        initial['evento'] = preselected_event.pk
    if preselected_oficio:
        initial['oficio'] = preselected_oficio.pk

    form = OrdemServicoForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, 'Ordem de serviço criada com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-ordens-servico-detalhe', kwargs={'pk': obj.pk}))

    return render(
        request,
        'eventos/documentos/ordens_servico_form.html',
        {
            'form': form,
            'object': None,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': preselected_event.pk if preselected_event else '',
            'preselected_oficio_id': preselected_oficio.pk if preselected_oficio else '',
        },
    )


@require_http_methods(['GET', 'POST'])
def ordem_servico_editar(request, pk):
    obj = get_object_or_404(OrdemServico.objects.select_related('evento', 'oficio'), pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-ordens-servico'))
    context_source = _get_context_source(request)
    form = OrdemServicoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Ordem de serviço atualizada.')
        return redirect(return_to or reverse('eventos:documentos-ordens-servico-detalhe', kwargs={'pk': obj.pk}))
    return render(
        request,
        'eventos/documentos/ordens_servico_form.html',
        {
            'form': form,
            'object': obj,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': obj.evento_id or '',
            'preselected_oficio_id': obj.oficio_id or '',
        },
    )


@require_http_methods(['GET'])
def ordem_servico_detalhe(request, pk):
    obj = get_object_or_404(OrdemServico.objects.select_related('evento', 'oficio'), pk=pk)
    return render(request, 'eventos/documentos/ordens_servico_detalhe.html', {'object': obj})


@require_http_methods(['GET', 'POST'])
def ordem_servico_excluir(request, pk):
    obj = get_object_or_404(OrdemServico, pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-ordens-servico'))
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Ordem de serviço excluída.')
        return redirect(return_to)
    return render(
        request,
        'eventos/documentos/ordens_servico_excluir.html',
        {'object': obj, 'return_to': return_to},
    )


@require_http_methods(['GET'])
def ordem_servico_download(request, pk, formato):
    obj = get_object_or_404(OrdemServico.objects.select_related('oficio'), pk=pk)
    formato = _clean(formato).lower()
    if formato not in {DocumentoFormato.DOCX.value, DocumentoFormato.PDF.value}:
        raise Http404('Formato inválido.')
    docx_bytes = (
        render_ordem_servico_docx(obj.oficio)
        if obj.oficio_id
        else render_ordem_servico_model_docx(obj)
    )
    payload = docx_bytes
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if formato == DocumentoFormato.PDF.value:
        payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
        content_type = 'application/pdf'
    response = HttpResponse(payload, content_type=content_type)
    ext = 'docx' if formato == DocumentoFormato.DOCX.value else 'pdf'
    response['Content-Disposition'] = f'attachment; filename="ordem_servico_{obj.pk}.{ext}"'
    return response


def justificativas_global(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'oficio_id': _clean(request.GET.get('oficio_id')),
    }
    queryset = (
        Justificativa.objects.select_related(
            'oficio',
            'oficio__evento',
            'modelo',
        ).order_by('-updated_at', '-created_at')
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(texto__icontains=filters['q'])
            | Q(oficio__protocolo__icontains=filters['q'])
            | Q(oficio__motivo__icontains=filters['q'])
            | Q(oficio__evento__titulo__icontains=filters['q'])
        ).distinct()
    if filters['oficio_id'].isdigit():
        queryset = queryset.filter(oficio_id=int(filters['oficio_id']))

    page_obj = _paginate(queryset, request.GET.get('page'))
    object_list = []
    for just in page_obj.object_list:
        just.detail_url = reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': just.pk})
        just.edicao_url = reverse('eventos:documentos-justificativas-editar', kwargs={'pk': just.pk})
        just.excluir_url = reverse('eventos:documentos-justificativas-excluir', kwargs={'pk': just.pk})
        just.oficio_url = reverse('eventos:oficio-step4', kwargs={'pk': just.oficio_id})
        just.evento_url = (
            reverse('eventos:guiado-painel', kwargs={'pk': just.oficio.evento_id})
            if just.oficio.evento_id else ''
        )
        object_list.append(just)

    return render(
        request,
        'eventos/documentos/justificativas_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'oficios_choices': Oficio.objects.order_by('-updated_at')[:200],
        },
    )


@require_http_methods(['GET', 'POST'])
def justificativa_nova(request):
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-justificativas'))
    _preselected_event, preselected_oficio = _resolve_preselected_context(request)
    if not preselected_oficio:
        oid = _parse_int(request.GET.get('oficio_id') or request.POST.get('oficio_id'))
        if oid:
            preselected_oficio = Oficio.objects.filter(pk=oid).first()
    form = JustificativaForm(request.POST or None, preselected_oficio=preselected_oficio)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        messages.success(request, 'Justificativa criada com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': obj.pk}))
    return render(
        request,
        'eventos/documentos/justificativas_form.html',
        {
            'form': form,
            'object': None,
            'return_to': return_to,
            'preselected_oficio': preselected_oficio,
        },
    )


@require_http_methods(['GET'])
def justificativa_detalhe(request, pk):
    obj = get_object_or_404(
        Justificativa.objects.select_related('oficio', 'oficio__evento', 'modelo'),
        pk=pk,
    )
    return render(
        request,
        'eventos/documentos/justificativas_detalhe.html',
        {'object': obj},
    )


@require_http_methods(['GET', 'POST'])
def justificativa_editar(request, pk):
    obj = get_object_or_404(
        Justificativa.objects.select_related('oficio', 'oficio__evento', 'modelo'),
        pk=pk,
    )
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-justificativas'))
    form = JustificativaForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Justificativa atualizada com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': obj.pk}))
    return render(
        request,
        'eventos/documentos/justificativas_form.html',
        {
            'form': form,
            'object': obj,
            'return_to': return_to,
            'preselected_oficio': obj.oficio,
        },
    )


@require_http_methods(['GET', 'POST'])
def justificativa_excluir(request, pk):
    obj = get_object_or_404(Justificativa.objects.select_related('oficio'), pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-justificativas'))
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Justificativa excluída com sucesso.')
        return redirect(return_to)
    return render(
        request,
        'eventos/documentos/justificativas_excluir.html',
        {'object': obj, 'return_to': return_to},
    )


def termos_global(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'status': _clean(request.GET.get('status')),
    }
    queryset = (
        EventoTermoParticipante.objects.select_related('evento', 'viajante', 'viajante__cargo')
        .prefetch_related(
            Prefetch(
                'evento__oficios',
                queryset=Oficio.objects.prefetch_related('viajantes').order_by('ano', 'numero', 'id'),
            )
        )
        .order_by('-updated_at', 'evento__titulo', 'viajante__nome')
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(evento__titulo__icontains=filters['q'])
            | Q(viajante__nome__icontains=filters['q'])
            | Q(viajante__cargo__nome__icontains=filters['q'])
        )
    if filters['evento_id'].isdigit():
        queryset = queryset.filter(evento_id=int(filters['evento_id']))
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])

    page_obj = _paginate(queryset, request.GET.get('page'))
    object_list = []
    for termo in page_obj.object_list:
        oficios_relacionados = []
        for oficio in termo.evento.oficios.all():
            viajante_ids = {viajante.pk for viajante in oficio.viajantes.all()}
            if termo.viajante_id in viajante_ids:
                oficios_relacionados.append(oficio)
        termo.oficios_relacionados = oficios_relacionados
        termo.oficios_display = ', '.join(oficio.numero_formatado for oficio in oficios_relacionados) if oficios_relacionados else '—'
        termo.termos_url = reverse('eventos:guiado-etapa-3', kwargs={'evento_id': termo.evento_id})
        termo.oficios_url = reverse('eventos:guiado-etapa-5', kwargs={'evento_id': termo.evento_id})
        termo.evento_url = reverse('eventos:guiado-painel', kwargs={'pk': termo.evento_id})
        termo.documentos_url = (
            reverse('eventos:oficio-step4', kwargs={'pk': oficios_relacionados[0].pk})
            if len(oficios_relacionados) == 1
            else ''
        )
        object_list.append(termo)

    return render(
        request,
        'eventos/global/termos_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'status_choices': EventoTermoParticipante.STATUS_CHOICES,
        },
    )


def _default_simulacao_state():
    return {
        'quantidade_servidores': '1',
        'chegada_final_data': '',
        'chegada_final_hora': '',
        'periodos': [
            {
                'saida_data': '',
                'saida_hora': '',
                'destino_cidade': '',
                'destino_uf': '',
            }
        ],
    }


def _load_simulacao_state(request):
    state = request.session.get(SIMULACAO_SESSION_KEY) or {}
    periodos = state.get('periodos')
    if not isinstance(periodos, list) or not periodos:
        return _default_simulacao_state()
    return {
        'quantidade_servidores': _clean(state.get('quantidade_servidores')) or '1',
        'chegada_final_data': _clean(state.get('chegada_final_data')),
        'chegada_final_hora': _clean(state.get('chegada_final_hora')),
        'periodos': periodos,
    }


def _parse_simulacao_post(request):
    try:
        period_count = max(1, min(int(request.POST.get('period_count') or 1), 12))
    except (TypeError, ValueError):
        period_count = 1

    periodos = []
    markers = []
    for index in range(period_count):
        row = {
            'saida_data': _clean(request.POST.get(f'saida_data_{index}')),
            'saida_hora': _clean(request.POST.get(f'saida_hora_{index}')),
            'destino_cidade': _clean(request.POST.get(f'destino_cidade_{index}')),
            'destino_uf': _clean(request.POST.get(f'destino_uf_{index}')).upper(),
        }
        periodos.append(row)
        if not any(row.values()):
            continue
        if not all(row.values()):
            raise ValueError(f'Preencha todos os campos do periodo {index + 1}.')
        saida = datetime.strptime(
            f"{row['saida_data']} {row['saida_hora']}",
            '%Y-%m-%d %H:%M',
        )
        markers.append(
            PeriodMarker(
                saida=saida,
                destino_cidade=row['destino_cidade'],
                destino_uf=row['destino_uf'],
            )
        )

    quantidade_servidores = _clean(request.POST.get('quantidade_servidores')) or '1'
    try:
        quantidade_servidores_int = max(1, int(quantidade_servidores))
    except (TypeError, ValueError):
        raise ValueError('Informe uma quantidade valida de servidores.')

    chegada_final_data = _clean(request.POST.get('chegada_final_data'))
    chegada_final_hora = _clean(request.POST.get('chegada_final_hora'))
    if not markers:
        raise ValueError('Informe ao menos um periodo de deslocamento.')
    if not chegada_final_data or not chegada_final_hora:
        raise ValueError('Informe a data e a hora de chegada final na sede.')

    chegada_final = datetime.strptime(
        f'{chegada_final_data} {chegada_final_hora}',
        '%Y-%m-%d %H:%M',
    )

    return {
        'quantidade_servidores': str(quantidade_servidores_int),
        'chegada_final_data': chegada_final_data,
        'chegada_final_hora': chegada_final_hora,
        'periodos': periodos,
        'markers': markers,
        'chegada_final': chegada_final,
    }


def simulacao_diarias_global(request):
    state = _load_simulacao_state(request)
    resultado = None
    erro = ''

    if request.method == 'POST':
        try:
            parsed = _parse_simulacao_post(request)
            state = {
                'quantidade_servidores': parsed['quantidade_servidores'],
                'chegada_final_data': parsed['chegada_final_data'],
                'chegada_final_hora': parsed['chegada_final_hora'],
                'periodos': parsed['periodos'],
            }
            resultado = calculate_periodized_diarias(
                parsed['markers'],
                parsed['chegada_final'],
                quantidade_servidores=int(parsed['quantidade_servidores']),
            )
            request.session[SIMULACAO_SESSION_KEY] = state
            request.session.modified = True
        except ValueError as exc:
            erro = str(exc)

    tabela_valores = [
        {
            'tipo': tipo,
            'valor_24h': formatar_valor_diarias(valores['24h']),
            'valor_15': formatar_valor_diarias(valores['15']),
            'valor_30': formatar_valor_diarias(valores['30']),
        }
        for tipo, valores in TABELA_DIARIAS.items()
    ]

    return render(
        request,
        'eventos/global/simulacao_diarias.html',
        {
            'state': state,
            'period_count': len(state['periodos']),
            'resultado': resultado,
            'erro': erro,
            'tabela_valores': tabela_valores,
        },
    )


TERMO_MODO_META = {
    TermoAutorizacao.MODO_RAPIDO: {
        'label': 'Termo simples',
        'description': 'Usado quando o contexto nao traz base suficiente para gerar um termo por servidor.',
        'template_name': TERMO_TEMPLATE_NAMES[TermoAutorizacao.MODO_RAPIDO],
    },
    TermoAutorizacao.MODO_AUTOMATICO_COM_VIATURA: {
        'label': 'Automatico com viatura',
        'description': 'Usado quando ha servidores consolidados e uma viatura efetiva aplicada ao contexto.',
        'template_name': TERMO_TEMPLATE_NAMES[TermoAutorizacao.MODO_AUTOMATICO_COM_VIATURA],
    },
    TermoAutorizacao.MODO_AUTOMATICO_SEM_VIATURA: {
        'label': 'Automatico sem viatura',
        'description': 'Usado quando ha servidores consolidados, mas nenhuma viatura efetiva no termo.',
        'template_name': TERMO_TEMPLATE_NAMES[TermoAutorizacao.MODO_AUTOMATICO_SEM_VIATURA],
    },
}


def _build_termo_filters(request):
    return {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'oficio_id': _clean(request.GET.get('oficio_id')),
        'status': _clean(request.GET.get('status')),
        'modo_geracao': _clean(request.GET.get('modo_geracao')),
    }


def _termo_status_meta(termo):
    fallback_label = getattr(termo, 'get_status_display', lambda: termo.status)() or termo.status or '-'
    meta = TERMO_STATUS_CARD_META.get(termo.status, {})
    return {
        'label': meta.get('label', fallback_label),
        'css_class': meta.get('css_class', 'is-muted'),
    }


def _termo_mode_meta(modo):
    return TERMO_MODO_META.get(
        (modo or '').strip().upper(),
        {'label': modo or 'Modo', 'description': '', 'template_name': ''},
    )


def _termo_context_display(termo):
    parts = []
    if termo.evento_id:
        parts.append((termo.evento.titulo or '').strip() or f'Evento #{termo.evento_id}')
    oficios_labels = (termo.oficios_relacionados_display or '').strip()
    if oficios_labels:
        parts.append(f'Oficios {oficios_labels}')
    elif termo.oficio_id:
        parts.append(f'Oficio {termo.oficio.numero_formatado}')
    elif termo.roteiro_id:
        parts.append(f'Roteiro #{termo.roteiro_id}')
    return ' | '.join(parts) if parts else 'Termo avulso'


def _build_saved_termo_filename(termo, formato):
    ext = 'docx' if formato == DocumentoFormato.DOCX.value else 'pdf'
    base = slugify(getattr(termo, 'titulo_display', '') or termo.servidor_display or termo.destino or termo.numero_formatado) or f'termo-{termo.pk}'
    return f'termo_autorizacao_{termo.pk}_{base}.{ext}'


def _build_termo_initial(preselected_event, preselected_oficio):
    initial = {'oficios': []}
    context = build_termo_context(
        evento=preselected_event,
        oficios=[preselected_oficio] if preselected_oficio else [],
        roteiro=getattr(preselected_oficio, 'roteiro_evento', None) if preselected_oficio else None,
    )
    if preselected_event:
        initial['evento'] = preselected_event.pk
    if preselected_oficio:
        initial['oficios'] = [preselected_oficio.pk]
    if context['roteiro']:
        initial['roteiro'] = context['roteiro'].pk
    if context['destino']:
        initial['destino'] = context['destino']
    if context['data_evento']:
        initial['data_evento'] = context['data_evento']
    if context['data_evento_fim']:
        initial['data_evento_fim'] = context['data_evento_fim']
    return initial


def _render_termo_form(
    request,
    *,
    form,
    object_instance=None,
    return_to='',
    context_source='',
    preselected_event=None,
    preselected_oficio=None,
    read_only_context=False,
):
    selected_viajantes = []
    selected_veiculo_payload = None
    selected_oficios_payload = []
    preview_payload = getattr(form, 'preview_payload', None)
    if object_instance and object_instance.viajante_id:
        selected_viajantes = [object_instance.viajante]
    elif hasattr(form, 'cleaned_viajantes') and form.cleaned_viajantes:
        selected_viajantes = list(form.cleaned_viajantes)
    if object_instance and object_instance.veiculo_id:
        selected_veiculo_payload = serializar_veiculo_para_oficio(object_instance.veiculo)
        selected_veiculo_payload['id'] = object_instance.veiculo.pk
        selected_veiculo_payload['label'] = (
            f"{selected_veiculo_payload['placa_formatada']} - {selected_veiculo_payload['modelo']}"
        ).strip(' -')
    elif hasattr(form, 'cleaned_veiculo') and form.cleaned_veiculo:
        selected_veiculo_payload = serializar_veiculo_para_oficio(form.cleaned_veiculo)
        selected_veiculo_payload['id'] = form.cleaned_veiculo.pk
        selected_veiculo_payload['label'] = (
            f"{selected_veiculo_payload['placa_formatada']} - {selected_veiculo_payload['modelo']}"
        ).strip(' -')
    if object_instance:
        related_oficios = list(object_instance.oficios.all())
        if not related_oficios and object_instance.oficio_id:
            related_oficios = [object_instance.oficio]
        selected_oficios_payload = [
            {'id': oficio.pk, 'label': f'Oficio {oficio.numero_formatado or f"#{oficio.pk}"}'}
            for oficio in related_oficios
        ]
        if preview_payload is None:
            preview_payload = build_termo_preview_payload(
                build_termo_context(
                    evento=object_instance.evento,
                    oficios=related_oficios,
                    roteiro=object_instance.roteiro,
                ),
                viajantes=selected_viajantes,
                veiculo=object_instance.veiculo,
            )
    elif getattr(form, 'cleaned_oficios', None):
        selected_oficios_payload = [
            {'id': oficio.pk, 'label': f'Oficio {oficio.numero_formatado or f"#{oficio.pk}"}'}
            for oficio in form.cleaned_oficios
        ]
    if preview_payload is None:
        preview_payload = build_termo_preview_payload(build_termo_context())
    return render(
        request,
        'eventos/documentos/termos_form.html',
        {
            'form': form,
            'object': object_instance,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': preselected_event.pk if preselected_event else '',
            'preselected_oficio_id': preselected_oficio.pk if preselected_oficio else '',
            'buscar_viajantes_url': reverse('eventos:oficio-step1-viajantes-api'),
            'buscar_veiculos_url': reverse('eventos:oficio-step2-veiculos-busca-api'),
            'preview_url': reverse('eventos:documentos-termos-preview'),
            'selected_viajantes_payload': [
                serializar_viajante_para_autocomplete(viajante) for viajante in selected_viajantes
            ],
            'selected_veiculo_payload': selected_veiculo_payload,
            'selected_oficios_payload': selected_oficios_payload,
            'preview_payload': preview_payload,
            'read_only_context': read_only_context,
            'show_viajantes_selector': object_instance is None,
            'show_veiculo_selector': object_instance is None,
        },
    )


def documentos_hub(request):
    oficios = list(Oficio.objects.prefetch_related('trechos').all())
    justificativas_pendentes = 0
    justificativas_preenchidas = 0
    for oficio in oficios:
        info = _build_oficio_justificativa_info(oficio)
        if info['status_key'] == 'pendente':
            justificativas_pendentes += 1
        elif info['status_key'] == 'preenchida':
            justificativas_preenchidas += 1

    cards = [
        {
            'label': 'Planos de trabalho',
            'count': PlanoTrabalho.objects.count(),
            'description': 'Modulo documental independente com criacao e edicao proprias.',
            'url': reverse('eventos:documentos-planos-trabalho'),
        },
        {
            'label': 'Ordens de servico',
            'count': OrdemServico.objects.count(),
            'description': 'Modulo documental independente com criacao e edicao proprias.',
            'url': reverse('eventos:documentos-ordens-servico'),
        },
        {
            'label': 'Justificativas',
            'count': justificativas_pendentes,
            'description': f'{justificativas_preenchidas} preenchidas e {justificativas_pendentes} pendentes no momento.',
            'url': reverse('eventos:documentos-justificativas'),
        },
        {
            'label': 'Termos',
            'count': TermoAutorizacao.objects.count(),
            'description': 'Modulo documental com formulario unico, contexto consolidado e downloads por registro.',
            'url': reverse('eventos:documentos-termos'),
        },
    ]
    return render(
        request,
        'eventos/global/documentos_hub.html',
        {
            'cards': cards,
            'total_oficios': len(oficios),
            'termos_pendentes': TermoAutorizacao.objects.filter(status=TermoAutorizacao.STATUS_RASCUNHO).count(),
            'termos_concluidos': TermoAutorizacao.objects.filter(status=TermoAutorizacao.STATUS_GERADO).count(),
            'justificativas_pendentes': justificativas_pendentes,
            'justificativas_preenchidas': justificativas_preenchidas,
        },
    )


def _load_termo_context_objects(evento_id='', oficio_ids=None, roteiro_id=''):
    oficio_ids = [int(pk) for pk in (oficio_ids or []) if str(pk).isdigit()]
    evento = None
    roteiro = None
    if str(evento_id).isdigit():
        evento = Evento.objects.filter(pk=int(evento_id)).first()
    if str(roteiro_id).isdigit():
        roteiro = (
            RoteiroEvento.objects.select_related('evento')
            .prefetch_related('destinos__cidade', 'destinos__estado')
            .filter(pk=int(roteiro_id))
            .first()
        )
    oficios_qs = (
        Oficio.objects.select_related('evento', 'roteiro_evento', 'veiculo')
        .prefetch_related('viajantes', 'trechos__destino_cidade', 'trechos__destino_estado')
        .filter(pk__in=oficio_ids)
    )
    oficios_map = {oficio.pk: oficio for oficio in oficios_qs}
    oficios = [oficios_map[pk] for pk in oficio_ids if pk in oficios_map]
    return evento, oficios, roteiro


def termos_global(request):
    filters = _build_termo_filters(request)
    queryset = (
        TermoAutorizacao.objects.select_related(
            'evento',
            'oficio',
            'roteiro',
            'viajante',
            'viajante__cargo',
            'veiculo',
        )
        .prefetch_related('oficios')
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(destino__icontains=filters['q'])
            | Q(evento__titulo__icontains=filters['q'])
            | Q(oficio__protocolo__icontains=filters['q'])
            | Q(oficios__protocolo__icontains=filters['q'])
            | Q(viajante__nome__icontains=filters['q'])
            | Q(servidor_nome__icontains=filters['q'])
            | Q(veiculo_modelo__icontains=filters['q'])
            | Q(veiculo_placa__icontains=filters['q'])
        ).distinct()
    if filters['evento_id'].isdigit():
        queryset = queryset.filter(evento_id=int(filters['evento_id']))
    if filters['oficio_id'].isdigit():
        oficio_id = int(filters['oficio_id'])
        queryset = queryset.filter(Q(oficio_id=oficio_id) | Q(oficios__id=oficio_id)).distinct()
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])
    if filters['modo_geracao']:
        queryset = queryset.filter(modo_geracao=filters['modo_geracao'])

    page_obj = _paginate(queryset.order_by('-updated_at', '-created_at'), request.GET.get('page'))
    object_list = list(page_obj.object_list)
    for termo in object_list:
        termo.process_status = _termo_status_meta(termo)
        termo.mode_meta = _termo_mode_meta(termo.modo_geracao)
        termo.context_display = _termo_context_display(termo)
        termo.title_display = termo.titulo_display
        termo.servidor_resumo = termo.servidor_display or 'Sem servidor'
        termo.destino_resumo = termo.destino or '-'
        termo.periodo_resumo = termo.periodo_display or '-'
        termo.evento_url = reverse('eventos:guiado-painel', kwargs={'pk': termo.evento_id}) if termo.evento_id else ''
        termo.detail_url = reverse('eventos:documentos-termos-detalhe', kwargs={'pk': termo.pk})
        termo.edicao_url = reverse('eventos:documentos-termos-editar', kwargs={'pk': termo.pk})
        termo.excluir_url = reverse('eventos:documentos-termos-excluir', kwargs={'pk': termo.pk})
        termo.download_docx_url = reverse(
            'eventos:documentos-termos-download',
            kwargs={'pk': termo.pk, 'formato': DocumentoFormato.DOCX.value},
        )
        termo.download_pdf_url = reverse(
            'eventos:documentos-termos-download',
            kwargs={'pk': termo.pk, 'formato': DocumentoFormato.PDF.value},
        )

    return render(
        request,
        'eventos/documentos/termos_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficios_choices': Oficio.objects.order_by('-updated_at')[:200],
            'status_choices': TermoAutorizacao.STATUS_CHOICES,
            'modo_choices': TermoAutorizacao.MODO_CHOICES,
        },
    )


@require_http_methods(['GET'])
def termo_autorizacao_preview(request):
    oficio_ids = _parse_int_list(request.GET.getlist('oficios'))
    if not oficio_ids:
        oficio_ids = _parse_int_list(_clean(request.GET.get('oficios_ids')).split(','))
    evento, oficios, roteiro = _load_termo_context_objects(
        evento_id=_clean(request.GET.get('evento')),
        oficio_ids=oficio_ids,
        roteiro_id=_clean(request.GET.get('roteiro')),
    )
    context = build_termo_context(evento=evento, oficios=oficios, roteiro=roteiro)
    return JsonResponse(build_termo_preview_payload(context))


@require_http_methods(['GET', 'POST'])
def termo_autorizacao_novo(request):
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-termos'))
    context_source = _get_context_source(request)
    preselected_event, preselected_oficio = _resolve_preselected_context(request)
    form = TermoAutorizacaoForm(
        request.POST or None,
        initial=_build_termo_initial(preselected_event, preselected_oficio),
    )
    if request.method == 'POST' and form.is_valid():
        termos = form.save_terms(user=request.user)
        primeiro_termo = termos[0]
        mode_meta = _termo_mode_meta(primeiro_termo.modo_geracao)
        messages.success(
            request,
            f'{len(termos)} termo(s) gerado(s) com modelo {mode_meta["label"].lower()}.',
        )
        if len(termos) == 1:
            return redirect(return_to or reverse('eventos:documentos-termos-detalhe', kwargs={'pk': primeiro_termo.pk}))
        return redirect(return_to or reverse('eventos:documentos-termos'))
    return _render_termo_form(
        request,
        form=form,
        return_to=return_to,
        context_source=context_source,
        preselected_event=preselected_event,
        preselected_oficio=preselected_oficio,
    )


@require_http_methods(['GET', 'POST'])
def termo_autorizacao_novo_rapido(request):
    return termo_autorizacao_novo(request)


@require_http_methods(['GET', 'POST'])
def termo_autorizacao_novo_automatico_com_viatura(request):
    return termo_autorizacao_novo(request)


@require_http_methods(['GET', 'POST'])
def termo_autorizacao_novo_automatico_sem_viatura(request):
    return termo_autorizacao_novo(request)


@require_http_methods(['GET'])
def termo_autorizacao_detalhe(request, pk):
    obj = get_object_or_404(
        TermoAutorizacao.objects.select_related(
            'evento',
            'oficio',
            'roteiro',
            'viajante',
            'viajante__cargo',
            'veiculo',
        ).prefetch_related('oficios'),
        pk=pk,
    )
    related_lote = []
    if obj.lote_uuid:
        related_lote = list(
            TermoAutorizacao.objects.select_related('viajante')
            .filter(lote_uuid=obj.lote_uuid)
            .exclude(pk=obj.pk)
            .order_by('created_at')[:20]
        )
    return render(
        request,
        'eventos/documentos/termos_detalhe.html',
        {
            'object': obj,
            'mode_meta': _termo_mode_meta(obj.modo_geracao),
            'process_status': _termo_status_meta(obj),
            'context_display': _termo_context_display(obj),
            'lote_objects': related_lote,
            'related_oficios': list(obj.oficios.all()) or ([obj.oficio] if obj.oficio_id else []),
        },
    )


@require_http_methods(['GET', 'POST'])
def termo_autorizacao_editar(request, pk):
    obj = get_object_or_404(
        TermoAutorizacao.objects.select_related('evento', 'oficio', 'roteiro', 'viajante', 'veiculo').prefetch_related('oficios'),
        pk=pk,
    )
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-termos'))
    context_source = _get_context_source(request)
    form = TermoAutorizacaoEdicaoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Termo atualizado com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-termos-detalhe', kwargs={'pk': obj.pk}))
    return _render_termo_form(
        request,
        form=form,
        object_instance=obj,
        return_to=return_to,
        context_source=context_source,
        preselected_event=obj.evento,
        preselected_oficio=obj.oficio,
        read_only_context=True,
    )


@require_http_methods(['GET', 'POST'])
def termo_autorizacao_excluir(request, pk):
    obj = get_object_or_404(TermoAutorizacao, pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-termos'))
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Termo excluido com sucesso.')
        return redirect(return_to)
    return render(
        request,
        'eventos/documentos/termos_excluir.html',
        {'object': obj, 'return_to': return_to},
    )


@require_http_methods(['GET'])
def termo_autorizacao_download(request, pk, formato):
    obj = get_object_or_404(
        TermoAutorizacao.objects.select_related('viajante', 'veiculo', 'veiculo__combustivel'),
        pk=pk,
    )
    formato = _clean(formato).lower()
    if formato not in {DocumentoFormato.DOCX.value, DocumentoFormato.PDF.value}:
        raise Http404('Formato invalido.')
    docx_bytes = render_saved_termo_autorizacao_docx(obj)
    payload = docx_bytes
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if formato == DocumentoFormato.PDF.value:
        payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
        content_type = 'application/pdf'
    obj.ultima_geracao_em = timezone.now()
    obj.ultimo_formato_gerado = formato
    obj.save(update_fields=['ultima_geracao_em', 'ultimo_formato_gerado', 'updated_at'])
    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = (
        f'attachment; filename="{_build_saved_termo_filename(obj, formato)}"'
    )
    return response
