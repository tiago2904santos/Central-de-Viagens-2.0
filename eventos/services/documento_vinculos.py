from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q

from eventos.models import Evento, Oficio, OrdemServico, PlanoTrabalho


@dataclass(frozen=True)
class VinculoDocumento:
    tipo: str
    origem: str  # direto | herdado | legado
    id: int
    rotulo: str


def _oficio_rotulo(oficio: Oficio) -> str:
    return f"Ofício {oficio.numero_formatado or f'#{oficio.pk}'}"


def _evento_rotulo(evento: Evento) -> str:
    return evento.titulo or f"Evento #{evento.pk}"


def _push_unique(itens: list[VinculoDocumento], item: VinculoDocumento) -> None:
    signature = (item.tipo, item.id, item.origem)
    if any((v.tipo, v.id, v.origem) == signature for v in itens):
        return
    itens.append(item)


def resolver_vinculos_ordem_servico(ordem: OrdemServico) -> dict:
    diretos: list[VinculoDocumento] = []
    herdados: list[VinculoDocumento] = []

    if ordem.evento_id and ordem.evento:
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="evento",
                origem="direto",
                id=ordem.evento.pk,
                rotulo=_evento_rotulo(ordem.evento),
            ),
        )
        for oficio in ordem.evento.oficios.order_by("-updated_at", "-created_at"):
            _push_unique(
                herdados,
                VinculoDocumento(
                    tipo="oficio",
                    origem="herdado",
                    id=oficio.pk,
                    rotulo=_oficio_rotulo(oficio),
                ),
            )

    if ordem.oficio_id and ordem.oficio:
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="oficio",
                origem="direto",
                id=ordem.oficio.pk,
                rotulo=_oficio_rotulo(ordem.oficio),
            ),
        )
        if not ordem.evento_id:
            ev_of = ordem.oficio.get_evento_principal()
            if ev_of:
                _push_unique(
                    herdados,
                    VinculoDocumento(
                        tipo="evento",
                        origem="herdado",
                        id=ev_of.pk,
                        rotulo=_evento_rotulo(ev_of),
                    ),
                )

    oficios_herdados_ids = [v.id for v in herdados if v.tipo == "oficio"]
    oficios_diretos_ids = [v.id for v in diretos if v.tipo == "oficio"]
    return {
        "diretos": diretos,
        "herdados": herdados,
        "oficios_herdados_ids": oficios_herdados_ids,
        "oficios_diretos_ids": oficios_diretos_ids,
    }


def resolver_vinculos_oficio(oficio: Oficio) -> dict:
    diretos: list[VinculoDocumento] = []
    herdados: list[VinculoDocumento] = []
    legado: list[VinculoDocumento] = []

    for link in oficio.vinculos_evento.select_related('evento').order_by('pk'):
        ev = link.evento
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="evento",
                origem="direto",
                id=ev.pk,
                rotulo=_evento_rotulo(ev),
            ),
        )

    for plano in (
        PlanoTrabalho.objects.filter(Q(oficio=oficio) | Q(oficios=oficio))
        .distinct()
        .order_by('-updated_at', '-created_at')
    ):
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="plano_trabalho",
                origem="direto",
                id=plano.pk,
                rotulo=f'PT {plano.numero_formatado or f"#{plano.pk}"}',
            ),
        )

    for os in OrdemServico.objects.filter(oficio=oficio).order_by('-updated_at', '-created_at'):
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="ordem_servico",
                origem="direto",
                id=os.pk,
                rotulo=f'OS {os.numero_formatado or f"#{os.pk}"}',
            ),
        )

    for link in oficio.vinculos_evento.select_related('evento').order_by('pk'):
        ev = link.evento
        for os in ev.ordens_servico.order_by('-updated_at', '-created_at'):
            if os.oficio_id == oficio.pk:
                continue
            _push_unique(
                herdados,
                VinculoDocumento(
                    tipo="ordem_servico",
                    origem="herdado",
                    id=os.pk,
                    rotulo=f'OS {getattr(os, "numero_formatado", "") or f"#{os.pk}"} (via evento)',
                ),
            )

    justificativa = getattr(oficio, "justificativa", None)
    if justificativa and justificativa.pk:
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="justificativa",
                origem="direto",
                id=justificativa.pk,
                rotulo=f"Justificativa #{justificativa.pk}",
            ),
        )

    termos_diretos = list(oficio.termos_autorizacao.order_by("-updated_at", "-created_at"))
    for termo in termos_diretos:
        _push_unique(
            diretos,
            VinculoDocumento(
                tipo="termo",
                origem="direto",
                id=termo.pk,
                rotulo=termo.numero_formatado,
            ),
        )

    termos_legado = list(oficio.termos_autorizacao_relacionados.exclude(oficio_id=oficio.pk).order_by("-updated_at", "-created_at"))
    for termo in termos_legado:
        _push_unique(
            legado,
            VinculoDocumento(
                tipo="termo",
                origem="legado",
                id=termo.pk,
                rotulo=termo.numero_formatado,
            ),
        )

    return {"diretos": diretos, "herdados": herdados, "legado": legado}


def resolver_vinculos_plano_trabalho(plano: PlanoTrabalho) -> dict:
    diretos: list[VinculoDocumento] = []
    herdados: list[VinculoDocumento] = []
    contexto = plano.get_contexto_vinculo()
    oficios = contexto['oficios_auxiliares']

    if contexto['evento_canonico']:
        _push_unique(
            diretos,
            VinculoDocumento(
                "evento",
                "direto",
                contexto['evento_canonico'].pk,
                _evento_rotulo(contexto['evento_canonico']),
            ),
        )

    for oficio in oficios:
        _push_unique(
            diretos,
            VinculoDocumento("oficio", "direto", oficio.pk, _oficio_rotulo(oficio)),
        )
        if not contexto['evento_canonico']:
            for link in oficio.vinculos_evento.select_related('evento').order_by('pk'):
                ev = link.evento
                _push_unique(
                    herdados,
                    VinculoDocumento("evento", "herdado", ev.pk, _evento_rotulo(ev)),
                )

    if contexto['roteiro_auxiliar']:
        _push_unique(
            diretos,
            VinculoDocumento(
                "roteiro",
                "direto",
                contexto['roteiro_auxiliar'].pk,
                f"Roteiro #{contexto['roteiro_auxiliar'].pk}",
            ),
        )

    return {"diretos": diretos, "herdados": herdados}


def resolver_vinculos_evento(evento: Evento) -> dict:
    return {
        "oficios": list(evento.oficios.order_by("-updated_at", "-created_at")),
        "roteiros": list(evento.roteiros.order_by("-updated_at", "-created_at")),
        "planos": list(evento.planos_trabalho.order_by("-updated_at", "-created_at")),
        "ordens": list(evento.ordens_servico.order_by("-updated_at", "-created_at")),
    }
