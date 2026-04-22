"""Estado do link de assinatura (etapa ou pedido legado)."""
from __future__ import annotations

from django.utils import timezone

from assinaturas.models import AssinaturaDocumento, AssinaturaEtapa


class EstadoLinkAssinatura:
    VALIDO = "valido"
    EXPIRADO = "expirado"
    JA_ASSINADO = "ja_assinado"
    INVALIDO = "invalido"


def estado_pedido_assinatura(assin: AssinaturaDocumento) -> str:
    """
    Estado agregado do pedido (para UI de resumo).
    """
    st = (assin.status or "").strip().lower()
    if st in (AssinaturaDocumento.Status.CONCLUIDO, "assinado"):
        return EstadoLinkAssinatura.JA_ASSINADO
    if st == AssinaturaDocumento.Status.INVALIDADO_ALTERACAO:
        return EstadoLinkAssinatura.INVALIDO
    if st not in (AssinaturaDocumento.Status.PENDENTE, AssinaturaDocumento.Status.PARCIAL):
        return EstadoLinkAssinatura.INVALIDO
    exp = getattr(assin, "expires_at", None)
    if exp and timezone.now() > exp:
        return EstadoLinkAssinatura.EXPIRADO
    return EstadoLinkAssinatura.VALIDO


def estado_etapa_assinatura(etapa: AssinaturaEtapa) -> str:
    """Estado do link de uma etapa."""
    if etapa.status == AssinaturaEtapa.Status.ASSINADO:
        return EstadoLinkAssinatura.JA_ASSINADO
    exp = etapa.expires_at or etapa.assinatura.expires_at
    if exp and timezone.now() > exp:
        return EstadoLinkAssinatura.EXPIRADO
    assin = etapa.assinatura
    st_parent = (assin.status or "").strip().lower()
    if st_parent == AssinaturaDocumento.Status.INVALIDADO_ALTERACAO:
        return EstadoLinkAssinatura.INVALIDO
    if st_parent in (
        AssinaturaDocumento.Status.CONCLUIDO,
        "concluido",
        "assinado",
    ):
        return EstadoLinkAssinatura.JA_ASSINADO
    # bloqueio: etapas anteriores devem estar assinadas
    bloqueada = (
        AssinaturaEtapa.objects.filter(assinatura=assin, ordem__lt=etapa.ordem)
        .exclude(status=AssinaturaEtapa.Status.ASSINADO)
        .exists()
    )
    if bloqueada:
        return EstadoLinkAssinatura.INVALIDO
    return EstadoLinkAssinatura.VALIDO
