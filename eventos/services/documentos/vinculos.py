from __future__ import annotations

from datetime import date, datetime
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from eventos.models import (
    Justificativa,
    Oficio,
    OficioDocumentoVinculo,
    OficioTrecho,
    OrdemServico,
    PlanoTrabalho,
    RoteiroEvento,
    TermoAutorizacao,
)
from eventos.services.justificativa import get_primeira_saida_oficio


DOCUMENTO_LABELS = {
    'justificativa': 'Justificativa',
    'ordem_servico': 'Ordem de serviço',
    'plano_trabalho': 'Plano de trabalho',
    'roteiro': 'Roteiro',
    'termo_autorizacao': 'Termo de autorização',
}


def _clean_text(value):
    return str(value or '').strip()


def _clean_upper(value):
    return _clean_text(value).upper()


def _unique_preserve(values):
    items = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


def _normalize_list(values):
    cleaned = []
    seen = set()
    for value in values or []:
        text = _clean_text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _normalize_ids(values):
    ids = []
    seen = set()
    for value in values or []:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            continue
        if numeric in seen:
            continue
        seen.add(numeric)
        ids.append(numeric)
    return ids


def _date_iso(value):
    if not value:
        return ''
    if isinstance(value, str):
        return value[:10]
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return ''


def _period_dict(start, end):
    start_iso = _date_iso(start)
    end_iso = _date_iso(end or start)
    return {'inicio': start_iso, 'fim': end_iso}


def _period_bounds(periodo):
    periodo = periodo or {}
    inicio = _clean_text(periodo.get('inicio'))
    fim = _clean_text(periodo.get('fim'))
    if not inicio and fim:
        inicio = fim
    if not fim and inicio:
        fim = inicio
    return inicio, fim


def _period_contains(container, contained):
    c_inicio, c_fim = _period_bounds(container)
    o_inicio, o_fim = _period_bounds(contained)
    if not c_inicio and not c_fim:
        return True
    if not o_inicio and not o_fim:
        return True
    if not c_inicio or not c_fim or not o_inicio or not o_fim:
        return False
    return c_inicio <= o_inicio and c_fim >= o_fim


def _periods_compatible(left, right):
    if _period_contains(left, right) or _period_contains(right, left):
        return True
    return False


def _locations_from_oficio(oficio):
    destinos = []
    for trecho in oficio.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'):
        cidade = _clean_text(getattr(trecho.destino_cidade, 'nome', '') if trecho.destino_cidade_id else '')
        estado = _clean_text(getattr(trecho.destino_estado, 'sigla', '') if trecho.destino_estado_id else '')
        if cidade and estado:
            destinos.append(f'{cidade}/{estado}'.upper())
        elif cidade:
            destinos.append(cidade.upper())
        elif estado:
            destinos.append(estado.upper())
    return _unique_preserve(destinos)


def _locations_from_text(value):
    parts = []
    raw = str(value or '').replace('\r', '\n').replace(';', ',')
    for item in raw.split(','):
        cleaned = _clean_text(item)
        if cleaned:
            parts.append(cleaned.upper())
    return _unique_preserve(parts)


def _normalize_event_ids(oficio):
    ids = list(oficio.eventos.values_list('pk', flat=True))
    if oficio.evento_id:
        ids.append(oficio.evento_id)
    return _normalize_ids(ids)


def _oficio_period(oficio):
    first_saida = get_primeira_saida_oficio(oficio)
    inicio = first_saida.date() if first_saida else None
    fim = oficio.retorno_chegada_data or oficio.retorno_saida_data
    if not fim:
        ultimo_trecho = oficio.trechos.order_by('ordem', 'pk').last()
        fim = getattr(ultimo_trecho, 'chegada_data', None) if ultimo_trecho else None
    if not inicio and fim:
        inicio = fim
    return _period_dict(inicio, fim)


def _roteiro_period(roteiro):
    inicio = roteiro.saida_dt.date() if roteiro.saida_dt else None
    fim = roteiro.retorno_chegada_dt or roteiro.chegada_dt
    fim = fim.date() if hasattr(fim, 'date') else fim
    if not inicio and fim:
        inicio = fim
    return _period_dict(inicio, fim)


def _ordem_period(ordem):
    inicio = ordem.data_deslocamento
    fim = ordem.data_deslocamento_fim or ordem.data_deslocamento
    return _period_dict(inicio, fim)


def _termo_period(termo):
    inicio = termo.data_evento
    fim = termo.data_evento_fim or termo.data_evento
    return _period_dict(inicio, fim)


def _plano_period(plano):
    inicio = plano.evento_data_inicio or plano.data_saida_sede
    fim = plano.evento_data_fim or plano.data_chegada_sede or plano.evento_data_inicio or plano.data_saida_sede
    return _period_dict(inicio, fim)


def snapshot_oficio(oficio: Oficio) -> dict:
    return {
        'tipo': 'oficio',
        'label': f'Ofício {oficio.numero_formatado or f"#{oficio.pk}"}',
        'pk': oficio.pk,
        'evento_ids': _normalize_event_ids(oficio),
        'roteiro_id': oficio.roteiro_evento_id,
        'destinos': _locations_from_oficio(oficio),
        'periodo': _oficio_period(oficio),
        'viajantes_ids': _normalize_ids(oficio.viajantes.values_list('pk', flat=True)),
        'motorista_viajante_id': oficio.motorista_viajante_id,
        'motorista_nome': _clean_text(oficio.motorista),
        'veiculo_id': oficio.veiculo_id,
        'veiculo_placa': _clean_upper(getattr(oficio, 'placa_formatada', '') or oficio.placa),
        'veiculo_modelo': _clean_text(oficio.modelo),
        'motivo': _clean_text(oficio.motivo),
        'quantidade_servidores': oficio.viajantes.count(),
        'quantidade_diarias': _clean_text(oficio.quantidade_diarias),
        'valor_diarias': _clean_text(oficio.valor_diarias),
        'valor_diarias_extenso': _clean_text(oficio.valor_diarias_extenso),
    }


def snapshot_roteiro(roteiro: RoteiroEvento) -> dict:
    destinos = []
    for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk'):
        cidade = _clean_text(getattr(destino.cidade, 'nome', '') if destino.cidade_id else '')
        estado = _clean_text(getattr(destino.estado, 'sigla', '') if destino.estado_id else '')
        if cidade and estado:
            destinos.append(f'{cidade}/{estado}'.upper())
        elif cidade:
            destinos.append(cidade.upper())
        elif estado:
            destinos.append(estado.upper())
    return {
        'tipo': 'roteiro',
        'label': f'Roteiro #{roteiro.pk}',
        'pk': roteiro.pk,
        'evento_ids': [roteiro.evento_id] if roteiro.evento_id else [],
        'roteiro_id': roteiro.pk,
        'destinos': _unique_preserve(destinos),
        'periodo': _roteiro_period(roteiro),
    }


def snapshot_justificativa(justificativa: Justificativa) -> dict:
    oficio = justificativa.oficio if justificativa.oficio_id else None
    oficio_snapshot = snapshot_oficio(oficio) if oficio else {}
    return {
        'tipo': 'justificativa',
        'label': f'Justificativa #{justificativa.pk}',
        'pk': justificativa.pk,
        'oficio_id': justificativa.oficio_id,
        'evento_ids': oficio_snapshot.get('evento_ids') or [],
        'motivo': _clean_text(oficio_snapshot.get('motivo') or ''),
        'texto': _clean_text(justificativa.texto),
        'destinos': oficio_snapshot.get('destinos') or [],
        'periodo': oficio_snapshot.get('periodo') or {'inicio': '', 'fim': ''},
    }


def snapshot_termo(termo: TermoAutorizacao) -> dict:
    oficio = termo.get_oficio_canonico()
    oficio_snapshot = snapshot_oficio(oficio) if oficio else {}
    destinos = _locations_from_text(termo.destino)
    if not destinos and oficio_snapshot:
        destinos = oficio_snapshot.get('destinos') or []
    viajantes_ids = [termo.viajante_id] if termo.viajante_id else []
    if not viajantes_ids and oficio_snapshot:
        viajantes_ids = oficio_snapshot.get('viajantes_ids') or []
    oficio_ids = _normalize_ids(termo.oficios.values_list('pk', flat=True))
    if termo.oficio_id and termo.oficio_id not in oficio_ids:
        oficio_ids.append(termo.oficio_id)
    return {
        'tipo': 'termo_autorizacao',
        'label': termo.numero_formatado or f'TA #{termo.pk}',
        'pk': termo.pk,
        'evento_ids': [termo.evento_id] if termo.evento_id else (oficio_snapshot.get('evento_ids') or []),
        'oficio_id': termo.oficio_id,
        'oficios_ids': oficio_ids,
        'roteiro_id': termo.roteiro_id,
        'destinos': destinos,
        'periodo': _termo_period(termo),
        'viajantes_ids': viajantes_ids,
        'veiculo_id': termo.veiculo_id,
        'veiculo_placa': _clean_upper(termo.veiculo_placa),
        'veiculo_modelo': _clean_text(termo.veiculo_modelo),
        'texto_destino': _clean_text(termo.destino),
    }


def snapshot_plano(plano: PlanoTrabalho) -> dict:
    oficio = plano.oficio if plano.oficio_id else None
    oficio_snapshot = snapshot_oficio(oficio) if oficio else {}
    destinos = []
    for item in plano.destinos_json or []:
        if not isinstance(item, dict):
            continue
        cidade = _clean_text(item.get('cidade_nome'))
        estado = _clean_text(item.get('estado_sigla')).upper()
        if cidade and estado:
            destinos.append(f'{cidade}/{estado}'.upper())
        elif cidade:
            destinos.append(cidade.upper())
        elif estado:
            destinos.append(estado)
    if not destinos and oficio_snapshot:
        destinos = oficio_snapshot.get('destinos') or []
    related_oficio_ids = _normalize_ids(plano.oficios.values_list('pk', flat=True))
    if plano.oficio_id and plano.oficio_id not in related_oficio_ids:
        related_oficio_ids.append(plano.oficio_id)
    return {
        'tipo': 'plano_trabalho',
        'label': plano.numero_formatado or f'PT #{plano.pk}',
        'pk': plano.pk,
        'evento_ids': [plano.evento_id] if plano.evento_id else (oficio_snapshot.get('evento_ids') or []),
        'oficio_id': plano.oficio_id,
        'oficios_ids': related_oficio_ids,
        'roteiro_id': plano.roteiro_id,
        'destinos': destinos,
        'periodo': _plano_period(plano),
        'quantidade_servidores': plano.quantidade_servidores or '',
        'diarias_quantidade': _clean_text(plano.diarias_quantidade),
        'diarias_valor_total': _clean_text(plano.diarias_valor_total),
        'diarias_valor_unitario': _clean_text(plano.diarias_valor_unitario),
        'diarias_valor_extenso': _clean_text(plano.diarias_valor_extenso),
    }


def snapshot_ordem(ordem: OrdemServico) -> dict:
    oficio_snapshot = snapshot_oficio(ordem.oficio) if ordem.oficio_id else {}
    destinos = []
    for item in ordem.destinos_json or []:
        if not isinstance(item, dict):
            continue
        cidade = _clean_text(item.get('cidade_nome'))
        estado = _clean_text(item.get('estado_sigla')).upper()
        if cidade and estado:
            destinos.append(f'{cidade}/{estado}'.upper())
        elif cidade:
            destinos.append(cidade.upper())
        elif estado:
            destinos.append(estado)
    if not destinos and oficio_snapshot:
        destinos = oficio_snapshot.get('destinos') or []
    return {
        'tipo': 'ordem_servico',
        'label': ordem.numero_formatado or f'OS #{ordem.pk}',
        'pk': ordem.pk,
        'evento_ids': [ordem.evento_id] if ordem.evento_id else (oficio_snapshot.get('evento_ids') or []),
        'oficio_id': ordem.oficio_id,
        'destinos': destinos,
        'periodo': _ordem_period(ordem),
        'viajantes_ids': _normalize_ids(ordem.viajantes.values_list('pk', flat=True)),
        'modelo_motivo_id': ordem.modelo_motivo_id,
        'motivo': _clean_text(ordem.motivo_texto or ordem.finalidade),
        'finalidade': _clean_text(ordem.finalidade),
    }


def build_document_snapshot(documento) -> dict:
    if isinstance(documento, RoteiroEvento):
        return snapshot_roteiro(documento)
    if isinstance(documento, Justificativa):
        return snapshot_justificativa(documento)
    if isinstance(documento, PlanoTrabalho):
        return snapshot_plano(documento)
    if isinstance(documento, OrdemServico):
        return snapshot_ordem(documento)
    if isinstance(documento, TermoAutorizacao):
        return snapshot_termo(documento)
    raise TypeError(f'Documento não suportado para vínculo: {type(documento)!r}')


def _documento_tipo(documento) -> str:
    if isinstance(documento, RoteiroEvento):
        return 'roteiro'
    if isinstance(documento, Justificativa):
        return 'justificativa'
    if isinstance(documento, PlanoTrabalho):
        return 'plano_trabalho'
    if isinstance(documento, OrdemServico):
        return 'ordem_servico'
    if isinstance(documento, TermoAutorizacao):
        return 'termo_autorizacao'
    raise TypeError(f'Documento não suportado para vínculo: {type(documento)!r}')


def _documento_label(documento, snapshot=None):
    snapshot = snapshot or build_document_snapshot(documento)
    return snapshot.get('label') or DOCUMENTO_LABELS.get(snapshot.get('tipo'), documento.__class__.__name__)


def _compare_eventos(oficio_snapshot, documento_snapshot):
    oficio_ids = set(oficio_snapshot.get('evento_ids') or [])
    documento_ids = set(documento_snapshot.get('evento_ids') or [])
    if not oficio_ids or not documento_ids:
        return True, []
    if oficio_ids.intersection(documento_ids):
        return True, []
    return False, [
        {
            'campo': 'evento_ids',
            'oficio': sorted(oficio_ids),
            'documento': sorted(documento_ids),
            'mensagem': 'Os documentos apontam para eventos diferentes.',
        },
    ]


def _compare_scalar(oficio_value, documento_value, campo, mensagem):
    oficio_clean = _clean_text(oficio_value)
    documento_clean = _clean_text(documento_value)
    if not oficio_clean or not documento_clean:
        return True, []
    if oficio_clean.casefold() == documento_clean.casefold():
        return True, []
    return False, [
        {
            'campo': campo,
            'oficio': oficio_clean,
            'documento': documento_clean,
            'mensagem': mensagem,
        },
    ]


def _compare_numeric(oficio_value, documento_value, campo, mensagem):
    if oficio_value in (None, '') or documento_value in (None, ''):
        return True, []
    try:
        oficio_num = int(oficio_value)
    except (TypeError, ValueError):
        oficio_num = oficio_value
    try:
        documento_num = int(documento_value)
    except (TypeError, ValueError):
        documento_num = documento_value
    if oficio_num == documento_num:
        return True, []
    return False, [
        {
            'campo': campo,
            'oficio': oficio_value,
            'documento': documento_value,
            'mensagem': mensagem,
        },
    ]


def _compare_destinos(oficio_snapshot, documento_snapshot, *, strict=False):
    left = _normalize_list(oficio_snapshot.get('destinos') or [])
    right = _normalize_list(documento_snapshot.get('destinos') or [])
    if not left or not right:
        return True, []
    if strict:
        if left == right:
            return True, []
        return False, [
            {
                'campo': 'destinos',
                'oficio': left,
                'documento': right,
                'mensagem': 'Os destinos não têm a mesma sequência e não podem ser sincronizados automaticamente.',
            },
        ]
    left_set = set(left)
    right_set = set(right)
    if left_set.issubset(right_set) or right_set.issubset(left_set):
        return True, []
    return False, [
        {
            'campo': 'destinos',
            'oficio': left,
            'documento': right,
            'mensagem': 'Os destinos não são compatíveis entre si.',
        },
    ]


def _compare_periodo(oficio_snapshot, documento_snapshot):
    left = oficio_snapshot.get('periodo') or {}
    right = documento_snapshot.get('periodo') or {}
    if _periods_compatible(left, right):
        return True, []
    return False, [
        {
            'campo': 'periodo',
            'oficio': left,
            'documento': right,
            'mensagem': 'Os períodos informados são incompatíveis.',
        },
    ]


def _compare_viajantes(oficio_snapshot, documento_snapshot):
    left = _normalize_ids(oficio_snapshot.get('viajantes_ids') or [])
    right = _normalize_ids(documento_snapshot.get('viajantes_ids') or [])
    if not left or not right:
        return True, []
    left_set = set(left)
    right_set = set(right)
    if left_set.issubset(right_set) or right_set.issubset(left_set):
        return True, []
    return False, [
        {
            'campo': 'viajantes_ids',
            'oficio': left,
            'documento': right,
            'mensagem': 'As equipes envolvidas são divergentes.',
        },
    ]


def _merge_result(base_result, *, compatible, conflitos, herdados_oficio, herdados_documento, observacoes=None):
    base_result['compativel'] = compatible
    base_result['status'] = 'COMPATIVEL' if compatible else 'CONFLITO'
    base_result['conflitos'] = conflitos
    base_result['campos_herdaveis_do_oficio_para_documento'] = _unique_preserve(herdados_oficio)
    base_result['campos_herdaveis_do_documento_para_oficio'] = _unique_preserve(herdados_documento)
    base_result['observacoes'] = _unique_preserve(observacoes or [])
    return base_result


def avaliar_compatibilidade_oficio_documento(oficio: Oficio, documento) -> dict:
    oficio_snapshot = snapshot_oficio(oficio)
    documento_snapshot = build_document_snapshot(documento)
    doc_tipo = _documento_tipo(documento)
    conflitos = []
    herdados_oficio = []
    herdados_documento = []
    observacoes = []
    compatible = True
    base = {
        'tipo_documento': doc_tipo,
        'documento_label': _documento_label(documento, documento_snapshot),
        'compativel': True,
        'status': 'COMPATIVEL',
        'oficio_snapshot': oficio_snapshot,
        'documento_snapshot': documento_snapshot,
    }

    if doc_tipo == 'roteiro':
        ok, issues = _compare_eventos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('evento_ids') or documento_snapshot.get('evento_ids'):
            herdados_oficio.append('evento_ids')
            herdados_documento.append('evento_ids')
        ok, issues = _compare_destinos(oficio_snapshot, documento_snapshot, strict=True)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('destinos') or documento_snapshot.get('destinos'):
            herdados_oficio.append('destinos')
            herdados_documento.append('destinos')
        ok, issues = _compare_periodo(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('periodo') or documento_snapshot.get('periodo'):
            herdados_oficio.append('periodo')
            herdados_documento.append('periodo')
    elif doc_tipo == 'justificativa':
        oficio_id = documento_snapshot.get('oficio_id')
        if oficio_id and oficio_id != oficio.pk:
            compatible = False
            conflitos.append(
                {
                    'campo': 'oficio_id',
                    'oficio': oficio.pk,
                    'documento': oficio_id,
                    'mensagem': 'A justificativa já pertence a outro ofício.',
                }
            )
        else:
            herdados_oficio.append('motivo')
            herdados_documento.append('texto')
            observacoes.append('A justificativa seguirá o mesmo contexto do ofício.');
    elif doc_tipo == 'termo_autorizacao':
        ok, issues = _compare_eventos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('evento_ids') or documento_snapshot.get('evento_ids'):
            herdados_oficio.append('evento_ids')
            herdados_documento.append('evento_ids')
        ok, issues = _compare_destinos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('destinos') or documento_snapshot.get('destinos'):
            herdados_oficio.append('destinos')
            herdados_documento.append('destinos')
        ok, issues = _compare_periodo(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('periodo') or documento_snapshot.get('periodo'):
            herdados_oficio.append('periodo')
            herdados_documento.append('periodo')
        ok, issues = _compare_viajantes(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('viajantes_ids') or documento_snapshot.get('viajantes_ids'):
            herdados_oficio.append('viajantes_ids')
            herdados_documento.append('viajantes_ids')
        ok, issues = _compare_scalar(oficio_snapshot.get('veiculo_id'), documento_snapshot.get('veiculo_id'), 'veiculo_id', 'As viaturas são diferentes.')
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('veiculo_id') or documento_snapshot.get('veiculo_id'):
            herdados_oficio.append('veiculo_id')
            herdados_documento.append('veiculo_id')
    elif doc_tipo == 'plano_trabalho':
        ok, issues = _compare_eventos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('evento_ids') or documento_snapshot.get('evento_ids'):
            herdados_oficio.append('evento_ids')
            herdados_documento.append('evento_ids')
        ok, issues = _compare_destinos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('destinos') or documento_snapshot.get('destinos'):
            herdados_oficio.append('destinos')
            herdados_documento.append('destinos')
        ok, issues = _compare_periodo(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('periodo') or documento_snapshot.get('periodo'):
            herdados_oficio.append('periodo')
            herdados_documento.append('periodo')
        ok, issues = _compare_numeric(
            oficio_snapshot.get('quantidade_servidores'),
            documento_snapshot.get('quantidade_servidores'),
            'quantidade_servidores',
            'A quantidade de servidores é divergente.',
        )
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('quantidade_servidores') or documento_snapshot.get('quantidade_servidores'):
            herdados_oficio.append('quantidade_servidores')
            herdados_documento.append('quantidade_servidores')
    elif doc_tipo == 'ordem_servico':
        ok, issues = _compare_eventos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('evento_ids') or documento_snapshot.get('evento_ids'):
            herdados_oficio.append('evento_ids')
            herdados_documento.append('evento_ids')
        ok, issues = _compare_destinos(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('destinos') or documento_snapshot.get('destinos'):
            herdados_oficio.append('destinos')
            herdados_documento.append('destinos')
        ok, issues = _compare_periodo(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('periodo') or documento_snapshot.get('periodo'):
            herdados_oficio.append('periodo')
            herdados_documento.append('periodo')
        ok, issues = _compare_viajantes(oficio_snapshot, documento_snapshot)
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('viajantes_ids') or documento_snapshot.get('viajantes_ids'):
            herdados_oficio.append('viajantes_ids')
            herdados_documento.append('viajantes_ids')
        ok, issues = _compare_scalar(oficio_snapshot.get('motivo'), documento_snapshot.get('motivo'), 'motivo', 'O motivo do deslocamento é diferente.')
        compatible = compatible and ok
        conflitos.extend(issues)
        if oficio_snapshot.get('motivo') or documento_snapshot.get('motivo'):
            herdados_oficio.append('motivo')
            herdados_documento.append('motivo')
    else:
        compatible = False
        conflitos.append(
            {
                'campo': 'tipo_documento',
                'oficio': doc_tipo,
                'documento': doc_tipo,
                'mensagem': 'Tipo documental ainda não implementado para vínculo.',
            }
        )

    return _merge_result(
        base,
        compatible=compatible,
        conflitos=conflitos,
        herdados_oficio=herdados_oficio,
        herdados_documento=herdados_documento,
        observacoes=observacoes,
    )


DOCUMENTO_CONFIG = {
    'roteiro': {
        'model': RoteiroEvento,
        'label': 'Roteiro',
        'queryset': lambda: RoteiroEvento.objects.select_related(
            'evento',
            'origem_estado',
            'origem_cidade',
        ).prefetch_related(
            'destinos',
            'destinos__estado',
            'destinos__cidade',
            'trechos',
            'trechos__origem_estado',
            'trechos__origem_cidade',
            'trechos__destino_estado',
            'trechos__destino_cidade',
        ),
    },
    'justificativa': {
        'model': Justificativa,
        'label': 'Justificativa',
        'queryset': lambda: Justificativa.objects.select_related('oficio'),
    },
    'termo_autorizacao': {
        'model': TermoAutorizacao,
        'label': 'Termo de autorização',
        'queryset': lambda: TermoAutorizacao.objects.select_related(
            'oficio',
            'evento',
            'roteiro',
            'viajante',
            'veiculo',
        ).prefetch_related('oficios'),
    },
    'plano_trabalho': {
        'model': PlanoTrabalho,
        'label': 'Plano de trabalho',
        'queryset': lambda: PlanoTrabalho.objects.select_related(
            'oficio',
            'evento',
            'roteiro',
            'solicitante',
            'coordenador_operacional',
            'coordenador_administrativo',
        ).prefetch_related('oficios'),
    },
    'ordem_servico': {
        'model': OrdemServico,
        'label': 'Ordem de serviço',
        'queryset': lambda: OrdemServico.objects.select_related('oficio', 'evento').prefetch_related('viajantes'),
    },
}


def _documento_queryset(tipo_documento):
    config = DOCUMENTO_CONFIG.get(tipo_documento)
    if not config:
        return None
    return config['queryset']()


def _documento_link_url(tipo_documento, pk, *, oficio_pk=None):
    if not pk:
        return ''
    if tipo_documento == 'roteiro':
        return reverse('eventos:roteiro-avulso-editar', kwargs={'pk': pk})
    if tipo_documento == 'justificativa':
        if oficio_pk:
            return reverse('eventos:oficio-justificativa', kwargs={'pk': oficio_pk})
        return reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': pk})
    if tipo_documento == 'termo_autorizacao':
        return reverse('eventos:documentos-termos-detalhe', kwargs={'pk': pk})
    if tipo_documento == 'plano_trabalho':
        return reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': pk})
    if tipo_documento == 'ordem_servico':
        return reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': pk})
    return ''


def _normalize_json_destinos(destinos):
    normalized = []
    seen = set()
    for destino in destinos or []:
        if not isinstance(destino, dict):
            continue
        cidade = _clean_text(destino.get('cidade_nome')).upper()
        estado = _clean_text(destino.get('estado_sigla')).upper()
        if cidade and estado:
            key = f'{cidade}/{estado}'
            payload = {'cidade_nome': cidade, 'estado_sigla': estado}
        elif cidade:
            key = cidade
            payload = {'cidade_nome': cidade, 'estado_sigla': ''}
        elif estado:
            key = estado
            payload = {'cidade_nome': '', 'estado_sigla': estado}
        else:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(payload)
    return normalized


def _office_evento_principal(oficio):
    return oficio.get_evento_principal() if oficio else None


def _office_destinos_labels(oficio):
    return _locations_from_oficio(oficio) if oficio else []


def _office_period_dates(oficio):
    if not oficio:
        return None, None
    first_saida = get_primeira_saida_oficio(oficio)
    inicio = first_saida.date() if first_saida else None
    fim = oficio.retorno_chegada_data or oficio.retorno_saida_data
    if not fim:
        ultimo_trecho = oficio.trechos.order_by('ordem', 'pk').last()
        fim = getattr(ultimo_trecho, 'chegada_data', None) if ultimo_trecho else None
    if not inicio and fim:
        inicio = fim
    return inicio, fim


def _office_destinos_json_from_trechos(oficio):
    destinos = []
    for trecho in oficio.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'):
        cidade = _clean_text(getattr(trecho.destino_cidade, 'nome', '') if trecho.destino_cidade_id else '')
        estado = _clean_text(getattr(trecho.destino_estado, 'sigla', '') if trecho.destino_estado_id else '')
        if not cidade and not estado:
            continue
        destinos.append({'cidade_nome': cidade, 'estado_sigla': estado})
    return _normalize_json_destinos(destinos)


def _criar_trechos_oficio_a_partir_de_destinos(oficio, destinos, *, origem_cidade_id=None, origem_estado_id=None):
    if oficio.trechos.exists():
        return []
    created = []
    for ordem, destino in enumerate(destinos or []):
        if not isinstance(destino, dict):
            continue
        estado_id = _normalize_ids([destino.get('estado_id') or destino.get('destino_estado_id')])[0] if (destino.get('estado_id') or destino.get('destino_estado_id')) else None
        cidade_id = _normalize_ids([destino.get('cidade_id') or destino.get('destino_cidade_id')])[0] if (destino.get('cidade_id') or destino.get('destino_cidade_id')) else None
        if not estado_id and not cidade_id:
            continue
        created.append(
            OficioTrecho.objects.create(
                oficio=oficio,
                ordem=ordem,
                origem_cidade_id=origem_cidade_id,
                origem_estado_id=origem_estado_id,
                destino_cidade_id=cidade_id,
                destino_estado_id=estado_id,
            )
        )
    return created


def _office_viajantes_ids(oficio):
    return _normalize_ids(oficio.viajantes.values_list('pk', flat=True)) if oficio and oficio.pk else []


def _field_is_empty(value):
    if value is None:
        return True
    if value == '':
        return True
    if value == [] or value == {}:
        return True
    return False


def _set_if_empty(obj, field_name, value, changed_fields):
    current = getattr(obj, field_name)
    if not _field_is_empty(current) or _field_is_empty(value):
        return False
    setattr(obj, field_name, value)
    changed_fields.append(field_name)
    return True


def _date_to_midnight(value: date | None):
    if not value:
        return None
    dt = datetime.combine(value, datetime.min.time())
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def _sync_roteiro(oficio, roteiro):
    changed_oficio = []
    changed_documento = []

    if not oficio.roteiro_evento_id and roteiro.evento_id:
        oficio.roteiro_evento = roteiro
        changed_oficio.append('roteiro_evento')
    if not roteiro.evento_id:
        principal = _office_evento_principal(oficio)
        if principal:
            roteiro.evento = principal
            changed_documento.append('evento')
    elif not oficio.eventos.exists():
        oficio.eventos.add(roteiro.evento)
        changed_oficio.append('eventos')

    if not oficio.cidade_sede_id and roteiro.origem_cidade_id:
        oficio.cidade_sede = roteiro.origem_cidade
        changed_oficio.append('cidade_sede')
    if not oficio.estado_sede_id and roteiro.origem_estado_id:
        oficio.estado_sede = roteiro.origem_estado
        changed_oficio.append('estado_sede')
    if not roteiro.origem_cidade_id and oficio.cidade_sede_id:
        roteiro.origem_cidade = oficio.cidade_sede
        changed_documento.append('origem_cidade')
    if not roteiro.origem_estado_id and oficio.estado_sede_id:
        roteiro.origem_estado = oficio.estado_sede
        changed_documento.append('origem_estado')
    if not oficio.trechos.exists() and roteiro.destinos.exists():
        destinos_payload = [
            {'estado_id': destino.estado_id, 'cidade_id': destino.cidade_id}
            for destino in roteiro.destinos.select_related('estado', 'cidade').order_by('ordem', 'pk')
        ]
        created_trechos = _criar_trechos_oficio_a_partir_de_destinos(
            oficio,
            destinos_payload,
            origem_cidade_id=oficio.cidade_sede_id,
            origem_estado_id=oficio.estado_sede_id,
        )
        if created_trechos:
            changed_oficio.append('trechos')

    inicio_oficio, fim_oficio = _office_period_dates(oficio)
    if not roteiro.saida_dt and inicio_oficio:
        roteiro.saida_dt = _date_to_midnight(inicio_oficio)
        changed_documento.append('saida_dt')
    if not roteiro.chegada_dt and fim_oficio:
        roteiro.chegada_dt = _date_to_midnight(fim_oficio)
        changed_documento.append('chegada_dt')
    if not oficio.retorno_chegada_data and roteiro.chegada_dt:
        oficio.retorno_chegada_data = roteiro.chegada_dt.date()
        changed_oficio.append('retorno_chegada_data')
    if not oficio.retorno_saida_data and roteiro.saida_dt:
        oficio.retorno_saida_data = roteiro.saida_dt.date()
        changed_oficio.append('retorno_saida_data')

    if not oficio.quantidade_diarias and roteiro.quantidade_diarias:
        oficio.quantidade_diarias = roteiro.quantidade_diarias
        changed_oficio.append('quantidade_diarias')
    if not oficio.valor_diarias and roteiro.valor_diarias is not None:
        oficio.valor_diarias = roteiro.valor_diarias
        changed_oficio.append('valor_diarias')
    if not oficio.valor_diarias_extenso and roteiro.valor_diarias_extenso:
        oficio.valor_diarias_extenso = roteiro.valor_diarias_extenso
        changed_oficio.append('valor_diarias_extenso')

    return changed_oficio, changed_documento


def _sync_justificativa(oficio, justificativa):
    changed_oficio = []
    changed_documento = []

    if not justificativa.oficio_id:
        justificativa.oficio = oficio
        changed_documento.append('oficio')
    if not oficio.motivo and justificativa.texto:
        oficio.motivo = justificativa.texto
        changed_oficio.append('motivo')
    if not justificativa.texto and oficio.motivo:
        justificativa.texto = oficio.motivo
        changed_documento.append('texto')

    return changed_oficio, changed_documento


def _sync_termo(oficio, termo):
    changed_oficio = []
    changed_documento = []

    principal_evento = _office_evento_principal(oficio)
    if not termo.evento_id and principal_evento:
        termo.evento = principal_evento
        changed_documento.append('evento')
    if not oficio.eventos.exists() and termo.evento_id:
        oficio.eventos.add(termo.evento)
        changed_oficio.append('eventos')
    if not termo.oficio_id:
        termo.oficio = oficio
        changed_documento.append('oficio')
    if not termo.roteiro_id and oficio.roteiro_evento_id:
        termo.roteiro = oficio.roteiro_evento
        changed_documento.append('roteiro')
    if not oficio.roteiro_evento_id and termo.roteiro_id:
        oficio.roteiro_evento = termo.roteiro
        changed_oficio.append('roteiro_evento')

    destinos_oficio = _office_destinos_labels(oficio)
    if not termo.destino and destinos_oficio:
        termo.destino = ', '.join(destinos_oficio)
        changed_documento.append('destino')
    elif termo.destino and not destinos_oficio:
        pass

    inicio_oficio, fim_oficio = _office_period_dates(oficio)
    if not termo.data_evento and inicio_oficio:
        termo.data_evento = inicio_oficio
        changed_documento.append('data_evento')
    if not termo.data_evento_fim and fim_oficio:
        termo.data_evento_fim = fim_oficio
        changed_documento.append('data_evento_fim')
    if not oficio.retorno_saida_data and termo.data_evento:
        oficio.retorno_saida_data = termo.data_evento
        changed_oficio.append('retorno_saida_data')
    if not oficio.retorno_chegada_data and termo.data_evento_fim:
        oficio.retorno_chegada_data = termo.data_evento_fim
        changed_oficio.append('retorno_chegada_data')

    viajantes_ids = _office_viajantes_ids(oficio)
    termo_viajante_id = termo.viajante_id
    if not termo_viajante_id and len(viajantes_ids) == 1:
        termo.viajante_id = viajantes_ids[0]
        changed_documento.append('viajante')
    elif termo_viajante_id and not oficio.viajantes.filter(pk=termo_viajante_id).exists():
        oficio.viajantes.add(termo.viajante)
        changed_oficio.append('viajantes')

    if not termo.veiculo_id and oficio.veiculo_id:
        termo.veiculo = oficio.veiculo
        changed_documento.append('veiculo')
    if not oficio.veiculo_id and termo.veiculo_id:
        oficio.veiculo = termo.veiculo
        changed_oficio.append('veiculo')
        if not oficio.placa and termo.veiculo_placa:
            oficio.placa = termo.veiculo_placa
            changed_oficio.append('placa')
        if not oficio.modelo and termo.veiculo_modelo:
            oficio.modelo = termo.veiculo_modelo
            changed_oficio.append('modelo')
        if not oficio.combustivel and termo.veiculo_combustivel:
            oficio.combustivel = termo.veiculo_combustivel
            changed_oficio.append('combustivel')

    termo.populate_snapshots_from_relations(force=False)
    for snapshot_field in [
        'servidor_nome',
        'servidor_rg',
        'servidor_cpf',
        'servidor_telefone',
        'servidor_lotacao',
        'veiculo_placa',
        'veiculo_modelo',
        'veiculo_combustivel',
        'modo_geracao',
        'template_variant',
        'status',
        'lote_uuid',
    ]:
        if snapshot_field not in changed_documento:
            changed_documento.append(snapshot_field)
    return changed_oficio, changed_documento


def _sync_plano(oficio, plano):
    changed_oficio = []
    changed_documento = []

    principal_evento = _office_evento_principal(oficio)
    if not plano.evento_id and principal_evento:
        plano.evento = principal_evento
        changed_documento.append('evento')
    if not oficio.eventos.exists() and plano.evento_id:
        oficio.eventos.add(plano.evento)
        changed_oficio.append('eventos')
    if not plano.oficio_id:
        plano.oficio = oficio
        changed_documento.append('oficio')
    if oficio.roteiro_evento_id and not plano.roteiro_id:
        plano.roteiro = oficio.roteiro_evento
        changed_documento.append('roteiro')
    if plano.roteiro_id and not oficio.roteiro_evento_id:
        oficio.roteiro_evento = plano.roteiro
        changed_oficio.append('roteiro_evento')

    if not plano.destinos_json:
        plano.destinos_json = _office_destinos_json_from_trechos(oficio)
        if plano.destinos_json:
            changed_documento.append('destinos_json')
    if not oficio.trechos.exists() and plano.destinos_json:
        created_trechos = _criar_trechos_oficio_a_partir_de_destinos(
            oficio,
            plano.destinos_json,
            origem_cidade_id=oficio.cidade_sede_id,
            origem_estado_id=oficio.estado_sede_id,
        )
        if created_trechos:
            changed_oficio.append('trechos')

    inicio_oficio, fim_oficio = _office_period_dates(oficio)
    if not plano.evento_data_inicio and inicio_oficio:
        plano.evento_data_inicio = inicio_oficio
        changed_documento.append('evento_data_inicio')
    if not plano.evento_data_fim and fim_oficio:
        plano.evento_data_fim = fim_oficio
        changed_documento.append('evento_data_fim')
    if not plano.data_saida_sede and inicio_oficio:
        plano.data_saida_sede = inicio_oficio
        changed_documento.append('data_saida_sede')
    if not plano.data_chegada_sede and fim_oficio:
        plano.data_chegada_sede = fim_oficio
        changed_documento.append('data_chegada_sede')
    if not oficio.quantidade_diarias and plano.diarias_quantidade:
        oficio.quantidade_diarias = plano.diarias_quantidade
        changed_oficio.append('quantidade_diarias')
    if not oficio.valor_diarias and plano.diarias_valor_total:
        oficio.valor_diarias = plano.diarias_valor_total
        changed_oficio.append('valor_diarias')
    if not oficio.valor_diarias_extenso and plano.diarias_valor_extenso:
        oficio.valor_diarias_extenso = plano.diarias_valor_extenso
        changed_oficio.append('valor_diarias_extenso')
    if not plano.quantidade_servidores and oficio.viajantes.exists():
        plano.quantidade_servidores = oficio.viajantes.count()
        changed_documento.append('quantidade_servidores')

    return changed_oficio, changed_documento


def _sync_ordem(oficio, ordem):
    changed_oficio = []
    changed_documento = []

    principal_evento = _office_evento_principal(oficio)
    if not ordem.evento_id and principal_evento:
        ordem.evento = principal_evento
        changed_documento.append('evento')
    if not oficio.eventos.exists() and ordem.evento_id:
        oficio.eventos.add(ordem.evento)
        changed_oficio.append('eventos')
    if not ordem.oficio_id:
        ordem.oficio = oficio
        changed_documento.append('oficio')

    if not ordem.destinos_json:
        ordem.destinos_json = _office_destinos_json_from_trechos(oficio)
        if ordem.destinos_json:
            changed_documento.append('destinos_json')
    if not oficio.trechos.exists() and ordem.destinos_json:
        created_trechos = _criar_trechos_oficio_a_partir_de_destinos(
            oficio,
            ordem.destinos_json,
            origem_cidade_id=oficio.cidade_sede_id,
            origem_estado_id=oficio.estado_sede_id,
        )
        if created_trechos:
            changed_oficio.append('trechos')
    if not ordem.data_deslocamento:
        inicio_oficio, fim_oficio = _office_period_dates(oficio)
        if inicio_oficio:
            ordem.data_deslocamento = inicio_oficio
            changed_documento.append('data_deslocamento')
        if fim_oficio:
            ordem.data_deslocamento_fim = fim_oficio
            changed_documento.append('data_deslocamento_fim')

    if not ordem.viajantes.exists() and oficio.viajantes.exists():
        ordem.viajantes.set(oficio.viajantes.all())
        changed_documento.append('viajantes')
    if not oficio.viajantes.exists() and ordem.viajantes.exists():
        oficio.viajantes.add(*ordem.viajantes.all())
        changed_oficio.append('viajantes')

    if not ordem.finalidade and oficio.motivo:
        ordem.finalidade = oficio.motivo
        changed_documento.append('finalidade')
    if not ordem.motivo_texto and oficio.motivo:
        ordem.motivo_texto = oficio.motivo
        changed_documento.append('motivo_texto')
    if not oficio.motivo and (ordem.finalidade or ordem.motivo_texto):
        oficio.motivo = ordem.finalidade or ordem.motivo_texto
        changed_oficio.append('motivo')

    return changed_oficio, changed_documento


def _persist_instance(instance, changed_fields):
    changed_fields = [
        field
        for field in dict.fromkeys(changed_fields or [])
        if field not in {'eventos', 'viajantes', 'm2m', 'trechos'}
    ]
    if not hasattr(instance, 'save'):
        return
    update_fields = list(changed_fields)
    if hasattr(instance, 'updated_at'):
        update_fields.append('updated_at')
    if update_fields:
        instance.save(update_fields=update_fields)
    else:
        instance.save()


def _comparar_e_sincronizar(oficio, documento, compatibilidade=None):
    compatibilidade = compatibilidade or avaliar_compatibilidade_oficio_documento(oficio, documento)
    if not compatibilidade.get('compativel'):
        return {
            'ok': False,
            'compatibilidade': compatibilidade,
            'campos_herdados_oficio': [],
            'campos_herdados_documento': [],
            'conflitos': compatibilidade.get('conflitos') or [],
        }

    doc_tipo = _documento_tipo(documento)
    changed_oficio = []
    changed_documento = []

    if doc_tipo == 'roteiro':
        changed_oficio, changed_documento = _sync_roteiro(oficio, documento)
    elif doc_tipo == 'justificativa':
        changed_oficio, changed_documento = _sync_justificativa(oficio, documento)
    elif doc_tipo == 'termo_autorizacao':
        changed_oficio, changed_documento = _sync_termo(oficio, documento)
    elif doc_tipo == 'plano_trabalho':
        changed_oficio, changed_documento = _sync_plano(oficio, documento)
    elif doc_tipo == 'ordem_servico':
        changed_oficio, changed_documento = _sync_ordem(oficio, documento)
    else:
        return {
            'ok': False,
            'compatibilidade': compatibilidade,
            'campos_herdados_oficio': [],
            'campos_herdados_documento': [],
            'conflitos': [{'campo': 'tipo_documento', 'mensagem': 'Tipo documental não suportado.'}],
        }

    resultado = {
        'ok': True,
        'compatibilidade': compatibilidade,
        'campos_herdados_oficio': _unique_preserve(changed_oficio),
        'campos_herdados_documento': _unique_preserve(changed_documento),
        'conflitos': compatibilidade.get('conflitos') or [],
    }

    _persist_instance(oficio, changed_oficio)
    _persist_instance(documento, changed_documento)

    return resultado


def _link_pair_signature(tipo_documento, object_id):
    return (tipo_documento, int(object_id))


def _existing_link_map(oficio):
    links = oficio.documentos_vinculados.select_related('content_type').order_by('pk')
    return { _link_pair_signature(link.tipo_documento, link.object_id): link for link in links }


def _serialize_link_item(oficio, documento, *, compatibilidade=None, origem='direto', link=None):
    compatibilidade = compatibilidade or avaliar_compatibilidade_oficio_documento(oficio, documento)
    tipo_documento = _documento_tipo(documento)
    documento_snapshot = compatibilidade.get('documento_snapshot') or build_document_snapshot(documento)
    label = compatibilidade.get('documento_label') or _documento_label(documento, documento_snapshot)
    status = (link.status_compatibilidade if link else compatibilidade.get('status')) or 'COMPATIVEL'
    return {
        'tipo_documento': tipo_documento,
        'documento_id': documento.pk,
        'titulo': label,
        'url': _documento_link_url(tipo_documento, documento.pk, oficio_pk=oficio.pk),
        'badge_label': 'Compatível' if status == 'COMPATIVEL' else 'Conflito',
        'badge_css_class': 'is-success' if status == 'COMPATIVEL' else 'is-danger',
        'status_compatibilidade': status,
        'status_label': 'Compatível' if status == 'COMPATIVEL' else 'Conflito',
        'origem': origem,
        'conflitos': link.conflitos if link else (compatibilidade.get('conflitos') or []),
        'observacoes': link.observacoes if link else (compatibilidade.get('observacoes') or []),
        'campos_herdados_oficio': link.campos_herdados_oficio if link else (compatibilidade.get('campos_herdaveis_do_oficio_para_documento') or []),
        'campos_herdados_documento': link.campos_herdados_documento if link else (compatibilidade.get('campos_herdaveis_do_documento_para_oficio') or []),
        'snapshot_oficio': link.snapshot_oficio if link else compatibilidade.get('oficio_snapshot') or {},
        'snapshot_documento': link.snapshot_documento if link else documento_snapshot,
    }


def listar_documentos_compativeis_para_oficio(oficio, *, tipos=None, limite_por_tipo=25):
    tipos = set(tipos or DOCUMENTO_CONFIG.keys())
    existentes = _existing_link_map(oficio)
    candidatos = []

    for tipo_documento in tipos:
        queryset = _documento_queryset(tipo_documento)
        if queryset is None:
            continue
        for documento in queryset.order_by('-updated_at', '-created_at')[:limite_por_tipo]:
            if _link_pair_signature(tipo_documento, documento.pk) in existentes:
                continue
            compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, documento)
            if not compatibilidade.get('compativel'):
                continue
            candidatos.append(_serialize_link_item(oficio, documento, compatibilidade=compatibilidade, origem='candidato'))
    candidatos.sort(key=lambda item: (item['tipo_documento'], item['titulo'].casefold()))
    return candidatos


def reconciliar_vinculos_oficio(oficio):
    """
    Atualiza os vínculos documentais do ofício, promovendo relações legadas
    para `OficioDocumentoVinculo` quando necessário e refletindo o estado atual.
    """
    resultado = []
    if not oficio.pk:
        return resultado

    with transaction.atomic():
        existentes = _existing_link_map(oficio)
        relacoes_legadas = []

        if oficio.roteiro_evento_id and oficio.roteiro_evento:
            relacoes_legadas.append(('roteiro', oficio.roteiro_evento))
        try:
            justificativa = oficio.justificativa
        except Justificativa.DoesNotExist:
            justificativa = None
        if justificativa is not None:
            relacoes_legadas.append(('justificativa', justificativa))
        for plano in oficio.planos_trabalho.select_related('evento', 'roteiro').order_by('pk'):
            relacoes_legadas.append(('plano_trabalho', plano))
        for ordem in oficio.ordens_servico.select_related('evento').prefetch_related('viajantes').order_by('pk'):
            relacoes_legadas.append(('ordem_servico', ordem))
        for termo in oficio.termos_autorizacao.select_related('evento', 'roteiro', 'viajante', 'veiculo').prefetch_related('oficios').order_by('pk'):
            relacoes_legadas.append(('termo_autorizacao', termo))

        for tipo_documento, documento in relacoes_legadas:
            assinatura = _link_pair_signature(tipo_documento, documento.pk)
            compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, documento)
            if assinatura in existentes:
                link = existentes[assinatura]
                sync_result = _comparar_e_sincronizar(oficio, documento, compatibilidade=compatibilidade)
                link.status_compatibilidade = compatibilidade.get('status') if compatibilidade.get('compativel') else OficioDocumentoVinculo.STATUS_CONFLITO
                link.snapshot_oficio = compatibilidade.get('oficio_snapshot') or {}
                link.snapshot_documento = compatibilidade.get('documento_snapshot') or {}
                link.campos_herdados_oficio = sync_result['campos_herdados_oficio']
                link.campos_herdados_documento = sync_result['campos_herdados_documento']
                link.conflitos = compatibilidade.get('conflitos') or []
                link.observacoes = compatibilidade.get('observacoes') or []
                link.documento_rotulo = compatibilidade.get('documento_label') or link.documento_rotulo
                link.save(
                    update_fields=[
                        'status_compatibilidade',
                        'snapshot_oficio',
                        'snapshot_documento',
                        'campos_herdados_oficio',
                        'campos_herdados_documento',
                        'conflitos',
                        'observacoes',
                        'documento_rotulo',
                        'updated_at',
                    ]
                )
                resultado.append(link)
                continue

            content_type = ContentType.objects.get_for_model(documento, for_concrete_model=False)
            link = OficioDocumentoVinculo(
                oficio=oficio,
                tipo_documento=tipo_documento,
                content_type=content_type,
                object_id=documento.pk,
                documento_rotulo=compatibilidade.get('documento_label') or _documento_label(documento),
                status_compatibilidade=compatibilidade.get('status') if compatibilidade.get('compativel') else OficioDocumentoVinculo.STATUS_CONFLITO,
                snapshot_oficio=compatibilidade.get('oficio_snapshot') or {},
                snapshot_documento=compatibilidade.get('documento_snapshot') or {},
                campos_herdados_oficio=[],
                campos_herdados_documento=[],
                conflitos=compatibilidade.get('conflitos') or [],
                observacoes=compatibilidade.get('observacoes') or [],
            )
            if compatibilidade.get('compativel'):
                sync_result = _comparar_e_sincronizar(oficio, documento, compatibilidade=compatibilidade)
                link.campos_herdados_oficio = sync_result['campos_herdados_oficio']
                link.campos_herdados_documento = sync_result['campos_herdados_documento']
                link.status_compatibilidade = OficioDocumentoVinculo.STATUS_COMPATIVEL
            link.save()
            resultado.append(link)

        return resultado


def vincular_documento_ao_oficio(oficio, documento):
    compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, documento)
    if not compatibilidade.get('compativel'):
        return {
            'ok': False,
            'compatibilidade': compatibilidade,
            'link': None,
        }

    with transaction.atomic():
        sync_result = _comparar_e_sincronizar(oficio, documento, compatibilidade=compatibilidade)
        content_type = ContentType.objects.get_for_model(documento, for_concrete_model=False)
        link, _created = OficioDocumentoVinculo.objects.update_or_create(
            oficio=oficio,
            content_type=content_type,
            object_id=documento.pk,
            defaults={
                'tipo_documento': compatibilidade.get('tipo_documento') or _documento_tipo(documento),
                'documento_rotulo': compatibilidade.get('documento_label') or _documento_label(documento),
                'status_compatibilidade': OficioDocumentoVinculo.STATUS_COMPATIVEL,
                'snapshot_oficio': compatibilidade.get('oficio_snapshot') or {},
                'snapshot_documento': compatibilidade.get('documento_snapshot') or {},
                'campos_herdados_oficio': sync_result['campos_herdados_oficio'],
                'campos_herdados_documento': sync_result['campos_herdados_documento'],
                'conflitos': sync_result['conflitos'],
                'observacoes': compatibilidade.get('observacoes') or [],
            },
        )
    return {
        'ok': True,
        'compatibilidade': compatibilidade,
        'link': link,
        'sync': sync_result,
    }


def documentos_vinculados_oficio(oficio):
    itens = []
    if not oficio.pk:
        return itens

    links = oficio.documentos_vinculados.select_related('content_type').order_by('pk')
    for link in links:
        documento = getattr(link, 'documento', None)
        if documento is None:
            continue
        compatibilidade = {
            'tipo_documento': link.tipo_documento,
            'documento_label': link.documento_rotulo,
            'status': link.status_compatibilidade,
            'compativel': link.status_compatibilidade == OficioDocumentoVinculo.STATUS_COMPATIVEL,
            'conflitos': link.conflitos,
            'observacoes': link.observacoes,
            'oficio_snapshot': link.snapshot_oficio,
            'documento_snapshot': link.snapshot_documento,
            'campos_herdaveis_do_oficio_para_documento': link.campos_herdados_oficio,
            'campos_herdaveis_do_documento_para_oficio': link.campos_herdados_documento,
        }
        itens.append(_serialize_link_item(oficio, documento, compatibilidade=compatibilidade, origem='vinculo', link=link))

    existentes = {_link_pair_signature(item['tipo_documento'], item['documento_id']) for item in itens}

    legados = []
    if oficio.roteiro_evento_id and oficio.roteiro_evento:
        legados.append(('roteiro', oficio.roteiro_evento))
    try:
        justificativa = oficio.justificativa
    except Justificativa.DoesNotExist:
        justificativa = None
    if justificativa is not None:
        legados.append(('justificativa', justificativa))

    for tipo_documento, documento in legados:
        assinatura = _link_pair_signature(tipo_documento, documento.pk)
        if assinatura in existentes:
            continue
        compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, documento)
        itens.append(_serialize_link_item(oficio, documento, compatibilidade=compatibilidade, origem='legado'))

    for plano in oficio.planos_trabalho.select_related('evento', 'roteiro').order_by('pk'):
        assinatura = _link_pair_signature('plano_trabalho', plano.pk)
        if assinatura in existentes:
            continue
        compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, plano)
        itens.append(_serialize_link_item(oficio, plano, compatibilidade=compatibilidade, origem='legado'))

    for ordem in oficio.ordens_servico.select_related('evento').prefetch_related('viajantes').order_by('pk'):
        assinatura = _link_pair_signature('ordem_servico', ordem.pk)
        if assinatura in existentes:
            continue
        compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, ordem)
        itens.append(_serialize_link_item(oficio, ordem, compatibilidade=compatibilidade, origem='legado'))

    for termo in oficio.termos_autorizacao.select_related('evento', 'roteiro', 'viajante', 'veiculo').prefetch_related('oficios').order_by('pk'):
        assinatura = _link_pair_signature('termo_autorizacao', termo.pk)
        if assinatura in existentes:
            continue
        compatibilidade = avaliar_compatibilidade_oficio_documento(oficio, termo)
        itens.append(_serialize_link_item(oficio, termo, compatibilidade=compatibilidade, origem='legado'))

    return itens
