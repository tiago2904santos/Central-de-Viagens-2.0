from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from eventos.models import Evento, Oficio, OrdemServico, PlanoTrabalho, RoteiroEvento, TermoAutorizacao


@dataclass(frozen=True)
class ContextoDocumento:
    tipo: str
    origem: str  # direto | herdado
    id: int
    rotulo: str


def _oficio_rotulo(oficio: Oficio) -> str:
    return f"Ofício {oficio.numero_formatado or f'#{oficio.pk}'}"


def _evento_rotulo(evento: Evento) -> str:
    return evento.titulo or f"Evento #{evento.pk}"


def _push_unique(itens: list[ContextoDocumento], item: ContextoDocumento) -> None:
    signature = (item.tipo, item.id, item.origem)
    if any((v.tipo, v.id, v.origem) == signature for v in itens):
        return
    itens.append(item)


def resolver_vinculos_ordem_servico(ordem: OrdemServico) -> dict:
    diretos: list[ContextoDocumento] = []
    herdados: list[ContextoDocumento] = []

    if ordem.evento_id and ordem.evento:
        _push_unique(
            diretos,
            ContextoDocumento(
                tipo="evento",
                origem="direto",
                id=ordem.evento.pk,
                rotulo=_evento_rotulo(ordem.evento),
            ),
        )
        for oficio in ordem.evento.oficios.order_by("-updated_at", "-created_at"):
            _push_unique(
                herdados,
                ContextoDocumento(
                    tipo="oficio",
                    origem="herdado",
                    id=oficio.pk,
                    rotulo=_oficio_rotulo(oficio),
                ),
            )

    if ordem.oficio_id and ordem.oficio:
        _push_unique(
            diretos,
            ContextoDocumento(
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
                    ContextoDocumento(
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


def _coletar_documentos_compartilhando_evento(oficio: Oficio) -> tuple[list[ContextoDocumento], list[ContextoDocumento]]:
    """
    Documentos no mesmo evento que o ofício (sem vínculo lateral ofício↔documento).
    Diretos: referenciam este ofício. Herdados: mesmo evento, outro vínculo primário.
    """
    diretos: list[ContextoDocumento] = []
    herdados: list[ContextoDocumento] = []
    evento_ids = list(oficio.vinculos_evento.values_list("evento_id", flat=True))
    if not evento_ids:
        return diretos, herdados

    eventos = Evento.objects.filter(pk__in=evento_ids)
    for ev in eventos:
        for r in RoteiroEvento.objects.filter(evento=ev).order_by("-updated_at"):
            if oficio.roteiro_evento_id == r.pk:
                _push_unique(diretos, ContextoDocumento("roteiro", "direto", r.pk, str(r)))
            else:
                _push_unique(herdados, ContextoDocumento("roteiro", "herdado", r.pk, str(r)))
        for t in (
            TermoAutorizacao.objects.filter(termo_pai__isnull=True)
            .filter(Q(evento=ev) | Q(oficio=oficio) | Q(oficios=oficio))
            .distinct()
            .order_by("-updated_at")
        ):
            ligado_a_oficio = t.oficio_id == oficio.pk or t.oficios.filter(pk=oficio.pk).exists()
            if ligado_a_oficio:
                _push_unique(diretos, ContextoDocumento("termo", "direto", t.pk, t.titulo_display))
            else:
                _push_unique(herdados, ContextoDocumento("termo", "herdado", t.pk, t.titulo_display))
        for p in (
            PlanoTrabalho.objects.filter(Q(evento=ev) | Q(oficio=oficio) | Q(oficios=oficio))
            .distinct()
            .order_by("-updated_at")
        ):
            ligado_a_oficio = p.oficio_id == oficio.pk or p.oficios.filter(pk=oficio.pk).exists()
            if ligado_a_oficio:
                _push_unique(diretos, ContextoDocumento("plano_trabalho", "direto", p.pk, f"PT {p.numero_formatado}"))
            else:
                _push_unique(
                    herdados,
                    ContextoDocumento("plano_trabalho", "herdado", p.pk, f"PT {p.numero_formatado}"),
                )
        for o in (
            OrdemServico.objects.filter(Q(evento=ev) | Q(oficio=oficio)).distinct().order_by("-updated_at")
        ):
            if o.oficio_id == oficio.pk:
                _push_unique(diretos, ContextoDocumento("ordem_servico", "direto", o.pk, f"OS {o.numero_formatado}"))
            else:
                _push_unique(
                    herdados,
                    ContextoDocumento("ordem_servico", "herdado", o.pk, f"OS {o.numero_formatado} (via evento)"),
                )

    try:
        jus = oficio.justificativa
    except Exception:
        jus = None
    if jus:
        _push_unique(diretos, ContextoDocumento("justificativa", "direto", jus.pk, f"Justificativa #{jus.pk}"))

    return diretos, herdados


def resolver_vinculos_oficio(oficio: Oficio) -> dict:
    diretos: list[ContextoDocumento] = []
    herdados: list[ContextoDocumento] = []
    legado: list[ContextoDocumento] = []

    for link in oficio.vinculos_evento.select_related("evento").order_by("pk"):
        ev = link.evento
        _push_unique(
            diretos,
            ContextoDocumento(
                tipo="evento",
                origem="direto",
                id=ev.pk,
                rotulo=_evento_rotulo(ev),
            ),
        )

    doc_diretos, doc_herdados = _coletar_documentos_compartilhando_evento(oficio)
    for item in doc_diretos:
        _push_unique(diretos, item)
    for item in doc_herdados:
        _push_unique(herdados, item)

    return {"diretos": diretos, "herdados": herdados, "legado": legado}


def resolver_vinculos_plano_trabalho(plano: PlanoTrabalho) -> dict:
    diretos: list[ContextoDocumento] = []
    herdados: list[ContextoDocumento] = []
    contexto = plano.get_contexto_vinculo()
    oficios = contexto["oficios_auxiliares"]

    if contexto["evento_canonico"]:
        _push_unique(
            diretos,
            ContextoDocumento(
                "evento",
                "direto",
                contexto["evento_canonico"].pk,
                _evento_rotulo(contexto["evento_canonico"]),
            ),
        )

    for oficio in oficios:
        _push_unique(
            diretos,
            ContextoDocumento("oficio", "direto", oficio.pk, _oficio_rotulo(oficio)),
        )
        if not contexto["evento_canonico"]:
            for link in oficio.vinculos_evento.select_related("evento").order_by("pk"):
                ev = link.evento
                _push_unique(
                    herdados,
                    ContextoDocumento("evento", "herdado", ev.pk, _evento_rotulo(ev)),
                )

    if contexto["roteiro_auxiliar"]:
        _push_unique(
            diretos,
            ContextoDocumento(
                "roteiro",
                "direto",
                contexto["roteiro_auxiliar"].pk,
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
