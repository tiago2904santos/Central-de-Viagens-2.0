"""Snapshots documentais (períodos, destinos, equipe) para compatibilidade e resgate por evento.

Extraído do antigo módulo de vínculos ofício↔documento; permanece como base neutra
para heurísticas sem promover acoplamento lateral entre documentos.
"""
from __future__ import annotations

from datetime import date, datetime

from eventos.models import (
    Justificativa,
    Oficio,
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
    'oficio': 'Ofício',
}


def _clean_text(value):
    return str(value or '').strip()


def _unique_preserve(values):
    items = []
    seen = set()
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        items.append(value)
    return items


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


def periods_overlap(left: dict, right: dict) -> bool:
    """True se os intervalos [inicio,fim] ISO se intersectam (ou um lado vazio é tratado como wildcard fraco)."""
    a1, a2 = _period_bounds(left or {})
    b1, b2 = _period_bounds(right or {})
    if not a1 or not a2 or not b1 or not b2:
        return True
    return a1 <= b2 and b1 <= a2


def periods_strictly_disjoint(left: dict, right: dict) -> bool:
    a1, a2 = _period_bounds(left or {})
    b1, b2 = _period_bounds(right or {})
    if not a1 or not a2 or not b1 or not b2:
        return False
    return a2 < b1 or b2 < a1


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
    if getattr(oficio, 'evento_id', None):
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
    cidade_ids = []
    for trecho in oficio.trechos.all().order_by('ordem', 'pk'):
        if trecho.destino_cidade_id:
            cidade_ids.append(trecho.destino_cidade_id)
    cidade_ids = _normalize_ids(cidade_ids)
    return {
        'tipo': 'oficio',
        'label': f'Ofício {oficio.numero_formatado or f"#{oficio.pk}"}',
        'pk': oficio.pk,
        'evento_ids': _normalize_event_ids(oficio),
        'roteiro_id': oficio.roteiro_evento_id,
        'destinos': _locations_from_oficio(oficio),
        'cidade_ids_destino': cidade_ids,
        'periodo': _oficio_period(oficio),
        'viajantes_ids': _normalize_ids(oficio.viajantes.values_list('pk', flat=True)),
        'motorista_viajante_id': oficio.motorista_viajante_id,
        'motorista_nome': _clean_text(oficio.motorista),
        'veiculo_id': oficio.veiculo_id,
        'veiculo_placa': _clean_text(getattr(oficio, 'placa_formatada', '') or oficio.placa).upper(),
        'veiculo_modelo': _clean_text(oficio.modelo),
        'motivo': _clean_text(oficio.motivo),
        'quantidade_servidores': oficio.viajantes.count(),
        'quantidade_diarias': _clean_text(oficio.quantidade_diarias),
        'valor_diarias': _clean_text(oficio.valor_diarias),
        'valor_diarias_extenso': _clean_text(oficio.valor_diarias_extenso),
    }


def snapshot_roteiro(roteiro: RoteiroEvento) -> dict:
    destinos = []
    cidade_ids = []
    for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'pk'):
        cidade = _clean_text(getattr(destino.cidade, 'nome', '') if destino.cidade_id else '')
        estado = _clean_text(getattr(destino.estado, 'sigla', '') if destino.estado_id else '')
        if cidade and estado:
            destinos.append(f'{cidade}/{estado}'.upper())
        elif cidade:
            destinos.append(cidade.upper())
        elif estado:
            destinos.append(estado.upper())
        if destino.cidade_id:
            cidade_ids.append(destino.cidade_id)
    cidade_ids = _normalize_ids(cidade_ids)
    return {
        'tipo': 'roteiro',
        'label': f'Roteiro #{roteiro.pk}',
        'pk': roteiro.pk,
        'evento_ids': [roteiro.evento_id] if roteiro.evento_id else [],
        'roteiro_id': roteiro.pk,
        'destinos': _unique_preserve(destinos),
        'cidade_ids_destino': cidade_ids,
        'periodo': _roteiro_period(roteiro),
        'veiculo_id': None,
        'viajantes_ids': [],
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
        'cidade_ids_destino': oficio_snapshot.get('cidade_ids_destino') or [],
        'periodo': oficio_snapshot.get('periodo') or {'inicio': '', 'fim': ''},
    }


def snapshot_termo(termo: TermoAutorizacao) -> dict:
    oficio = termo.get_oficio_canonico()
    oficio_snapshot = snapshot_oficio(oficio) if oficio else {}
    destinos = _locations_from_text(termo.destino)
    if not destinos and oficio_snapshot:
        destinos = oficio_snapshot.get('destinos') or []
    cidade_ids = list(oficio_snapshot.get('cidade_ids_destino') or [])
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
        'cidade_ids_destino': _normalize_ids(cidade_ids),
        'periodo': _termo_period(termo),
        'viajantes_ids': viajantes_ids,
        'veiculo_id': termo.veiculo_id,
        'veiculo_placa': _clean_text(termo.veiculo_placa).upper(),
        'veiculo_modelo': _clean_text(termo.veiculo_modelo),
        'texto_destino': _clean_text(termo.destino),
    }


def snapshot_plano(plano: PlanoTrabalho) -> dict:
    oficio = plano.oficio if plano.oficio_id else None
    oficio_snapshot = snapshot_oficio(oficio) if oficio else {}
    destinos = []
    cidade_ids = []
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
        cid = item.get('cidade_id')
        if cid:
            try:
                cidade_ids.append(int(cid))
            except (TypeError, ValueError):
                pass
    if not destinos and oficio_snapshot:
        destinos = oficio_snapshot.get('destinos') or []
    if not cidade_ids and oficio_snapshot:
        cidade_ids = list(oficio_snapshot.get('cidade_ids_destino') or [])
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
        'cidade_ids_destino': _normalize_ids(cidade_ids),
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
    cidade_ids = []
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
        cid = item.get('cidade_id')
        if cid:
            try:
                cidade_ids.append(int(cid))
            except (TypeError, ValueError):
                pass
    if not destinos and oficio_snapshot:
        destinos = oficio_snapshot.get('destinos') or []
    if not cidade_ids and oficio_snapshot:
        cidade_ids = list(oficio_snapshot.get('cidade_ids_destino') or [])
    return {
        'tipo': 'ordem_servico',
        'label': ordem.numero_formatado or f'OS #{ordem.pk}',
        'pk': ordem.pk,
        'evento_ids': [ordem.evento_id] if ordem.evento_id else (oficio_snapshot.get('evento_ids') or []),
        'oficio_id': ordem.oficio_id,
        'destinos': destinos,
        'cidade_ids_destino': _normalize_ids(cidade_ids),
        'periodo': _ordem_period(ordem),
        'viajantes_ids': _normalize_ids(ordem.viajantes.values_list('pk', flat=True)),
        'modelo_motivo_id': ordem.modelo_motivo_id,
        'motivo': _clean_text(ordem.motivo_texto or ordem.finalidade),
        'finalidade': _clean_text(ordem.finalidade),
    }


def build_document_snapshot(documento) -> dict:
    if isinstance(documento, Oficio):
        return snapshot_oficio(documento)
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
    raise TypeError(f'Documento não suportado para snapshot: {type(documento)!r}')


def documento_tipo_slug(documento) -> str:
    snap = build_document_snapshot(documento)
    return snap.get('tipo') or 'documento'


def documento_label(documento, snapshot=None):
    snapshot = snapshot or build_document_snapshot(documento)
    return snapshot.get('label') or DOCUMENTO_LABELS.get(snapshot.get('tipo'), documento.__class__.__name__)
