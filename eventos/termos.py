from __future__ import annotations

from datetime import datetime, time

from cadastros.models import Viajante

from .models import EventoParticipante, Oficio, TermoAutorizacao
from .utils import serializar_viajante_para_autocomplete, serializar_veiculo_para_oficio


TERMO_TEMPLATE_NAMES = {
    TermoAutorizacao.MODO_RAPIDO: 'termo_autorizacao.docx',
    TermoAutorizacao.MODO_AUTOMATICO_COM_VIATURA: 'termo_autorizacao_automatico.docx',
    TermoAutorizacao.MODO_AUTOMATICO_SEM_VIATURA: 'termo_autorizacao_automatico_sem_viatura.docx',
}


def _ordered_unique_strings(values):
    items = []
    seen = set()
    for value in values:
        item = (value or '').strip()
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _ordered_unique_models(objects):
    items = []
    seen = set()
    for obj in objects:
        if obj is None or not getattr(obj, 'pk', None) or obj.pk in seen:
            continue
        seen.add(obj.pk)
        items.append(obj)
    return items


def _label_local(cidade, estado):
    if cidade and estado:
        return f'{cidade.nome}/{estado.sigla}'
    if cidade:
        return cidade.nome
    if estado:
        return estado.sigla
    return ''


def _serialize_veiculo(veiculo):
    data = serializar_veiculo_para_oficio(veiculo)
    data['id'] = veiculo.pk
    data['label'] = f"{data['placa_formatada']} - {data['modelo']}".strip(' -')
    return data


def _serialize_oficio(oficio):
    numero = (getattr(oficio, 'numero_formatado', '') or '').strip() or f'#{oficio.pk}'
    protocolo = (getattr(oficio, 'protocolo_formatado', '') or '').strip()
    label = f'Oficio {numero}'
    if protocolo:
        label = f'{label} - {protocolo}'
    return {
        'id': oficio.pk,
        'label': label,
        'numero_formatado': numero,
    }


def _serialize_roteiro(roteiro):
    return {
        'id': roteiro.pk,
        'label': str(roteiro),
    }


def _oficio_destinos(oficio):
    labels = []
    for trecho in oficio.trechos.all():
        labels.append(
            _label_local(
                getattr(trecho, 'destino_cidade', None),
                getattr(trecho, 'destino_estado', None),
            )
        )
    return _ordered_unique_strings(labels)


def _roteiro_destinos(roteiro):
    labels = []
    for destino in roteiro.destinos.all():
        labels.append(_label_local(destino.cidade, destino.estado))
    return _ordered_unique_strings(labels)


def _evento_destinos(evento):
    labels = []
    for destino in evento.destinos.all():
        labels.append(_label_local(destino.cidade, destino.estado))
    return _ordered_unique_strings(labels)


def _combine_date_time(date_value, time_value, fallback_time):
    if not date_value:
        return None
    return datetime.combine(date_value, time_value or fallback_time)


def _oficio_period_bounds(oficio):
    points = []
    for trecho in oficio.trechos.all():
        saida = _combine_date_time(trecho.saida_data, trecho.saida_hora, time.min)
        chegada = _combine_date_time(trecho.chegada_data, trecho.chegada_hora, time.max)
        if saida:
            points.append(saida)
        if chegada:
            points.append(chegada)
    retorno_saida = _combine_date_time(oficio.retorno_saida_data, oficio.retorno_saida_hora, time.min)
    retorno_chegada = _combine_date_time(oficio.retorno_chegada_data, oficio.retorno_chegada_hora, time.max)
    if retorno_saida:
        points.append(retorno_saida)
    if retorno_chegada:
        points.append(retorno_chegada)
    if not points:
        return None, None
    return min(points).date(), max(points).date()


def _roteiro_period_bounds(roteiro):
    points = [
        value
        for value in [
            getattr(roteiro, 'saida_dt', None),
            getattr(roteiro, 'chegada_dt', None),
            getattr(roteiro, 'retorno_saida_dt', None),
            getattr(roteiro, 'retorno_chegada_dt', None),
        ]
        if value
    ]
    if not points:
        return None, None
    return min(points).date(), max(points).date()


def _period_display(data_inicio, data_fim):
    if not data_inicio:
        return '-'
    if data_fim and data_fim != data_inicio:
        return f'{data_inicio:%d/%m/%Y} a {data_fim:%d/%m/%Y}'
    return f'{data_inicio:%d/%m/%Y}'


def _evento_viajantes(evento):
    participante_ids = list(
        EventoParticipante.objects.filter(evento=evento).values_list('viajante_id', flat=True)
    )
    if not participante_ids:
        participante_ids = [
            viajante_id
            for viajante_id in Oficio.viajantes.through.objects.filter(
                oficio_id__in=Oficio.objects.filter(eventos=evento).values_list('pk', flat=True)
            ).values_list('viajante_id', flat=True)
            if viajante_id
        ]
    if not participante_ids:
        return []
    queryset = (
        Viajante.objects.select_related('cargo', 'unidade_lotacao')
        .filter(status=Viajante.STATUS_FINALIZADO, pk__in=participante_ids)
        .order_by('nome')
    )
    viajantes_map = {viajante.pk: viajante for viajante in queryset}
    return [viajantes_map[pk] for pk in participante_ids if pk in viajantes_map]


def build_termo_context(*, evento=None, oficios=None, roteiro=None):
    selected_oficios = _ordered_unique_models(oficios or [])
    all_destinos = []
    all_viajantes = []
    all_veiculos = []
    route_candidates = []
    event_candidates = []
    period_ranges = []

    if evento is not None:
        event_candidates.append(evento)
        all_destinos.extend(_evento_destinos(evento))
        period_ranges.append((evento.data_inicio, evento.data_fim or evento.data_inicio))
        route_candidates.extend(evento.roteiros.all())

    if roteiro is not None:
        route_candidates.append(roteiro)
        all_destinos.extend(_roteiro_destinos(roteiro))
        period_ranges.append(_roteiro_period_bounds(roteiro))
        if roteiro.evento_id:
            event_candidates.append(roteiro.evento)

    for oficio in selected_oficios:
        if oficio.evento_id:
            event_candidates.append(oficio.evento)
        if oficio.roteiro_evento_id:
            route_candidates.append(oficio.roteiro_evento)
        all_destinos.extend(_oficio_destinos(oficio))
        period_ranges.append(_oficio_period_bounds(oficio))
        all_viajantes.extend(list(oficio.viajantes.all()))
        if oficio.veiculo_id:
            all_veiculos.append(oficio.veiculo)

    unique_events = _ordered_unique_models(event_candidates)
    unique_routes = _ordered_unique_models(route_candidates)
    unique_viajantes = _ordered_unique_models(all_viajantes)
    unique_veiculos = _ordered_unique_models(all_veiculos)

    valid_ranges = [(start, end or start) for start, end in period_ranges if start]
    data_inicio = min((start for start, _end in valid_ranges), default=None)
    data_fim = max((end for _start, end in valid_ranges), default=data_inicio)

    contexto_evento = evento or (unique_events[0] if len(unique_events) == 1 else None)
    contexto_roteiro = roteiro or (unique_routes[0] if len(unique_routes) == 1 else None)
    veiculo_inferido = unique_veiculos[0] if len(unique_veiculos) == 1 else None
    destinos = _ordered_unique_strings(all_destinos)

    return {
        'evento': contexto_evento,
        'oficios': selected_oficios,
        'roteiro': contexto_roteiro,
        'destinos': destinos,
        'destino': ', '.join(destinos),
        'data_evento': data_inicio,
        'data_evento_fim': data_fim,
        'periodo_display': _period_display(data_inicio, data_fim),
        'viajantes': unique_viajantes,
        'veiculos': unique_veiculos,
        'veiculo_inferido': veiculo_inferido,
    }


def build_termo_preview_payload(context, *, viajantes=None, veiculo=None):
    effective_viajantes = _ordered_unique_models(viajantes if viajantes is not None else context['viajantes'])
    effective_veiculo = veiculo if veiculo is not None else context['veiculo_inferido']
    modo = TermoAutorizacao.infer_modo_geracao(
        has_servidores=bool(effective_viajantes),
        has_viatura=bool(effective_veiculo),
    )
    return {
        'evento': (
            {
                'id': context['evento'].pk,
                'label': (context['evento'].titulo or '').strip() or f'Evento #{context["evento"].pk}',
            }
            if context['evento']
            else None
        ),
        'oficios': [_serialize_oficio(oficio) for oficio in context['oficios']],
        'roteiro': _serialize_roteiro(context['roteiro']) if context['roteiro'] else None,
        'destinos': context['destinos'],
        'destino': context['destino'],
        'data_evento': context['data_evento'].isoformat() if context['data_evento'] else '',
        'data_evento_fim': context['data_evento_fim'].isoformat() if context['data_evento_fim'] else '',
        'periodo_display': context['periodo_display'],
        'viajantes': [serializar_viajante_para_autocomplete(viajante) for viajante in effective_viajantes],
        'veiculos': [_serialize_veiculo(veiculo_item) for veiculo_item in context['veiculos']],
        'veiculo_inferido': _serialize_veiculo(effective_veiculo) if effective_veiculo else None,
        'modo_geracao': modo,
        'modo_label': dict(TermoAutorizacao.MODO_CHOICES).get(modo, modo),
        'template_name': TERMO_TEMPLATE_NAMES[modo],
        'estimativa_termos': len(effective_viajantes) if effective_viajantes else 1,
        'total_viajantes': len(effective_viajantes),
        'total_viaturas': len(context['veiculos']),
    }
