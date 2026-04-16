from __future__ import annotations

from dataclasses import dataclass

from cadastros.models import ConfiguracaoSistema, Viajante

from ..models import Evento, EventoParticipante, Oficio, RoteiroEvento, TermoAutorizacao
from ..termos import build_termo_context
from .plano_trabalho_step2 import build_plano_step2_defaults, select_roteiro_mais_caro


def _ordered_unique_models(objects):
    items = []
    seen = set()
    for obj in objects or []:
        if obj is None or not getattr(obj, 'pk', None) or obj.pk in seen:
            continue
        seen.add(obj.pk)
        items.append(obj)
    return items


def _ordered_unique_strings(values):
    items = []
    seen = set()
    for value in values or []:
        item = (value or '').strip()
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _destino_label(cidade=None, estado=None):
    if cidade and estado:
        return f'{cidade.nome}/{estado.sigla}'
    if cidade:
        return cidade.nome
    if estado:
        return estado.sigla
    return ''


def _serialize_destino(destino):
    return {
        'estado_id': destino.estado_id,
        'estado_sigla': destino.estado.sigla if destino.estado_id else '',
        'cidade_id': destino.cidade_id,
        'cidade_nome': destino.cidade.nome if destino.cidade_id else '',
    }


def _oficio_destinos(oficio):
    labels = []
    for trecho in oficio.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'):
        labels.append(_destino_label(trecho.destino_cidade, trecho.destino_estado))
    return _ordered_unique_strings(labels)


def _roteiro_destinos(roteiro):
    labels = []
    for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk'):
        labels.append(_destino_label(destino.cidade, destino.estado))
    return _ordered_unique_strings(labels)


def _evento_destinos(evento):
    labels = []
    for destino in evento.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk'):
        labels.append(_destino_label(destino.cidade, destino.estado))
    return _ordered_unique_strings(labels)


def _oficio_period_bounds(oficio):
    points = []
    for trecho in oficio.trechos.all():
        if trecho.saida_data:
            points.append(trecho.saida_data)
        if trecho.chegada_data:
            points.append(trecho.chegada_data)
    if oficio.retorno_saida_data:
        points.append(oficio.retorno_saida_data)
    if oficio.retorno_chegada_data:
        points.append(oficio.retorno_chegada_data)
    if not points:
        return None, None
    return min(points), max(points)


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


def _evento_viajantes(evento, oficios=None):
    participante_ids = []
    selected_oficios = _ordered_unique_models(oficios or [])
    if evento is not None:
        participante_ids.extend(
            EventoParticipante.objects.filter(evento=evento).values_list('viajante_id', flat=True)
        )
        if selected_oficios:
            oficio_ids = [oficio.pk for oficio in selected_oficios if getattr(oficio, 'pk', None)]
        else:
            oficio_ids = list(Oficio.objects.filter(eventos=evento).values_list('pk', flat=True))
        if oficio_ids:
            participante_ids.extend(
                Oficio.viajantes.through.objects.filter(oficio_id__in=oficio_ids).values_list('viajante_id', flat=True)
            )
    else:
        oficio_ids = [oficio.pk for oficio in selected_oficios if getattr(oficio, 'pk', None)]
        if oficio_ids:
            participante_ids.extend(
                Oficio.viajantes.through.objects.filter(oficio_id__in=oficio_ids).values_list('viajante_id', flat=True)
            )
    participante_ids = list(dict.fromkeys(participante_ids))
    if not participante_ids:
        return []
    queryset = (
        Viajante.objects.select_related('cargo', 'unidade_lotacao')
        .filter(status=Viajante.STATUS_FINALIZADO, pk__in=participante_ids)
        .order_by('nome')
    )
    viajantes_map = {viajante.pk: viajante for viajante in queryset}
    return [viajantes_map[pk] for pk in participante_ids if pk in viajantes_map]


@dataclass(frozen=True)
class ContextoEventoBase:
    evento: Evento | None
    roteiro: RoteiroEvento | None
    oficios: tuple[Oficio, ...]
    destinos: tuple[str, ...]
    destino: str
    data_evento: object | None
    data_evento_fim: object | None
    viajantes: tuple[Viajante, ...]
    veiculo: object | None
    default_roteiro: RoteiroEvento | None


def build_evento_contexto_base(evento: Evento | None, *, oficios=None, roteiro=None) -> ContextoEventoBase:
    selected_oficios = _ordered_unique_models(oficios or [])
    selected_roteiro = roteiro or (select_roteiro_mais_caro(evento) if evento else None)
    destination_labels = []
    period_ranges = []
    vehicle_candidates = []
    event_candidates = []

    if evento is not None:
        event_candidates.append(evento)
        destination_labels.extend(_evento_destinos(evento))
        period_ranges.append((evento.data_inicio, evento.data_fim or evento.data_inicio))
        if getattr(evento, 'veiculo_id', None):
            vehicle_candidates.append(evento.veiculo)

    if selected_roteiro is not None:
        event_candidates.append(getattr(selected_roteiro, 'evento', None))
        destination_labels.extend(_roteiro_destinos(selected_roteiro))
        period_ranges.append(_roteiro_period_bounds(selected_roteiro))

    for oficio in selected_oficios:
        if oficio.evento_id:
            event_candidates.append(oficio.evento)
        if oficio.roteiro_evento_id:
            event_candidates.append(oficio.roteiro_evento.evento if oficio.roteiro_evento else None)
        destination_labels.extend(_oficio_destinos(oficio))
        period_ranges.append(_oficio_period_bounds(oficio))
        if oficio.veiculo_id:
            vehicle_candidates.append(oficio.veiculo)

    valid_ranges = [(start, end or start) for start, end in period_ranges if start]
    data_inicio = min((start for start, _end in valid_ranges), default=None)
    data_fim = max((end for _start, end in valid_ranges), default=data_inicio)
    destination_labels = _ordered_unique_strings(destination_labels)

    unique_events = _ordered_unique_models(event_candidates)
    contexto_evento = evento or (unique_events[0] if len(unique_events) == 1 else None)
    unique_viajantes = tuple(_evento_viajantes(evento, selected_oficios)) if (evento or selected_oficios) else tuple()
    unique_veiculos = _ordered_unique_models(vehicle_candidates)

    return ContextoEventoBase(
        evento=contexto_evento,
        roteiro=selected_roteiro or (contexto_evento.roteiros.order_by('-updated_at').first() if contexto_evento else None),
        oficios=tuple(selected_oficios),
        destinos=tuple(destination_labels),
        destino=', '.join(destination_labels),
        data_evento=data_inicio,
        data_evento_fim=data_fim,
        viajantes=unique_viajantes,
        veiculo=unique_veiculos[0] if len(unique_veiculos) == 1 else None,
        default_roteiro=selected_roteiro,
    )


def build_contexto_roteiro_from_evento(evento: Evento | None):
    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    sede_cidade = getattr(config, 'cidade_sede_padrao', None) if config else None
    if not sede_cidade:
        sede_cidade = getattr(evento, 'cidade_base', None) or getattr(evento, 'cidade_principal', None)
    if sede_cidade and sede_cidade.pk:
        initial['origem_cidade'] = sede_cidade.pk
        if getattr(sede_cidade, 'estado_id', None):
            initial['origem_estado'] = sede_cidade.estado_id
    destinos = [
        _serialize_destino(destino)
        for destino in evento.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk')
    ] if evento else []
    return {'initial': initial, 'destinos': destinos}


def build_contexto_oficio_from_evento(evento: Evento | None):
    base = build_evento_contexto_base(evento)
    return {
        'evento': base.evento,
        'roteiro': base.default_roteiro or base.roteiro,
        'destino': base.destino,
        'data_evento': base.data_evento,
        'data_evento_fim': base.data_evento_fim,
        'viajantes_ids': [viajante.pk for viajante in base.viajantes],
        'veiculo_id': base.veiculo.pk if base.veiculo else None,
    }


def build_contexto_plano_trabalho_from_evento(evento: Evento | None):
    defaults = build_plano_step2_defaults(evento)
    return {
        'evento': evento,
        'roteiro': defaults.roteiro,
        'destinos_json': list(defaults.destinos_json or []),
        'data_evento_inicio': defaults.evento_data_inicio,
        'data_evento_fim': defaults.evento_data_fim,
        'data_saida_sede': defaults.data_saida_sede,
        'hora_saida_sede': defaults.hora_saida_sede,
        'data_chegada_sede': defaults.data_chegada_sede,
        'hora_chegada_sede': defaults.hora_chegada_sede,
        'warnings': defaults.warnings,
    }


def build_contexto_ordem_servico_from_evento(evento: Evento | None):
    base = build_evento_contexto_base(evento)
    viajantes_ids = [viajante.pk for viajante in base.viajantes]
    viajantes_ids = list(dict.fromkeys(pk for pk in viajantes_ids if pk))
    return {
        'evento': evento,
        'data_deslocamento': base.data_evento,
        'data_deslocamento_fim': base.data_evento_fim,
        'destinos_payload': [
            _serialize_destino(destino)
            for destino in evento.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk')
        ] if evento else [],
        'destino': base.destino,
        'viajantes_ids': viajantes_ids,
    }


def build_contexto_termo_from_evento(evento: Evento | None, *, oficios=None, roteiro=None):
    return build_termo_context(evento=evento, oficios=oficios, roteiro=roteiro)


def ensure_termo_generico_evento(evento: Evento | None, *, user=None):
    if not evento:
        return None
    contexto = build_contexto_termo_from_evento(evento)
    root = (
        TermoAutorizacao.objects.select_related('evento', 'roteiro', 'veiculo')
        .prefetch_related('oficios', 'derivacoes')
        .filter(
            evento=evento,
            termo_pai__isnull=True,
            derivacao_tipo=TermoAutorizacao.DERIVACAO_TIPO_GENERICA,
        )
        .order_by('created_at', 'pk')
        .first()
    )
    if root is None:
        root = TermoAutorizacao(
            evento=evento,
            derivacao_tipo=TermoAutorizacao.DERIVACAO_TIPO_GENERICA,
            modo_geracao=TermoAutorizacao.MODO_GENERICO,
            template_variant=TermoAutorizacao.TEMPLATE_SEMIPREENCHIDO,
            status=TermoAutorizacao.STATUS_RASCUNHO,
            criado_por=user if user and getattr(user, 'pk', None) else None,
        )

    updates = []
    if contexto['roteiro'] and not root.roteiro_id:
        root.roteiro = contexto['roteiro']
        updates.append('roteiro')
    if contexto['destino'] and not (root.destino or '').strip():
        root.destino = contexto['destino']
        updates.append('destino')
    if contexto['data_evento'] and not root.data_evento:
        root.data_evento = contexto['data_evento']
        updates.append('data_evento')
    if contexto['data_evento_fim'] and not root.data_evento_fim:
        root.data_evento_fim = contexto['data_evento_fim']
        updates.append('data_evento_fim')
    veiculo_contexto = contexto.get('veiculo_inferido')
    if veiculo_contexto and not root.veiculo_id:
        root.veiculo = veiculo_contexto
        updates.append('veiculo')
    elif getattr(evento, 'veiculo_id', None) and not root.veiculo_id:
        root.veiculo = evento.veiculo
        updates.append('veiculo')
    if user and not root.criado_por_id:
        root.criado_por = user
        updates.append('criado_por')
    root.modo_geracao = TermoAutorizacao.MODO_GENERICO
    root.template_variant = TermoAutorizacao.TEMPLATE_SEMIPREENCHIDO
    root.status = TermoAutorizacao.STATUS_GERADO if root.is_ready_for_generation() else TermoAutorizacao.STATUS_RASCUNHO
    root.save()
    return root


def attach_termo_derivacoes(root: TermoAutorizacao | None, termos: list[TermoAutorizacao] | None = None):
    if not root:
        return []
    termos = list(termos or [])
    for termo in termos:
        termo.termo_pai = root
        if root.evento_id and not termo.evento_id:
            termo.evento = root.evento
        if root.roteiro_id and not termo.roteiro_id:
            termo.roteiro = root.roteiro
        if root.destino and not (termo.destino or '').strip():
            termo.destino = root.destino
        if root.data_evento and not termo.data_evento:
            termo.data_evento = root.data_evento
        if root.data_evento_fim and not termo.data_evento_fim:
            termo.data_evento_fim = root.data_evento_fim
        if root.veiculo_id and not termo.veiculo_id:
            termo.veiculo = root.veiculo
        if root.oficio_id:
            termo.oficio = root.oficio
            termo.oficios.set([root.oficio])
        termo.save()
        if root.oficio_id:
            root.oficios.add(root.oficio)
    return termos
