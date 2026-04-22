"""Contexto para UI administrativa (resumo de pedido e links por etapa)."""
from __future__ import annotations

from django.urls import reverse

from assinaturas.models import AssinaturaDocumento, AssinaturaEtapa
from assinaturas.services.assinatura_estado import (
    EstadoLinkAssinatura,
    estado_etapa_assinatura,
    estado_pedido_assinatura,
)


def resumo_assinatura_para_template(request, documento_tipo: str, documento_id: int) -> dict:
    tipo = (documento_tipo or "").strip()
    pedido = (
        AssinaturaDocumento.objects.filter(documento_tipo__iexact=tipo, documento_id=documento_id)
        .prefetch_related("etapas")
        .order_by("-id")
        .first()
    )
    out: dict = {
        "pedido": pedido,
        "etapas_rows": [],
        "estado_pedido": None,
        "estado_pedido_codigo": "",
        "estado_pedido_label": "",
        "criar_pedido_url": reverse("assinaturas:pedido_criar"),
        "documento_tipo": tipo,
        "documento_id": documento_id,
        "next_url": request.get_full_path(),
    }
    if not pedido:
        out["estado_pedido_label"] = "Sem pedido de assinatura"
        return out

    out["url_verificacao"] = request.build_absolute_uri(
        reverse("assinaturas:verificar", kwargs={"token": str(pedido.verificacao_token)})
    )
    out["estado_pedido"] = estado_pedido_assinatura(pedido)
    out["estado_pedido_codigo"] = (pedido.status or "").strip().lower()
    st = out["estado_pedido_codigo"]
    if st in ("concluido", "assinado"):
        out["estado_pedido_label"] = "Concluído"
    elif st == "invalidado_alteracao":
        out["estado_pedido_label"] = "Invalidado por alteração"
    elif st == "parcial":
        out["estado_pedido_label"] = "Parcial (aguardando próximo assinante)"
    elif st == "pendente":
        out["estado_pedido_label"] = "Pendente"
    else:
        out["estado_pedido_label"] = pedido.get_status_display()

    rows = []
    for et in pedido.etapas.order_by("ordem"):
        est_link = estado_etapa_assinatura(et)
        link_assinar = ""
        if est_link == EstadoLinkAssinatura.VALIDO:
            link_assinar = request.build_absolute_uri(reverse("assinaturas:assinar", kwargs={"token": str(et.token)}))
        link_resultado = ""
        if et.status == AssinaturaEtapa.Status.ASSINADO:
            link_resultado = request.build_absolute_uri(
                reverse("assinaturas:resultado", kwargs={"token": str(et.token)})
            )
        rows.append(
            {
                "etapa": et,
                "estado_link": est_link,
                "link_assinar": link_assinar,
                "link_resultado": link_resultado,
                "pode_copiar_link": bool(link_assinar),
            }
        )
    out["etapas_rows"] = rows
    return out


def merge_assinatura_admin(request, context: dict, documento_tipo: str, documento_id: int) -> dict:
    new_ctx = dict(context)
    new_ctx["assinatura_admin"] = resumo_assinatura_para_template(request, documento_tipo, documento_id)
    return new_ctx
