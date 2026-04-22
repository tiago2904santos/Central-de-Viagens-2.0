"""
Configuracao extensivel da posicao da assinatura no PDF.

Hoje todos os tipos usam o mesmo layout (ultima pagina, canto inferior direito).
Para novos tipos (TermoAutorizacao, Oficio, ...), acrescente entradas em LAYOUT_POR_TIPO.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssinaturaLayoutRect:
    """page_index < 0 significa 'ultima pagina' (ex.: -1)."""

    page_index: int
    margin: float
    height_ratio: float
    aspect: float


_DEFAULT = AssinaturaLayoutRect(page_index=-1, margin=36.0, height_ratio=0.15, aspect=3.0)

# Chaves em minusculo: mesmo formato que documento_tipo em criar_pedido_assinatura.
LAYOUT_POR_TIPO: dict[str, AssinaturaLayoutRect] = {
    "eventos.oficio": _DEFAULT,
    "eventos.justificativa": _DEFAULT,
    "eventos.planotrabalho": _DEFAULT,
    "eventos.ordemservico": _DEFAULT,
    "eventos.termoautorizacao": _DEFAULT,
}


def resolver_layout_assinatura(documento_tipo: str) -> AssinaturaLayoutRect:
    key = (documento_tipo or "").strip().lower()
    return LAYOUT_POR_TIPO.get(key, _DEFAULT)
