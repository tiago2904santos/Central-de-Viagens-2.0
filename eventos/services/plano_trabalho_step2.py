from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from ..models import Evento, RoteiroEvento


STEP2_SOURCE_EVENTO = 'evento'
STEP2_SOURCE_MANUAL = 'manual'
STEP2_SOURCE_ROTEIRO_EVENTO = 'roteiro_evento'


def _is_empty(value):
    return value in (None, '', [], {}, ())


def _serialize_destino(destino) -> dict:
    return {
        'estado_id': destino.estado_id,
        'estado_sigla': (destino.estado.sigla if destino.estado_id else ''),
        'cidade_id': destino.cidade_id,
        'cidade_nome': (destino.cidade.nome if destino.cidade_id else ''),
    }


def _route_window(roteiro):
    if not roteiro or not roteiro.saida_dt:
        return None, None, None, None
    chegada_final = roteiro.retorno_chegada_dt or roteiro.chegada_dt
    if not chegada_final or chegada_final <= roteiro.saida_dt:
        return None, None, None, None
    saida_dt = timezone.localtime(roteiro.saida_dt) if timezone.is_aware(roteiro.saida_dt) else roteiro.saida_dt
    chegada_dt = timezone.localtime(chegada_final) if timezone.is_aware(chegada_final) else chegada_final
    return (
        saida_dt.date(),
        saida_dt.time(),
        chegada_dt.date(),
        chegada_dt.time(),
    )


def _roteiro_sort_key(roteiro):
    valor = roteiro.valor_diarias if roteiro.valor_diarias is not None else Decimal('-1')
    duracao_min = roteiro.periodo_total_min()
    created_ts = roteiro.created_at.timestamp() if roteiro.created_at else float('inf')
    return (-valor, -duracao_min, created_ts, roteiro.pk or 0)


def select_roteiro_mais_caro(evento: Evento | None) -> RoteiroEvento | None:
    if not evento:
        return None
    roteiros = list(
        evento.roteiros.filter(valor_diarias__isnull=False)
        .select_related('evento')
        .prefetch_related('destinos__cidade', 'destinos__estado')
    )
    if not roteiros:
        return None
    return sorted(roteiros, key=_roteiro_sort_key)[0]


@dataclass(frozen=True)
class PlanoTrabalhoStep2Defaults:
    evento_id: int | None
    evento_data_inicio: object | None
    evento_data_fim: object | None
    destinos_json: list[dict] = field(default_factory=list)
    roteiro: RoteiroEvento | None = None
    warnings: tuple[str, ...] = ()

    @property
    def roteiro_id(self):
        return self.roteiro.pk if self.roteiro else None

    @property
    def data_saida_sede(self):
        saida_data, _saida_hora, _chegada_data, _chegada_hora = _route_window(self.roteiro)
        return saida_data

    @property
    def hora_saida_sede(self):
        _saida_data, saida_hora, _chegada_data, _chegada_hora = _route_window(self.roteiro)
        return saida_hora

    @property
    def data_chegada_sede(self):
        _saida_data, _saida_hora, chegada_data, _chegada_hora = _route_window(self.roteiro)
        return chegada_data

    @property
    def hora_chegada_sede(self):
        _saida_data, _saida_hora, _chegada_data, chegada_hora = _route_window(self.roteiro)
        return chegada_hora

    @property
    def has_roteiro(self):
        return self.roteiro is not None


def build_plano_step2_defaults(evento: Evento | None) -> PlanoTrabalhoStep2Defaults:
    if not evento:
        return PlanoTrabalhoStep2Defaults(
            evento_id=None,
            evento_data_inicio=None,
            evento_data_fim=None,
            destinos_json=[],
            roteiro=None,
            warnings=(),
        )

    roteiro = select_roteiro_mais_caro(evento)
    destinos_json = [
        _serialize_destino(destino)
        for destino in evento.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk')
    ]
    warnings = []
    if not roteiro:
        warnings.append('O evento não possui roteiro com valor válido para preencher a calculadora automaticamente.')
    else:
        saida_data, saida_hora, chegada_data, chegada_hora = _route_window(roteiro)
        if not (saida_data and saida_hora and chegada_data and chegada_hora):
            warnings.append('O roteiro mais caro está incompleto e não conseguiu preencher a calculadora automaticamente.')

    return PlanoTrabalhoStep2Defaults(
        evento_id=evento.pk,
        evento_data_inicio=evento.data_inicio,
        evento_data_fim=evento.data_fim,
        destinos_json=destinos_json,
        roteiro=roteiro,
        warnings=tuple(warnings),
    )


def reconcile_plano_step2_state(
    plano,
    *,
    defaults: PlanoTrabalhoStep2Defaults,
    incoming: dict,
    present_fields: set[str],
):
    """
    Ajusta a etapa 2 de um Plano de Trabalho com base no estado herdado do evento.

    - Mantém manual edits quando a origem já é manual.
    - Reaplica defaults apenas enquanto a seção segue herdada.
    - Trata campos presentes com valor vazio como limpeza explícita pelo usuário.
    """
    origin = dict(plano.step2_origem_json or {})
    resolved = {}
    warnings = list(defaults.warnings)
    changed = False

    def _set(field_name, value):
        nonlocal changed
        current = getattr(plano, field_name)
        if current != value:
            changed = True
        resolved[field_name] = value

    def _set_source(section, source):
        nonlocal changed
        if origin.get(section) != source:
            changed = True
        origin[section] = source

    def _present(*names):
        return any(name in present_fields for name in names)

    incoming_roteiro = incoming.get('roteiro')
    route_present = _present('roteiro')
    route_source = origin.get('roteiro')

    if route_present:
        if incoming_roteiro and defaults.roteiro and getattr(incoming_roteiro, 'pk', None) == defaults.roteiro.pk:
            _set('roteiro', defaults.roteiro)
            _set_source('roteiro', STEP2_SOURCE_EVENTO)
        elif incoming_roteiro:
            _set('roteiro', incoming_roteiro)
            _set_source('roteiro', STEP2_SOURCE_MANUAL)
        else:
            _set('roteiro', None)
            _set_source('roteiro', STEP2_SOURCE_MANUAL)
    else:
        if route_source != STEP2_SOURCE_MANUAL:
            if plano.roteiro_id:
                _set('roteiro', plano.roteiro)
            elif defaults.roteiro:
                _set('roteiro', defaults.roteiro)
                _set_source('roteiro', STEP2_SOURCE_EVENTO)

    effective_roteiro = resolved.get('roteiro', plano.roteiro if plano.roteiro_id else defaults.roteiro)
    route_saida_data, route_saida_hora, route_chegada_data, route_chegada_hora = _route_window(effective_roteiro)

    start_present = _present('evento_data_inicio')
    end_present = _present('evento_data_fim')
    period_source = origin.get('periodo')
    if start_present or end_present:
        start_value = incoming.get('evento_data_inicio')
        end_value = incoming.get('evento_data_fim')
        _set('evento_data_inicio', start_value)
        _set('evento_data_fim', end_value)
        if (
            defaults.evento_data_inicio is not None
            and defaults.evento_data_fim is not None
            and start_value == defaults.evento_data_inicio
            and end_value == defaults.evento_data_fim
        ):
            _set_source('periodo', STEP2_SOURCE_EVENTO)
        else:
            _set_source('periodo', STEP2_SOURCE_MANUAL)
    elif period_source != STEP2_SOURCE_MANUAL:
        if not plano.evento_data_inicio and defaults.evento_data_inicio is not None:
            _set('evento_data_inicio', defaults.evento_data_inicio)
            _set('evento_data_fim', defaults.evento_data_fim)
            _set_source('periodo', STEP2_SOURCE_EVENTO)

    destinos_present = _present('destinos_json', 'destinos_payload', 'roteiro_json')
    destino_source = origin.get('destino')
    if destinos_present:
        destinos_value = list(incoming.get('destinos_json') or [])
        _set('destinos_json', destinos_value)
        if destinos_value and destinos_value == defaults.destinos_json:
            _set_source('destino', STEP2_SOURCE_EVENTO)
        else:
            _set_source('destino', STEP2_SOURCE_MANUAL)
    elif destino_source != STEP2_SOURCE_MANUAL:
        if not plano.destinos_json and defaults.destinos_json:
            _set('destinos_json', list(defaults.destinos_json))
            _set_source('destino', STEP2_SOURCE_EVENTO)

    calc_present = _present('data_saida_sede', 'hora_saida_sede', 'data_chegada_sede', 'hora_chegada_sede')
    calc_source = origin.get('calculadora')
    if calc_present:
        incoming_saida_data = incoming.get('data_saida_sede')
        incoming_saida_hora = incoming.get('hora_saida_sede')
        incoming_chegada_data = incoming.get('data_chegada_sede')
        incoming_chegada_hora = incoming.get('hora_chegada_sede')
        blank_payload = all(_is_empty(value) for value in (
            incoming_saida_data,
            incoming_saida_hora,
            incoming_chegada_data,
            incoming_chegada_hora,
        ))
        if blank_payload:
            _set('data_saida_sede', None)
            _set('hora_saida_sede', None)
            _set('data_chegada_sede', None)
            _set('hora_chegada_sede', None)
            _set_source('calculadora', STEP2_SOURCE_MANUAL)
        elif (
            route_saida_data is not None
            and route_saida_hora is not None
            and route_chegada_data is not None
            and route_chegada_hora is not None
            and incoming_saida_data == route_saida_data
            and incoming_saida_hora == route_saida_hora
            and incoming_chegada_data == route_chegada_data
            and incoming_chegada_hora == route_chegada_hora
        ):
            _set('data_saida_sede', route_saida_data)
            _set('hora_saida_sede', route_saida_hora)
            _set('data_chegada_sede', route_chegada_data)
            _set('hora_chegada_sede', route_chegada_hora)
            _set_source('calculadora', STEP2_SOURCE_ROTEIRO_EVENTO)
        else:
            _set('data_saida_sede', incoming_saida_data)
            _set('hora_saida_sede', incoming_saida_hora)
            _set('data_chegada_sede', incoming_chegada_data)
            _set('hora_chegada_sede', incoming_chegada_hora)
            _set_source('calculadora', STEP2_SOURCE_MANUAL)
    elif calc_source != STEP2_SOURCE_MANUAL:
        if route_saida_data and route_saida_hora and route_chegada_data and route_chegada_hora:
            _set('data_saida_sede', route_saida_data)
            _set('hora_saida_sede', route_saida_hora)
            _set('data_chegada_sede', route_chegada_data)
            _set('hora_chegada_sede', route_chegada_hora)
            _set_source('calculadora', STEP2_SOURCE_ROTEIRO_EVENTO)

    if route_saida_data and route_saida_hora and route_chegada_data and route_chegada_hora:
        warnings = [w for w in warnings if w]
    elif defaults.evento_id and not defaults.roteiro:
        warnings.append('Sem roteiro válido: a calculadora ficará em branco até haver um roteiro com valor salvo.')

    return {
        'resolved': resolved,
        'origin': origin,
        'warnings': tuple(dict.fromkeys(warnings)),
        'changed': changed,
    }
