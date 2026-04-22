"""Sincronização de assinatura com alterações do documento."""
from __future__ import annotations

import hashlib

from django.db import transaction
from django.utils import timezone

from assinaturas.models import AssinaturaDocumento
from assinaturas.services.documento_pdf_gerador import gerar_pdf_bytes_para_assinatura


class DocumentoBloqueadoPorAssinatura(Exception):
    """Compat legado: não deve mais ser disparada para edição."""


def assinatura_concluida_para(documento_tipo: str, documento_id: int | None) -> bool:
    if not documento_id:
        return False
    tipo = (documento_tipo or "").strip()
    return AssinaturaDocumento.objects.filter(
        documento_tipo__iexact=tipo,
        documento_id=int(documento_id),
        status=AssinaturaDocumento.Status.CONCLUIDO,
    ).exists()


def invalidar_assinaturas_por_alteracao(documento_tipo: str, documento_id: int | None) -> int:
    """
    Invalida pedidos apenas quando o PDF canônico atual diverge da versão congelada.
    Mantém histórico (não remove registros), apenas altera o status vigente.
    """
    if not documento_id:
        return 0
    tipo = (documento_tipo or "").strip()
    qs = AssinaturaDocumento.objects.filter(
        documento_tipo__iexact=tipo,
        documento_id=int(documento_id),
        status__in=[
            AssinaturaDocumento.Status.PENDENTE,
            AssinaturaDocumento.Status.PARCIAL,
            AssinaturaDocumento.Status.CONCLUIDO,
        ],
    )
    if not qs.exists():
        return 0

    try:
        pdf_canonico_atual = gerar_pdf_bytes_para_assinatura(tipo, int(documento_id))
    except Exception:
        # Sem PDF canônico não há base segura para invalidar.
        return 0
    if not pdf_canonico_atual.startswith(b"%PDF"):
        return 0
    hash_atual = hashlib.sha256(pdf_canonico_atual).hexdigest()

    now = timezone.now()
    total = 0
    with transaction.atomic():
        for pedido in qs.select_for_update():
            if pedido.status == AssinaturaDocumento.Status.INVALIDADO_ALTERACAO:
                continue
            hash_referencia = (pedido.arquivo_original_sha256 or "").strip().lower()
            if hash_referencia and hash_referencia == hash_atual:
                continue
            pedido.status = AssinaturaDocumento.Status.INVALIDADO_ALTERACAO
            pedido.invalidado_em = now
            pedido.invalidado_motivo = "Documento alterado com impacto no PDF canônico."
            pedido.save(update_fields=["status", "invalidado_em", "invalidado_motivo"])
            total += 1
    return total


def garantir_documento_editavel(documento_tipo: str, documento_id: int | None) -> None:
    # Edição sempre permitida, com sincronização por hash do PDF canônico.
    invalidar_assinaturas_por_alteracao(documento_tipo, documento_id)
