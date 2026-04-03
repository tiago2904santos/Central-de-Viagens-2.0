from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.forms import inlineformset_factory
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from cadastros.models import AssinaturaConfiguracao, Cargo, ConfiguracaoSistema, Estado, Viajante

from .forms import (
    JustificativaForm,
    OrdemServicoForm,
    PlanoTrabalhoForm,
    TermoAutorizacaoEdicaoForm,
    TermoAutorizacaoForm,
)
from .models import (
    EfetivoPlanoTrabalhoDocumento,
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
from .services.diarias import (
    PeriodMarker,
    TABELA_DIARIAS,
    calculate_periodized_diarias,
    calcular_diarias_com_valor,
    formatar_valor_diarias,
    infer_tipo_destino_from_paradas,
)
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
from .services.plano_trabalho_domain import (
    build_metas_formatada,
    build_recursos_necessarios_formatado,
    get_atividades_catalogo,
)
from .termos import TERMO_TEMPLATE_NAMES, build_termo_context, build_termo_preview_payload
from .utils import serializar_viajante_para_autocomplete, serializar_veiculo_para_oficio
from .views import _build_oficio_justificativa_info
from utils.valor_extenso import valor_por_extenso_ptbr


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

ORDER_DIR_CHOICES = (
    ('desc', 'Decrescente'),
    ('asc', 'Crescente'),
)


def _resolve_ordering(filters, allowed_fields, default_key):
    order_key = (filters.get('order_by') or default_key).strip().lower()
    order_dir = (filters.get('order_dir') or 'desc').strip().lower()
    order_key = order_key if order_key in allowed_fields else default_key
    order_dir = 'asc' if order_dir == 'asc' else 'desc'
    order_field = allowed_fields[order_key]
    if order_dir == 'desc':
        order_field = f'-{order_field}'
    filters['order_by'] = order_key
    filters['order_dir'] = order_dir
    return order_field

def _get_default_pt_cargo():
    preferred_names = [
        'AGENTE DE POLÃCIA CIVIL',
        'AGENTE DE POLICIA CIVIL',
    ]
    for name in preferred_names:
        cargo = Cargo.objects.filter(nome__iexact=name).first()
        if cargo:
            return cargo
    return Cargo.objects.filter(is_padrao=True).order_by('nome').first() or Cargo.objects.order_by('nome').first()


PlanoTrabalhoEfetivoFormSet = inlineformset_factory(
    PlanoTrabalho,
    EfetivoPlanoTrabalhoDocumento,
    fields=('cargo', 'quantidade'),
    extra=1,
    can_delete=True,
    widgets={
        'cargo': forms.Select(),
        'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
    },
)


def _extract_efetivo_rows(post_data, prefix='efetivo'):
    rows = []
    try:
        total = int(post_data.get(f'{prefix}-TOTAL_FORMS', 0) or 0)
    except (TypeError, ValueError):
        total = 0
    for idx in range(total):
        cargo = (post_data.get(f'{prefix}-{idx}-cargo') or '').strip()
        quantidade = (post_data.get(f'{prefix}-{idx}-quantidade') or '').strip()
        delete_flag = str(post_data.get(f'{prefix}-{idx}-DELETE') or '').lower() in {'on', 'true', '1'}
        if delete_flag:
            continue
        if not cargo and not quantidade:
            continue
        if not cargo or not quantidade:
            continue
        if not cargo.isdigit() or not quantidade.isdigit():
            continue
        rows.append((int(cargo), int(quantidade)))
    return rows


def _get_coordenador_operacional_create_url():
    try:
        return reverse('eventos:coordenadores-operacionais-cadastrar')
    except NoReverseMatch:
        return ''


def _get_solicitantes_manager_url():
    try:
        return reverse('eventos:plano-trabalho-solicitantes-lista')
    except NoReverseMatch:
        return ''


def _get_horarios_manager_url():
    try:
        return reverse('eventos:plano-trabalho-horarios-lista')
    except NoReverseMatch:
        return ''


@require_http_methods(['GET'])
def plano_trabalho_coordenadores_api(request):
    """API de busca de coordenadores operacionais para o Plano de Trabalho."""
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'results': []})
    from .models import CoordenadorOperacional
    qs = CoordenadorOperacional.objects.filter(ativo=True)
    qs = qs.filter(Q(nome__icontains=q) | Q(cargo__icontains=q) | Q(unidade__icontains=q))
    results = []
    for coord in qs.order_by('ordem', 'nome')[:20]:
        results.append({
            'id': coord.pk,
            'nome': coord.nome,
            'cargo': coord.cargo or '',
            'unidade': coord.unidade or '',
            'display': f'{coord.cargo} — {coord.nome}' if coord.cargo else coord.nome,
        })
    return JsonResponse({'results': results})


def _build_plano_trabalho_efetivo_formset(request, *, instance=None):
    has_payload = request.method == 'POST' and any(k.startswith('efetivo-') for k in request.POST.keys())
    default_cargo = _get_default_pt_cargo()
    initial = None
    if request.method != 'POST':
        has_existing_rows = bool(instance and instance.pk and instance.efetivos.exists())
        if not has_existing_rows:
            initial = [{'cargo': default_cargo.pk if default_cargo else '', 'quantidade': 0}]
    kwargs = {
        'instance': instance,
        'prefix': 'efetivo',
        'initial': initial,
    }
    if instance is None:
        kwargs['queryset'] = EfetivoPlanoTrabalhoDocumento.objects.none()
    formset = PlanoTrabalhoEfetivoFormSet(request.POST if has_payload else None, **kwargs)
    # When there are already saved rows, suppress the automatic blank extra row so
    # the user only sees what was persisted; new rows are added via the JS "+" button.
    has_existing_rows = bool(instance and instance.pk and instance.efetivos.exists())
    if has_existing_rows:
        formset.extra = 0
    return formset, has_payload, default_cargo


def _save_efetivo_rows(plano, rows):
    EfetivoPlanoTrabalhoDocumento.objects.filter(plano_trabalho=plano).delete()
    for cargo_id, quantidade in rows:
        if quantidade <= 0:
            continue
        EfetivoPlanoTrabalhoDocumento.objects.create(
            plano_trabalho=plano,
            cargo_id=cargo_id,
            quantidade=quantidade,
        )
    plano.quantidade_servidores = plano.efetivos.aggregate(total=Sum('quantidade')).get('total') or 0
    plano.save(update_fields=['quantidade_servidores', 'updated_at'])


def _build_plano_diarias_markers(plano):
    destinos = list(plano.destinos_json or [])
    if (
        plano.data_saida_sede
        and plano.hora_saida_sede
        and plano.data_chegada_sede
        and plano.hora_chegada_sede
        and destinos
    ):
        primeiro_destino = next(
            (
                item for item in destinos
                if isinstance(item, dict) and str(item.get('cidade_nome') or '').strip()
            ),
            None,
        )
        if primeiro_destino:
            saida_dt = datetime.combine(plano.data_saida_sede, plano.hora_saida_sede)
            chegada_dt = datetime.combine(plano.data_chegada_sede, plano.hora_chegada_sede)
            if chegada_dt > saida_dt:
                return [
                    PeriodMarker(
                        saida=saida_dt,
                        destino_cidade=str(primeiro_destino.get('cidade_nome') or '').strip(),
                        destino_uf=str(primeiro_destino.get('estado_sigla') or '').strip().upper(),
                    )
                ], chegada_dt

    if plano.roteiro_id:
        trechos = list(plano.roteiro.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'))
        markers = []
        chegada_final = None
        for trecho in trechos:
            if trecho.saida_dt and trecho.destino_cidade_id:
                markers.append(
                    PeriodMarker(
                        saida=trecho.saida_dt,
                        destino_cidade=trecho.destino_cidade.nome,
                        destino_uf=(trecho.destino_estado.sigla if trecho.destino_estado_id else ''),
                    )
                )
            if trecho.chegada_dt and (not chegada_final or trecho.chegada_dt > chegada_final):
                chegada_final = trecho.chegada_dt
        if markers and chegada_final:
            return markers, chegada_final

    oficios = list(plano.oficios.all())
    if not oficios and plano.oficio_id:
        oficios = [plano.oficio]
    for oficio in oficios:
        trechos = list(oficio.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'))
        if not trechos:
            continue
        markers = []
        for trecho in trechos:
            if not trecho.saida_data or not trecho.saida_hora or not trecho.destino_cidade_id:
                markers = []
                break
            markers.append(
                PeriodMarker(
                    saida=datetime.combine(trecho.saida_data, trecho.saida_hora),
                    destino_cidade=trecho.destino_cidade.nome,
                    destino_uf=(trecho.destino_estado.sigla if trecho.destino_estado_id else ''),
                )
            )
        if markers and oficio.retorno_chegada_data and oficio.retorno_chegada_hora:
            chegada_final = datetime.combine(oficio.retorno_chegada_data, oficio.retorno_chegada_hora)
            return markers, chegada_final
    return [], None


def _refresh_plano_diarias(plano):
    markers, chegada_final = _build_plano_diarias_markers(plano)
    if not markers or not chegada_final:
        PlanoTrabalho.objects.filter(pk=plano.pk).update(
            diarias_quantidade='',
            diarias_valor_total='',
            diarias_valor_unitario='',
            diarias_valor_extenso='',
            updated_at=timezone.now(),
        )
        return
    try:
        resultado = calculate_periodized_diarias(
            markers,
            chegada_final,
            quantidade_servidores=max(1, int(plano.quantidade_servidores or 1)),
        )
    except Exception:
        return
    totais = (resultado or {}).get('totais') or {}
    PlanoTrabalho.objects.filter(pk=plano.pk).update(
        diarias_quantidade=totais.get('total_diarias', '') or '',
        diarias_valor_total=totais.get('total_valor', '') or '',
        diarias_valor_unitario=totais.get('valor_por_servidor', '') or '',
        diarias_valor_extenso=totais.get('valor_extenso', '') or '',
        updated_at=timezone.now(),
    )

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
EMPTY_DISPLAY_ALIASES = {'-', 'â€”', 'Ã¢â‚¬â€'}
OFICIO_CONTEXT_CHOICES = [
    ('EVENTO', 'Com evento'),
    ('AVULSO', 'Sem evento'),
]
OFICIO_VIAGEM_STATUS_CHOICES = [
    ('FUTURA', 'Viagem futura'),
    ('EM_ANDAMENTO', 'Em andamento'),
    ('CONCLUIDA', 'Concluida'),
    ('HOJE', 'Viagens de hoje'),
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
OFICIO_DATE_SCOPE_CHOICES = [
    ('all', 'Periodo livre'),
    ('today', 'Hoje'),
    ('next_7', 'Proximos 7 dias'),
    ('upcoming', 'Viagens futuras'),
    ('past', 'Viagens passadas'),
]
OFICIO_ORDER_BY_DEFAULT = 'numero'
OFICIO_ORDER_DIR_DEFAULT = 'desc'
VIAGEM_STATUS_CARD_META = {
    'FUTURA': {'label': 'Vai acontecer', 'css_class': 'is-trip-future'},
    'EM_ANDAMENTO': {'label': 'Em andamento', 'css_class': 'is-trip-ongoing'},
    'CONCLUIDA': {'label': 'Ja aconteceu', 'css_class': 'is-trip-past'},
    'INDEFINIDA': {'label': 'Sem periodo', 'css_class': 'is-trip-muted'},
}
OFICIO_CARD_THEME_META = {
    'accent': {
        'label': 'Concluido',
        'css_class': 'is-tone-accent',
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


def _parse_decimal_money(value):
    raw = _clean(value)
    if not raw:
        return None
    normalized = raw.replace('R$', '').replace('r$', '').replace(' ', '')
    if ',' in normalized:
        normalized = normalized.replace('.', '').replace(',', '.')
    try:
        return Decimal(normalized)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_currency_brl(value):
    parsed = _parse_decimal_money(value)
    if parsed is None:
        return ''
    return f'R$ {formatar_valor_diarias(parsed)}'


def _is_empty_display_value(value):
    return _clean(value) in EMPTY_DISPLAY_ALIASES


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


def _parse_date(value):
    item = _clean(value)
    if not item:
        return None
    try:
        return date.fromisoformat(item)
    except ValueError:
        return None


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
    return 'â€”'


def _oficio_destinos_display(oficio):
    labels = []
    seen = set()
    for trecho in oficio.trechos.all():
        label = _label_local(
            getattr(trecho, 'destino_cidade', None),
            getattr(trecho, 'destino_estado', None),
        )
        if label == 'â€”' or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    if labels:
        return ', '.join(labels)
    return oficio.get_tipo_destino_display() or 'â€”'


def _roteiro_destinos_display(roteiro):
    labels = []
    for destino in roteiro.destinos.all():
        labels.append(_label_local(destino.cidade, destino.estado))
    return ', '.join(labels) if labels else 'â€”'


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
        return 'Ã¢â‚¬â€'
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
    default_label = getattr(oficio, 'get_status_display', lambda: oficio.status)() or oficio.status or 'Ã¢â‚¬â€'
    meta = OFICIO_STATUS_CARD_META.get(oficio.status, {})
    return {
        'label': meta.get('label', default_label),
        'css_class': meta.get('css_class', 'is-muted'),
    }


def _document_card_status_meta(status_key, fallback_label='Ã¢â‚¬â€'):
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

    status_meta = _document_card_status_meta(status_key, STATUS_LABELS.get(status_key, 'Ã¢â‚¬â€'))
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
        {'label': 'Protocolo', 'value': oficio.protocolo_formatado or 'Ã¢â‚¬â€'},
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
                    {'label': 'Primeira sa\u00edda', 'value': justificativa_info['primeira_saida_display'] or 'Ã¢â‚¬â€'},
                    {'label': 'Protocolo', 'value': oficio.protocolo_formatado or 'Ã¢â‚¬â€'},
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
                    'Marcado no resumo para geraÃƒÂ§ÃƒÂ£o do termo preenchido.'
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
        'date_start': _parse_date(request.GET.get('date_start')),
        'date_end': _parse_date(request.GET.get('date_end')),
        'date_scope': _parse_single_choice(
            request.GET.get('date_scope'),
            dict(OFICIO_DATE_SCOPE_CHOICES).keys(),
            'all',
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


def _oficio_list_first_name(value):
    parts = [part for part in _clean(value).split() if part]
    if not parts:
        return ''
    return parts[0]


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
    viajantes = [
        primeiro_nome
        for primeiro_nome in (_oficio_list_first_name(nome) for nome in _oficio_list_viajante_names(oficio))
        if primeiro_nome
    ]
    if not viajantes:
        return 'Nenhum servidor'
    return ', '.join(viajantes)


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
    if not text or _is_empty_display_value(text):
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


def _oficio_list_compact_date_display(oficio):
    inicio, _fim = _oficio_list_period_bounds(oficio)
    data_base = inicio or getattr(oficio, 'data_criacao', None)
    if not data_base:
        return 'A definir'
    return f'{data_base:%d/%m/%Y}'


def _oficio_list_download_action(actions, label):
    for action in actions:
        if action['label'] == label and action['available']:
            return action
    return None


def _oficio_list_table_actions(oficio, oficio_downloads):
    actions = []

    actions.append(
        {
            'label': 'Abrir',
            'aria_label': 'Abrir cadastro do oficio',
            'url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
            'css_class': 'btn-doc-action--primary',
            'icon': 'bi-box-arrow-up-right',
            'download': False,
            'icon_only': False,
        }
    )

    docx_action = _oficio_list_download_action(oficio_downloads['actions'], 'DOCX')
    if docx_action:
        actions.append(
            {
                'label': 'DOCX',
                'aria_label': 'Baixar DOCX do oficio',
                'url': docx_action['url'],
                'css_class': 'btn-doc-action--secondary',
                'icon': 'bi-filetype-docx',
                'download': True,
                'icon_only': True,
            }
        )

    pdf_action = _oficio_list_download_action(oficio_downloads['actions'], 'PDF')
    if pdf_action:
        actions.append(
            {
                'label': 'PDF',
                'aria_label': 'Baixar PDF do oficio',
                'url': pdf_action['url'],
                'css_class': 'btn-doc-action--pdf',
                'icon': 'bi-filetype-pdf',
                'download': True,
                'icon_only': True,
            }
        )

    actions.append(
        {
            'label': 'Excluir',
            'aria_label': 'Excluir oficio',
            'url': reverse('eventos:oficio-excluir', kwargs={'pk': oficio.pk}),
            'css_class': 'btn-doc-action--danger',
            'icon': 'bi-trash3',
            'download': False,
            'icon_only': True,
        }
    )
    return actions


def _oficio_list_footer_actions(oficio, oficio_downloads):
    actions = []
    actions.append(
        {
            'label': 'Abrir',
            'aria_label': 'Abrir cadastro do oficio',
            'url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
            'css_class': 'btn-doc-action--primary',
            'icon': 'bi-box-arrow-up-right',
            'download': False,
            'icon_only': False,
        }
    )

    docx_action = _oficio_list_download_action(oficio_downloads['actions'], 'DOCX')
    if docx_action:
        actions.append(
            {
                'label': 'DOCX',
                'aria_label': 'Baixar DOCX do oficio',
                'url': docx_action['url'],
                'css_class': 'btn-doc-action--secondary',
                'icon': 'bi-filetype-docx',
                'download': True,
                'icon_only': True,
            }
        )

    pdf_action = _oficio_list_download_action(oficio_downloads['actions'], 'PDF')
    if pdf_action:
        actions.append(
            {
                'label': 'PDF',
                'aria_label': 'Baixar PDF do oficio',
                'url': pdf_action['url'],
                'css_class': 'btn-doc-action--pdf',
                'icon': 'bi-filetype-pdf',
                'download': True,
                'icon_only': True,
            }
        )

    actions.append(
        {
            'label': 'Excluir',
            'aria_label': 'Excluir oficio',
            'url': reverse('eventos:oficio-excluir', kwargs={'pk': oficio.pk}),
            'css_class': 'btn-doc-action--danger',
            'icon': 'bi-trash3',
            'download': False,
            'icon_only': True,
        }
    )
    return actions


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
    if relative_label:
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
    if _is_empty_display_value(placa):
        placa = ''
    if _is_empty_display_value(modelo):
        modelo = ''
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
    if _is_empty_display_value(placa):
        placa = ''
    if _is_empty_display_value(modelo):
        modelo = ''

    vehicle_primary = 'Nao informado'
    vehicle_secondary = ''
    if placa and modelo:
        vehicle_primary = f'{placa} - {modelo}'
    elif placa:
        vehicle_primary = placa
        vehicle_secondary = 'Modelo nao informado'
    elif modelo:
        vehicle_primary = modelo

    driver_display = _oficio_list_driver_display(oficio)
    driver_secondary = 'Servidor cadastrado' if getattr(oficio, 'motorista_viajante_id', None) else 'Informado manualmente'
    driver_oficio = _clean(getattr(oficio, 'motorista_oficio_numero', ''))
    driver_protocolo = _clean(getattr(oficio, 'motorista_protocolo', ''))
    is_carona = bool(driver_oficio or driver_protocolo)
    if driver_display == 'Nao informado':
        driver_secondary = ''

    return {
        'title': 'Veiculo e motorista',
        'vehicle_primary': vehicle_primary,
        'vehicle_secondary': vehicle_secondary,
        'driver_primary': driver_display,
        'driver_secondary': driver_secondary,
        'is_carona': is_carona,
        'driver_oficio': driver_oficio or 'Nao informado',
        'driver_protocolo': driver_protocolo or 'Nao informado',
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
            'relative_label': 'acontece hoje' if delta == 0 else f'faltam {delta} dias',
        }
    if hoje > fim:
        delta = (hoje - fim).days
        meta = VIAGEM_STATUS_CARD_META['CONCLUIDA']
        return {
            'key': 'CONCLUIDA',
            'label': meta['label'],
            'css_class': meta['css_class'],
            'relative_label': 'aconteceu hoje' if delta == 0 else f'aconteceu ha {delta} dias',
        }

    meta = VIAGEM_STATUS_CARD_META['EM_ANDAMENTO']
    if inicio == fim == hoje:
        relative_label = 'acontece hoje'
    elif hoje == inicio:
        relative_label = 'comecou hoje'
    elif hoje == fim:
        relative_label = 'termina hoje'
    else:
        relative_label = 'em andamento'
    return {
        'key': 'EM_ANDAMENTO',
        'label': meta['label'],
        'css_class': meta['css_class'],
        'relative_label': relative_label,
    }


def _oficio_list_theme(oficio, viagem_status, today=None):
    inicio, fim = _oficio_list_period_bounds(oficio)
    hoje = today or timezone.localdate()
    theme_key = 'red'
    reason = 'Documento em rascunho ou pendente.'

    if oficio.status == Oficio.STATUS_FINALIZADO:
        if not inicio:
            theme_key = 'blue'
            reason = 'Oficio finalizado sem periodo definido.'
        else:
            fim = fim or inicio
            if hoje < inicio:
                theme_key = 'blue'
                reason = 'Finalizado para evento futuro.'
            elif inicio <= hoje <= fim:
                theme_key = 'orange'
                reason = 'Finalizado com evento em andamento.'
            else:
                theme_key = 'accent'
                reason = 'Finalizado com evento concluido.'

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
        'detail_url': reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
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
    if not saved_terms:
        return None

    subcards = []
    saved_viajante_ids = set()
    for termo in saved_terms:
        if termo.viajante_id:
            saved_viajante_ids.add(termo.viajante_id)
        subcards.append(_oficio_list_saved_term_card(termo))

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
    oficio_status = _oficio_process_status_meta(oficio)
    table_actions = _oficio_list_table_actions(oficio, oficio_downloads)
    footer_actions = _oficio_list_footer_actions(oficio, oficio_downloads)
    return {
        'pk': oficio.pk,
        'numero_display': _oficio_list_display_or_default(oficio.numero_formatado, 'A definir'),
        'data_display': _oficio_list_compact_date_display(oficio),
        'protocolo_display': _oficio_list_display_or_default(oficio.protocolo_formatado, 'Nao informado'),
        'destino_display': _oficio_list_display_or_default(destinos_display, 'Nao definido'),
        'servidores_display': _oficio_list_basic_viajantes_summary(oficio),
        'veiculo_display': vehicle_display,
        'status_badge': oficio_status,
        'table_actions': table_actions,
        'footer_actions': footer_actions,
        'theme': theme,
        'header_chips': [
            chip
            for chip in _oficio_list_header_chips(oficio, destinos_display, periodo_display)
            if chip
        ],
        'corner_badges': _oficio_list_corner_badges(oficio, viagem_status),
        'viajantes_block': _oficio_list_viajantes_block(oficio),
        'transport_block': _oficio_list_transport_block(oficio),
        'justificativa': justificativa,
        'termos': termos,
        'evento_url': reverse('eventos:guiado-painel', kwargs={'pk': oficio.evento_id}) if oficio.evento_id else '',
        'wizard_url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
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
            'is_today_trip': viagem_status['key'] == 'EM_ANDAMENTO' and viagem_status.get('relative_label') == 'acontece hoje',
            'has_justificativa': justificativa_info['filled'],
            'has_termo': bool(termos),
            'data_inicio': data_evento_inicio,
            'data_fim': data_evento_fim or data_evento_inicio,
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


def _matches_oficio_list_date(card, filters, today=None):
    inicio = card['filter_meta'].get('data_inicio')
    fim = card['filter_meta'].get('data_fim') or inicio
    if not inicio:
        return not (filters['date_start'] or filters['date_end'] or filters['date_scope'] != 'all')

    if filters['date_start'] and fim and fim < filters['date_start']:
        return False
    if filters['date_end'] and inicio > filters['date_end']:
        return False

    base_today = today or timezone.localdate()
    scope = filters['date_scope']
    if scope == 'all':
        return True
    if scope == 'today':
        return inicio <= base_today <= (fim or inicio)
    if scope == 'next_7':
        return base_today <= inicio <= (base_today + timedelta(days=7))
    if scope == 'upcoming':
        return inicio > base_today
    if scope == 'past':
        return (fim or inicio) < base_today
    return True


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
            'termos_autorizacao',
            'termos_autorizacao_relacionados',
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
            'HOJE' if card['filter_meta']['is_today_trip'] else card['filter_meta']['viagem_status'],
            dict(OFICIO_VIAGEM_STATUS_CHOICES).keys(),
        ):
            continue
        if not _matches_oficio_list_presence(filters['justificativa'], card['filter_meta']['has_justificativa']):
            continue
        if not _matches_oficio_list_presence(filters['termo'], card['filter_meta']['has_termo']):
            continue
        if not _matches_oficio_list_date(card, filters):
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
            'status_choices': Oficio.STATUS_CHOICES,
            'contexto_choices': OFICIO_CONTEXT_CHOICES,
            'viagem_status_choices': OFICIO_VIAGEM_STATUS_CHOICES,
            'presence_choices': OFICIO_PRESENCE_CHOICES,
            'order_by_choices': OFICIO_ORDER_BY_CHOICES,
            'order_dir_choices': OFICIO_ORDER_DIR_CHOICES,
            'date_scope_choices': OFICIO_DATE_SCOPE_CHOICES,
            'oficio_novo_url': reverse('eventos:oficio-novo'),
            'hide_page_header': True,
        },
    )


def roteiro_global_lista(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'status': _clean(request.GET.get('status')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'tipo': _clean(request.GET.get('tipo')).upper(),
        'order_by': _clean(request.GET.get('order_by')),
        'order_dir': _clean(request.GET.get('order_dir')),
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

    roteiro_order_map = {
        'updated_at': 'updated_at',
        'evento': 'evento__titulo',
        'status': 'status',
        'created_at': 'created_at',
    }
    ordering = _resolve_ordering(filters, roteiro_order_map, 'updated_at')

    page_obj = _paginate(
        queryset.distinct().order_by(ordering, '-created_at'),
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
            'order_by_choices': [
                ('updated_at', 'AtualizaÃ§Ã£o'),
                ('evento', 'Evento'),
                ('status', 'Status'),
                ('created_at', 'CriaÃ§Ã£o'),
            ],
            'order_dir_choices': ORDER_DIR_CHOICES,
            'novo_roteiro_url': (
                reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': selected_event.pk})
                if selected_event
                else ''
            ),
            'novo_roteiro_avulso_url': reverse('eventos:roteiro-avulso-cadastrar'),
            'eventos_url': reverse('eventos:lista'),
            'selected_event': selected_event,
        },
    )


def _base_documento_filters(request):
    return {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'oficio_id': _clean(request.GET.get('oficio_id')),
        'status': _clean(request.GET.get('status')),
        'order_by': _clean(request.GET.get('order_by')),
        'order_dir': _clean(request.GET.get('order_dir')),
    }


def _format_periodo_curto(data_inicio, data_fim):
    if not data_inicio:
        return 'A definir'
    if data_fim and data_fim != data_inicio:
        return f'{data_inicio:%d/%m/%Y} a {data_fim:%d/%m/%Y}'
    return f'{data_inicio:%d/%m/%Y}'


def _build_plano_trabalho_status_meta(plano, related_event=None):
    if plano.status == PlanoTrabalho.STATUS_FINALIZADO:
        inicio = plano.evento_data_inicio or getattr(related_event, 'data_inicio', None)
        fim = plano.evento_data_fim or getattr(related_event, 'data_fim', None) or inicio
        hoje = timezone.localdate()
        if not inicio or hoje < inicio:
            return {
                'label': plano.get_status_display(),
                'badge_css_class': 'is-info',
                'theme_class': 'is-tone-blue',
            }
        if inicio <= hoje <= fim:
            return {
                'label': plano.get_status_display(),
                'badge_css_class': 'is-warning',
                'theme_class': 'is-tone-orange',
            }
        return {
            'label': plano.get_status_display(),
            'badge_css_class': 'is-finalizado',
            'theme_class': 'is-tone-accent',
        }
    return {
        'label': plano.get_status_display(),
        'badge_css_class': 'is-rascunho',
        'theme_class': 'is-tone-red',
    }


def _resolve_temporal_theme(inicio, fim):
    hoje = timezone.localdate()
    if not inicio:
        return {'badge_css_class': 'is-info', 'theme_class': 'is-tone-blue'}
    limite = fim or inicio
    if hoje < inicio:
        return {'badge_css_class': 'is-info', 'theme_class': 'is-tone-blue'}
    if inicio <= hoje <= limite:
        return {'badge_css_class': 'is-warning', 'theme_class': 'is-tone-orange'}
    return {'badge_css_class': 'is-finalizado', 'theme_class': 'is-tone-accent'}


def _build_ordem_servico_status_meta(ordem):
    label = ordem.get_status_display()
    if ordem.status != OrdemServico.STATUS_FINALIZADO:
        return {
            'label': label,
            'badge_css_class': 'is-rascunho',
            'theme_class': 'is-tone-red',
        }

    inicio = getattr(getattr(ordem, 'evento', None), 'data_inicio', None)
    fim = getattr(getattr(ordem, 'evento', None), 'data_fim', None)
    if (not inicio or not fim) and ordem.oficio_id:
        oficio_inicio, oficio_fim = _oficio_list_period_bounds(ordem.oficio)
        inicio = inicio or oficio_inicio
        fim = fim or oficio_fim

    temporal = _resolve_temporal_theme(inicio, fim)
    return {
        'label': label,
        'badge_css_class': temporal['badge_css_class'],
        'theme_class': temporal['theme_class'],
    }


def _build_termo_card_theme_meta(termo):
    css = _clean(getattr(getattr(termo, 'process_status', {}), 'get', lambda *_: '')('css_class'))
    mapping = {
        'is-rascunho': {'badge_css_class': 'is-rascunho', 'theme_class': 'is-tone-red'},
        'is-finalizado-future': {'badge_css_class': 'is-info', 'theme_class': 'is-tone-blue'},
        'is-finalizado-ongoing': {'badge_css_class': 'is-warning', 'theme_class': 'is-tone-orange'},
        'is-finalizado': {'badge_css_class': 'is-finalizado', 'theme_class': 'is-tone-accent'},
    }
    return mapping.get(css, {'badge_css_class': 'is-muted', 'theme_class': 'is-tone-gray'})


def _resolve_plano_trabalho_periodo(plano, related_event):
    if plano.evento_data_inicio:
        return _format_periodo_curto(plano.evento_data_inicio, plano.evento_data_fim)
    if related_event and related_event.data_inicio:
        return _format_periodo_curto(related_event.data_inicio, related_event.data_fim)
    return 'Periodo a definir'


def _decorate_plano_trabalho_list_items(items):
    atividades_catalogo = get_atividades_catalogo()

    def _build_initials(value):
        parts = [chunk for chunk in str(value or '').strip().split() if chunk]
        if not parts:
            return 'PT'
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f'{parts[0][0]}{parts[1][0]}'.upper()

    def _parse_decimal_br(value):
        raw = _clean(value)
        if not raw:
            return None
        normalized = raw.replace('R$', '').replace(' ', '')
        if ',' in normalized:
            normalized = normalized.replace('.', '').replace(',', '.')
        try:
            return Decimal(normalized)
        except (InvalidOperation, ValueError, TypeError):
            return None

    for plano in items:
        related_oficios = plano.get_oficios_relacionados() if hasattr(plano, 'get_oficios_relacionados') else []
        related_event = plano.get_evento_relacionado() if hasattr(plano, 'get_evento_relacionado') else plano.evento
        status_meta = _build_plano_trabalho_status_meta(plano, related_event=related_event)
        destino_display = plano.destinos_formatados_display or 'Destino a definir'
        periodo_display = _resolve_plano_trabalho_periodo(plano, related_event)
        solicitante_display = (
            _clean(getattr(plano.solicitante, 'nome', ''))
            or _clean(plano.solicitante_outros)
            or 'Nao informado'
        )
        equipe_display = (
            f'{plano.quantidade_servidores} servidor(es)'
            if plano.quantidade_servidores
            else 'Nao informada'
        )
        coord_operacional_display = _clean(getattr(plano.coordenador_operacional, 'nome', '')) or 'Nao informado'
        coord_administrativo_display = _clean(getattr(plano.coordenador_administrativo, 'nome', '')) or 'Nao informado'
        roteiro_display = 'Manual' if (plano.destinos_json and not plano.roteiro_id) else (
            f'#{plano.roteiro_id}' if plano.roteiro_id else 'Nao vinculado'
        )
        diarias_display = _clean(plano.diarias_quantidade)
        if diarias_display and 'di' not in diarias_display.lower():
            diarias_display = f'{diarias_display} diarias'
        diarias_display = diarias_display or 'Nao calculadas'
        valor_total_textual = _clean(plano.diarias_valor_total)
        valor_total_decimal = _parse_decimal_br(valor_total_textual)
        if valor_total_decimal is None and plano.valor_diarias is not None:
            try:
                valor_total_model = Decimal(str(plano.valor_diarias))
            except (InvalidOperation, ValueError, TypeError):
                valor_total_model = None
            if valor_total_model is not None and valor_total_model > 0:
                valor_total_decimal = valor_total_model

        if valor_total_decimal is not None and valor_total_decimal > 0:
            valor_plano_display = f'R$ {formatar_valor_diarias(valor_total_decimal)}'
        else:
            valor_plano_display = valor_total_textual or 'Nao calculado'

        valor_unitario_display = _clean(plano.diarias_valor_unitario)
        if valor_total_decimal is not None and valor_total_decimal > 0 and (plano.quantidade_servidores or 0) > 0:
            valor_por_servidor = valor_total_decimal / Decimal(plano.quantidade_servidores)
            valor_unitario_display = f'R$ {formatar_valor_diarias(valor_por_servidor)}'
        elif valor_unitario_display:
            valor_unitario_decimal = _parse_decimal_br(valor_unitario_display)
            if valor_unitario_decimal is not None:
                valor_unitario_display = f'R$ {formatar_valor_diarias(valor_unitario_decimal)}'
        valor_unitario_display = valor_unitario_display or 'Nao calculado'
        valor_extenso_display = _clean(plano.diarias_valor_extenso) or 'Nao informado'

        saida_sede_display = 'Nao informada'
        if plano.data_saida_sede and plano.hora_saida_sede:
            saida_sede_display = f'{plano.data_saida_sede:%d/%m/%Y} {plano.hora_saida_sede:%H:%M}'
        elif plano.data_saida_sede:
            saida_sede_display = f'{plano.data_saida_sede:%d/%m/%Y}'

        chegada_sede_display = 'Nao informada'
        if plano.data_chegada_sede and plano.hora_chegada_sede:
            chegada_sede_display = f'{plano.data_chegada_sede:%d/%m/%Y} {plano.hora_chegada_sede:%H:%M}'
        elif plano.data_chegada_sede:
            chegada_sede_display = f'{plano.data_chegada_sede:%d/%m/%Y}'

        oficios_count = len(related_oficios)
        if oficios_count == 1:
            oficios_count_label = '1 oficio vinculado'
        elif oficios_count > 1:
            oficios_count_label = f'{oficios_count} oficios vinculados'
        else:
            oficios_count_label = 'Aguardando vinculo documental'
        atividades_labels = [
            item['nome']
            for item in atividades_catalogo
            if item['codigo'] in {
                codigo.strip()
                for codigo in _clean(plano.atividades_codigos).split(',')
                if codigo.strip()
            }
        ]
        resumo_curto = _clean(plano.recursos_texto) or ', '.join(atividades_labels[:3]) or _clean(plano.observacoes)
        resumo_curto = resumo_curto or 'Sem resumo adicional registrado para este plano.'
        plano.status_meta = status_meta
        plano.card_theme_class = status_meta['theme_class']
        plano.destino_display = destino_display
        plano.periodo_display = periodo_display
        plano.contexto_display = (
            (related_event.titulo or '').strip()
            if related_event
            else 'Plano sem evento vinculado'
        )
        plano.header_chips = [
            {'label': 'PLANO', 'value': f'PT {plano.numero_formatado or f"#{plano.pk}"}', 'css_class': 'is-key'},
            {'label': 'DESTINO', 'value': destino_display, 'css_class': ''},
            {'label': 'PERIODO', 'value': periodo_display, 'css_class': 'is-date'},
            {'label': 'SOLICITANTE', 'value': solicitante_display, 'css_class': ''},
        ]
        plano.oficios_block = {
            'count_label': oficios_count_label,
            'items': [
                {
                    'initials': _build_initials(oficio.numero_formatado or f'#{oficio.pk}'),
                    'name': f'Oficio {oficio.numero_formatado or f"#{oficio.pk}"} - {oficio.get_status_display()}',
                    'css_class': '',
                    'url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
                }
                for oficio in related_oficios
            ]
            or [
                {
                    'initials': 'PT',
                    'name': 'Nenhum oficio vinculado a este plano',
                    'css_class': 'is-empty',
                    'url': '',
                }
            ],
        }
        plano.calculadora_block = {
            'valor_total': valor_plano_display,
            'diarias': diarias_display,
            'equipe': equipe_display,
            'valor_unitario': valor_unitario_display,
            'saida_sede': saida_sede_display,
            'chegada_sede': chegada_sede_display,
            'valor_extenso': valor_extenso_display,
            'bloco_valor_total': {
                'titulo': 'Valor total',
                'valor': valor_plano_display,
                'subtitulo': diarias_display,
            },
            'bloco_valor_unitario': {
                'titulo': 'Valor por servidor',
                'valor': valor_unitario_display,
                'subtitulo': equipe_display,
            },
        }
        plano.info_rows = [
            {
                'label': 'Coordenadores',
                'operacional': coord_operacional_display,
                'administrativo': coord_administrativo_display,
            },
        ]
        plano.oficios_items = [
            {
                'label': f'Oficio {oficio.numero_formatado or f"#{oficio.pk}"}',
                'url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
                'meta': oficio.get_status_display(),
            }
            for oficio in related_oficios
        ]
        plano.oficios_count_label = oficios_count_label
        plano.open_url = reverse('eventos:documentos-planos-trabalho-detalhe', kwargs={'pk': plano.pk})
        plano.edit_url = reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': plano.pk})
        plano.download_docx_url = reverse(
            'eventos:documentos-planos-trabalho-download',
            kwargs={'pk': plano.pk, 'formato': DocumentoFormato.DOCX.value},
        )
        plano.download_pdf_url = reverse(
            'eventos:documentos-planos-trabalho-download',
            kwargs={'pk': plano.pk, 'formato': DocumentoFormato.PDF.value},
        )
        plano.delete_url = reverse('eventos:documentos-planos-trabalho-excluir', kwargs={'pk': plano.pk})
        plano.updated_display = plano.updated_at.strftime('%d/%m/%Y %H:%M')
        plano.resumo_curto = resumo_curto


def _build_plano_trabalho_form_ui_context(form, *, obj=None, preselected_event=None, preselected_oficio=None, data_preview=None):
    def get_selected_ids(field_name):
        values = []
        if form.is_bound:
            values.extend(form.data.getlist(field_name))
            single_value = form.data.get(field_name)
            if single_value and field_name != 'oficios_relacionados':
                values.append(single_value)
        else:
            initial = form.initial.get(field_name)
            if isinstance(initial, (list, tuple, set)):
                values.extend(initial)
            elif initial:
                values.append(initial)
        ids = []
        seen = set()
        for value in values:
            parsed = _parse_int(value)
            if not parsed or parsed in seen:
                continue
            seen.add(parsed)
            ids.append(parsed)
        return ids

    if obj and obj.pk:
        evento = obj.evento
    else:
        evento = preselected_event
        if not evento:
            evento_id = _parse_int(form.data.get('evento') if form.is_bound else form.initial.get('evento'))
            evento = Evento.objects.filter(pk=evento_id).first() if evento_id else None

    if obj and obj.pk:
        roteiro = obj.roteiro
    else:
        roteiro_id = _parse_int(form.data.get('roteiro') if form.is_bound else form.initial.get('roteiro'))
        roteiro = (
            RoteiroEvento.objects.select_related('evento').prefetch_related('destinos__cidade', 'destinos__estado')
            .filter(pk=roteiro_id)
            .first()
            if roteiro_id
            else None
        )

    if obj and obj.pk:
        related_oficios = list(obj.oficios.all())
        if not related_oficios and obj.oficio_id:
            related_oficios = [obj.oficio]
    else:
        related_ids = get_selected_ids('oficios_relacionados')
        oficio_ids = get_selected_ids('oficio')
        for oficio_id in oficio_ids:
            if oficio_id not in related_ids:
                related_ids.append(oficio_id)
        if not related_ids and preselected_oficio:
            related_oficios = [preselected_oficio]
        else:
            query = {
                oficio.pk: oficio
                for oficio in Oficio.objects.select_related('evento').filter(pk__in=related_ids)
            }
            related_oficios = [query[pk] for pk in related_ids if pk in query]

    destinos_labels = []
    seen_destinos = set()
    if obj and obj.pk and obj.destinos_json:
        for destino in obj.destinos_json:
            if not isinstance(destino, dict):
                continue
            cidade = _clean(destino.get('cidade_nome'))
            uf = _clean(destino.get('estado_sigla')).upper()
            label = f'{cidade}/{uf}' if cidade and uf else cidade
            if not label or label in seen_destinos:
                continue
            seen_destinos.add(label)
            destinos_labels.append(label)
    elif roteiro:
        for destino in roteiro.destinos.all():
            label = _label_local(getattr(destino, 'cidade', None), getattr(destino, 'estado', None))
            if label == 'â€”' or label in seen_destinos:
                continue
            seen_destinos.add(label)
            destinos_labels.append(label)
    elif evento:
        for destino in evento.destinos.all():
            label = _label_local(getattr(destino, 'cidade', None), getattr(destino, 'estado', None))
            if label == 'â€”' or label in seen_destinos:
                continue
            seen_destinos.add(label)
            destinos_labels.append(label)

    if obj and obj.pk:
        data_inicio = obj.evento_data_inicio or getattr(evento, 'data_inicio', None)
        data_fim = obj.evento_data_fim or getattr(evento, 'data_fim', None)
    else:
        data_inicio = None
        data_fim = None
        if form.is_bound:
            try:
                data_inicio = datetime.strptime(_clean(form.data.get('evento_data_inicio')), '%Y-%m-%d').date()
            except ValueError:
                data_inicio = None
            try:
                data_fim = datetime.strptime(_clean(form.data.get('evento_data_fim')), '%Y-%m-%d').date()
            except ValueError:
                data_fim = None
        if not data_inicio:
            data_inicio = getattr(evento, 'data_inicio', None)
        if not data_fim:
            data_fim = getattr(evento, 'data_fim', None)
        if not data_inicio and roteiro and getattr(roteiro, 'saida_dt', None):
            data_inicio = roteiro.saida_dt.date()
        if not data_fim and roteiro and getattr(roteiro, 'chegada_dt', None):
            data_fim = roteiro.chegada_dt.date()

    if obj and obj.pk and obj.atividades_codigos:
        selected_codes = [codigo.strip() for codigo in obj.atividades_codigos.split(',') if codigo.strip()]
    else:
        selected_codes = form.data.getlist('atividades_codigos') if form.is_bound else list(form.initial.get('atividades_codigos') or [])
    atividades_catalogo = get_atividades_catalogo()
    selected_activities = [
        item for item in atividades_catalogo
        if item['codigo'] in selected_codes
    ]

    solicitante_label = 'A definir'
    if obj and obj.pk:
        if obj.solicitante_id:
            solicitante_label = obj.solicitante.nome
        elif obj.solicitante_outros:
            solicitante_label = obj.solicitante_outros
    else:
        solicitante_raw = _clean(form.data.get('solicitante_outros') if form.is_bound else form.initial.get('solicitante_outros'))
        if solicitante_raw:
            solicitante_label = solicitante_raw

    number_label = obj.numero_formatado if obj and obj.pk else getattr(form, 'proximo_numero_preview', '') or 'A definir'
    status_label = obj.get_status_display() if obj and obj.pk else PlanoTrabalho.STATUS_RASCUNHO.title()

    return {
        'header_badges': [
            {'label': 'Plano', 'value': number_label},
            {'label': 'Status', 'value': status_label},
            {'label': 'Data base', 'value': (data_preview or timezone.localdate()).strftime('%d/%m/%Y')},
        ],
        'glance': {
            'evento': getattr(evento, 'titulo', '') or 'Sem evento vinculado',
            'oficios': ', '.join(oficio.numero_formatado or f'#{oficio.pk}' for oficio in related_oficios) or 'Sem ofÃ­cios vinculados',
            'roteiro': (f'Roteiro #{roteiro.pk}' if roteiro else 'Sem roteiro definido'),
            'periodo': _format_periodo_curto(data_inicio, data_fim),
            'destinos': ', '.join(destinos_labels) or 'Destinos preenchidos no formulÃ¡rio',
            'solicitante': solicitante_label,
            'atividades': [item['nome'] for item in selected_activities],
            'atividades_count_label': (
                f'{len(selected_activities)} atividade(s) selecionada(s)'
                if selected_activities
                else 'Nenhuma atividade selecionada'
            ),
        },
        'selected_codes': selected_codes,
    }


def _resolve_preselected_context(request):
    preselected_event_id = _parse_int(request.GET.get('preselected_event_id') or request.POST.get('preselected_event_id'))
    preselected_oficio_id = _parse_int(request.GET.get('preselected_oficio_id') or request.POST.get('preselected_oficio_id'))
    preselected_event = Evento.objects.filter(pk=preselected_event_id).first() if preselected_event_id else None
    preselected_oficio = Oficio.objects.filter(pk=preselected_oficio_id).first() if preselected_oficio_id else None
    return preselected_event, preselected_oficio


def _autosave_bool(value):
    return str(value or '').strip().lower() in {'1', 'true', 'on', 'yes'}


def _autosave_int(value):
    raw = str(value or '').strip()
    return int(raw) if raw.isdigit() else None


def _autosave_date(value):
    raw = _clean(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _autosave_datetime(value):
    raw = _clean(value)
    if not raw:
        return None
    normalized = raw
    if normalized.endswith('Z'):
        normalized = normalized[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _autosave_time(value):
    raw = _clean(value)
    if not raw:
        return None
    try:
        return time.fromisoformat(raw)
    except ValueError:
        return None


def _normalize_horario_autosave(padrao, manual):
    horario = _clean(padrao)
    if horario == PlanoTrabalhoForm.HORARIO_OUTROS:
        horario = _clean(manual)
    if not horario:
        return ''
    if '-' in horario and 'até' not in horario:
        parts = [part.strip() for part in horario.split('-', 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            horario = f'{parts[0]} até {parts[1]}'
    return horario


def _normalize_decimal_autosave(value):
    raw = _clean(value)
    if not raw:
        return ''
    raw = raw.replace('R$', '').replace('r$', '').replace(' ', '')
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    return raw


def _parse_autosave_request_payload(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (TypeError, ValueError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    payload = request.POST.dict()
    for key in ('oficios_relacionados_ids', 'coordenadores_ids', 'atividades_codigos', 'oficios_relacionados', 'roteiro'):
        values = request.POST.getlist(key)
        if len(values) > 1:
            payload[key] = values
    return payload


def _parse_autosave_list(value):
    if isinstance(value, list):
        return value
    raw = _clean(value)
    if not raw:
        return []
    if raw.startswith('['):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            parsed = []
        return parsed if isinstance(parsed, list) else []
    return [item.strip() for item in raw.split(',') if item.strip()]


def _split_roteiro_values(values):
    roteiro_id = ''
    roteiro_payload = ''
    for value in values or []:
        raw = _clean(value)
        if not raw:
            continue
        if raw.startswith('[') or raw.startswith('{'):
            roteiro_payload = raw
            continue
        if raw.isdigit():
            roteiro_id = raw
    return roteiro_id, roteiro_payload


def _normalize_plano_trabalho_post_data(post_data):
    if post_data is None:
        return None

    data = post_data.copy()
    roteiro_values = post_data.getlist('roteiro')
    roteiro_id, roteiro_payload = _split_roteiro_values(roteiro_values)
    if roteiro_values:
        data.setlist('roteiro', [roteiro_id])
    if roteiro_payload:
        data['roteiro_json'] = roteiro_payload
        data['destinos_payload'] = roteiro_payload
    return data


def _assign_plano_auto_number(plano):
    if plano.numero and plano.ano:
        return
    ano_atual = timezone.now().year
    plano.numero = PlanoTrabalho.get_next_available_numero(ano_atual)
    plano.ano = ano_atual
    plano.save(update_fields=['numero', 'ano', 'updated_at'])


@require_http_methods(['POST'])
def plano_trabalho_autosave(request):
    payload = _parse_autosave_request_payload(request)
    if payload is None:
        return JsonResponse({'success': False, 'error': 'Payload inválido.'}, status=400)

    plano_id = _autosave_int(payload.get('id'))
    if not plano_id:
        return JsonResponse({'success': False, 'error': 'ID do plano é obrigatório.'}, status=400)

    payload_keys = set(payload.keys())
    expected_updated_at = _autosave_datetime(payload.get('expected_updated_at')) if 'expected_updated_at' in payload_keys else None
    if 'expected_updated_at' in payload_keys and payload.get('expected_updated_at') and expected_updated_at is None:
        return JsonResponse({'success': False, 'error': 'expected_updated_at inválido.'}, status=400)

    dirty_fields = {
        str(item).strip()
        for item in _parse_autosave_list(payload.get('_dirty_fields'))
        if str(item).strip()
    }

    def _has(*keys):
        # Compatibilidade: clientes antigos (sem _dirty_fields) seguem por presença no payload.
        if dirty_fields:
            return any(key in dirty_fields for key in keys)
        return any(key in payload_keys for key in keys)

    with transaction.atomic():
        plano = PlanoTrabalho.objects.select_for_update().filter(pk=plano_id).first()
        if not plano:
            return JsonResponse({'success': False, 'error': 'Plano não encontrado.'}, status=404)

        if expected_updated_at and plano.updated_at and plano.updated_at != expected_updated_at:
            return JsonResponse(
                {
                    'success': False,
                    'error': 'Conflito de atualização. O plano foi alterado em outra aba/sessão.',
                    'code': 'stale_write',
                    'updated_at': timezone.localtime(plano.updated_at).isoformat(),
                },
                status=409,
            )

        if _autosave_bool(payload.get('force_rascunho')):
            plano.status = PlanoTrabalho.STATUS_RASCUNHO
        if not plano.numero or not plano.ano:
            _assign_plano_auto_number(plano)
        if _has('data_criacao'):
            plano.data_criacao = _autosave_date(payload.get('data_criacao')) or plano.data_criacao or timezone.localdate()
        elif not plano.data_criacao:
            plano.data_criacao = timezone.localdate()

        if _has('evento_id'):
            plano.evento_id = _autosave_int(payload.get('evento_id'))
        if _has('oficio_id'):
            plano.oficio_id = _autosave_int(payload.get('oficio_id'))
        if _has('roteiro_id'):
            plano.roteiro_id = _autosave_int(payload.get('roteiro_id'))
        if _has('coordenador_administrativo_id'):
            plano.coordenador_administrativo_id = _autosave_int(payload.get('coordenador_administrativo_id'))

        solicitante_escolha = _clean(payload.get('solicitante_escolha'))
        solicitante_outros = _clean(payload.get('solicitante_outros'))
        if _has('solicitante_escolha', 'solicitante_outros'):
            if solicitante_escolha and solicitante_escolha.isdigit():
                plano.solicitante_id = int(solicitante_escolha)
                plano.solicitante_outros = ''
            elif solicitante_escolha == PlanoTrabalhoForm.OUTROS_CHOICE:
                plano.solicitante_id = None
                plano.solicitante_outros = solicitante_outros
            else:
                plano.solicitante_id = None
                plano.solicitante_outros = solicitante_outros

        if _has('horario_atendimento_padrao', 'horario_atendimento_manual'):
            plano.horario_atendimento = _normalize_horario_autosave(
                payload.get('horario_atendimento_padrao'),
                payload.get('horario_atendimento_manual'),
            )
        if _has('evento_data_unica'):
            plano.evento_data_unica = _autosave_bool(payload.get('evento_data_unica'))
        if _has('evento_data_inicio'):
            plano.evento_data_inicio = _autosave_date(payload.get('evento_data_inicio'))
        if _has('evento_data_fim'):
            plano.evento_data_fim = _autosave_date(payload.get('evento_data_fim'))
        if plano.evento_data_unica and plano.evento_data_inicio:
            plano.evento_data_fim = plano.evento_data_inicio
        if _has('data_saida_sede'):
            plano.data_saida_sede = _autosave_date(payload.get('data_saida_sede'))
        if _has('hora_saida_sede'):
            plano.hora_saida_sede = _autosave_time(payload.get('hora_saida_sede'))
        if _has('data_chegada_sede'):
            plano.data_chegada_sede = _autosave_date(payload.get('data_chegada_sede'))
        if _has('hora_chegada_sede'):
            plano.hora_chegada_sede = _autosave_time(payload.get('hora_chegada_sede'))

        if _has('quantidade_servidores'):
            qtd_servidores = _autosave_int(payload.get('quantidade_servidores'))
            plano.quantidade_servidores = qtd_servidores if qtd_servidores and qtd_servidores > 0 else None

        if _has('atividades_codigos'):
            atividades = _parse_autosave_list(payload.get('atividades_codigos'))
            atividades = [str(item).strip().upper() for item in atividades if str(item).strip()]
            plano.atividades_codigos = ','.join(dict.fromkeys(atividades))
            plano.metas_formatadas = build_metas_formatada(plano.atividades_codigos)
            plano.recursos_texto = build_recursos_necessarios_formatado(plano.atividades_codigos)

        roteiro_payload_present = any(key in payload_keys for key in ('roteiro', 'roteiro_json', 'destinos_payload'))
        if roteiro_payload_present or _has('destinos_payload', 'roteiro_json', 'roteiro'):
            destinos = payload.get('destinos_payload')
            if destinos is None:
                destinos = payload.get('roteiro_json')
            if destinos is None:
                destinos = payload.get('roteiro')
            if not isinstance(destinos, list):
                try:
                    destinos = json.loads(destinos or '[]') if destinos else []
                except (TypeError, ValueError, UnicodeDecodeError):
                    destinos = []
            if not isinstance(destinos, list):
                destinos = []
            plano.destinos_json = destinos

        if _has('diarias', 'diarias_quantidade', 'qtd_diarias', 'diarias_valor_unitario', 'diarias_valor_total', 'valor_total_diarias', 'diarias_valor_extenso'):
            diarias_payload = payload.get('diarias') if isinstance(payload.get('diarias'), dict) else {}
            diarias_qtd_raw = (
                _clean(diarias_payload.get('qtd'))
                or _clean(payload.get('diarias_quantidade'))
                or _clean(payload.get('qtd_diarias'))
            )
            diarias_unit_raw = _clean(diarias_payload.get('valor_unitario')) or _clean(payload.get('diarias_valor_unitario'))
            diarias_total_raw = (
                _clean(diarias_payload.get('total'))
                or _clean(payload.get('diarias_valor_total'))
                or _clean(payload.get('valor_total_diarias'))
            )
            diarias_extenso_raw = _clean(diarias_payload.get('valor_extenso')) or _clean(payload.get('diarias_valor_extenso'))

            pessoas = plano.quantidade_servidores or 0
            try:
                diarias_calc = calcular_diarias_com_valor(
                    _normalize_decimal_autosave(diarias_qtd_raw),
                    _normalize_decimal_autosave(diarias_unit_raw),
                    pessoas,
                )
            except (ArithmeticError, ValueError, TypeError):
                diarias_calc = calcular_diarias_com_valor(0, 0, pessoas)

            plano.quantidade_diarias = diarias_calc['quantidade_diarias']
            plano.valor_diarias = diarias_calc['valor_total']
            plano.valor_diarias_extenso = diarias_extenso_raw or diarias_calc['valor_extenso']

            plano.diarias_quantidade = diarias_qtd_raw
            plano.diarias_valor_unitario = diarias_unit_raw
            plano.diarias_valor_total = diarias_total_raw or formatar_valor_diarias(diarias_calc['valor_total'])
            plano.diarias_valor_extenso = plano.valor_diarias_extenso

        plano.save()

        if _has('oficios_relacionados_ids', 'oficios_relacionados', 'oficio_id'):
            oficios_relacionados_ids = _parse_autosave_list(
                payload.get('oficios_relacionados_ids') or payload.get('oficios_relacionados')
            )
            parsed_oficios_ids = []
            for item in oficios_relacionados_ids:
                parsed = _autosave_int(item)
                if parsed:
                    parsed_oficios_ids.append(parsed)
            if plano.oficio_id and plano.oficio_id not in parsed_oficios_ids:
                parsed_oficios_ids.append(plano.oficio_id)
            plano.oficios.set(Oficio.objects.filter(pk__in=parsed_oficios_ids))

        if _has('coordenadores_ids'):
            coordenadores_ids = _parse_autosave_list(payload.get('coordenadores_ids'))
            parsed_coord_ids = []
            for item in coordenadores_ids:
                parsed = _autosave_int(item)
                if parsed:
                    parsed_coord_ids.append(parsed)
            plano.coordenadores.set(plano.coordenadores.model.objects.filter(pk__in=parsed_coord_ids, ativo=True))
            if parsed_coord_ids:
                plano.coordenador_operacional_id = parsed_coord_ids[0]
                plano.save(update_fields=['coordenador_operacional', 'updated_at'])

    return JsonResponse(
        {
            'success': True,
            'id': plano.pk,
            'status': plano.status,
            'valor_total': str(plano.valor_diarias or ''),
            'valor_extenso': plano.valor_diarias_extenso or '',
            'updated_at': timezone.localtime(plano.updated_at).isoformat(),
        }
    )


@require_http_methods(['POST'])
def plano_trabalho_calcular_diarias_api(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (TypeError, ValueError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'success': False, 'error': 'Payload inválido.'}, status=400)
    else:
        payload = request.POST.dict()

    if not isinstance(payload, dict):
        return JsonResponse({'ok': False, 'success': False, 'error': 'Payload inválido.'}, status=400)

    def _safe_int(value, default=0):
        try:
            parsed = int(str(value or '').strip())
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    def _to_dt(data_value, hora_value):
        data_str = str(data_value or '').strip()
        hora_str = str(hora_value or '').strip()
        if not data_str or not hora_str:
            return None
        try:
            return datetime.fromisoformat(f'{data_str}T{hora_str}')
        except (TypeError, ValueError):
            return None

    def _extract_destinos(raw_destinos):
        destinos = raw_destinos
        if isinstance(destinos, str):
            try:
                destinos = json.loads(destinos or '[]') if destinos else []
            except (TypeError, ValueError, UnicodeDecodeError):
                destinos = []
        if not isinstance(destinos, list):
            destinos = []

        paradas = []
        for item in destinos:
            if not isinstance(item, dict):
                continue
            cidade = str(item.get('cidade_nome') or item.get('cidade') or item.get('nome') or item.get('destino') or '').strip()
            uf = str(item.get('estado_sigla') or item.get('uf') or item.get('estado') or '').strip().upper()
            if cidade:
                paradas.append((cidade, uf))
        return paradas

    pessoas = _safe_int(payload.get('pessoas'), default=1)
    saida_dt = _to_dt(payload.get('saida_data'), payload.get('saida_hora'))
    chegada_dt = _to_dt(payload.get('chegada_data'), payload.get('chegada_hora'))
    if saida_dt and chegada_dt and chegada_dt <= saida_dt:
        return JsonResponse(
            {'ok': False, 'success': False, 'error': 'Data de chegada deve ser maior que saída.'},
        )

    paradas = _extract_destinos(payload.get('destinos_payload'))
    if not paradas:
        cidade_fallback = str(payload.get('destino_cidade') or payload.get('cidade') or '').strip()
        uf_fallback = str(payload.get('destino_uf') or payload.get('uf') or '').strip().upper()
        if cidade_fallback:
            paradas = [(cidade_fallback, uf_fallback)]

    # Fallback compatível: quando o frontend envia payload parcial (qtd/valor/pessoas),
    # mantém o comportamento legado sem gerar 400 em chamadas intermediárias.
    if not (saida_dt and chegada_dt and paradas):
        qtd_raw = _clean(payload.get('qtd')) or _clean(payload.get('diarias_quantidade'))
        valor_raw = _clean(payload.get('valor')) or _clean(payload.get('diarias_valor_unitario'))
        qtd_norm = _normalize_decimal_autosave(qtd_raw)
        valor_norm = _normalize_decimal_autosave(valor_raw)
        pessoas_norm = max(1, pessoas)
        try:
            dados = calcular_diarias_com_valor(
                qtd_norm,
                valor_norm,
                pessoas_norm,
            )
            dados_por_servidor = calcular_diarias_com_valor(qtd_norm, valor_norm, 1)
        except (ArithmeticError, ValueError, TypeError):
            dados = calcular_diarias_com_valor(0, 0, pessoas_norm)
            dados_por_servidor = calcular_diarias_com_valor(0, 0, 1)

        qtd_label = _clean(qtd_raw) or str(dados['quantidade_diarias'])
        valor_total_label = f'R$ {formatar_valor_diarias(dados["valor_total"])}' if dados['valor_total'] else ''
        if _clean(valor_raw):
            valor_unitario_normalizado = _normalize_decimal_autosave(valor_raw)
            try:
                valor_unitario_label = f'R$ {formatar_valor_diarias(Decimal(valor_unitario_normalizado))}' if valor_unitario_normalizado else ''
            except (InvalidOperation, TypeError, ValueError):
                valor_unitario_label = _clean(valor_raw)
        else:
            valor_unitario_base = dados.get('valor_unitario', '')
            valor_unitario_label = f'R$ {formatar_valor_diarias(valor_unitario_base)}' if valor_unitario_base else ''
        valor_por_servidor_label = f'R$ {formatar_valor_diarias(dados_por_servidor.get("valor_total", ""))}'
        valor_por_servidor_extenso = dados_por_servidor.get('valor_extenso', '') or ''
        valor_extenso_label = dados.get('valor_extenso', '') or ''

        return JsonResponse(
            {
                'ok': True,
                'success': True,
                'tipo_destino': '',
                'periodos': [],
                'totais': {
                    'total_diarias': qtd_label,
                    'total_horas': '',
                    'total_valor': valor_total_label,
                    'valor_extenso': valor_extenso_label,
                    'quantidade_servidores': pessoas_norm,
                    'diarias_por_servidor': qtd_label,
                    'valor_por_servidor': valor_por_servidor_label,
                    'valor_por_servidor_extenso': valor_por_servidor_extenso,
                    'valor_unitario_referencia': valor_unitario_label,
                },
                'qtd_diarias': qtd_label,
                'quantidade_diarias': qtd_label,
                'valor_total': valor_total_label,
                'valor_extenso': valor_extenso_label,
                'valor_unitario': valor_unitario_label,
                'valor_por_servidor': valor_por_servidor_label,
                'valor_por_servidor_extenso': valor_por_servidor_extenso,
            }
        )

    destino_cidade, destino_uf = paradas[0]
    markers = [
        PeriodMarker(
            saida=saida_dt,
            destino_cidade=destino_cidade,
            destino_uf=destino_uf,
        )
    ]

    try:
        resultado = calculate_periodized_diarias(
            markers,
            chegada_dt,
            quantidade_servidores=max(1, pessoas),
        )
    except ValueError as exc:
        return JsonResponse({'ok': False, 'success': False, 'error': str(exc)})

    tipo_destino = infer_tipo_destino_from_paradas(paradas)
    resultado['tipo_destino'] = tipo_destino
    totais = (resultado or {}).get('totais') or {}
    valor_por_servidor = totais.get('valor_por_servidor', '') or ''
    valor_por_servidor_extenso = totais.get('valor_por_servidor_extenso', '') or ''
    if not valor_por_servidor_extenso and valor_por_servidor:
        valor_por_servidor_extenso = valor_por_extenso_ptbr(valor_por_servidor)
        if valor_por_servidor_extenso == '(preencher manualmente)':
            valor_por_servidor_extenso = ''
    if valor_por_servidor_extenso:
        totais['valor_por_servidor_extenso'] = valor_por_servidor_extenso

    return JsonResponse(
        {
            'ok': True,
            'success': True,
            'tipo_destino': tipo_destino,
            'periodos': resultado.get('periodos', []),
            'totais': totais,
            # Compatibilidade com consumidores legados do PT
            'qtd_diarias': totais.get('total_diarias', '') or '',
            'quantidade_diarias': totais.get('total_diarias', '') or '',
            'valor_total': totais.get('total_valor', '') or '',
            'valor_extenso': totais.get('valor_extenso', '') or '',
            'valor_unitario': totais.get('valor_unitario_referencia', '') or '',
            'valor_por_servidor': valor_por_servidor,
            'valor_por_servidor_extenso': totais.get('valor_por_servidor_extenso', '') or '',
        }
    )


def planos_trabalho_global(request):
    filters = _base_documento_filters(request)
    queryset = (
        PlanoTrabalho.objects.select_related('evento', 'oficio', 'solicitante', 'roteiro')
        .prefetch_related('oficios', 'oficios__evento')
        .all()
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(recursos_texto__icontains=filters['q'])
            | Q(observacoes__icontains=filters['q'])
            | Q(evento__titulo__icontains=filters['q'])
            | Q(oficio__motivo__icontains=filters['q'])
            | Q(oficios__motivo__icontains=filters['q'])
        )
    if filters['evento_id'].isdigit():
        event_id = int(filters['evento_id'])
        queryset = queryset.filter(Q(evento_id=event_id) | Q(oficios__evento_id=event_id))
    if filters['oficio_id'].isdigit():
        queryset = queryset.filter(Q(oficio_id=int(filters['oficio_id'])) | Q(oficios__id=int(filters['oficio_id'])))
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])

    plano_order_map = {
        'numero': 'numero',
        'updated_at': 'updated_at',
        'created_at': 'created_at',
        'status': 'status',
        'evento': 'evento__titulo',
    }
    ordering = _resolve_ordering(filters, plano_order_map, 'numero')

    queryset = queryset.distinct()
    page_obj = _paginate(queryset.order_by(ordering, '-created_at'), request.GET.get('page'))
    object_list = list(page_obj.object_list)
    _decorate_plano_trabalho_list_items(object_list)
    return render(
        request,
        'eventos/documentos/planos_trabalho_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficios_choices': Oficio.objects.order_by('-updated_at')[:200],
            'status_choices': PlanoTrabalho.STATUS_CHOICES,
            'order_by_choices': [
                ('numero', 'Numero'),
                ('updated_at', 'AtualizaÃ§Ã£o'),
                ('created_at', 'CriaÃ§Ã£o'),
                ('status', 'Status'),
                ('evento', 'Evento'),
            ],
            'order_dir_choices': ORDER_DIR_CHOICES,
            'plano_novo_url': reverse('eventos:documentos-planos-trabalho-novo'),
        },
    )


@require_http_methods(['GET', 'POST'])
def plano_trabalho_novo(request):
    return_to_default = reverse('eventos:documentos-planos-trabalho')
    return_to = _get_safe_return_to(request, return_to_default)
    context_source = _get_context_source(request)
    preselected_event, preselected_oficio = _resolve_preselected_context(request)

    if request.method == 'GET':
        novo = PlanoTrabalho.objects.create(
            status=PlanoTrabalho.STATUS_RASCUNHO,
            data_criacao=timezone.localdate(),
            evento=preselected_event,
            oficio=preselected_oficio,
        )
        _assign_plano_auto_number(novo)
        if preselected_oficio:
            novo.oficios.add(preselected_oficio)
        query = {}
        if return_to:
            query['return_to'] = return_to
        if context_source:
            query['context_source'] = context_source
        edit_url = reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': novo.pk})
        if query:
            edit_url = f"{edit_url}?{urlencode(query)}"
        return redirect(edit_url)

    initial = {}
    if preselected_event:
        initial['evento'] = preselected_event.pk
    if preselected_oficio:
        initial['oficio'] = preselected_oficio.pk
        initial['oficios_relacionados'] = [preselected_oficio.pk]

    bound_data = _normalize_plano_trabalho_post_data(request.POST) if request.method == 'POST' else None
    form = PlanoTrabalhoForm(bound_data or None, initial=initial)
    formset, has_efetivo_payload, default_cargo = _build_plano_trabalho_efetivo_formset(request)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        if has_efetivo_payload:
            rows = _extract_efetivo_rows(request.POST, prefix='efetivo')
            _save_efetivo_rows(obj, rows)
            _refresh_plano_diarias(obj)
        messages.success(request, 'Plano de trabalho criado com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-planos-trabalho-detalhe', kwargs={'pk': obj.pk}))

    ui_context = _build_plano_trabalho_form_ui_context(
        form,
        preselected_event=preselected_event,
        preselected_oficio=preselected_oficio,
        data_preview=timezone.localdate(),
    )

    return render(
        request,
        'eventos/documentos/planos_trabalho_form.html',
        {
            'form': form,
            'efetivo_formset': formset,
            'object': None,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': preselected_event.pk if preselected_event else '',
            'preselected_oficio_id': preselected_oficio.pk if preselected_oficio else '',
            'estados_choices': Estado.objects.filter(ativo=True).order_by('nome'),
            'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
            'proximo_numero_pt': form.proximo_numero_preview,
            'data_geracao_preview': timezone.localdate(),
            'pt_header_badges': ui_context['header_badges'],
            'pt_glance': ui_context['glance'],
            'pt_selected_activity_codes': ui_context['selected_codes'],
            'plano_trabalho_atividades_catalogo': get_atividades_catalogo(),
            'pt_default_cargo_label': default_cargo.nome if default_cargo else 'Cargo padrÃ£o',
            'pt_coordenador_operacional_create_url': _get_coordenador_operacional_create_url(),
            'pt_solicitantes_manager_url': _get_solicitantes_manager_url(),
            'pt_horarios_manager_url': _get_horarios_manager_url(),
            'buscar_coordenadores_url': reverse('eventos:documentos-planos-trabalho-coordenadores-api'),
            'selected_coordenadores_payload': [],
            'hide_page_header': True,
        },
    )


@require_http_methods(['GET', 'POST'])
def plano_trabalho_editar(request, pk):
    obj = get_object_or_404(PlanoTrabalho.objects.select_related('evento', 'oficio', 'roteiro').prefetch_related('oficios'), pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-planos-trabalho'))
    context_source = _get_context_source(request)
    bound_data = _normalize_plano_trabalho_post_data(request.POST) if request.method == 'POST' else None
    form = PlanoTrabalhoForm(bound_data or None, instance=obj)
    formset, has_efetivo_payload, default_cargo = _build_plano_trabalho_efetivo_formset(request, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save()
        if has_efetivo_payload:
            rows = _extract_efetivo_rows(request.POST, prefix='efetivo')
            _save_efetivo_rows(obj, rows)
            _refresh_plano_diarias(obj)
        if request.POST.get('finalizar'):
            obj.status = PlanoTrabalho.STATUS_FINALIZADO
            obj.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Plano de trabalho finalizado.')
            return redirect(return_to or reverse('eventos:documentos-planos-trabalho'))
        messages.success(request, 'Plano de trabalho atualizado como rascunho.')
        return redirect(return_to or reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': obj.pk}))

    ui_context = _build_plano_trabalho_form_ui_context(
        form,
        obj=obj,
        data_preview=obj.data_criacao,
    )
    return render(
        request,
        'eventos/documentos/planos_trabalho_form.html',
        {
            'form': form,
            'efetivo_formset': formset,
            'object': obj,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': obj.evento_id or '',
            'preselected_oficio_id': obj.oficio_id or '',
            'estados_choices': Estado.objects.filter(ativo=True).order_by('nome'),
            'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
            'proximo_numero_pt': obj.numero_formatado,
            'data_geracao_preview': obj.data_criacao,
            'pt_header_badges': ui_context['header_badges'],
            'pt_glance': ui_context['glance'],
            'pt_selected_activity_codes': ui_context['selected_codes'],
            'plano_trabalho_atividades_catalogo': get_atividades_catalogo(),
            'pt_default_cargo_label': default_cargo.nome if default_cargo else 'Cargo padrÃ£o',
            'pt_coordenador_operacional_create_url': _get_coordenador_operacional_create_url(),
            'pt_solicitantes_manager_url': _get_solicitantes_manager_url(),
            'pt_horarios_manager_url': _get_horarios_manager_url(),
            'buscar_coordenadores_url': reverse('eventos:documentos-planos-trabalho-coordenadores-api'),
            'selected_coordenadores_payload': [
                {'id': c.pk, 'nome': c.nome, 'cargo': c.cargo or '', 'display': f'{c.cargo} — {c.nome}' if c.cargo else c.nome}
                for c in obj.coordenadores.filter(ativo=True)
            ],
            'hide_page_header': True,
            'plano_id': obj.pk,
        },
    )


@require_http_methods(['GET'])
def plano_trabalho_detalhe(request, pk):
    obj = get_object_or_404(PlanoTrabalho.objects.select_related('evento', 'oficio', 'solicitante', 'roteiro').prefetch_related('oficios'), pk=pk)
    obj.diarias_valor_total_display = _format_currency_brl(obj.diarias_valor_total or obj.valor_diarias)
    if obj.valor_diarias is not None and (obj.quantidade_servidores or 0) > 0:
        valor_por_servidor = Decimal(obj.valor_diarias) / Decimal(obj.quantidade_servidores)
        obj.diarias_valor_unitario_display = _format_currency_brl(valor_por_servidor)
    else:
        obj.diarias_valor_unitario_display = _format_currency_brl(obj.diarias_valor_unitario)
    return render(request, 'eventos/documentos/planos_trabalho_detalhe.html', {'object': obj})


@require_http_methods(['GET', 'POST'])
def plano_trabalho_excluir(request, pk):
    obj = get_object_or_404(PlanoTrabalho, pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-planos-trabalho'))
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Plano de trabalho excluÃ­do.')
        return redirect(return_to)
    return render(
        request,
        'eventos/documentos/planos_trabalho_excluir.html',
        {'object': obj, 'return_to': return_to},
    )


@require_http_methods(['GET'])
def plano_trabalho_download(request, pk, formato):
    obj = get_object_or_404(PlanoTrabalho.objects.select_related('oficio').prefetch_related('oficios'), pk=pk)
    formato = _clean(formato).lower()
    if formato not in {DocumentoFormato.DOCX.value, DocumentoFormato.PDF.value}:
        raise Http404('Formato invÃ¡lido.')
    related_oficios = obj.get_oficios_relacionados() if hasattr(obj, 'get_oficios_relacionados') else list(obj.oficios.all())
    oficio_ref = related_oficios[0] if len(related_oficios) == 1 else None
    docx_bytes = render_plano_trabalho_docx(oficio_ref) if oficio_ref else render_plano_trabalho_model_docx(obj)
    payload = docx_bytes
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if formato == DocumentoFormato.PDF.value:
        payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
        content_type = 'application/pdf'
    response = HttpResponse(payload, content_type=content_type)
    ext = 'docx' if formato == DocumentoFormato.DOCX.value else 'pdf'
    response['Content-Disposition'] = f'attachment; filename="plano_trabalho_{obj.pk}.{ext}"'
    return response


def _ordem_servico_viajantes_display(ordem):
    nomes = list(ordem.get_viajantes_relacionados())
    if not nomes and ordem.responsaveis:
        return ', '.join([line.strip() for line in (ordem.responsaveis or '').splitlines() if line.strip()])
    nomes = [str(v.nome or '').strip() for v in nomes if str(v.nome or '').strip()]
    if not nomes:
        return 'Nao informado'
    if len(nomes) <= 3:
        return ', '.join(nomes)
    return f"{', '.join(nomes[:3])} +{len(nomes) - 3}"


def _ordem_servico_destinos_display(ordem):
    destinos = []
    seen = set()
    for item in ordem.destinos_json or []:
        if not isinstance(item, dict):
            continue
        cidade = _clean(item.get('cidade_nome'))
        uf = _clean(item.get('estado_sigla')).upper()
        if cidade and uf:
            label = f'{cidade}/{uf}'
        elif cidade:
            label = cidade
        else:
            continue
        if label in seen:
            continue
        seen.add(label)
        destinos.append(label)
    return ', '.join(destinos) if destinos else 'Nao informado'


def _ordem_servico_chefia_contexto():
    config = ConfiguracaoSistema.get_singleton()
    assinatura = (
        AssinaturaConfiguracao.objects.select_related('viajante', 'viajante__cargo')
        .filter(
            configuracao=config,
            tipo=AssinaturaConfiguracao.TIPO_ORDEM_SERVICO,
            ativo=True,
        )
        .order_by('ordem', 'pk')
        .first()
    )

    nome = ''
    cargo = ''
    if assinatura and assinatura.viajante_id:
        nome = _clean(getattr(assinatura.viajante, 'nome', ''))
        cargo = _clean(getattr(getattr(assinatura.viajante, 'cargo', None), 'nome', ''))

    if not nome:
        nome = _clean(getattr(config, 'nome_chefia', ''))
    if not cargo:
        cargo = _clean(getattr(config, 'cargo_chefia', ''))

    return {
        'nome': nome or 'Nao informada',
        'cargo': cargo or 'Cargo nao informado',
    }


def _ordem_servico_missing_fields(ordem):
    missing = []
    if not ordem.data_deslocamento:
        missing.append('data de deslocamento')
    if not _clean(ordem.motivo_texto or ordem.finalidade):
        missing.append('motivo')
    if not (ordem.destinos_json or []):
        missing.append('destino')
    if not ordem.get_viajantes_relacionados() and not _clean(ordem.responsaveis):
        missing.append('equipe')
    return missing


def _ordem_servico_viajantes_items(ordem, limit=4):
    viajantes = list(ordem.get_viajantes_relacionados())
    items = []

    for viajante in viajantes[:limit]:
        nome = _clean(getattr(viajante, 'nome', ''))
        if not nome:
            continue
        cargo = _clean(getattr(getattr(viajante, 'cargo', None), 'nome', ''))
        lotacao = _clean(getattr(getattr(viajante, 'unidade_lotacao', None), 'nome', ''))
        items.append({'nome': nome, 'cargo': cargo, 'lotacao': lotacao})

    if items:
        restante = len(viajantes) - len(items)
        if restante > 0:
            items.append({'nome': f'+{restante} servidor(es)', 'cargo': '', 'lotacao': ''})
        return items

    nomes = [_clean(line) for line in str(ordem.responsaveis or '').splitlines() if _clean(line)]
    for nome in nomes[:limit]:
        items.append({'nome': nome, 'cargo': '', 'lotacao': ''})
    restante = len(nomes) - len(items)
    if restante > 0:
        items.append({'nome': f'+{restante} servidor(es)', 'cargo': '', 'lotacao': ''})

    if not items:
        return [{'nome': 'Nenhum servidor vinculado', 'cargo': '', 'lotacao': ''}]
    return items


def ordens_servico_global(request):
    filters = _base_documento_filters(request)
    queryset = OrdemServico.objects.select_related('evento', 'oficio').prefetch_related(
        Prefetch('viajantes', queryset=Viajante.objects.select_related('cargo', 'unidade_lotacao')),
        Prefetch('oficio__viajantes', queryset=Viajante.objects.select_related('cargo', 'unidade_lotacao')),
    ).all()
    chefia_contexto = _ordem_servico_chefia_contexto()
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

    ordem_order_map = {
        'updated_at': 'updated_at',
        'created_at': 'created_at',
        'status': 'status',
        'evento': 'evento__titulo',
        'numero': 'numero',
    }
    ordering = _resolve_ordering(filters, ordem_order_map, 'numero')

    page_obj = _paginate(queryset.order_by(ordering, '-created_at'), request.GET.get('page'))
    object_list = list(page_obj.object_list)
    for ordem in object_list:
        ordem.status_meta = _build_ordem_servico_status_meta(ordem)
        ordem.card_theme_class = ordem.status_meta['theme_class']
        ordem.open_url = reverse('eventos:documentos-ordens-servico-detalhe', kwargs={'pk': ordem.pk})
        ordem.edit_url = reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': ordem.pk})
        ordem.delete_url = reverse('eventos:documentos-ordens-servico-excluir', kwargs={'pk': ordem.pk})
        ordem.download_docx_url = reverse(
            'eventos:documentos-ordens-servico-download',
            kwargs={'pk': ordem.pk, 'formato': DocumentoFormato.DOCX.value},
        )
        ordem.download_pdf_url = reverse(
            'eventos:documentos-ordens-servico-download',
            kwargs={'pk': ordem.pk, 'formato': DocumentoFormato.PDF.value},
        )
        ordem.evento_display = (
            (ordem.evento.titulo or '').strip() if ordem.evento_id else 'Sem evento'
        )
        ordem.oficio_display = (
            ordem.oficio.numero_formatado if ordem.oficio_id else 'Sem oficio'
        )
        ordem.data_criacao_display = ordem.data_criacao.strftime('%d/%m/%Y') if ordem.data_criacao else 'Nao informada'
        ordem.data_deslocamento_display = ordem.data_deslocamento.strftime('%d/%m/%Y') if ordem.data_deslocamento else 'Nao informada'
        ordem.viajantes_display = _ordem_servico_viajantes_display(ordem)
        ordem.destinos_display = _ordem_servico_destinos_display(ordem)
        ordem.motivo_display = _clean(ordem.motivo_texto or ordem.finalidade) or 'Nao informado'
        ordem.missing_fields = _ordem_servico_missing_fields(ordem)
        ordem.header_chips = [
            {'label': 'Ordem', 'value': ordem.numero_formatado or EMPTY_DISPLAY, 'css_class': 'is-key'},
            {'label': 'Evento', 'value': ordem.evento_display, 'css_class': ''},
            {'label': 'Oficio', 'value': ordem.oficio_display, 'css_class': ''},
            {'label': 'Criacao', 'value': ordem.data_criacao_display, 'css_class': 'is-date'},
            {'label': 'Deslocamento', 'value': ordem.data_deslocamento_display, 'css_class': 'is-date'},
        ]
        ordem.corner_badges = [
            {'value': ordem.status_meta['label'], 'css_class': ordem.status_meta['badge_css_class']},
        ]
        if ordem.missing_fields:
            ordem.corner_badges.append({'value': f'Pendencias: {len(ordem.missing_fields)}', 'css_class': 'is-warning'})
        ordem.viajantes_block = {
            'count_label': f"{len(ordem.get_viajantes_relacionados()) or len([line for line in str(ordem.responsaveis or '').splitlines() if _clean(line)])} servidor(es)",
            'items': _ordem_servico_viajantes_items(ordem),
        }
        ordem.contexto_block = {
            'destinos': ordem.destinos_display,
            'chefia_nome': chefia_contexto['nome'],
            'chefia_cargo': chefia_contexto['cargo'],
        }
    return render(
        request,
        'eventos/documentos/ordens_servico_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficios_choices': Oficio.objects.order_by('-updated_at')[:200],
            'status_choices': OrdemServico.STATUS_CHOICES,
            'order_by_choices': [
                ('numero', 'NÃºmero'),
                ('updated_at', 'AtualizaÃ§Ã£o'),
                ('created_at', 'CriaÃ§Ã£o'),
                ('status', 'Status'),
                ('evento', 'Evento'),
            ],
            'order_dir_choices': ORDER_DIR_CHOICES,
            'ordem_novo_url': reverse('eventos:documentos-ordens-servico-novo'),
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
        messages.success(request, 'Ordem de serviÃ§o criada com sucesso.')
        return redirect(return_to or reverse('eventos:documentos-ordens-servico-detalhe', kwargs={'pk': obj.pk}))
    return _render_ordem_servico_form(
        request,
        form=form,
        return_to=return_to,
        context_source=context_source,
        preselected_event=preselected_event,
        preselected_oficio=preselected_oficio,
    )


@require_http_methods(['GET', 'POST'])
def ordem_servico_editar(request, pk):
    obj = get_object_or_404(OrdemServico.objects.select_related('evento', 'oficio'), pk=pk)
    return_to = _get_safe_return_to(request, reverse('eventos:documentos-ordens-servico'))
    context_source = _get_context_source(request)
    form = OrdemServicoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Ordem de serviÃ§o atualizada.')
        return redirect(return_to or reverse('eventos:documentos-ordens-servico-detalhe', kwargs={'pk': obj.pk}))
    return _render_ordem_servico_form(
        request,
        form=form,
        object_instance=obj,
        return_to=return_to,
        context_source=context_source,
    )


def _render_ordem_servico_form(
    request,
    *,
    form,
    object_instance=None,
    return_to='',
    context_source='',
    preselected_event=None,
    preselected_oficio=None,
):
    selected_viajantes = []
    if object_instance:
        selected_viajantes = object_instance.get_viajantes_relacionados()
    elif form.is_bound:
        selected_viajantes = list(form.cleaned_data.get('viajantes') or []) if hasattr(form, 'cleaned_data') else []
    else:
        initial_ids = form.initial.get('viajantes') or []
        selected_viajantes = list(Viajante.objects.select_related('cargo').filter(pk__in=initial_ids).order_by('nome'))

    numero_preview = object_instance.numero_formatado if object_instance and object_instance.pk else getattr(form, 'proximo_numero_preview', '')
    return render(
        request,
        'eventos/documentos/ordens_servico_form.html',
        {
            'form': form,
            'object': object_instance,
            'return_to': return_to,
            'context_source': context_source,
            'preselected_event_id': preselected_event.pk if preselected_event else (object_instance.evento_id if object_instance else ''),
            'preselected_oficio_id': preselected_oficio.pk if preselected_oficio else (object_instance.oficio_id if object_instance else ''),
            'estados_choices': Estado.objects.filter(ativo=True).order_by('nome'),
            'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
            'motivos_manager_url': reverse('eventos:modelos-motivo-lista'),
            'motivo_texto_api_base_url': reverse('eventos:modelos-motivo-texto-api', kwargs={'pk': 0}),
            'selected_viajantes_payload': [
                serializar_viajante_para_autocomplete(viajante) for viajante in selected_viajantes
            ],
            'ordem_numero_preview': numero_preview,
            'hide_page_header': True,
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
        messages.success(request, 'Ordem de serviÃ§o excluÃ­da.')
        return redirect(return_to)
    return render(
        request,
        'eventos/documentos/ordens_servico_excluir.html',
        {'object': obj, 'return_to': return_to},
    )


@require_http_methods(['GET'])
def ordem_servico_download(request, pk, formato):
    obj = get_object_or_404(OrdemServico.objects.select_related('oficio', 'evento', 'modelo_motivo'), pk=pk)
    formato = _clean(formato).lower()
    if formato not in {DocumentoFormato.DOCX.value, DocumentoFormato.PDF.value}:
        raise Http404('Formato invÃ¡lido.')
    docx_bytes = render_ordem_servico_model_docx(obj)
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
        'order_by': _clean(request.GET.get('order_by')),
        'order_dir': _clean(request.GET.get('order_dir')),
    }
    queryset = (
        Justificativa.objects.select_related(
            'oficio',
            'oficio__evento',
            'modelo',
        )
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

    justificativa_order_map = {
        'numero': 'pk',
        'updated_at': 'updated_at',
        'created_at': 'created_at',
        'oficio': 'oficio__numero',
        'modelo': 'modelo__nome',
    }
    ordering = _resolve_ordering(filters, justificativa_order_map, 'numero')
    queryset = queryset.order_by(ordering, '-created_at')

    page_obj = _paginate(queryset, request.GET.get('page'))
    object_list = []
    for just in page_obj.object_list:
        just.detail_url = reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': just.pk})
        just.edicao_url = reverse('eventos:documentos-justificativas-editar', kwargs={'pk': just.pk})
        just.excluir_url = reverse('eventos:documentos-justificativas-excluir', kwargs={'pk': just.pk})
        just.oficio_url = (
            reverse('eventos:oficio-step4', kwargs={'pk': just.oficio_id})
            if just.oficio_id else ''
        )
        just.evento_url = (
            reverse('eventos:guiado-painel', kwargs={'pk': just.oficio.evento_id})
            if just.oficio_id and just.oficio and just.oficio.evento_id else ''
        )
        just.card_theme_class = 'is-tone-blue'
        has_text = bool(_clean(just.texto))
        just.status_badge_label = 'Preenchida' if has_text else 'Pendente'
        just.status_badge_css_class = 'is-info' if has_text else 'is-pending'
        just.modelo_display = just.modelo.nome if just.modelo_id else 'Sem modelo'
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
            'order_by_choices': [
                ('numero', 'Numero'),
                ('updated_at', 'AtualizaÃ§Ã£o'),
                ('created_at', 'CriaÃ§Ã£o'),
                ('oficio', 'OfÃ­cio'),
                ('modelo', 'Modelo'),
            ],
            'order_dir_choices': ORDER_DIR_CHOICES,
            'justificativa_novo_url': reverse('eventos:documentos-justificativas-nova'),
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
        messages.success(request, 'Justificativa excluÃ­da com sucesso.')
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
        termo.oficios_display = ', '.join(oficio.numero_formatado for oficio in oficios_relacionados) if oficios_relacionados else 'â€”'
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
        'order_by': _clean(request.GET.get('order_by')),
        'order_dir': _clean(request.GET.get('order_dir')),
    }


def _termo_status_meta(termo):
    fallback_label = getattr(termo, 'get_status_display', lambda: termo.status)() or termo.status or '-'
    status = (termo.status or '').strip().upper()
    if status == TermoAutorizacao.STATUS_RASCUNHO:
        return {
            'label': fallback_label,
            'css_class': 'is-rascunho',
        }

    if status == TermoAutorizacao.STATUS_GERADO:
        hoje = timezone.localdate()
        inicio = getattr(termo, 'data_evento', None)
        fim = getattr(termo, 'data_evento_fim', None) or inicio
        if not inicio or hoje < inicio:
            css_class = 'is-finalizado-future'
        elif inicio <= hoje <= fim:
            css_class = 'is-finalizado-ongoing'
        else:
            css_class = 'is-finalizado'
        return {
            'label': fallback_label,
            'css_class': css_class,
        }

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
            'api_oficios_por_evento_url': reverse('eventos:documentos-termos-api-oficios-por-evento'),
            'selected_viajantes_payload': [
                serializar_viajante_para_autocomplete(viajante) for viajante in selected_viajantes
            ],
            'selected_veiculo_payload': selected_veiculo_payload,
            'selected_oficios_payload': selected_oficios_payload,
            'preview_payload': preview_payload,
            'read_only_context': read_only_context,
            'show_viajantes_selector': object_instance is None,
            'show_veiculo_selector': object_instance is None,
            'estados_choices': Estado.objects.filter(ativo=True).order_by('nome'),
            'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
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
            'viajante__unidade_lotacao',
            'veiculo',
            'veiculo__combustivel',
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

    termo_order_map = {
        'numero': 'pk',
        'updated_at': 'updated_at',
        'created_at': 'created_at',
        'status': 'status',
        'evento': 'evento__titulo',
        'servidor': 'servidor_nome',
    }
    ordering = _resolve_ordering(filters, termo_order_map, 'numero')

    page_obj = _paginate(queryset.order_by(ordering, '-created_at'), request.GET.get('page'))
    object_list = list(page_obj.object_list)
    for termo in object_list:
        termo.process_status = _termo_status_meta(termo)
        termo.card_theme_meta = _build_termo_card_theme_meta(termo)
        termo.card_theme_class = termo.card_theme_meta['theme_class']
        termo.status_badge_css_class = termo.card_theme_meta['badge_css_class']
        termo.mode_meta = _termo_mode_meta(termo.modo_geracao)
        termo.context_display = _termo_context_display(termo)
        termo.title_display = termo.titulo_display
        termo.servidor_nome_card = (termo.servidor_display or '').strip()
        termo.servidor_resumo = termo.servidor_nome_card or 'Sem servidor'
        termo.servidor_lotacao_card = (termo.servidor_lotacao or '').strip()
        termo.servidor_cargo_card = (
            (getattr(getattr(termo, 'viajante', None), 'cargo', None) and getattr(termo.viajante.cargo, 'nome', ''))
            or ''
        ).strip()
        termo.destino_resumo = termo.destino or '-'
        termo.periodo_resumo = termo.periodo_display or '-'
        termo.oficios_resumo = termo.oficios_relacionados_display or 'Sem oficio'
        termo.veiculo_placa_card = (termo.veiculo_placa or '').strip()
        termo.veiculo_modelo_card = (termo.veiculo_modelo or '').strip()
        termo.veiculo_combustivel_card = (termo.veiculo_combustivel or '').strip()

        termo.has_servidor_card = bool(termo.servidor_nome_card)
        termo.has_viatura_card = bool(
            termo.veiculo_placa_card
            or termo.veiculo_modelo_card
            or termo.veiculo_combustivel_card
            or termo.veiculo_id
        )

        has_oficio_link = bool(termo.oficio_id or (termo.oficios_resumo and termo.oficios_resumo != 'Sem oficio'))
        if termo.evento_id and has_oficio_link:
            termo.vinculo_badge_label = 'Evento + oficio'
            termo.vinculo_badge_detail = f"{(termo.evento.titulo or '').strip() or f'Evento #{termo.evento_id}'} • {termo.oficios_resumo}"
        elif termo.evento_id:
            termo.vinculo_badge_label = 'Evento'
            termo.vinculo_badge_detail = (termo.evento.titulo or '').strip() or f'Evento #{termo.evento_id}'
        elif has_oficio_link:
            termo.vinculo_badge_label = 'Oficio'
            termo.vinculo_badge_detail = termo.oficios_resumo
        else:
            termo.vinculo_badge_label = ''
            termo.vinculo_badge_detail = ''

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
            'order_by_choices': [
                ('numero', 'Numero'),
                ('updated_at', 'AtualizaÃ§Ã£o'),
                ('created_at', 'CriaÃ§Ã£o'),
                ('status', 'Status'),
                ('evento', 'Evento'),
                ('servidor', 'Servidor'),
            ],
            'order_dir_choices': ORDER_DIR_CHOICES,
            'termo_novo_url': reverse('eventos:documentos-termos-novo'),
        },
    )


@require_http_methods(['GET'])
def termo_autorizacao_oficios_por_evento(request):
    evento_id = _clean(request.GET.get('evento_id'))
    if not evento_id or not evento_id.isdigit():
        return JsonResponse({'oficios': []})
    oficios = list(
        Oficio.objects.filter(evento_id=int(evento_id)).order_by('-updated_at')
    )
    result = [
        {'id': o.pk, 'label': f'Oficio {o.numero_formatado or f"#{o.pk}"}'}
        for o in oficios
    ]
    return JsonResponse({'oficios': result})


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

