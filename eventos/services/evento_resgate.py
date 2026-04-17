"""
Resgate seguro de documentos avulsos para eventos compatíveis.

O evento é o agregador oficial; não há vínculo lateral documento↔documento.
Associação automática só com candidato claro; ambiguidade vira sugestão auditável.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from eventos.models import (
    Evento,
    EventoDocumentoSugestao,
    EventoResgateAuditoria,
    Oficio,
    OficioEventoVinculo,
    OrdemServico,
    PlanoTrabalho,
    RoteiroEvento,
    TermoAutorizacao,
)
from eventos.services.documento_snapshots import (
    build_document_snapshot,
    periods_overlap,
    periods_strictly_disjoint,
)


@dataclass
class CandidatoEvento:
    evento: Evento
    score: int
    signals: list[str]


def _parse_iso_date(value: str) -> date | None:
    if not value or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _evento_cidade_ids(evento: Evento) -> set[int]:
    ids: set[int] = set()
    for destino in evento.destinos.all().only('cidade_id'):
        if destino.cidade_id:
            ids.add(destino.cidade_id)
    for attr in ('cidade_principal_id', 'cidade_base_id'):
        cid = getattr(evento, attr, None)
        if cid:
            ids.add(cid)
    return ids


def _evento_periodo_dict(evento: Evento) -> dict:
    ini = evento.data_inicio.isoformat() if evento.data_inicio else ''
    fim = evento.data_fim.isoformat() if evento.data_fim else ini
    return {'inicio': ini, 'fim': fim}


def _evento_viajante_ids(evento: Evento) -> set[int]:
    return set(evento.participantes.values_list('viajante_id', flat=True))


def _documento_ja_tem_evento_exclusivo(documento, snapshot: dict) -> bool:
    eids = [int(x) for x in (snapshot.get('evento_ids') or []) if x]
    if eids:
        return True
    if snapshot.get('tipo') == 'oficio' and isinstance(documento, Oficio):
        return documento.vinculos_evento.exists()
    if snapshot.get('oficio_id'):
        oficio = getattr(documento, 'oficio', None)
        if oficio and oficio.pk and oficio.get_evento_principal():
            return True
    return False


def _score_documento_evento(documento, snapshot: dict, evento: Evento) -> tuple[int, list[str]]:
    signals: list[str] = []
    score = 0
    ev_cidades = _evento_cidade_ids(evento)
    doc_cidades = {int(x) for x in (snapshot.get('cidade_ids_destino') or []) if x}
    if ev_cidades and doc_cidades and ev_cidades.intersection(doc_cidades):
        score += 45
        signals.append('destino_cidade_coincidente')
    elif ev_cidades and snapshot.get('destinos'):
        labels_doc = {d for d in (snapshot.get('destinos') or [])}
        for ed in evento.destinos.select_related('cidade', 'estado').all():
            if not ed.cidade_id:
                continue
            uf = (ed.estado.sigla if ed.estado_id else '').strip().upper()
            nome = (ed.cidade.nome or '').strip().upper()
            label = f'{nome}/{uf}' if uf else nome
            if label and label in labels_doc:
                score += 40
                signals.append('destino_label_coincidente')
                break

    ev_periodo = _evento_periodo_dict(evento)
    doc_periodo = snapshot.get('periodo') or {}
    if periods_strictly_disjoint(ev_periodo, doc_periodo):
        return 0, ['conflito_periodo_estrito']
    if periods_overlap(ev_periodo, doc_periodo):
        score += 35
        signals.append('periodo_sobreposto')

    ev_viajantes = _evento_viajante_ids(evento)
    doc_viajantes = {int(x) for x in (snapshot.get('viajantes_ids') or []) if x}
    if ev_viajantes and doc_viajantes and ev_viajantes.intersection(doc_viajantes):
        score += 20
        signals.append('equipe_sobreposicao')

    if getattr(evento, 'veiculo_id', None) and snapshot.get('veiculo_id'):
        if evento.veiculo_id == snapshot.get('veiculo_id'):
            score += 8
            signals.append('mesma_viatura')

    if getattr(evento, 'motorista_id', None) and snapshot.get('motorista_viajante_id'):
        if evento.motorista_id == snapshot.get('motorista_viajante_id'):
            score += 8
            signals.append('mesmo_motorista')

    return score, signals


def _listar_eventos_candidatos(snapshot: dict) -> list[Evento]:
    ini_s = (snapshot.get('periodo') or {}).get('inicio') or ''
    fim_s = (snapshot.get('periodo') or {}).get('fim') or ini_s
    ini_d = _parse_iso_date(ini_s)
    fim_d = _parse_iso_date(fim_s) or ini_d
    qs = Evento.objects.all()
    if ini_d and fim_d:
        qs = qs.filter(data_fim__gte=ini_d, data_inicio__lte=fim_d)
    return list(qs.select_related('cidade_principal', 'cidade_base').prefetch_related('destinos')[:50])


def list_candidate_events_for_document(documento) -> list[CandidatoEvento]:
    snapshot = build_document_snapshot(documento)
    if _documento_ja_tem_evento_exclusivo(documento, snapshot):
        return []
    candidatos: list[CandidatoEvento] = []
    for evento in _listar_eventos_candidatos(snapshot):
        score, signals = _score_documento_evento(documento, snapshot, evento)
        if score <= 0 or 'conflito_periodo_estrito' in signals:
            continue
        if score < 55:
            continue
        candidatos.append(CandidatoEvento(evento=evento, score=score, signals=signals))
    candidatos.sort(key=lambda c: (-c.score, c.evento.pk))
    return candidatos


def _decisao_auto(candidatos: list[CandidatoEvento]) -> tuple[bool, str]:
    if not candidatos:
        return False, 'sem_candidato'
    best = candidatos[0]
    second_score = candidatos[1].score if len(candidatos) > 1 else -1
    if best.score >= 78 and (second_score < 45 or best.score - second_score >= 22):
        return True, 'candidato_unico_forte'
    if len(candidatos) == 1 and best.score >= 70:
        return True, 'unico_candidato_medio_forte'
    if len(candidatos) >= 2 and abs(best.score - second_score) < 12 and best.score >= 60:
        return False, 'ambiguidade'
    if len(candidatos) >= 2 and second_score >= 58:
        return False, 'multiplos_fortes'
    return False, 'confianca_insuficiente'


def _registrar_auditoria(*, acao: str, documento, evento: Evento | None, detalhes: dict[str, Any]) -> None:
    ct = ContentType.objects.get_for_model(documento.__class__)
    EventoResgateAuditoria.objects.create(
        acao=acao,
        content_type=ct,
        object_id=documento.pk,
        evento=evento,
        detalhes=detalhes,
    )


def _registrar_sugestao(documento, candidatos: list[CandidatoEvento], motivo: str) -> None:
    ct = ContentType.objects.get_for_model(documento.__class__)
    payload = {
        'motivo': motivo,
        'candidates': [
            {'evento_id': c.evento.pk, 'score': c.score, 'signals': c.signals}
            for c in candidatos[:6]
        ],
    }
    EventoDocumentoSugestao.objects.update_or_create(
        content_type=ct,
        object_id=documento.pk,
        defaults={'payload': payload, 'status': EventoDocumentoSugestao.STATUS_PENDENTE},
    )


def _limpar_sugestao_pendente(documento) -> None:
    ct = ContentType.objects.get_for_model(documento.__class__)
    EventoDocumentoSugestao.objects.filter(content_type=ct, object_id=documento.pk).delete()


def _anexar_documento_ao_evento(documento, evento: Evento) -> None:
    if isinstance(documento, Oficio):
        if not documento.esta_vinculado_a_evento(evento):
            documento.eventos.add(evento)
        return
    if isinstance(documento, RoteiroEvento):
        documento.evento = evento
        documento.tipo = RoteiroEvento.TIPO_EVENTO
        documento.save(update_fields=['evento', 'tipo', 'updated_at'])
        return
    if isinstance(documento, (PlanoTrabalho, OrdemServico, TermoAutorizacao)):
        documento.evento = evento
        documento.save(update_fields=['evento', 'updated_at'])
        return
    raise TypeError(type(documento))


def auto_attach_document_to_event_if_safe(documento) -> dict[str, Any]:
    snapshot = build_document_snapshot(documento)
    if _documento_ja_tem_evento_exclusivo(documento, snapshot):
        _limpar_sugestao_pendente(documento)
        return {'ok': True, 'skipped': True, 'reason': 'ja_vinculado'}

    candidatos = list_candidate_events_for_document(documento)
    pode_auto, motivo = _decisao_auto(candidatos)

    if pode_auto and candidatos:
        evento = candidatos[0].evento
        with transaction.atomic():
            _anexar_documento_ao_evento(documento, evento)
            _registrar_auditoria(
                acao=EventoResgateAuditoria.ACAO_AUTO_ANEXOU,
                documento=documento,
                evento=evento,
                detalhes={'score': candidatos[0].score, 'signals': candidatos[0].signals, 'regra': motivo},
            )
        _limpar_sugestao_pendente(documento)
        return {'ok': True, 'attached': True, 'evento_id': evento.pk, 'regra': motivo}

    if len(candidatos) >= 2 and motivo in ('ambiguidade', 'multiplos_fortes'):
        _registrar_sugestao(documento, candidatos, motivo)
        _registrar_auditoria(
            acao=EventoResgateAuditoria.ACAO_SUGESTAO,
            documento=documento,
            evento=None,
            detalhes={'motivo': motivo, 'top': [{'id': c.evento.pk, 'score': c.score} for c in candidatos[:4]]},
        )
        return {'ok': True, 'suggestion': True, 'reason': motivo}

    if candidatos and motivo == 'confianca_insuficiente':
        _registrar_auditoria(
            acao=EventoResgateAuditoria.ACAO_IGNOROU_BAIXA_CONFIANCA,
            documento=documento,
            evento=None,
            detalhes={'motivo': motivo, 'best': candidatos[0].score},
        )
        return {'ok': True, 'ignored': True, 'reason': motivo}

    _registrar_auditoria(
        acao=EventoResgateAuditoria.ACAO_SEM_CANDIDATO,
        documento=documento,
        evento=None,
        detalhes={'motivo': motivo},
    )
    return {'ok': True, 'noop': True, 'reason': motivo}


def _oficios_sem_vinculo_evento():
    vinculados = OficioEventoVinculo.objects.values_list('oficio_id', flat=True)
    return Oficio.objects.exclude(pk__in=vinculados).filter(tipo_origem=Oficio.ORIGEM_AVULSO)


def resgatar_documentos_orfaos_para_evento(evento: Evento) -> dict[str, int]:
    """Após salvar evento: tenta anexar documentos avulsos claramente compatíveis com este evento."""
    stats = {'auto': 0, 'sugestao': 0, 'ignorados': 0}

    def processar(qs):
        nonlocal stats
        for doc in qs.order_by('-pk')[:100]:
            snap = build_document_snapshot(doc)
            if _documento_ja_tem_evento_exclusivo(doc, snap):
                continue
            cands = list_candidate_events_for_document(doc)
            foco = [c for c in cands if c.evento.pk == evento.pk]
            if not foco:
                continue
            ordenado = foco + [c for c in cands if c.evento.pk != evento.pk]
            pode, motivo = _decisao_auto(ordenado)
            if pode and ordenado[0].evento.pk == evento.pk:
                with transaction.atomic():
                    _anexar_documento_ao_evento(doc, evento)
                    _registrar_auditoria(
                        acao=EventoResgateAuditoria.ACAO_AUTO_ANEXOU,
                        documento=doc,
                        evento=evento,
                        detalhes={'contexto': 'pos_evento', 'regra': motivo, 'score': ordenado[0].score},
                    )
                stats['auto'] += 1
            elif len([c for c in cands if c.score >= 58]) >= 2:
                _registrar_sugestao(doc, cands, 'ambiguidade_pos_evento')
                stats['sugestao'] += 1
            else:
                stats['ignorados'] += 1

    processar(_oficios_sem_vinculo_evento())
    processar(RoteiroEvento.objects.filter(evento__isnull=True, tipo=RoteiroEvento.TIPO_AVULSO))
    processar(PlanoTrabalho.objects.filter(evento__isnull=True, oficio__isnull=True))
    processar(OrdemServico.objects.filter(evento__isnull=True, oficio__isnull=True))
    processar(
        TermoAutorizacao.objects.filter(
            evento__isnull=True,
            termo_pai__isnull=True,
            oficio__isnull=True,
        )
    )
    return stats


def tentar_resgatar_documento(documento) -> None:
    try:
        auto_attach_document_to_event_if_safe(documento)
    except Exception:
        pass
