"""Leitura do servidor padrao de assinatura por tipo (ConfiguracaoSistema / AssinaturaConfiguracao)."""
from __future__ import annotations

from cadastros.models import AssinaturaConfiguracao, ConfiguracaoSistema


def get_viajante_assinatura_padrao(tipo: str) -> tuple[object | None, str]:
    """
    Devolve (viajante|None, nome_para_exibicao).
    tipo: AssinaturaConfiguracao.TIPO_*.
    """
    config = ConfiguracaoSistema.get_singleton()
    rec = (
        AssinaturaConfiguracao.objects.select_related("viajante", "viajante__cargo")
        .filter(configuracao=config, tipo=tipo, ordem=1, ativo=True)
        .first()
    )
    if rec and rec.viajante_id:
        v = rec.viajante
        nome = (getattr(v, "nome", "") or "").strip()
        return v, nome or f"Viajante #{v.pk}"
    return None, ""
