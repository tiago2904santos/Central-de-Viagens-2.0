from __future__ import annotations

from datetime import datetime, time
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import Truncator, slugify
from django.views.decorators.http import require_http_methods

from .forms import DocumentoAvulsoForm
from .models import (
    DocumentoAvulso,
    Evento,
    EventoFundamentacao,
    EventoTermoParticipante,
    Oficio,
    OficioTrecho,
    RoteiroEvento,
    RoteiroEventoTrecho,
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
    create_base_document,
    document_to_bytes,
    get_document_template_path,
    get_termo_autorizacao_template_path,
    render_docx_template_bytes,
)
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

ROTEIRO_STATUS_CARD_META = {
    RoteiroEvento.STATUS_RASCUNHO: {'label': 'Rascunho', 'css_class': 'is-rascunho'},
    'ASSINADO': {'label': 'Assinado', 'css_class': 'is-assinado'},
    RoteiroEvento.STATUS_FINALIZADO: {'label': 'Finalizado', 'css_class': 'is-finalizado'},
}

ROTEIRO_VINCULO_META = {
    RoteiroEvento.TIPO_AVULSO: {'label': 'Avulso', 'css_class': 'is-avulso'},
    RoteiroEvento.TIPO_EVENTO: {'label': 'Vinculado a evento', 'css_class': 'is-evento'},
}


def _clean(value):
    return str(value or '').strip()


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


def _normalize_documento_avulso_tipo(value):
    normalized = _clean(value).upper()
    allowed = {choice[0] for choice in DocumentoAvulso.TIPO_CHOICES}
    return normalized if normalized in allowed else ''


def _documento_avulso_tipo_to_oficio_tipo(tipo_documento):
    mapping = {
        DocumentoAvulso.TIPO_OFICIO: DocumentoOficioTipo.OFICIO,
        DocumentoAvulso.TIPO_TERMO_AUTORIZACAO: DocumentoOficioTipo.TERMO_AUTORIZACAO,
        DocumentoAvulso.TIPO_JUSTIFICATIVA: DocumentoOficioTipo.JUSTIFICATIVA,
        DocumentoAvulso.TIPO_PLANO_TRABALHO: DocumentoOficioTipo.PLANO_TRABALHO,
        DocumentoAvulso.TIPO_ORDEM_SERVICO: DocumentoOficioTipo.ORDEM_SERVICO,
    }
    return mapping.get((tipo_documento or '').strip().upper())


def _build_documento_avulso_filename(documento, formato):
    ext = 'docx' if (formato or '').lower() == DocumentoFormato.DOCX.value else 'pdf'
    nome_slug = slugify(documento.titulo or '') or f'documento-avulso-{documento.pk}'
    return f'{nome_slug}_{documento.pk}.{ext}'


def _render_documento_avulso_docx_bytes(documento):
    placeholders = documento.placeholders if isinstance(documento.placeholders, dict) else {}
    tipo_documento_oficio = _documento_avulso_tipo_to_oficio_tipo(documento.tipo_documento)
    if tipo_documento_oficio is None:
        document = create_base_document(documento.titulo or 'Documento avulso', subtitle='Modelo avulso')
        if documento.conteudo_texto:
            document.add_paragraph(documento.conteudo_texto)
        if placeholders:
            document.add_paragraph('')
            document.add_paragraph('Dados preenchidos (placeholders):')
            for key, value in placeholders.items():
                document.add_paragraph(f'{key}: {value or ""}')
        return document_to_bytes(document)

    if tipo_documento_oficio == DocumentoOficioTipo.TERMO_AUTORIZACAO:
        template_path = get_termo_autorizacao_template_path(documento.termo_template_variant)
    else:
        template_path = get_document_template_path(tipo_documento_oficio)
    mapping = {str(key): '' if value is None else str(value) for key, value in placeholders.items()}
    return render_docx_template_bytes(template_path, mapping)


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
    justificativa_exists = (
        justificativa_info['required']
        or justificativa_info['filled']
        or bool((oficio.justificativa_texto or '').strip())
    )
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


def _document_status_summary(oficio, tipo_documento, fundamentacao_tipo):
    meta = get_document_type_meta(tipo_documento)
    fundamentacao = getattr(oficio.evento, 'fundamentacao', None) if oficio.evento_id else None
    if not oficio.evento_id:
        return {
            'status_key': 'not_applicable',
            'status_label': STATUS_LABELS['not_applicable'],
            'detail': 'Oficio sem evento vinculado.',
            'fundamentacao_label': 'Sem evento',
            'docx': None,
            'pdf': None,
            'download_docx_url': '',
            'download_pdf_url': '',
        }
    if not fundamentacao or not _clean(fundamentacao.tipo_documento):
        return {
            'status_key': 'not_applicable',
            'status_label': STATUS_LABELS['not_applicable'],
            'detail': 'Etapa 4 do evento ainda nao definiu o documento base.',
            'fundamentacao_label': 'Nao definido',
            'docx': None,
            'pdf': None,
            'download_docx_url': '',
            'download_pdf_url': '',
        }
    if fundamentacao.tipo_documento != fundamentacao_tipo:
        return {
            'status_key': 'not_applicable',
            'status_label': STATUS_LABELS['not_applicable'],
            'detail': f'Evento configurado para {fundamentacao.get_tipo_documento_display().lower()}.',
            'fundamentacao_label': fundamentacao.get_tipo_documento_display(),
            'docx': None,
            'pdf': None,
            'download_docx_url': '',
            'download_pdf_url': '',
        }

    docx_status = get_document_generation_status(oficio, tipo_documento, DocumentoFormato.DOCX)
    pdf_status = get_document_generation_status(oficio, tipo_documento, DocumentoFormato.PDF)
    if docx_status['status'] == 'available' or pdf_status['status'] == 'available':
        status_key = 'available'
        detail = 'Documento pronto para download.'
    elif docx_status['status'] == 'pending' or pdf_status['status'] == 'pending':
        status_key = 'pending'
        detail = (docx_status.get('errors') or pdf_status.get('errors') or ['Pendencias de preenchimento.'])[0]
    else:
        status_key = 'unavailable'
        detail = (docx_status.get('errors') or pdf_status.get('errors') or ['Documento indisponivel.'])[0]

    return {
        'status_key': status_key,
        'status_label': STATUS_LABELS[status_key],
        'detail': detail,
        'fundamentacao_label': fundamentacao.get_tipo_documento_display(),
        'docx': docx_status,
        'pdf': pdf_status,
        'download_docx_url': (
            reverse(
                'eventos:oficio-documento-download',
                kwargs={'pk': oficio.pk, 'tipo_documento': meta.slug, 'formato': DocumentoFormato.DOCX.value},
            )
            if docx_status['status'] == 'available'
            else ''
        ),
        'download_pdf_url': (
            reverse(
                'eventos:oficio-documento-download',
                kwargs={'pk': oficio.pk, 'tipo_documento': meta.slug, 'formato': DocumentoFormato.PDF.value},
            )
            if pdf_status['status'] == 'available'
            else ''
        ),
    }


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


def oficio_global_lista(request):
    filters = _build_oficio_filters(request)
    queryset = (
        Oficio.objects.select_related('evento', 'evento__fundamentacao', 'cidade_sede', 'estado_sede', 'roteiro_evento')
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
        )
        .all()
    )

    if filters['q']:
        queryset = queryset.filter(
            Q(evento__titulo__icontains=filters['q'])
            | Q(motivo__icontains=filters['q'])
            | Q(viajantes__nome__icontains=filters['q'])
            | Q(trechos__destino_cidade__nome__icontains=filters['q'])
            | Q(trechos__destino_estado__sigla__icontains=filters['q'])
        )
    if filters['status']:
        queryset = queryset.filter(status=filters['status'])
    
    if filters['ano'].isdigit():
        queryset = queryset.filter(ano=int(filters['ano']))
    if filters['numero'].isdigit():
        queryset = queryset.filter(numero=int(filters['numero']))
    if filters['protocolo']:
        protocolo_digits = Oficio.normalize_protocolo(filters['protocolo'])
        queryset = queryset.filter(protocolo__icontains=protocolo_digits or filters['protocolo'])
    if filters['destino']:
        queryset = queryset.filter(
            Q(tipo_destino__icontains=filters['destino'])
            | Q(trechos__destino_cidade__nome__icontains=filters['destino'])
            | Q(trechos__destino_estado__sigla__icontains=filters['destino'])
            | Q(cidade_sede__nome__icontains=filters['destino'])
        )

    page_obj = _paginate(
        queryset.distinct().order_by('-updated_at', '-created_at'),
        request.GET.get('page'),
    )
    object_list = list(page_obj.object_list)
    for oficio in object_list:
        oficio.destinos_display = _oficio_destinos_display(oficio)
        oficio.periodo_display = _oficio_periodo_display(oficio)
        oficio.viajantes_display = _oficio_viajantes_display(oficio)
        oficio.justificativa_info = _build_oficio_justificativa_info(oficio)
        oficio.process_status = _oficio_process_status_meta(oficio)
        oficio.evento_url = ''
        oficio.edicao_url = reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk})
        oficio.excluir_url = reverse('eventos:oficio-excluir', kwargs={'pk': oficio.pk})
        oficio.card_documents = _build_oficio_document_cards(oficio)
        oficio.evento_titulo_display = (
            (oficio.evento.titulo or '').strip()
            if oficio.evento_id
            else 'Of\u00edcio avulso'
        ) or '(sem t\u00edtulo)'

    return render(
        request,
        'eventos/global/oficios_lista.html',
        {
            'object_list': object_list,
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'status_choices': Oficio.STATUS_CHOICES,
        },
    )


def _roteiro_origem_display(roteiro):
    return _label_local(roteiro.origem_cidade, roteiro.origem_estado)


def _roteiro_destino_principal_display(roteiro):
    primeiro_destino = next(iter(roteiro.destinos.all()), None)
    if primeiro_destino:
        return _label_local(primeiro_destino.cidade, primeiro_destino.estado)
    return 'â€”'


def _roteiro_periodo_display(roteiro):
    inicio = roteiro.saida_dt
    fim = roteiro.retorno_chegada_dt or roteiro.chegada_dt
    if not inicio and not fim:
        return 'â€”'
    if inicio and fim:
        if inicio.date() == fim.date():
            return f'{inicio:%d/%m/%Y} {inicio:%H:%M} - {fim:%H:%M}'
        return f'{inicio:%d/%m/%Y %H:%M} at\u00e9 {fim:%d/%m/%Y %H:%M}'
    ponto = inicio or fim
    return ponto.strftime('%d/%m/%Y %H:%M')


def _roteiro_process_status_meta(roteiro):
    default_label = getattr(roteiro, 'get_status_display', lambda: roteiro.status)() or roteiro.status or 'â€”'
    meta = ROTEIRO_STATUS_CARD_META.get(roteiro.status, {})
    return {
        'label': meta.get('label', default_label),
        'css_class': meta.get('css_class', 'is-muted'),
    }


def _roteiro_vinculo_meta(roteiro):
    tipo = RoteiroEvento.TIPO_AVULSO if (roteiro.tipo == RoteiroEvento.TIPO_AVULSO or not roteiro.evento_id) else RoteiroEvento.TIPO_EVENTO
    meta = ROTEIRO_VINCULO_META[tipo]
    return {
        'label': meta['label'],
        'css_class': meta['css_class'],
    }


def _build_roteiro_resumo_trechos(roteiro):
    items = []
    trechos = list(roteiro.trechos.all())
    for trecho in trechos[:2]:
        origem = _label_local(trecho.origem_cidade, trecho.origem_estado)
        destino = _label_local(trecho.destino_cidade, trecho.destino_estado)
        tipo = trecho.get_tipo_display()
        horario = trecho.saida_dt.strftime('%d/%m/%Y %H:%M') if trecho.saida_dt else 'Sem hor\u00e1rio'
        items.append(f'{tipo}: {origem} -> {destino} ({horario})')
    restante = max(len(trechos) - len(items), 0)
    return {'items': items, 'remaining_count': restante}


def _build_roteiro_card_actions(roteiro, selected_event=None):
    actions = [
        {'label': 'Editar', 'url': roteiro.editar_url, 'style': 'primary'},
    ]
    if roteiro.evento_url:
        actions.append({'label': 'Visualizar', 'url': roteiro.evento_url, 'style': 'secondary'})
    elif roteiro.etapa_url:
        actions.append({'label': 'Visualizar', 'url': roteiro.etapa_url, 'style': 'secondary'})

    usar_no_cadastro_url = ''
    if roteiro.is_avulso:
        usar_no_cadastro_url = reverse('eventos:oficio-novo')
    elif roteiro.oficios_url:
        usar_no_cadastro_url = roteiro.oficios_url
    if usar_no_cadastro_url:
        actions.append({'label': 'Usar no cadastro', 'url': usar_no_cadastro_url, 'style': 'secondary'})

    if roteiro.etapa_url and roteiro.etapa_url != usar_no_cadastro_url:
        actions.append({'label': 'Etapa 2', 'url': roteiro.etapa_url, 'style': 'secondary'})

    return actions


def roteiro_global_lista(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'status': _clean(request.GET.get('status')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'tipo': _clean(request.GET.get('tipo')).upper(),
    }
    queryset = (
        RoteiroEvento.objects.select_related('evento', 'origem_estado', 'origem_cidade')
        .prefetch_related(
            'destinos__estado',
            'destinos__cidade',
            Prefetch(
                'trechos',
                queryset=RoteiroEventoTrecho.objects.select_related(
                    'origem_estado',
                    'origem_cidade',
                    'destino_estado',
                    'destino_cidade',
                ),
            ),
        )
        .annotate(oficios_count=Count('oficios', distinct=True), trechos_count=Count('trechos', distinct=True))
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
    

    page_obj = _paginate(
        queryset.distinct().order_by('-updated_at', '-created_at'),
        request.GET.get('page'),
    )
    object_list = list(page_obj.object_list)
    for roteiro in object_list:
        roteiro.destinos_display = _roteiro_destinos_display(roteiro)
        roteiro.origem_display = _roteiro_origem_display(roteiro)
        roteiro.destino_principal_display = _roteiro_destino_principal_display(roteiro)
        roteiro.periodo_display = _roteiro_periodo_display(roteiro)
        roteiro.is_avulso = roteiro.tipo == RoteiroEvento.TIPO_AVULSO or not roteiro.evento_id
        roteiro.process_status = _roteiro_process_status_meta(roteiro)
        roteiro.vinculo_meta = _roteiro_vinculo_meta(roteiro)
        if roteiro.is_avulso:
            roteiro.editar_url = reverse('eventos:roteiro-avulso-editar', kwargs={'pk': roteiro.pk})
            roteiro.evento_url = ''
            roteiro.etapa_url = ''
            roteiro.oficios_url = ''
        else:
            roteiro.editar_url = reverse('eventos:roteiro-avulso-editar', kwargs={'pk': roteiro.pk})
            roteiro.evento_url = ''
            roteiro.etapa_url = ''
            roteiro.oficios_url = ''
        roteiro.evento_titulo_display = (
            (roteiro.evento.titulo or '').strip()
            if roteiro.evento_id
            else 'Roteiro avulso'
        ) or '(sem t\u00edtulo)'
        roteiro.trechos_preview = _build_roteiro_resumo_trechos(roteiro)
        roteiro.actions = _build_roteiro_card_actions(roteiro)

    selected_event = None

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
            'tipo_choices': [('', 'Todos'), (RoteiroEvento.TIPO_AVULSO, 'Avulsos')],
            'novo_roteiro_url': '',
            'novo_roteiro_avulso_url': reverse('eventos:roteiro-avulso-cadastrar'),
            'selected_event': selected_event,
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
            'count': Oficio.objects.filter(evento__fundamentacao__tipo_documento=EventoFundamentacao.TIPO_PT).count(),
            'description': 'Lista global derivada dos oficios e da etapa 4 do evento.',
            'url': reverse('eventos:documentos-planos-trabalho'),
        },
        {
            'label': 'Ordens de servico',
            'count': Oficio.objects.filter(evento__fundamentacao__tipo_documento=EventoFundamentacao.TIPO_OS).count(),
            'description': 'Acompanhamento global dos documentos de missao gerados por oficio.',
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
            'count': 0,
            'description': 'Situacao global dos termos por participante.',
            'url': reverse('eventos:documentos-termos'),
        },
    ]
    documentos_avulsos_qs = (
        DocumentoAvulso.objects.select_related('evento', 'roteiro', 'plano_trabalho', 'oficio', 'criado_por')
        .order_by('-updated_at', '-created_at')
    )
    documentos_avulsos = list(documentos_avulsos_qs[:20])
    for documento in documentos_avulsos:
        documento.editar_url = reverse('eventos:documentos-avulsos-editar', kwargs={'pk': documento.pk})
        documento.download_docx_url = reverse(
            'eventos:documentos-avulsos-download',
            kwargs={'pk': documento.pk, 'formato': DocumentoFormato.DOCX.value},
        )
        documento.download_pdf_url = reverse(
            'eventos:documentos-avulsos-download',
            kwargs={'pk': documento.pk, 'formato': DocumentoFormato.PDF.value},
        )
        documento.vinculos = [
            label
            for label, enabled in [
                ('Evento', bool(documento.evento_id)),
                ('Roteiro', bool(documento.roteiro_id)),
                ('PT/OS', bool(documento.plano_trabalho_id)),
                ('Ofício', bool(documento.oficio_id)),
            ]
            if enabled
        ]
    return render(
        request,
        'eventos/global/documentos_hub.html',
        {
            'cards': cards,
            'total_oficios': len(oficios),
            'termos_pendentes': EventoTermoParticipante.objects.filter(
                status=EventoTermoParticipante.STATUS_PENDENTE
            ).count(),
            'termos_concluidos': EventoTermoParticipante.objects.filter(
                status=EventoTermoParticipante.STATUS_CONCLUIDO
            ).count(),
            'justificativas_pendentes': justificativas_pendentes,
            'justificativas_preenchidas': justificativas_preenchidas,
            'documentos_avulsos': documentos_avulsos,
            'documentos_avulsos_total': documentos_avulsos_qs.count(),
            'documentos_avulsos_count': documentos_avulsos_qs.filter(
                classificacao=DocumentoAvulso.CLASSIFICACAO_AVULSO
            ).count(),
            'documentos_vinculados_count': documentos_avulsos_qs.filter(
                classificacao=DocumentoAvulso.CLASSIFICACAO_VINCULADO
            ).count(),
            'tipos_documento_avulso': DocumentoAvulso.TIPO_CHOICES,
        },
    )


@require_http_methods(['GET', 'POST'])
def documento_avulso_novo(request):
    tipo = _normalize_documento_avulso_tipo(
        request.GET.get('tipo') if request.method == 'GET' else request.POST.get('tipo_documento')
    )
    if request.method == 'GET' and not tipo:
        return render(
            request,
            'eventos/global/documento_avulso_selector.html',
            {'tipos_documento_avulso': DocumentoAvulso.TIPO_CHOICES},
        )

    form = DocumentoAvulsoForm(
        request.POST or None,
        tipo_predefinido=tipo,
    )
    if request.method == 'POST' and form.is_valid():
        documento = form.save(commit=False)
        documento.criado_por = request.user
        documento.save()
        messages.success(request, 'Documento avulso criado com sucesso.')
        return redirect('eventos:documentos-avulsos-editar', pk=documento.pk)

    return render(
        request,
        'eventos/global/documento_avulso_form.html',
        {
            'form': form,
            'object': None,
            'tipo_documento': tipo,
            'titulo_pagina': 'Novo documento avulso',
        },
    )


@require_http_methods(['GET', 'POST'])
def planos_trabalho_novo(request):
    """
    Página dedicada de criação de Plano de Trabalho avulso.
    Evento não é obrigatório; o vínculo com evento é opcional e pode ser feito depois.
    """
def documento_avulso_editar(request, pk):
    documento = get_object_or_404(
        DocumentoAvulso.objects.select_related('evento', 'roteiro', 'plano_trabalho', 'oficio', 'criado_por'),
        pk=pk,
    )
    form = DocumentoAvulsoForm(request.POST or None, instance=documento)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Documento avulso atualizado.')
        return redirect('eventos:documentos-avulsos-editar', pk=documento.pk)

    # Página dedicada de PT: título e link "Voltar" para listagem de planos
    is_plano_trabalho = documento.tipo_documento == DocumentoAvulso.TIPO_PLANO_TRABALHO
    context = {
        'form': form,
        'object': documento,
        'tipo_documento': documento.tipo_documento,
        'titulo_pagina': 'Editar Plano de Trabalho' if is_plano_trabalho else 'Editar documento avulso',
        'voltar_url': reverse('eventos:documentos-planos-trabalho') if is_plano_trabalho else None,
        'voltar_label': 'Voltar para planos de trabalho' if is_plano_trabalho else None,
    }
    return render(request, 'eventos/global/documento_avulso_form.html', context)


@require_http_methods(['GET'])
def documento_avulso_download(request, pk, formato):
    documento = get_object_or_404(DocumentoAvulso, pk=pk)
    formato = _clean(formato).lower()
    if formato not in {DocumentoFormato.DOCX.value, DocumentoFormato.PDF.value}:
        raise Http404('Formato inválido.')
    try:
        docx_bytes = _render_documento_avulso_docx_bytes(documento)
        payload = docx_bytes
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if formato == DocumentoFormato.PDF.value:
            payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
            content_type = 'application/pdf'
    except (DocumentGenerationError, DocumentRendererUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect('eventos:documentos-avulsos-editar', pk=documento.pk)
    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = (
        f'attachment; filename="{_build_documento_avulso_filename(documento, formato)}"'
    )
    return response


def _build_documento_derivado_rows(queryset, *, request, tipo_documento, fundamentacao_tipo, situacao):
    next_url = request.get_full_path()
    rows = []
    for oficio in queryset:
        status_info = _document_status_summary(oficio, tipo_documento, fundamentacao_tipo)
        if situacao and situacao != 'todos' and status_info['status_key'] != situacao:
            continue
        meta = DOCUMENT_STATUS_CARD_META.get(status_info['status_key'], {})
        status_info['status_css_class'] = meta.get('css_class', 'is-muted')
        rows.append(
            {
                'oficio': oficio,
                'evento': oficio.evento,
                'destinos_display': _oficio_destinos_display(oficio),
                'periodo_display': _oficio_periodo_display(oficio),
                'viajantes_display': _oficio_viajantes_display(oficio),
                'status': status_info,
                'oficio_url': reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk}),
                'documentos_url': reverse('eventos:oficio-documentos', kwargs={'pk': oficio.pk}),
                'evento_url': '' if oficio.evento_id else '',
                'justificativa_url': _append_next(
                    reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
                    next_url,
                ),
            }
        )
    return rows


def _plano_trabalho_responsavel_display(oficio):
    fundamentacao = getattr(oficio.evento, 'fundamentacao', None) if oficio.evento_id else None
    if not fundamentacao:
        return '-'
    if getattr(fundamentacao, 'coordenador_operacional_id', None):
        return str(fundamentacao.coordenador_operacional)
    if getattr(fundamentacao, 'coordenador_administrativo_id', None):
        return fundamentacao.coordenador_administrativo.nome
    if _clean(getattr(fundamentacao, 'solicitante_outros', '')):
        return fundamentacao.solicitante_outros
    if getattr(fundamentacao, 'solicitante_id', None):
        return str(fundamentacao.solicitante)
    return '-'


def _plano_trabalho_solicitante_display(oficio):
    fundamentacao = getattr(oficio.evento, 'fundamentacao', None) if oficio.evento_id else None
    if not fundamentacao:
        return '-'
    if _clean(getattr(fundamentacao, 'solicitante_outros', '')):
        return fundamentacao.solicitante_outros
    if getattr(fundamentacao, 'solicitante_id', None):
        return str(fundamentacao.solicitante)
    return '-'


def _plano_trabalho_resumo_display(oficio):
    fundamentacao = getattr(oficio.evento, 'fundamentacao', None) if oficio.evento_id else None
    texto = _clean(getattr(fundamentacao, 'texto_fundamentacao', '')) or _clean(oficio.motivo)
    if not texto:
        return 'Sem resumo preenchido.'
    return Truncator(texto).chars(180)


def _build_plano_trabalho_actions(oficio, status_info):
    actions = []
    if oficio.evento_id:
        actions.append(
            {
                'label': 'Editar',
                'url': reverse('eventos:guiado-etapa-4', kwargs={'evento_id': oficio.evento_id}),
                'style': 'primary',
            }
        )
    else:
        actions.append(
            {
                'label': 'Editar',
                'url': reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk}),
                'style': 'primary',
            }
        )
    actions.append(
        {
            'label': 'Visualizar',
            'url': reverse('eventos:oficio-documentos', kwargs={'pk': oficio.pk}),
            'style': 'secondary',
        }
    )
    if status_info.get('download_pdf_url'):
        actions.append(
            {
                'label': 'PDF',
                'url': status_info['download_pdf_url'],
                'style': 'secondary',
            }
        )
    if status_info.get('download_docx_url'):
        actions.append(
            {
                'label': 'DOCX',
                'url': status_info['download_docx_url'],
                'style': 'secondary',
            }
        )
    return actions


def _build_plano_trabalho_footer_actions(oficio):
    actions = []
    if oficio.evento_id:
        actions.append(
            {
                'label': 'Painel do evento',
                'url': '',
                'style': 'secondary',
            }
        )
    actions.append(
        {
            'label': 'Oficio base',
            'url': reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk}),
            'style': 'secondary',
        }
    )
    return actions


def _documento_derivado_global(
    request,
    *,
    template_title,
    template_page_title,
    template_subtitle,
    tipo_documento,
    fundamentacao_tipo,
    template_name='eventos/global/documento_derivado_lista.html',
):
    filters = {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'ano': _clean(request.GET.get('ano')),
        'situacao': _clean(request.GET.get('situacao')) or 'todos',
        'oficio_status': _clean(request.GET.get('oficio_status')),
    }
    queryset = (
        Oficio.objects.select_related('evento', 'evento__fundamentacao')
        .prefetch_related('trechos', 'viajantes', 'viajantes__cargo')
        .all()
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(evento__titulo__icontains=filters['q'])
            | Q(motivo__icontains=filters['q'])
            | Q(protocolo__icontains=Oficio.normalize_protocolo(filters['q']) or filters['q'])
            | Q(trechos__destino_cidade__nome__icontains=filters['q'])
            | Q(viajantes__nome__icontains=filters['q'])
        )
    
    if filters['ano'].isdigit():
        queryset = queryset.filter(ano=int(filters['ano']))
    if filters['oficio_status']:
        queryset = queryset.filter(status=filters['oficio_status'])

    rows = _build_documento_derivado_rows(
        queryset.distinct().order_by('-updated_at', '-created_at'),
        request=request,
        tipo_documento=tipo_documento,
        fundamentacao_tipo=fundamentacao_tipo,
        situacao=filters['situacao'],
    )
    page_obj = _paginate(rows, request.GET.get('page'))
    return render(
        request,
        template_name,
        {
            'object_list': list(page_obj.object_list),
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficio_status_choices': Oficio.STATUS_CHOICES,
            'page_title': template_title,
            'header_title': template_page_title,
            'subtitle': template_subtitle,
            'situacao_choices': [
                ('todos', 'Todos'),
                ('available', 'Disponiveis'),
                ('pending', 'Pendentes'),
                ('unavailable', 'Indisponiveis'),
                ('not_applicable', 'Nao aplicaveis'),
            ],
            'status_card_meta': DOCUMENT_STATUS_CARD_META,
        },
    )


def planos_trabalho_global(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'ano': _clean(request.GET.get('ano')),
        'situacao': _clean(request.GET.get('situacao')) or 'todos',
        'oficio_status': _clean(request.GET.get('oficio_status')),
    }
    queryset = (
        Oficio.objects.select_related(
            'evento',
            'evento__fundamentacao',
            'evento__fundamentacao__solicitante',
            'evento__fundamentacao__coordenador_operacional',
            'evento__fundamentacao__coordenador_administrativo',
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
        )
        .filter(evento__isnull=False)
        .exclude(evento__fundamentacao__tipo_documento=EventoFundamentacao.TIPO_OS)
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(evento__titulo__icontains=filters['q'])
            | Q(motivo__icontains=filters['q'])
            | Q(evento__fundamentacao__texto_fundamentacao__icontains=filters['q'])
            | Q(protocolo__icontains=Oficio.normalize_protocolo(filters['q']) or filters['q'])
            | Q(trechos__destino_cidade__nome__icontains=filters['q'])
            | Q(viajantes__nome__icontains=filters['q'])
        )
    
    if filters['ano'].isdigit():
        queryset = queryset.filter(ano=int(filters['ano']))
    if filters['oficio_status']:
        queryset = queryset.filter(status=filters['oficio_status'])

    selected_event = (
        Evento.objects.filter(pk=int(filters['evento_id'])).first()
        if filters['evento_id'].isdigit()
        else None
    )
    rows = []
    for oficio in queryset.distinct().order_by('-updated_at', '-created_at'):
        status_info = _document_status_summary(
            oficio,
            DocumentoOficioTipo.PLANO_TRABALHO,
            EventoFundamentacao.TIPO_PT,
        )
        if filters['situacao'] != 'todos' and status_info['status_key'] != filters['situacao']:
            continue
        process_status = _document_card_status_meta(status_info['status_key'], status_info['status_label'])
        fundamentacao = getattr(oficio.evento, 'fundamentacao', None)
        oficio.process_status = process_status
        oficio.status_info = status_info
        oficio.evento_url = ''
        oficio.evento_titulo_display = (oficio.evento.titulo or '').strip() or '(sem titulo)'
        oficio.identificacao_display = f'Plano de trabalho - {oficio.numero_formatado}'
        oficio.destinos_display = _oficio_destinos_display(oficio)
        oficio.periodo_display = _oficio_periodo_display(oficio)
        oficio.viajantes_display = _oficio_viajantes_display(oficio)
        oficio.responsavel_display = _plano_trabalho_responsavel_display(oficio)
        oficio.solicitante_display = _plano_trabalho_solicitante_display(oficio)
        oficio.resumo_display = _plano_trabalho_resumo_display(oficio)
        oficio.footer_actions = _build_plano_trabalho_footer_actions(oficio)
        oficio.card_actions = _build_plano_trabalho_actions(oficio, status_info)
        oficio.document_summary_items = [
            {'label': 'Configuracao', 'value': status_info['fundamentacao_label']},
            {'label': 'Solicitante', 'value': oficio.solicitante_display},
            {
                'label': 'Atendimento',
                'value': _clean(getattr(fundamentacao, 'horario_atendimento', '')) or '-',
            },
        ]
        rows.append(oficio)

    page_obj = _paginate(rows, request.GET.get('page'))
    return render(
        request,
        'eventos/global/planos_trabalho_lista.html',
        {
            'object_list': list(page_obj.object_list),
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'oficio_status_choices': Oficio.STATUS_CHOICES,
            'situacao_choices': [
                ('todos', 'Todos'),
                ('available', 'Disponiveis'),
                ('pending', 'Pendentes'),
                ('unavailable', 'Indisponiveis'),
                ('not_applicable', 'Nao aplicaveis'),
            ],
            'selected_event': selected_event,
        },
    )


def ordens_servico_global(request):
    """Lista de ordens de serviço em cards (mesmo padrão da lista de ofícios)."""
    return _documento_derivado_global(
        request,
        template_title='Lista de ordens de serviço - Central de Viagens',
        template_page_title='Lista de ordens de serviço',
        template_subtitle='Acompanhe cada ordem de serviço em um card, com vínculo ao evento, período, equipe e ações.',
        tipo_documento=DocumentoOficioTipo.ORDEM_SERVICO,
        fundamentacao_tipo=EventoFundamentacao.TIPO_OS,
        template_name='eventos/global/ordens_servico_lista.html',
    )


def _build_justificativa_card_actions(oficio, next_url):
    documento = _build_oficio_document_actions(oficio, DocumentoOficioTipo.JUSTIFICATIVA)
    actions = [
        {
            'label': 'Editar',
            'url': _append_next(reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}), next_url),
            'style': 'primary',
            'available': True,
        },
        {
            'label': 'Visualizar',
            'url': reverse('eventos:oficio-documentos', kwargs={'pk': oficio.pk}),
            'style': 'secondary',
            'available': True,
        },
    ]
    for action in documento['actions']:
        actions.append(
            {
                'label': action['label'],
                'url': action['url'],
                'style': 'secondary',
                'available': action['available'],
            }
        )
    return documento, actions


def _build_justificativa_detail(oficio, info, documento):
    texto = _clean(oficio.justificativa_texto)
    if texto:
        return Truncator(texto).chars(240)
    if info['status_key'] == 'nao_exigida':
        return 'Justificativa nao obrigatoria para o prazo atual.'
    if info['status_key'] == 'indefinida':
        return 'Aguardando roteiro valido para definir a obrigatoriedade.'
    if info['status_key'] == 'indisponivel':
        return info['schema_message']
    return documento['detail']


def justificativas_global(request):
    filters = {
        'q': _clean(request.GET.get('q')),
        'evento_id': _clean(request.GET.get('evento_id')),
        'ano': _clean(request.GET.get('ano')),
        'status': _clean(request.GET.get('status')),
    }
    queryset = (
        Oficio.objects.select_related('evento', 'justificativa_modelo')
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
        )
        .all()
    )
    if filters['q']:
        queryset = queryset.filter(
            Q(evento__titulo__icontains=filters['q'])
            | Q(motivo__icontains=filters['q'])
            | Q(justificativa_texto__icontains=filters['q'])
            | Q(justificativa_modelo__nome__icontains=filters['q'])
            | Q(protocolo__icontains=Oficio.normalize_protocolo(filters['q']) or filters['q'])
            | Q(trechos__destino_cidade__nome__icontains=filters['q'])
        )
    
    if filters['ano'].isdigit():
        queryset = queryset.filter(ano=int(filters['ano']))

    next_url = request.get_full_path()
    object_list = []
    for oficio in queryset.distinct().order_by('-updated_at', '-created_at'):
        info = _build_oficio_justificativa_info(oficio)
        if filters['status'] and info['status_key'] != filters['status']:
            continue
        documento, actions = _build_justificativa_card_actions(oficio, next_url)
        oficio.info = info
        oficio.process_status = _document_card_status_meta(info['status_key'], info['status_label'])
        oficio.destinos_display = _oficio_destinos_display(oficio)
        oficio.periodo_display = _oficio_periodo_display(oficio)
        oficio.viajantes_display = _oficio_viajantes_display(oficio)
        oficio.justificativa_actions = actions
        oficio.justificativa_detail = _build_justificativa_detail(oficio, info, documento)
        oficio.justificativa_url = _append_next(
            reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
            next_url,
        )
        oficio.documentos_url = reverse('eventos:oficio-documentos', kwargs={'pk': oficio.pk})
        oficio.oficio_url = reverse('eventos:oficio-editar', kwargs={'pk': oficio.pk})
        oficio.evento_url = ''
        oficio.evento_titulo_display = (
            (oficio.evento.titulo or '').strip()
            if oficio.evento_id
            else 'Oficio avulso'
        ) or '(sem titulo)'
        oficio.data_display = (
            oficio.data_criacao.strftime('%d/%m/%Y')
            if oficio.data_criacao
            else oficio.created_at.strftime('%d/%m/%Y')
        )
        oficio.modelo_display = (
            (oficio.justificativa_modelo.nome or '').strip()
            if oficio.justificativa_modelo_id
            else 'Sem modelo'
        )
        oficio.tema_display = Truncator(_clean(oficio.motivo) or 'Tema nao informado.').chars(160)
        oficio.antecedencia_display = (
            f"{info['dias_antecedencia']} dia(s)"
            if info['dias_antecedencia'] is not None
            else '-'
        )
        oficio.summary_items = [
            {'label': 'Tema', 'value': oficio.tema_display},
            {'label': 'Modelo', 'value': oficio.modelo_display},
            {'label': 'Primeira saida', 'value': info['primeira_saida_display'] or '-'},
            {'label': 'Protocolo', 'value': oficio.protocolo_formatado or '-'},
        ]
        object_list.append(oficio)
    page_obj = _paginate(object_list, request.GET.get('page'))
    return render(
        request,
        'eventos/global/justificativas_lista.html',
        {
            'object_list': list(page_obj.object_list),
            'page_obj': page_obj,
            'pagination_query': _query_without_page(request),
            'filters': filters,
            'eventos_choices': _eventos_choices(),
            'novo_justificativa_url': reverse('eventos:modelos-justificativa-cadastrar'),
            'status_choices': [
                ('pendente', 'Pendentes'),
                ('preenchida', 'Preenchidas'),
                ('nao_exigida', 'Nao exigidas'),
                ('indefinida', 'Aguardando roteiro'),
                ('indisponivel', 'Indisponiveis'),
            ],
        },
    )


TERMO_STATUS_CARD_META = {
    EventoTermoParticipante.STATUS_PENDENTE: {'label': 'Pendente', 'css_class': 'is-pendente'},
    EventoTermoParticipante.STATUS_DISPENSADO: {'label': 'Dispensado', 'css_class': 'is-dispensado'},
    EventoTermoParticipante.STATUS_GERADO: {'label': 'Gerado', 'css_class': 'is-gerado'},
    EventoTermoParticipante.STATUS_CONCLUIDO: {'label': 'Concluído', 'css_class': 'is-concluido'},
}


def _build_termo_oficio_context(oficios_relacionados):
    if not oficios_relacionados:
        return {
            'principal': '-',
            'detail': 'Nenhum oficio vinculado.',
        }
    principal = oficios_relacionados[0].numero_formatado
    extras = len(oficios_relacionados) - 1
    detail = principal
    if extras > 0:
        detail = f'{principal} + {extras} oficio(s)'
    return {
        'principal': principal,
        'detail': detail,
    }


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
        oficio_context = _build_termo_oficio_context(oficios_relacionados)
        termo.oficios_display = oficio_context['detail']
        termo.oficio_principal_display = oficio_context['principal']
        termo.open_url = reverse('eventos:guiado-etapa-3', kwargs={'evento_id': termo.evento_id})
        termo.evento_url = reverse('eventos:guiado-painel', kwargs={'pk': termo.evento_id})
        meta = TERMO_STATUS_CARD_META.get(termo.status, {})
        termo.status_css_class = meta.get('css_class', 'is-pendente')
        termo.status_label = meta.get('label', termo.get_status_display())
        termo.modalidade_label = termo.get_modalidade_display()
        termo.cargo_display = getattr(getattr(termo.viajante, 'cargo', None), 'nome', '') or 'Sem cargo'
        termo.updated_display = termo.updated_at.strftime('%d/%m/%Y %H:%M')
        termo.download_available = termo.status != EventoTermoParticipante.STATUS_DISPENSADO
        termo.termo_docx_url = reverse(
            'eventos:guiado-etapa-3-termo-download',
            kwargs={'evento_id': termo.evento_id, 'viajante_id': termo.viajante_id, 'formato': 'docx'},
        )
        termo.termo_pdf_url = reverse(
            'eventos:guiado-etapa-3-termo-download',
            kwargs={'evento_id': termo.evento_id, 'viajante_id': termo.viajante_id, 'formato': 'pdf'},
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
