# -*- coding: utf-8 -*-
"""Logica de roteiro step 3 portada do legacy `eventos/views.py`."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cidade, Estado, ConfiguracaoSistema

from roteiros.services.diarias import (
    PeriodMarker,
    calculate_periodized_diarias,
    formatar_valor_diarias,
    infer_tipo_destino_from_paradas,
    locations_equivalent,
)
from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho
from roteiros.services.valor_extenso import valor_por_extenso_ptbr

ROTEIRO_MODO_EVENTO = "EVENTO_EXISTENTE"
ROTEIRO_MODO_PROPRIO = "ROTEIRO_PROPRIO"


def _parse_destinos_post(request):
    """
    Extrai da request.POST lista de (estado_id, cidade_id).
    Retorna (lista de tuplas (estado_id, cidade_id), erro ou None).
    """
    prefix_estado = 'destino_estado_'
    prefix_cidade = 'destino_cidade_'
    indices = set()
    for key in request.POST:
        if key.startswith(prefix_estado):
            try:
                idx = int(key[len(prefix_estado):])
                indices.add(idx)
            except ValueError:
                pass
    destinos = []
    for idx in sorted(indices):
        estado_id = request.POST.get(f'{prefix_estado}{idx}')
        cidade_id = request.POST.get(f'{prefix_cidade}{idx}')
        if estado_id and cidade_id:
            try:
                destinos.append((int(estado_id), int(cidade_id)))
            except (TypeError, ValueError):
                pass
    return destinos


def _get_parana_estado():
    return Estado.objects.filter(sigla__iexact='PR').order_by('id').first()


def _normalize_step3_state_destinos_para_parana(state, parana_estado_id):
    if not state or not parana_estado_id:
        return state
    for destino in state.get('destinos_atuais') or []:
        if destino.get('cidade_id'):
            destino['estado_id'] = parana_estado_id
    for trecho in state.get('trechos') or []:
        if trecho.get('destino_cidade_id'):
            trecho['destino_estado_id'] = parana_estado_id
        if trecho.get('origem_cidade_id') and trecho.get('origem_nome') and trecho.get('ordem', 0) > 0:
            trecho['origem_estado_id'] = parana_estado_id
    return state


def _validar_destinos(destinos):
    """
    Valida lista de (estado_id, cidade_id). Retorna (True, None) ou (False, mensagem).
    """
    if not destinos:
        return False, "Selecione pelo menos um destino (estado e cidade)."
    for estado_id, cidade_id in destinos:
        try:
            cidade = Cidade.objects.get(pk=cidade_id)
            if cidade.estado_id != estado_id:
                return False, "A cidade deve pertencer ao estado selecionado."
        except Cidade.DoesNotExist:
            return False, "Cidade inválida."
        if not Estado.objects.filter(pk=estado_id).exists():
            return False, "Estado inválido."
    return True, None


def _estrutura_trechos(roteiro, destinos_list=None):
    """
    Monta a estrutura de trechos (ida + retorno) a partir da sede e dos destinos do roteiro.
    Se destinos_list for None, usa roteiro.destinos. Retorna lista de dicts para o template:
    ordem, tipo, origem_estado, origem_cidade, destino_estado, destino_cidade,
    saida_dt, chegada_dt (do DB se existir), origem_nome, destino_nome, id (pk do trecho se existir).
    """
    from datetime import datetime
    if not roteiro.origem_estado_id and not roteiro.origem_cidade_id:
        return []
    if destinos_list is None:
        destinos_qs = roteiro.destinos.select_related('estado', 'cidade').order_by('ordem')
        destinos_list = [(d.estado_id, d.cidade_id) for d in destinos_qs]
    if not destinos_list:
        return []
    trechos_db = {}
    if roteiro.pk:
        for t in roteiro.trechos.select_related('origem_estado', 'origem_cidade', 'destino_estado', 'destino_cidade').order_by('ordem'):
            trechos_db[t.ordem] = t
    out = []
    ordem = 0
    # Origem = sede
    o_estado, o_cidade = roteiro.origem_estado_id, roteiro.origem_cidade_id
    o_nome = (roteiro.origem_cidade.nome if roteiro.origem_cidade else (roteiro.origem_estado.sigla if roteiro.origem_estado else 'â€”'))
    for estado_id, cidade_id in destinos_list:
        try:
            d_cidade = Cidade.objects.filter(pk=cidade_id).select_related('estado').first()
            d_nome = d_cidade.nome if d_cidade else Estado.objects.filter(pk=estado_id).first().sigla if estado_id else 'â€”'
        except Exception:
            d_nome = 'â€”'
        t_db = trechos_db.get(ordem)
        t_adic = getattr(t_db, 'tempo_adicional_min', None) if t_db else 0
        if t_adic is None:
            t_adic = 0
        t_cru = getattr(t_db, 'tempo_cru_estimado_min', None) if t_db else None
        if t_cru is None and t_db and t_db.duracao_estimada_min is not None:
            t_cru = max((t_db.duracao_estimada_min or 0) - t_adic, 0)
        out.append({
            'ordem': ordem,
            'tipo': RoteiroTrecho.TIPO_IDA,
            'origem_estado_id': o_estado,
            'origem_cidade_id': o_cidade,
            'destino_estado_id': estado_id,
            'destino_cidade_id': cidade_id,
            'origem_nome': o_nome,
            'destino_nome': d_nome,
            'saida_dt': t_db.saida_dt if t_db else None,
            'chegada_dt': t_db.chegada_dt if t_db else None,
            'id': t_db.pk if t_db else None,
            'distancia_km': t_db.distancia_km if t_db else None,
            'duracao_estimada_min': t_db.duracao_estimada_min if t_db else None,
            'tempo_cru_estimado_min': t_cru,
            'tempo_adicional_min': t_adic,
            'rota_fonte': (getattr(t_db, 'rota_fonte', '') or '') if t_db else '',
        })
        o_estado, o_cidade = estado_id, cidade_id
        o_nome = d_nome
        ordem += 1
    # Retorno: Ãºltimo destino -> sede
    sede_nome = (roteiro.origem_cidade.nome if roteiro.origem_cidade else (roteiro.origem_estado.sigla if roteiro.origem_estado else 'â€”'))
    t_db = trechos_db.get(ordem)
    t_adic = getattr(t_db, 'tempo_adicional_min', None) if t_db else 0
    if t_adic is None:
        t_adic = 0
    t_cru = getattr(t_db, 'tempo_cru_estimado_min', None) if t_db else None
    if t_cru is None and t_db and t_db.duracao_estimada_min is not None:
        t_cru = max((t_db.duracao_estimada_min or 0) - t_adic, 0)
    out.append({
        'ordem': ordem,
        'tipo': RoteiroTrecho.TIPO_RETORNO,
        'origem_estado_id': o_estado,
        'origem_cidade_id': o_cidade,
        'destino_estado_id': roteiro.origem_estado_id,
        'destino_cidade_id': roteiro.origem_cidade_id,
        'origem_nome': o_nome,
        'destino_nome': sede_nome,
        'saida_dt': t_db.saida_dt if t_db else None,
        'chegada_dt': t_db.chegada_dt if t_db else None,
        'id': t_db.pk if t_db else None,
        'distancia_km': t_db.distancia_km if t_db else None,
        'duracao_estimada_min': t_db.duracao_estimada_min if t_db else None,
        'tempo_cru_estimado_min': t_cru,
        'tempo_adicional_min': t_adic,
        'rota_fonte': (getattr(t_db, 'rota_fonte', '') or '') if t_db else '',
    })
    return out
def _trechos_list_json_compat(trechos_list):
    """Serializa trechos para trechos_json (string) e para json_script no template."""
    rows = []
    for row in trechos_list or []:
        item = {}
        for k, v in row.items():
            if v is None:
                item[k] = None
            elif hasattr(v, 'isoformat'):
                item[k] = v.isoformat()
            elif isinstance(v, Decimal):
                item[k] = float(v)
            else:
                item[k] = v
        rows.append(item)
    return rows, json.dumps(rows)
def _atualizar_datas_roteiro_apos_salvar_trechos(roteiro):
    trechos_salvos = list(roteiro.trechos.order_by('ordem'))
    if not trechos_salvos:
        return
    update_fields = []
    primeira_saida = trechos_salvos[0].saida_dt
    if primeira_saida is not None:
        roteiro.saida_dt = primeira_saida
        update_fields.append('saida_dt')
    if trechos_salvos[-1].tipo == RoteiroTrecho.TIPO_RETORNO:
        ultima_saida_retorno = trechos_salvos[-1].saida_dt
        if ultima_saida_retorno is not None:
            roteiro.retorno_saida_dt = ultima_saida_retorno
            update_fields.append('retorno_saida_dt')
        if len(trechos_salvos) >= 2 and trechos_salvos[-2].chegada_dt is not None:
            roteiro.chegada_dt = trechos_salvos[-2].chegada_dt
            update_fields.append('chegada_dt')
        if trechos_salvos[-1].chegada_dt is not None:
            roteiro.retorno_chegada_dt = trechos_salvos[-1].chegada_dt
            update_fields.append('retorno_chegada_dt')
    else:
        if trechos_salvos[-1].chegada_dt is not None:
            roteiro.chegada_dt = trechos_salvos[-1].chegada_dt
            update_fields.append('chegada_dt')
    if update_fields:
        update_fields.append('status')
        roteiro.save(update_fields=update_fields)

def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_step3_date(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_step3_time(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:5], '%H:%M').time().replace(second=0, microsecond=0)
    except ValueError:
        return None


def _step3_date_input(value):
    if not value:
        return ''
    if isinstance(value, str):
        return value
    return value.strftime('%Y-%m-%d')


def _step3_time_input(value):
    if not value:
        return ''
    if isinstance(value, str):
        return value[:5]
    return value.strftime('%H:%M')


def _step3_local_label(cidade=None, estado=None):
    cidade_nome = ''
    estado_sigla = ''
    if cidade:
        cidade_nome = cidade.nome
        estado_sigla = getattr(getattr(cidade, 'estado', None), 'sigla', '') or estado_sigla
    if estado and not estado_sigla:
        estado_sigla = estado.sigla
    if cidade_nome and estado_sigla:
        return f'{cidade_nome}/{estado_sigla}'
    return cidade_nome or estado_sigla or ''


def _step3_get_local_parts(cidade=None, estado=None, nome=''):
    cidade_nome = ''
    estado_sigla = ''
    if cidade:
        cidade_nome = getattr(cidade, 'nome', '') or ''
        estado_sigla = getattr(getattr(cidade, 'estado', None), 'sigla', '') or ''
    if estado and not estado_sigla:
        estado_sigla = getattr(estado, 'sigla', '') or ''
    if nome and not cidade_nome:
        raw_nome = str(nome or '').strip()
        if '/' in raw_nome:
            cidade_nome, _, maybe_uf = raw_nome.partition('/')
            if not estado_sigla:
                estado_sigla = maybe_uf.strip().upper()
        else:
            cidade_nome = raw_nome
    return cidade_nome.strip(), estado_sigla.strip().upper()


def _step3_locations_equivalent(*, cidade_a=None, estado_a=None, nome_a='', cidade_b=None, estado_b=None, nome_b=''):
    cidade_a_nome, estado_a_sigla = _step3_get_local_parts(cidade=cidade_a, estado=estado_a, nome=nome_a)
    cidade_b_nome, estado_b_sigla = _step3_get_local_parts(cidade=cidade_b, estado=estado_b, nome=nome_b)
    return locations_equivalent(cidade_a_nome, estado_a_sigla, cidade_b_nome, estado_b_sigla)


def _build_step3_bate_volta_diario_state(data=None):
    payload = data or {}
    return {
        'ativo': bool(payload.get('ativo')),
        'data_inicio': payload.get('data_inicio') or '',
        'data_fim': payload.get('data_fim') or '',
        'ida_saida_hora': payload.get('ida_saida_hora') or '',
        'ida_tempo_min': payload.get('ida_tempo_min') or '',
        'volta_saida_hora': payload.get('volta_saida_hora') or '',
        'volta_tempo_min': payload.get('volta_tempo_min') or '',
    }


def _extract_step3_posted_trechos(request):
    pattern = re.compile(r'^trecho_(\d+)_(.+)$')
    indexed = {}
    for key in request.POST:
        match = pattern.match(key)
        if not match:
            continue
        idx = int(match.group(1))
        field_name = match.group(2)
        indexed.setdefault(idx, {})[field_name] = request.POST.get(key)
    return [indexed[idx] for idx in sorted(indexed)]


def _infer_step3_destinos_from_trechos(raw_trechos, sede_estado=None, sede_cidade=None):
    destinos = []
    seen = set()
    for trecho in raw_trechos or []:
        destino_estado_id = _parse_int(trecho.get('destino_estado_id'))
        destino_cidade_id = _parse_int(trecho.get('destino_cidade_id'))
        destino_nome = trecho.get('destino_nome') or ''
        destino_cidade = Cidade.objects.select_related('estado').filter(pk=destino_cidade_id).first() if destino_cidade_id else None
        destino_estado = Estado.objects.filter(pk=destino_estado_id or getattr(destino_cidade, 'estado_id', None)).first() if (destino_estado_id or destino_cidade) else None
        if _step3_locations_equivalent(
            cidade_a=destino_cidade,
            estado_a=destino_estado,
            nome_a=destino_nome,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        ):
            continue
        key = (destino_estado_id, destino_cidade_id, str(destino_nome or '').strip().upper())
        if key in seen:
            continue
        seen.add(key)
        destinos.append(
            {
                'estado_id': destino_estado_id,
                'cidade_id': destino_cidade_id,
                'estado': destino_estado,
                'cidade': destino_cidade,
            }
        )
    return destinos


def _step3_has_intermediate_return_to_sede(state):
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(state.get('sede_cidade_id'))).first()
    sede_estado = Estado.objects.filter(pk=_parse_int(state.get('sede_estado_id')) or getattr(sede_cidade, 'estado_id', None)).first()
    if not sede_cidade and not sede_estado:
        return False
    return any(
        _step3_locations_equivalent(
            cidade_a=Cidade.objects.select_related('estado').filter(pk=_parse_int(trecho.get('destino_cidade_id'))).first(),
            estado_a=Estado.objects.filter(pk=_parse_int(trecho.get('destino_estado_id'))).first(),
            nome_a=trecho.get('destino_nome') or '',
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        )
        for trecho in (state.get('trechos') or [])
    )


def _step3_format_date_time_br(data_value, hora_value):
    data_obj = data_value if hasattr(data_value, 'strftime') and not isinstance(data_value, str) else _parse_step3_date(data_value)
    hora_obj = hora_value if hasattr(hora_value, 'strftime') and not isinstance(hora_value, str) else _parse_step3_time(hora_value)
    partes = []
    if data_obj:
        partes.append(data_obj.strftime('%d/%m/%Y'))
    if hora_obj:
        partes.append(hora_obj.strftime('%H:%M'))
    return ' '.join(partes)


def _split_route_datetime(dt):
    if not dt:
        return '', ''
    if getattr(dt, 'tzinfo', None):
        dt = timezone.localtime(dt)
    return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')


def _destinos_para_template(destinos_list):
    if not destinos_list:
        return []
    estado_ids = {estado_id for estado_id, _ in destinos_list if estado_id}
    cidade_ids = {cidade_id for _, cidade_id in destinos_list if cidade_id}
    estados_map = {obj.pk: obj for obj in Estado.objects.filter(pk__in=estado_ids)}
    cidades_map = {
        obj.pk: obj
        for obj in Cidade.objects.select_related('estado').filter(pk__in=cidade_ids)
    }
    return [
        {
            'estado_id': estado_id,
            'cidade_id': cidade_id,
            'estado': estados_map.get(estado_id),
            'cidade': cidades_map.get(cidade_id),
        }
        for estado_id, cidade_id in destinos_list
    ]


def _build_step3_state_from_estrutura(estrutura, destinos_atuais, sede_estado_id, sede_cidade_id, seed_source_label=''):
    trechos = []
    retorno = {
        'origem_nome': '',
        'destino_nome': '',
        'saida_cidade': '',
        'chegada_cidade': '',
        'saida_data': '',
        'saida_hora': '',
        'chegada_data': '',
        'chegada_hora': '',
        'distancia_km': '',
        'duracao_estimada_min': '',
        'tempo_cru_estimado_min': '',
        'tempo_adicional_min': 0,
        'rota_fonte': '',
    }
    for item in estrutura or []:
        saida_data, saida_hora = _split_route_datetime(item.get('saida_dt'))
        chegada_data, chegada_hora = _split_route_datetime(item.get('chegada_dt'))
        tempo_adicional = item.get('tempo_adicional_min') or 0
        mapped = {
            'ordem': item.get('ordem', 0),
            'origem_nome': item.get('origem_nome') or '',
            'destino_nome': item.get('destino_nome') or '',
            'origem_estado_id': item.get('origem_estado_id'),
            'origem_cidade_id': item.get('origem_cidade_id'),
            'destino_estado_id': item.get('destino_estado_id'),
            'destino_cidade_id': item.get('destino_cidade_id'),
            'saida_data': saida_data,
            'saida_hora': saida_hora,
            'chegada_data': chegada_data,
            'chegada_hora': chegada_hora,
            'distancia_km': _step3_decimal_input(item.get('distancia_km')),
            'duracao_estimada_min': item.get('duracao_estimada_min'),
            'tempo_cru_estimado_min': _step3_resolve_travel_minutes(
                item.get('tempo_cru_estimado_min'),
                item.get('duracao_estimada_min'),
                tempo_adicional,
            ),
            'tempo_adicional_min': tempo_adicional,
            'rota_fonte': item.get('rota_fonte') or '',
        }
        if item.get('tipo') == RoteiroTrecho.TIPO_RETORNO:
            retorno.update(
                {
                    'origem_nome': mapped['origem_nome'],
                    'destino_nome': mapped['destino_nome'],
                    'saida_cidade': mapped['origem_nome'],
                    'chegada_cidade': mapped['destino_nome'],
                    'saida_data': mapped['saida_data'],
                    'saida_hora': mapped['saida_hora'],
                    'chegada_data': mapped['chegada_data'],
                    'chegada_hora': mapped['chegada_hora'],
                    'distancia_km': mapped['distancia_km'],
                    'duracao_estimada_min': mapped['duracao_estimada_min'],
                    'tempo_cru_estimado_min': mapped['tempo_cru_estimado_min'],
                    'tempo_adicional_min': mapped['tempo_adicional_min'],
                    'rota_fonte': mapped['rota_fonte'],
                }
            )
            continue
        trechos.append(mapped)
    return {
        'roteiro_modo': ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': None,
        'roteiro_evento_label': '',
        'sede_estado_id': sede_estado_id,
        'sede_cidade_id': sede_cidade_id,
        'destinos_atuais': destinos_atuais,
        'trechos': trechos,
        'retorno': retorno,
        'bate_volta_diario': _build_step3_bate_volta_diario_state(),
        'seed_source_label': seed_source_label,
    }


def _parse_step3_decimal(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        if ',' in raw and '.' in raw:
            if raw.rfind(',') > raw.rfind('.'):
                raw = raw.replace('.', '').replace(',', '.')
            else:
                raw = raw.replace(',', '')
        else:
            raw = raw.replace(',', '.')
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _step3_decimal_input(value):
    decimal_value = _parse_step3_decimal(value)
    if decimal_value is None:
        return ''
    return f'{decimal_value.quantize(Decimal("0.01")):.2f}'


def _step3_resolve_travel_minutes(raw_minutes, total_minutes, additional_minutes=0):
    value = _parse_int(raw_minutes)
    if value is not None:
        return value
    total = _parse_int(total_minutes)
    additional = _parse_int(additional_minutes) or 0
    if total is None:
        return ''
    return max(total - additional, 0)


def _build_step3_roteiro_label(roteiro):
    origem = _step3_local_label(roteiro.origem_cidade, roteiro.origem_estado) or 'Sede nÃ£o informada'
    destinos = [
        _step3_local_label(destino.cidade, destino.estado)
        for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'id')
    ]
    resumo = ' -> '.join(destinos[:3]) if destinos else 'Sem destinos'
    if len(destinos) > 3:
        resumo += ' -> ...'
    return f'Roteiro #{roteiro.pk} - {origem} -> {resumo}'


def _serialize_step3_state(state):
    retorno = state.get('retorno') or {}
    return {
        'roteiro_modo': state.get('roteiro_modo') or ROTEIRO_MODO_PROPRIO,
        'roteiro_id': state.get('roteiro_evento_id'),
        'roteiro_evento_id': state.get('roteiro_evento_id'),
        'roteiro_evento_label': state.get('roteiro_evento_label') or '',
        'sede_estado_id': state.get('sede_estado_id'),
        'sede_cidade_id': state.get('sede_cidade_id'),
        'destinos_atuais': [
            {
                'estado_id': item.get('estado_id'),
                'cidade_id': item.get('cidade_id'),
            }
            for item in (state.get('destinos_atuais') or [])
        ],
        'trechos': [
            {
                'ordem': trecho.get('ordem', 0),
                'origem_nome': trecho.get('origem_nome') or '',
                'destino_nome': trecho.get('destino_nome') or '',
                'origem_estado_id': trecho.get('origem_estado_id'),
                'origem_cidade_id': trecho.get('origem_cidade_id'),
                'destino_estado_id': trecho.get('destino_estado_id'),
                'destino_cidade_id': trecho.get('destino_cidade_id'),
                'saida_data': trecho.get('saida_data') or '',
                'saida_hora': trecho.get('saida_hora') or '',
                'chegada_data': trecho.get('chegada_data') or '',
                'chegada_hora': trecho.get('chegada_hora') or '',
                'distancia_km': _step3_decimal_input(trecho.get('distancia_km')),
                'duracao_estimada_min': trecho.get('duracao_estimada_min'),
                'tempo_cru_estimado_min': trecho.get('tempo_cru_estimado_min'),
                'tempo_adicional_min': trecho.get('tempo_adicional_min') or 0,
                'rota_fonte': trecho.get('rota_fonte') or '',
            }
            for trecho in (state.get('trechos') or [])
        ],
        'retorno': {
            'origem_nome': retorno.get('origem_nome') or '',
            'destino_nome': retorno.get('destino_nome') or '',
            'saida_cidade': retorno.get('saida_cidade') or '',
            'chegada_cidade': retorno.get('chegada_cidade') or '',
            'saida_data': retorno.get('saida_data') or '',
            'saida_hora': retorno.get('saida_hora') or '',
            'chegada_data': retorno.get('chegada_data') or '',
            'chegada_hora': retorno.get('chegada_hora') or '',
            'distancia_km': _step3_decimal_input(retorno.get('distancia_km')),
            'duracao_estimada_min': retorno.get('duracao_estimada_min') or '',
            'tempo_cru_estimado_min': retorno.get('tempo_cru_estimado_min') or '',
            'tempo_adicional_min': retorno.get('tempo_adicional_min') or 0,
            'rota_fonte': retorno.get('rota_fonte') or '',
        },
        'bate_volta_diario': _build_step3_bate_volta_diario_state(state.get('bate_volta_diario')),
        'seed_source_label': state.get('seed_source_label') or '',
    }


def _build_step3_empty_state(oficio=None, roteiro_modo=None, seed_source_label='', roteiro_evento_id=None, roteiro_evento_label=''):
    sede_cidade = None
    sede_estado = None
    if oficio is not None and getattr(oficio, "evento_id", None) and getattr(oficio, "evento", None):
        sede_cidade = oficio.evento.cidade_base or oficio.evento.cidade_principal
        sede_estado = getattr(sede_cidade, 'estado', None) or oficio.evento.estado_principal
    if not sede_cidade and not sede_estado:
        config = ConfiguracaoSistema.get_singleton()
        sede_cidade = getattr(config, 'cidade_sede_padrao', None) if config else None
        sede_estado = getattr(sede_cidade, 'estado', None)
    return {
        'roteiro_modo': roteiro_modo or ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': roteiro_evento_id,
        'roteiro_evento_label': roteiro_evento_label or '',
        'sede_estado_id': sede_estado.pk if sede_estado else None,
        'sede_cidade_id': sede_cidade.pk if sede_cidade else None,
        'destinos_atuais': [{'estado_id': None, 'cidade_id': None, 'estado': None, 'cidade': None}],
        'trechos': [],
        'retorno': {
            'origem_nome': '',
            'destino_nome': _step3_local_label(sede_cidade, sede_estado),
            'saida_cidade': '',
            'chegada_cidade': _step3_local_label(sede_cidade, sede_estado),
            'saida_data': '',
            'saida_hora': '',
            'chegada_data': '',
            'chegada_hora': '',
            'distancia_km': '',
            'duracao_estimada_min': '',
            'tempo_cru_estimado_min': '',
            'tempo_adicional_min': 0,
            'rota_fonte': '',
        },
        'bate_volta_diario': _build_step3_bate_volta_diario_state(),
        'seed_source_label': seed_source_label or '',
    }


def _get_step3_saved_routes(oficio, include_ids=None):
    include_ids = {int(value) for value in (include_ids or []) if value}
    queryset = (
        Roteiro.objects.filter(Q(status=Roteiro.STATUS_FINALIZADO) | Q(pk__in=include_ids))
        .select_related('origem_estado', 'origem_cidade', 'origem_cidade__estado')
        .prefetch_related(
            'destinos',
            'destinos__estado',
            'destinos__cidade',
            'trechos',
            'trechos__origem_estado',
            'trechos__origem_cidade',
            'trechos__origem_cidade__estado',
            'trechos__destino_estado',
            'trechos__destino_cidade',
            'trechos__destino_cidade__estado',
        )
        .distinct()
    )
    routes = list(queryset)
    oficio_event_ids = set()
    eventos_rel = getattr(oficio, 'eventos', None)
    if eventos_rel is not None and hasattr(eventos_rel, 'values_list'):
        oficio_event_ids.update(eventos_rel.values_list('pk', flat=True))
    evento_id = getattr(oficio, 'evento_id', None)
    if evento_id:
        oficio_event_ids.add(int(evento_id))
    evento_obj = getattr(oficio, 'evento', None)
    if evento_obj is not None:
        oficio_event_ids.add(int(evento_obj.pk))
    return sorted(
        routes,
        key=lambda roteiro: (
            0 if roteiro.pk == oficio.roteiro_evento_id else 1,
            0 if roteiro.evento_id and roteiro.evento_id in oficio_event_ids else 1,
            0 if roteiro.tipo == Roteiro.TIPO_AVULSO else 1,
            -(roteiro.created_at.timestamp() if roteiro.created_at else 0),
        ),
    )


def _build_step3_state_from_roteiro_evento(roteiro, seed_source_label='PrÃ©-preenchido com o roteiro salvo.'):
    state = _build_step3_state_from_saved_trechos(
        roteiro,
        seed_source_label=seed_source_label,
    )
    if not state.get('trechos'):
        state = _build_step3_state_from_estrutura(
            _estrutura_trechos(roteiro),
            _destinos_roteiro_para_template(roteiro),
            roteiro.origem_estado_id,
            roteiro.origem_cidade_id,
            seed_source_label,
        )
    state['roteiro_modo'] = ROTEIRO_MODO_EVENTO
    state['roteiro_evento_id'] = roteiro.pk
    state['roteiro_evento_label'] = _build_step3_roteiro_label(roteiro)
    if not state['retorno']['saida_data']:
        state['retorno']['saida_data'], state['retorno']['saida_hora'] = _split_route_datetime(roteiro.retorno_saida_dt)
    if not state['retorno']['chegada_data']:
        state['retorno']['chegada_data'], state['retorno']['chegada_hora'] = _split_route_datetime(roteiro.retorno_chegada_dt)
    state['bate_volta_diario'] = _infer_step3_bate_volta_diario_from_state(state)
    return state


def _build_step3_state_from_saved_trechos(roteiro, seed_source_label=''):
    state = _build_step3_state_from_estrutura(
        [],
        [],
        roteiro.origem_estado_id,
        roteiro.origem_cidade_id,
        seed_source_label,
    )
    state['sede_estado_id'] = roteiro.origem_estado_id
    state['sede_cidade_id'] = roteiro.origem_cidade_id
    state['destinos_atuais'] = _destinos_roteiro_para_template(roteiro)

    trechos_salvos = list(
        roteiro.trechos.select_related(
            'origem_estado',
            'origem_cidade',
            'origem_cidade__estado',
            'destino_estado',
            'destino_cidade',
            'destino_cidade__estado',
        ).order_by('ordem', 'id')
    )
    if not trechos_salvos:
        return state

    ordem = 0
    for trecho in trechos_salvos:
        origem_nome, _ = _step3_get_local_parts(
            cidade=trecho.origem_cidade,
            estado=trecho.origem_estado,
        )
        destino_nome, _ = _step3_get_local_parts(
            cidade=trecho.destino_cidade,
            estado=trecho.destino_estado,
        )
        saida_data, saida_hora = _split_route_datetime(trecho.saida_dt)
        chegada_data, chegada_hora = _split_route_datetime(trecho.chegada_dt)
        tempo_adicional = trecho.tempo_adicional_min if trecho.tempo_adicional_min is not None else 0
        tempo_cru = trecho.tempo_cru_estimado_min
        if tempo_cru is None and trecho.duracao_estimada_min is not None:
            tempo_cru = max((trecho.duracao_estimada_min or 0) - tempo_adicional, 0)
        trecho_payload = {
            'ordem': ordem,
            'origem_estado_id': trecho.origem_estado_id,
            'origem_cidade_id': trecho.origem_cidade_id,
            'destino_estado_id': trecho.destino_estado_id,
            'destino_cidade_id': trecho.destino_cidade_id,
            'origem_nome': origem_nome,
            'destino_nome': destino_nome,
            'saida_data': saida_data,
            'saida_hora': saida_hora,
            'chegada_data': chegada_data,
            'chegada_hora': chegada_hora,
            'distancia_km': _step3_decimal_input(trecho.distancia_km),
            'duracao_estimada_min': trecho.duracao_estimada_min or '',
            'tempo_cru_estimado_min': tempo_cru if tempo_cru is not None else '',
            'tempo_adicional_min': tempo_adicional,
            'rota_fonte': trecho.rota_fonte or '',
        }
        if trecho.tipo == RoteiroTrecho.TIPO_RETORNO:
            state['retorno'] = {
                'saida_cidade': origem_nome,
                'chegada_cidade': destino_nome,
                'saida_data': saida_data,
                'saida_hora': saida_hora,
                'chegada_data': chegada_data,
                'chegada_hora': chegada_hora,
                'distancia_km': _step3_decimal_input(trecho.distancia_km),
                'duracao_estimada_min': trecho.duracao_estimada_min or '',
                'tempo_cru_estimado_min': tempo_cru if tempo_cru is not None else '',
                'tempo_adicional_min': tempo_adicional,
                'rota_fonte': trecho.rota_fonte or '',
            }
        else:
            state['trechos'].append(trecho_payload)
            ordem += 1

    return state


def _infer_step3_bate_volta_diario_from_state(state):
    fallback = _build_step3_bate_volta_diario_state()
    destinos = [
        item
        for item in (state.get('destinos_atuais') or [])
        if _parse_int(item.get('estado_id')) and _parse_int(item.get('cidade_id'))
    ]
    trechos = state.get('trechos') or []
    if len(destinos) != 1 or len(trechos) < 2 or (len(trechos) % 2) != 0:
        return fallback

    sede_estado_id = _parse_int(state.get('sede_estado_id'))
    sede_cidade_id = _parse_int(state.get('sede_cidade_id'))
    destino_estado_id = _parse_int(destinos[0].get('estado_id'))
    destino_cidade_id = _parse_int(destinos[0].get('cidade_id'))
    if not all([sede_estado_id, sede_cidade_id, destino_estado_id, destino_cidade_id]):
        return fallback

    ida_hora_ref = None
    volta_hora_ref = None
    ida_min_ref = None
    volta_min_ref = None
    dias = []

    for idx in range(0, len(trechos), 2):
        ida = trechos[idx] or {}
        volta = trechos[idx + 1] or {}

        if _parse_int(ida.get('origem_estado_id')) != sede_estado_id:
            return fallback
        if _parse_int(ida.get('origem_cidade_id')) != sede_cidade_id:
            return fallback
        if _parse_int(ida.get('destino_estado_id')) != destino_estado_id:
            return fallback
        if _parse_int(ida.get('destino_cidade_id')) != destino_cidade_id:
            return fallback

        if _parse_int(volta.get('origem_estado_id')) != destino_estado_id:
            return fallback
        if _parse_int(volta.get('origem_cidade_id')) != destino_cidade_id:
            return fallback
        if _parse_int(volta.get('destino_estado_id')) != sede_estado_id:
            return fallback
        if _parse_int(volta.get('destino_cidade_id')) != sede_cidade_id:
            return fallback

        ida_data = ida.get('saida_data') or ''
        volta_data = volta.get('saida_data') or ''
        ida_hora = ida.get('saida_hora') or ''
        volta_hora = volta.get('saida_hora') or ''
        if not ida_data or not volta_data or ida_data != volta_data:
            return fallback
        if not ida_hora or not volta_hora:
            return fallback

        ida_min = _parse_int(
            _step3_resolve_travel_minutes(
                ida.get('tempo_cru_estimado_min'),
                ida.get('duracao_estimada_min'),
                ida.get('tempo_adicional_min') or 0,
            )
        )
        volta_min = _parse_int(
            _step3_resolve_travel_minutes(
                volta.get('tempo_cru_estimado_min'),
                volta.get('duracao_estimada_min'),
                volta.get('tempo_adicional_min') or 0,
            )
        )
        if not ida_min or not volta_min:
            return fallback

        ida_hora_ref = ida_hora if ida_hora_ref is None else ida_hora_ref
        volta_hora_ref = volta_hora if volta_hora_ref is None else volta_hora_ref
        ida_min_ref = ida_min if ida_min_ref is None else ida_min_ref
        volta_min_ref = volta_min if volta_min_ref is None else volta_min_ref
        if ida_hora != ida_hora_ref or volta_hora != volta_hora_ref:
            return fallback
        if ida_min != ida_min_ref or volta_min != volta_min_ref:
            return fallback

        dia = _parse_step3_date(ida_data)
        if not dia:
            return fallback
        dias.append(dia)

    dias.sort()
    for current_idx in range(1, len(dias)):
        if (dias[current_idx] - dias[current_idx - 1]).days != 1:
            return fallback

    return _build_step3_bate_volta_diario_state(
        {
            'ativo': True,
            'data_inicio': dias[0].strftime('%Y-%m-%d'),
            'data_fim': dias[-1].strftime('%Y-%m-%d'),
            'ida_saida_hora': ida_hora_ref,
            'ida_tempo_min': ida_min_ref,
            'volta_saida_hora': volta_hora_ref,
            'volta_tempo_min': volta_min_ref,
        }
    )


def _build_step3_route_options(oficio):
    options = []
    state_map = {}
    include_ids = [oficio.roteiro_evento_id] if oficio.roteiro_evento_id else []
    for roteiro in _get_step3_saved_routes(oficio, include_ids=include_ids):
        destinos = [
            _step3_local_label(destino.cidade, destino.estado)
            for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'id')
        ]
        resumo = ' -> '.join(destinos[:3]) if destinos else 'Sem destinos'
        if len(destinos) > 3:
            resumo += ' -> ...'
        state = _build_step3_state_from_roteiro_evento(roteiro)
        state_map[roteiro.pk] = state
        tipo_label = 'Avulso' if roteiro.tipo == Roteiro.TIPO_AVULSO else 'Evento'
        evento = getattr(roteiro, 'evento', None)
        if getattr(roteiro, 'evento_id', None) and evento is not None:
            tipo_label = f'{tipo_label}: {getattr(evento, "titulo", "") or ""}'.strip()
        options.append(
            {
                'id': roteiro.pk,
                'label': state['roteiro_evento_label'],
                'resumo': resumo,
                'status': roteiro.status,
                'tipo_label': tipo_label,
                'state': _serialize_step3_state(state),
            }
        )
    return options, state_map


def _build_step3_state_from_post(request, oficio=None, route_state_map=None):
    route_state_map = route_state_map or {}
    roteiro_modo = (request.POST.get('roteiro_modo') or '').strip()
    if roteiro_modo not in {ROTEIRO_MODO_EVENTO, ROTEIRO_MODO_PROPRIO}:
        roteiro_modo = ROTEIRO_MODO_EVENTO if route_state_map else ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = _parse_int(request.POST.get('roteiro_id') or request.POST.get('roteiro_evento_id'))
    sede_estado_id = _parse_int(request.POST.get('sede_estado'))
    sede_cidade_id = _parse_int(request.POST.get('sede_cidade'))
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=sede_cidade_id).first() if sede_cidade_id else None
    sede_estado = Estado.objects.filter(pk=sede_estado_id or getattr(sede_cidade, 'estado_id', None)).first() if (sede_estado_id or sede_cidade) else None
    destinos_list = _parse_destinos_post(request)
    posted_trechos = _extract_step3_posted_trechos(request)
    has_structure = bool(
        sede_estado_id
        or sede_cidade_id
        or destinos_list
        or posted_trechos
    )

    if roteiro_modo == ROTEIRO_MODO_EVENTO and roteiro_evento_id and roteiro_evento_id in route_state_map and not has_structure:
        state = deepcopy(route_state_map[roteiro_evento_id])
    elif posted_trechos:
        state = _build_step3_empty_state(
            oficio,
            roteiro_modo=roteiro_modo,
            roteiro_evento_id=roteiro_evento_id,
            roteiro_evento_label=route_state_map.get(roteiro_evento_id, {}).get('roteiro_evento_label', ''),
        )
        state['sede_estado_id'] = sede_estado_id
        state['sede_cidade_id'] = sede_cidade_id
        state['trechos'] = []
        for idx, trecho in enumerate(posted_trechos):
            state['trechos'].append(
                {
                    'ordem': idx,
                    'origem_nome': (trecho.get('origem_nome') or '').strip(),
                    'destino_nome': (trecho.get('destino_nome') or '').strip(),
                    'origem_estado_id': _parse_int(trecho.get('origem_estado_id')),
                    'origem_cidade_id': _parse_int(trecho.get('origem_cidade_id')),
                    'destino_estado_id': _parse_int(trecho.get('destino_estado_id')),
                    'destino_cidade_id': _parse_int(trecho.get('destino_cidade_id')),
                    'saida_data': (trecho.get('saida_data') or '').strip(),
                    'saida_hora': (trecho.get('saida_hora') or '').strip(),
                    'chegada_data': (trecho.get('chegada_data') or '').strip(),
                    'chegada_hora': (trecho.get('chegada_hora') or '').strip(),
                    'distancia_km': (trecho.get('distancia_km') or '').strip(),
                    'tempo_cru_estimado_min': (trecho.get('tempo_cru_estimado_min') or '').strip(),
                    'tempo_adicional_min': (trecho.get('tempo_adicional_min') or '').strip() or 0,
                    'duracao_estimada_min': (trecho.get('duracao_estimada_min') or '').strip(),
                    'rota_fonte': (trecho.get('rota_fonte') or '').strip(),
                }
            )
        state['destinos_atuais'] = _infer_step3_destinos_from_trechos(state['trechos'], sede_estado=sede_estado, sede_cidade=sede_cidade)
        if not state['destinos_atuais'] and destinos_list:
            state['destinos_atuais'] = _destinos_para_template(destinos_list)
    else:
        destinos_atuais = _destinos_para_template(destinos_list)
        estrutura = []
        if sede_estado_id or sede_cidade_id:
            roteiro_virtual = _roteiro_virtual_para_trechos(
                {'origem_estado': sede_estado_id, 'origem_cidade': sede_cidade_id}
            )
            estrutura = _estrutura_trechos(roteiro_virtual, destinos_list)
        state = _build_step3_state_from_estrutura(
            estrutura,
            destinos_atuais or [{'estado_id': None, 'cidade_id': None, 'estado': None, 'cidade': None}],
            sede_estado_id,
            sede_cidade_id,
            '',
        )

    def _posted_or_default(name, default=''):
        if name in request.POST:
            return (request.POST.get(name) or '').strip()
        return default

    for idx, trecho in enumerate(state.get('trechos', [])):
        trecho['saida_data'] = _posted_or_default(f'trecho_{idx}_saida_data', trecho.get('saida_data', ''))
        trecho['saida_hora'] = _posted_or_default(f'trecho_{idx}_saida_hora', trecho.get('saida_hora', ''))
        trecho['chegada_data'] = _posted_or_default(f'trecho_{idx}_chegada_data', trecho.get('chegada_data', ''))
        trecho['chegada_hora'] = _posted_or_default(f'trecho_{idx}_chegada_hora', trecho.get('chegada_hora', ''))
        trecho['distancia_km'] = _posted_or_default(f'trecho_{idx}_distancia_km', _step3_decimal_input(trecho.get('distancia_km')))
        trecho['tempo_cru_estimado_min'] = _posted_or_default(f'trecho_{idx}_tempo_cru_estimado_min', trecho.get('tempo_cru_estimado_min') or '')
        trecho['tempo_adicional_min'] = _posted_or_default(f'trecho_{idx}_tempo_adicional_min', trecho.get('tempo_adicional_min') or 0)
        trecho['duracao_estimada_min'] = _posted_or_default(f'trecho_{idx}_duracao_estimada_min', trecho.get('duracao_estimada_min') or '')
        trecho['rota_fonte'] = _posted_or_default(f'trecho_{idx}_rota_fonte', trecho.get('rota_fonte') or '')

    state['retorno'].update(
        {
            'saida_data': _posted_or_default('retorno_saida_data', state['retorno'].get('saida_data', '')),
            'saida_hora': _posted_or_default('retorno_saida_hora', state['retorno'].get('saida_hora', '')),
            'chegada_data': _posted_or_default('retorno_chegada_data', state['retorno'].get('chegada_data', '')),
            'chegada_hora': _posted_or_default('retorno_chegada_hora', state['retorno'].get('chegada_hora', '')),
            'distancia_km': _posted_or_default('retorno_distancia_km', state['retorno'].get('distancia_km', '')),
            'tempo_cru_estimado_min': _posted_or_default('retorno_tempo_cru_estimado_min', state['retorno'].get('tempo_cru_estimado_min', '')),
            'tempo_adicional_min': _posted_or_default('retorno_tempo_adicional_min', state['retorno'].get('tempo_adicional_min', 0)),
            'duracao_estimada_min': _posted_or_default('retorno_duracao_estimada_min', state['retorno'].get('duracao_estimada_min', '')),
            'rota_fonte': _posted_or_default('retorno_rota_fonte', state['retorno'].get('rota_fonte', '')),
        }
    )
    tempo_cru_retorno = _parse_int(state['retorno'].get('tempo_cru_estimado_min'))
    tempo_adicional_retorno = _parse_int(state['retorno'].get('tempo_adicional_min')) or 0
    if tempo_adicional_retorno < 0:
        tempo_adicional_retorno = 0
    duracao_retorno = _parse_int(state['retorno'].get('duracao_estimada_min'))
    if duracao_retorno is None and ((tempo_cru_retorno or 0) + tempo_adicional_retorno) > 0:
        duracao_retorno = (tempo_cru_retorno or 0) + tempo_adicional_retorno
    state['retorno']['tempo_adicional_min'] = tempo_adicional_retorno
    state['retorno']['duracao_estimada_min'] = duracao_retorno if duracao_retorno is not None else ''
    state['bate_volta_diario'] = _build_step3_bate_volta_diario_state(
        {
            'ativo': request.POST.get('bate_volta_diario_ativo') in {'1', 'true', 'True', 'on'},
            'data_inicio': (request.POST.get('bate_volta_data_inicio') or '').strip(),
            'data_fim': (request.POST.get('bate_volta_data_fim') or '').strip(),
            'ida_saida_hora': (request.POST.get('bate_volta_ida_saida_hora') or '').strip(),
            'ida_tempo_min': (request.POST.get('bate_volta_ida_tempo_min') or '').strip(),
            'volta_saida_hora': (request.POST.get('bate_volta_volta_saida_hora') or '').strip(),
            'volta_tempo_min': (request.POST.get('bate_volta_volta_tempo_min') or '').strip(),
        }
    )
    state['seed_source_label'] = ''
    state['roteiro_modo'] = roteiro_modo
    if roteiro_modo == ROTEIRO_MODO_EVENTO and roteiro_evento_id and roteiro_evento_id in route_state_map:
        state['roteiro_evento_id'] = roteiro_evento_id
        state['roteiro_evento_label'] = route_state_map[roteiro_evento_id].get('roteiro_evento_label') or ''
    else:
        state['roteiro_evento_id'] = None
        state['roteiro_evento_label'] = ''
    return state


def _validate_step3_state(state, oficio=None):
    errors = []
    roteiro_modo = state.get('roteiro_modo') or ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = state.get('roteiro_evento_id')
    roteiro_evento = None
    if roteiro_modo == ROTEIRO_MODO_EVENTO:
        if not roteiro_evento_id:
            errors.append('Selecione um roteiro salvo para usar neste ofÃ­cio.')
        else:
            roteiro_evento = Roteiro.objects.filter(pk=roteiro_evento_id).first()
            if not roteiro_evento:
                errors.append('O roteiro salvo selecionado nÃ£o estÃ¡ mais disponÃ­vel.')

    sede_estado_id = state.get('sede_estado_id')
    sede_cidade_id = state.get('sede_cidade_id')
    sede_estado = Estado.objects.filter(pk=sede_estado_id).first() if sede_estado_id else None
    sede_cidade = (
        Cidade.objects.select_related('estado').filter(pk=sede_cidade_id).first()
        if sede_cidade_id
        else None
    )
    if not sede_estado_id:
        errors.append('Informe o estado da sede.')
    if not sede_cidade_id:
        errors.append('Informe a cidade da sede.')
    if sede_estado and sede_cidade and sede_cidade.estado_id != sede_estado.id:
        errors.append('A cidade da sede deve pertencer ao estado selecionado.')

    destinos_list = [
        (item.get('estado_id'), item.get('cidade_id'))
        for item in state.get('destinos_atuais', [])
        if item.get('estado_id') and item.get('cidade_id')
    ]
    ok_destinos, msg_destinos = _validar_destinos(destinos_list)
    if not ok_destinos:
        errors.append(msg_destinos)
    bate_volta_diario = _build_step3_bate_volta_diario_state(state.get('bate_volta_diario'))
    if bate_volta_diario['ativo'] and len(destinos_list) != 1:
        errors.append('No modo bate-volta diÃ¡rio, informe exatamente um destino operacional.')

    cleaned_trechos = []
    raw_trechos = state.get('trechos', [])
    if not raw_trechos:
        errors.append('Adicione ao menos um trecho antes de salvar.')
    for idx, trecho in enumerate(raw_trechos, start=1):
        if not trecho.get('origem_estado_id') or not trecho.get('origem_cidade_id'):
            errors.append(f'Trecho {idx}: informe uma origem vÃ¡lida.')
        if not trecho.get('destino_estado_id') or not trecho.get('destino_cidade_id'):
            errors.append(f'Trecho {idx}: informe um destino vÃ¡lido.')
        saida_data = _parse_step3_date(trecho.get('saida_data'))
        saida_hora = _parse_step3_time(trecho.get('saida_hora'))
        chegada_data = _parse_step3_date(trecho.get('chegada_data'))
        chegada_hora = _parse_step3_time(trecho.get('chegada_hora'))
        if not saida_data or not saida_hora:
            errors.append(f'Trecho {idx}: informe a saÃ­da (data e hora).')
        if not chegada_data or not chegada_hora:
            errors.append(f'Trecho {idx}: informe a chegada (data e hora).')
        if saida_data and saida_hora and chegada_data and chegada_hora:
            if datetime.combine(chegada_data, chegada_hora) < datetime.combine(saida_data, saida_hora):
                errors.append(f'Trecho {idx}: a chegada deve ocorrer no mesmo momento ou apÃ³s a saÃ­da.')

        tempo_cru = trecho.get('tempo_cru_estimado_min')
        try:
            tempo_cru = int(tempo_cru) if str(tempo_cru).strip() != '' else None
        except (TypeError, ValueError):
            tempo_cru = None
        tempo_adicional = trecho.get('tempo_adicional_min')
        try:
            tempo_adicional = max(0, int(tempo_adicional))
        except (TypeError, ValueError):
            tempo_adicional = 0
        duracao_estimada = trecho.get('duracao_estimada_min')
        try:
            duracao_estimada = int(duracao_estimada) if str(duracao_estimada).strip() != '' else None
        except (TypeError, ValueError):
            duracao_estimada = None
        if duracao_estimada is None and ((tempo_cru or 0) + tempo_adicional) > 0:
            duracao_estimada = (tempo_cru or 0) + tempo_adicional

        cleaned_trechos.append(
            {
                'ordem': idx - 1,
                'origem_estado_id': trecho.get('origem_estado_id'),
                'origem_cidade_id': trecho.get('origem_cidade_id'),
                'destino_estado_id': trecho.get('destino_estado_id'),
                'destino_cidade_id': trecho.get('destino_cidade_id'),
                'saida_data': saida_data,
                'saida_hora': saida_hora,
                'chegada_data': chegada_data,
                'chegada_hora': chegada_hora,
                'distancia_km': _parse_step3_decimal(trecho.get('distancia_km')),
                'tempo_cru_estimado_min': tempo_cru,
                'tempo_adicional_min': tempo_adicional,
                'duracao_estimada_min': duracao_estimada,
                'rota_fonte': (trecho.get('rota_fonte') or '').strip(),
            }
        )

    retorno = state.get('retorno', {})
    retorno_saida_data = _parse_step3_date(retorno.get('saida_data'))
    retorno_saida_hora = _parse_step3_time(retorno.get('saida_hora'))
    retorno_chegada_data = _parse_step3_date(retorno.get('chegada_data'))
    retorno_chegada_hora = _parse_step3_time(retorno.get('chegada_hora'))
    if not retorno_saida_data or not retorno_saida_hora:
        errors.append('Informe a saÃ­da do retorno (data e hora).')
    if not retorno_chegada_data or not retorno_chegada_hora:
        errors.append('Informe a chegada do retorno (data e hora).')
    if retorno_saida_data and retorno_saida_hora and retorno_chegada_data and retorno_chegada_hora:
        if datetime.combine(retorno_chegada_data, retorno_chegada_hora) < datetime.combine(retorno_saida_data, retorno_saida_hora):
            errors.append('O retorno deve chegar no mesmo momento ou apÃ³s a saÃ­da.')
    ultimo_trecho = cleaned_trechos[-1] if cleaned_trechos else None
    ultimo_trecho_retorna_sede = False
    if ultimo_trecho and sede_cidade:
        ultimo_destino_cidade = Cidade.objects.select_related('estado').filter(pk=ultimo_trecho.get('destino_cidade_id')).first()
        ultimo_destino_estado = Estado.objects.filter(pk=ultimo_trecho.get('destino_estado_id')).first()
        ultimo_trecho_retorna_sede = _step3_locations_equivalent(
            cidade_a=ultimo_destino_cidade,
            estado_a=ultimo_destino_estado,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        )
    if (
        ultimo_trecho
        and not ultimo_trecho_retorna_sede
        and ultimo_trecho.get('chegada_data')
        and ultimo_trecho.get('chegada_hora')
        and retorno_saida_data
        and retorno_saida_hora
    ):
        chegada_final_ida = datetime.combine(ultimo_trecho['chegada_data'], ultimo_trecho['chegada_hora'])
        saida_retorno = datetime.combine(retorno_saida_data, retorno_saida_hora)
        if saida_retorno < chegada_final_ida:
            errors.append('O retorno deve sair no mesmo momento ou apÃ³s a chegada do Ãºltimo trecho.')

    return {
        'ok': not errors,
        'errors': errors,
        'roteiro_modo': roteiro_modo,
        'roteiro_evento': roteiro_evento,
        'sede_estado': sede_estado,
        'sede_cidade': sede_cidade,
        'trechos': cleaned_trechos,
        'retorno_saida_data': retorno_saida_data,
        'retorno_saida_hora': retorno_saida_hora,
        'retorno_chegada_data': retorno_chegada_data,
        'retorno_chegada_hora': retorno_chegada_hora,
    }


def _collect_step3_markers_payload(state, oficio=None):
    roteiro_modo = state.get('roteiro_modo') or ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = state.get('roteiro_evento_id')
    if roteiro_modo == ROTEIRO_MODO_EVENTO and not roteiro_evento_id:
        raise ValueError('Selecione um roteiro salvo para usar neste ofÃ­cio.')
    trechos = state.get('trechos') or []
    if not trechos:
        raise ValueError('Preencha datas e horas para calcular.')

    cidade_ids = {item.get('destino_cidade_id') for item in trechos if item.get('destino_cidade_id')}
    estado_ids = {item.get('destino_estado_id') for item in trechos if item.get('destino_estado_id')}
    cidades_map = {
        obj.pk: obj
        for obj in Cidade.objects.select_related('estado').filter(pk__in=cidade_ids)
    }
    estados_map = {obj.pk: obj for obj in Estado.objects.filter(pk__in=estado_ids)}
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(state.get('sede_cidade_id'))).first()
    sede_estado = Estado.objects.filter(pk=_parse_int(state.get('sede_estado_id')) or getattr(sede_cidade, 'estado_id', None)).first() if (state.get('sede_estado_id') or sede_cidade) else None

    markers = []
    paradas = []
    for trecho in trechos:
        saida_data = _parse_step3_date(trecho.get('saida_data'))
        saida_hora = _parse_step3_time(trecho.get('saida_hora'))
        if not saida_data or not saida_hora:
            raise ValueError('Preencha datas e horas para calcular.')
        cidade = cidades_map.get(trecho.get('destino_cidade_id'))
        estado = getattr(cidade, 'estado', None) or estados_map.get(trecho.get('destino_estado_id'))
        cidade_nome = cidade.nome if cidade else (trecho.get('destino_nome') or '').split('/', 1)[0]
        uf_sigla = estado.sigla if estado else ''
        if not _step3_locations_equivalent(
            cidade_a=cidade,
            estado_a=estado,
            nome_a=cidade_nome,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        ):
            paradas.append((cidade_nome, uf_sigla))
        markers.append(
            PeriodMarker(
                saida=datetime.combine(saida_data, saida_hora),
                destino_cidade=cidade_nome,
                destino_uf=uf_sigla,
            )
        )

    retorno = state.get('retorno') or {}
    retorno_chegada_data = _parse_step3_date(retorno.get('chegada_data'))
    retorno_chegada_hora = _parse_step3_time(retorno.get('chegada_hora'))
    if not retorno_chegada_data or not retorno_chegada_hora:
        raise ValueError('Preencha datas e horas para calcular.')
    chegada_final = datetime.combine(retorno_chegada_data, retorno_chegada_hora)
    sede_cidade_nome, sede_uf_sigla = _step3_get_local_parts(cidade=sede_cidade, estado=sede_estado)
    return markers, paradas, chegada_final, sede_cidade_nome, sede_uf_sigla


def _step3_combine_date_time(data_value, hora_value):
    if not data_value or not hora_value:
        return None
    return datetime.combine(data_value, hora_value)

def _setup_roteiro_querysets(form, request, instance=None):
    """Preenche querysets de estado/cidade para sede (origem). No cadastro novo usa initial da config."""
    form.fields['origem_estado'].queryset = Estado.objects.order_by('nome')
    estado_id = None
    if request.method == 'POST':
        estado_id = request.POST.get('origem_estado')
        if estado_id:
            try:
                estado_id = int(estado_id)
            except (TypeError, ValueError):
                estado_id = None
    elif instance and instance.origem_estado_id:
        estado_id = instance.origem_estado_id
    else:
        # Cadastro novo: usar initial (ex.: cidade_sede_padrao da config)
        est = form.initial.get('origem_estado')
        if est is not None:
            estado_id = getattr(est, 'pk', est)
    if estado_id:
        form.fields['origem_cidade'].queryset = Cidade.objects.filter(estado_id=estado_id).order_by('nome')
    else:
        form.fields['origem_cidade'].queryset = Cidade.objects.none()
def _destinos_roteiro_para_template(objeto):
    """Lista de dicts {estado_id, cidade_id, cidade, estado} a partir de objeto com .destinos (Evento ou Roteiro)."""
    destinos_qs = objeto.destinos.select_related('estado', 'cidade').order_by('ordem', 'id')
    return [
        {'estado_id': d.estado_id, 'cidade_id': d.cidade_id, 'cidade': getattr(d, 'cidade', None), 'estado': getattr(d, 'estado', None)}
        for d in destinos_qs
    ]


def _roteiro_virtual_para_trechos(initial):
    """
    Objeto estilo roteiro (sem pk) para usar em _estrutura_trechos no cadastro novo.
    initial deve ter 'origem_estado' e/ou 'origem_cidade'. Retorna objeto com pk=None e atributos de origem.
    """
    from types import SimpleNamespace
    r = SimpleNamespace(pk=None, origem_estado_id=None, origem_cidade_id=None, origem_estado=None, origem_cidade=None)
    r.origem_estado_id = initial.get('origem_estado')
    r.origem_cidade_id = initial.get('origem_cidade')
    if r.origem_cidade_id:
        r.origem_cidade = Cidade.objects.filter(pk=r.origem_cidade_id).select_related('estado').first()
        if r.origem_cidade:
            r.origem_estado = r.origem_cidade.estado
    if not r.origem_estado and r.origem_estado_id:
        r.origem_estado = Estado.objects.filter(pk=r.origem_estado_id).first()
    return r


def _build_roteiro_avulso_route_options():
    """
    Build route_options from all avulso roteiros.
    Returns (options_list, state_map) mirroring _build_step3_route_options.
    """
    options = []
    state_map = {}
    roteiros = (
        Roteiro.objects
        .filter(tipo=Roteiro.TIPO_AVULSO)
        .prefetch_related(
            'destinos', 'destinos__estado', 'destinos__cidade',
            'trechos', 'trechos__origem_estado', 'trechos__origem_cidade',
            'trechos__destino_estado', 'trechos__destino_cidade',
            'origem_cidade', 'origem_estado',
        )
        .order_by('-pk')[:50]
    )
    for roteiro in roteiros:
        destinos = [
            _step3_local_label(destino.cidade, destino.estado)
            for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'id')
        ]
        resumo = ' -> '.join(destinos[:3]) if destinos else 'Sem destinos'
        if len(destinos) > 3:
            resumo += ' -> ...'
        state = _build_step3_state_from_roteiro_evento(roteiro)
        state_map[roteiro.pk] = state
        options.append({
            'id': roteiro.pk,
            'label': state.get('roteiro_evento_label') or f'Roteiro #{roteiro.pk}',
            'resumo': resumo,
            'status': roteiro.status,
            'tipo_label': 'Avulso',
            'state': _serialize_step3_state(state),
        })
    return options, state_map


def _build_avulso_step3_state_from_post(request, route_state_map=None):
    """Reuses Step 3 parser with avulso field aliases (origem_* -> sede_*)."""
    from types import SimpleNamespace

    post_data = request.POST.copy()
    if 'sede_estado' not in post_data and 'origem_estado' in post_data:
        post_data['sede_estado'] = post_data.get('origem_estado')
    if 'sede_cidade' not in post_data and 'origem_cidade' in post_data:
        post_data['sede_cidade'] = post_data.get('origem_cidade')

    fake_request = SimpleNamespace(POST=post_data)
    fake_oficio = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
    return _build_step3_state_from_post(
        fake_request,
        oficio=fake_oficio,
        route_state_map=route_state_map or {},
    )


def _calculate_avulso_diarias_from_state(state):
    """Calculates roteiro avulso diarias using official service with fixed one-server rule."""
    markers, paradas, chegada_final, sede_cidade, sede_uf = _collect_step3_markers_payload(state)
    resultado = calculate_periodized_diarias(
        markers,
        chegada_final,
        quantidade_servidores=1,
        sede_cidade=sede_cidade,
        sede_uf=sede_uf,
    )
    resultado['tipo_destino'] = infer_tipo_destino_from_paradas(paradas)
    return resultado


def _build_roteiro_diarias_from_request(request, *, roteiro=None, evento=None):
    from types import SimpleNamespace

    post_data = request.POST.copy()
    if 'roteiro_modo' not in post_data:
        post_data['roteiro_modo'] = ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = _parse_int(request.POST.get('roteiro_id') or request.POST.get('roteiro_evento_id'))
    if not roteiro_evento_id and roteiro is not None:
        roteiro_evento_id = roteiro.pk
    evento_id = None
    if evento is not None:
        evento_id = evento.pk
    elif roteiro is not None:
        evento_id = roteiro.evento_id
    route_context = SimpleNamespace(
        roteiro_evento_id=roteiro_evento_id,
        evento_id=evento_id,
    )
    route_options, route_state_map = _build_step3_route_options(route_context)
    fake_request = SimpleNamespace(POST=post_data)
    step3_state = _build_avulso_step3_state_from_post(fake_request, route_state_map=route_state_map)
    validated = _validate_step3_state(step3_state, oficio=route_context)
    if not validated['ok']:
        return route_options, step3_state, validated, None
    return route_options, step3_state, validated, _calculate_avulso_diarias_from_state(step3_state)


def _persistir_diarias_roteiro(roteiro, diarias_resultado):
    if not diarias_resultado:
        return
    roteiro.aplicar_diarias_calculadas(diarias_resultado)
    roteiro.save(update_fields=['quantidade_diarias', 'valor_diarias', 'valor_diarias_extenso'])


def _build_roteiro_diarias_fallback(roteiro):
    if not roteiro:
        return None
    if roteiro.valor_diarias is None and not roteiro.quantidade_diarias and not roteiro.valor_diarias_extenso:
        return None
    total_valor_decimal = roteiro.valor_diarias
    if total_valor_decimal is None:
        return None
    total_valor = formatar_valor_diarias(total_valor_decimal)
    return {
        'periodos': [],
        'totais': {
            'total_diarias': roteiro.quantidade_diarias or '',
            'total_horas': '',
            'total_valor': total_valor,
            'total_valor_decimal': total_valor_decimal,
            'valor_extenso': roteiro.valor_diarias_extenso or '',
            'quantidade_servidores': 1,
            'diarias_por_servidor': roteiro.quantidade_diarias or '',
            'valor_por_servidor': total_valor,
            'valor_por_servidor_decimal': total_valor_decimal,
            'valor_unitario_referencia': '',
        },
        'tipo_destino': '',
    }


def _salvar_roteiro_avulso_from_step3_state(roteiro, step3_state, validated, diarias_resultado=None):
    destinos_post = []
    for item in (step3_state.get('destinos_atuais') or []):
        estado_id = _parse_int(item.get('estado_id'))
        cidade_id = _parse_int(item.get('cidade_id'))
        if estado_id and cidade_id:
            destinos_post.append((estado_id, cidade_id))

    roteiro.destinos.all().delete()
    for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
        RoteiroDestino.objects.create(
            roteiro=roteiro,
            estado_id=estado_id,
            cidade_id=cidade_id,
            ordem=ordem,
        )

    roteiro.trechos.all().delete()
    trechos_validated = validated.get('trechos') or []
    for ordem, trecho in enumerate(trechos_validated):
        tempo_adicional = trecho.get('tempo_adicional_min') or 0
        tempo_cru = trecho.get('tempo_cru_estimado_min')
        duracao_estimada = trecho.get('duracao_estimada_min')
        if duracao_estimada is None and ((tempo_cru or 0) + tempo_adicional) > 0:
            duracao_estimada = (tempo_cru or 0) + tempo_adicional
        distancia = _parse_step3_decimal(trecho.get('distancia_km'))
        RoteiroTrecho.objects.create(
            roteiro=roteiro,
            ordem=ordem,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado_id=trecho.get('origem_estado_id'),
            origem_cidade_id=trecho.get('origem_cidade_id'),
            destino_estado_id=trecho.get('destino_estado_id'),
            destino_cidade_id=trecho.get('destino_cidade_id'),
            saida_dt=_step3_combine_date_time(trecho.get('saida_data'), trecho.get('saida_hora')),
            chegada_dt=_step3_combine_date_time(trecho.get('chegada_data'), trecho.get('chegada_hora')),
            distancia_km=distancia,
            duracao_estimada_min=duracao_estimada,
            tempo_cru_estimado_min=tempo_cru,
            tempo_adicional_min=tempo_adicional,
            rota_fonte=(trecho.get('rota_fonte') or '').strip(),
            rota_calculada_em=timezone.now() if (distancia is not None or tempo_cru is not None) else None,
        )

    retorno_state = step3_state.get('retorno') or {}
    retorno_tempo_cru = _parse_int(retorno_state.get('tempo_cru_estimado_min'))
    retorno_tempo_adicional = _parse_int(retorno_state.get('tempo_adicional_min')) or 0
    if retorno_tempo_adicional < 0:
        retorno_tempo_adicional = 0
    retorno_duracao = _parse_int(retorno_state.get('duracao_estimada_min'))
    if retorno_duracao is None and ((retorno_tempo_cru or 0) + retorno_tempo_adicional) > 0:
        retorno_duracao = (retorno_tempo_cru or 0) + retorno_tempo_adicional

    ultimo_trecho = trechos_validated[-1] if trechos_validated else None
    origem_retorno_estado_id = (ultimo_trecho or {}).get('destino_estado_id') or roteiro.origem_estado_id
    origem_retorno_cidade_id = (ultimo_trecho or {}).get('destino_cidade_id') or roteiro.origem_cidade_id
    distancia_retorno = _parse_step3_decimal(retorno_state.get('distancia_km'))

    RoteiroTrecho.objects.create(
        roteiro=roteiro,
        ordem=len(trechos_validated),
        tipo=RoteiroTrecho.TIPO_RETORNO,
        origem_estado_id=origem_retorno_estado_id,
        origem_cidade_id=origem_retorno_cidade_id,
        destino_estado_id=roteiro.origem_estado_id,
        destino_cidade_id=roteiro.origem_cidade_id,
        saida_dt=_step3_combine_date_time(validated.get('retorno_saida_data'), validated.get('retorno_saida_hora')),
        chegada_dt=_step3_combine_date_time(validated.get('retorno_chegada_data'), validated.get('retorno_chegada_hora')),
        distancia_km=distancia_retorno,
        duracao_estimada_min=retorno_duracao,
        tempo_cru_estimado_min=retorno_tempo_cru,
        tempo_adicional_min=retorno_tempo_adicional,
        rota_fonte=(retorno_state.get('rota_fonte') or '').strip(),
        rota_calculada_em=timezone.now() if (distancia_retorno is not None or retorno_tempo_cru is not None) else None,
    )

    _atualizar_datas_roteiro_apos_salvar_trechos(roteiro)
    _persistir_diarias_roteiro(roteiro, diarias_resultado)


def _build_roteiro_form_context(*, evento, form, obj, destinos_atuais, trechos_list, is_avulso=False, step3_state=None, route_options=None, seed_source_label=''):
    """
    Monta contexto completo para o formulÃ¡rio de roteiro (guiado e avulso).
    Quando step3_state Ã© fornecido, usa diretamente; caso contrÃ¡rio, constrÃ³i
    a partir de trechos_list + destinos_atuais (compatibilidade com forms guiados).
    """
    if step3_state is None:
        instance = obj or form.instance
        sede_estado_id = getattr(instance, 'origem_estado_id', None)
        sede_cidade_id = getattr(instance, 'origem_cidade_id', None)
        step3_state = _build_step3_state_from_estrutura(
            trechos_list,
            [{'estado_id': d.get('estado_id'), 'cidade_id': d.get('cidade_id')} for d in (destinos_atuais or [])],
            sede_estado_id,
            sede_cidade_id,
            seed_source_label,
        )
        step3_state['roteiro_modo'] = 'ROTEIRO_PROPRIO'

    sede_estado_id = step3_state.get('sede_estado_id')
    sede_cidade_id = step3_state.get('sede_cidade_id')
    estados_qs = Estado.objects.order_by('nome')
    sede_cidades_qs = (
        Cidade.objects.filter(estado_id=sede_estado_id).order_by('nome')
        if sede_estado_id
        else Cidade.objects.none()
    )
    diarias_resultado = None
    try:
        diarias_resultado = _calculate_avulso_diarias_from_state(step3_state)
    except ValueError:
        diarias_resultado = _build_roteiro_diarias_fallback(obj or form.instance)
    if diarias_resultado is None:
        diarias_resultado = _build_roteiro_diarias_fallback(obj or form.instance)
    destino_estado_fixo = _get_parana_estado()
    rows_src = list(trechos_list or [])
    if not rows_src:
        ts = (step3_state or {}).get('trechos') or []
        if ts:
            rows_src = list(ts)
    initial_trechos_data, trechos_json = _trechos_list_json_compat(rows_src)
    serialized_step3_state = _serialize_step3_state(step3_state)
    route_options_json = route_options or []
    if is_avulso:
        serialized_step3_state.pop('roteiro_evento_id', None)
        route_options_json = deepcopy(route_options_json)
        for route_option in route_options_json:
            state = route_option.get('state') or {}
            state.pop('roteiro_evento_id', None)
    return {
        'evento': evento,
        'object': obj,
        'form': form,
        'destinos_atuais': destinos_atuais,
        'estados': estados_qs,
        'api_cidades_por_estado_url': reverse('roteiros:api_cidades_por_estado', kwargs={'estado_id': 0}),
        'trechos': trechos_list,
        'trechos_json': trechos_json,
        'initial_trechos_data': initial_trechos_data,
        'step3_state_json': serialized_step3_state,
        'step3_diarias_resultado': diarias_resultado,
        'step3_seed_source_label': step3_state.get('seed_source_label', ''),
        'api_calcular_diarias_url': reverse('roteiros:calcular_diarias'),
        'roteiro_modo': step3_state.get('roteiro_modo', 'ROTEIRO_PROPRIO'),
        'roteiro_id': step3_state.get('roteiro_evento_id'),
        'roteiro_evento_id': step3_state.get('roteiro_evento_id'),
        'roteiros_evento': route_options or [],
        'roteiros_evento_json': route_options_json,
        'has_event_routes': bool(route_options),
        'is_avulso': is_avulso,
        'retorno_state': step3_state.get('retorno', {}),
        'sede_estado_id': sede_estado_id,
        'sede_cidade_id': sede_cidade_id,
        'sede_cidades_qs': sede_cidades_qs,
        'destino_estado_fixo_id': getattr(destino_estado_fixo, 'pk', None),
        'destino_estado_fixo_nome': (
            f'{destino_estado_fixo.nome} ({destino_estado_fixo.sigla})'
            if destino_estado_fixo
            else 'ParanÃ¡ (PR)'
        ),
    }
