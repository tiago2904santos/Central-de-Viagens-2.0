"""Agregação de documentos por evento (pacote documental único)."""
from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from eventos.models import (
    Evento,
    EventoDocumentoSugestao,
    EventoResgateAuditoria,
    Justificativa,
    Oficio,
    OrdemServico,
    PlanoTrabalho,
    RoteiroEvento,
    TermoAutorizacao,
)


def _item_doc(titulo, url, badge, origem: str):
    return {'titulo': titulo, 'url': url, 'badge_label': badge, 'origem': origem}


def build_evento_document_pacote(evento: Evento) -> dict:
    """
    Lista documentos do evento por tipo, com origem aproximada (fluxo, resgate ou indireto).
    `origem`: `evento_direto` | `via_oficio` | `sugestao_pendente` (apenas metadado em outra lista).
    """
    oficios = list(evento.oficios.order_by('-updated_at', '-created_at'))
    roteiros = list(evento.roteiros.order_by('-updated_at', '-created_at'))
    planos = list(
        PlanoTrabalho.objects.filter(
            Q(evento_id=evento.pk) | Q(oficio__eventos=evento.pk) | Q(oficios__eventos=evento.pk)
        )
        .distinct()
        .order_by('-updated_at', '-created_at')
    )
    ordens = list(
        OrdemServico.objects.filter(Q(evento_id=evento.pk) | Q(oficio__eventos=evento.pk))
        .distinct()
        .order_by('-updated_at', '-created_at')
    )
    termos = list(
        TermoAutorizacao.objects.filter(termo_pai__isnull=True)
        .filter(Q(evento_id=evento.pk) | Q(oficio__eventos=evento.pk) | Q(oficios__eventos=evento.pk))
        .distinct()
        .order_by('-updated_at', '-created_at')
    )

    justificativas = []
    for oficio in oficios:
        try:
            j = oficio.justificativa
        except Justificativa.DoesNotExist:
            continue
        if j:
            justificativas.append(j)

    def origem_plano(p: PlanoTrabalho) -> str:
        if p.evento_id == evento.pk:
            return 'evento_direto'
        return 'via_oficio'

    def origem_ordem(o: OrdemServico) -> str:
        if o.evento_id == evento.pk:
            return 'evento_direto'
        return 'via_oficio'

    def origem_termo(t: TermoAutorizacao) -> str:
        if t.evento_id == evento.pk:
            return 'evento_direto'
        return 'via_oficio'

    sections = [
        {
            'key': 'oficios',
            'title': 'Ofícios',
            'items': [
                _item_doc(
                    f'Ofício {o.numero_formatado or f"#{o.pk}"}',
                    reverse('eventos:oficio-step1', kwargs={'pk': o.pk}),
                    o.get_status_display(),
                    'evento_direto',
                )
                for o in oficios
            ],
        },
        {
            'key': 'roteiros',
            'title': 'Roteiros',
            'items': [
                _item_doc(
                    str(r),
                    reverse('eventos:roteiro-avulso-editar', kwargs={'pk': r.pk}),
                    r.get_status_display(),
                    'evento_direto',
                )
                for r in roteiros
            ],
        },
        {
            'key': 'termos',
            'title': 'Termos de autorização',
            'items': [
                _item_doc(
                    t.titulo_display,
                    reverse('eventos:documentos-termos-detalhe', kwargs={'pk': t.pk}),
                    t.get_status_display(),
                    origem_termo(t),
                )
                for t in termos
            ],
        },
        {
            'key': 'justificativas',
            'title': 'Justificativas (via ofício)',
            'items': [
                _item_doc(
                    f'Justificativa #{j.pk}',
                    reverse('eventos:oficio-justificativa', kwargs={'pk': j.oficio_id}),
                    '—',
                    'via_oficio',
                )
                for j in justificativas
            ],
        },
        {
            'key': 'planos',
            'title': 'Planos de trabalho',
            'items': [
                _item_doc(
                    f'PT {p.numero_formatado or f"#{p.pk}"}',
                    reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': p.pk}),
                    p.get_status_display(),
                    origem_plano(p),
                )
                for p in planos
            ],
        },
        {
            'key': 'ordens',
            'title': 'Ordens de serviço',
            'items': [
                _item_doc(
                    f'OS {o.numero_formatado or f"#{o.pk}"}',
                    reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': o.pk}),
                    o.get_status_display(),
                    origem_ordem(o),
                )
                for o in ordens
            ],
        },
    ]

    sugestoes = list(
        EventoDocumentoSugestao.objects.filter(status=EventoDocumentoSugestao.STATUS_PENDENTE)
        .select_related('content_type')
        .order_by('-updated_at')[:20]
    )
    resgates = list(
        EventoResgateAuditoria.objects.filter(evento=evento)
        .select_related('content_type')
        .order_by('-created_at')[:15]
    )
    return {'sections': sections, 'sugestoes_globais': sugestoes, 'resgates_evento': resgates}
