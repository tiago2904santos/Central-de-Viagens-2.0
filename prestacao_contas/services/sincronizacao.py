from __future__ import annotations

from typing import List, Tuple

from django.db import transaction

from cadastros.models import Viajante
from eventos.models import Oficio
from prestacao_contas.models import PrestacaoConta


def _descricao_evento_oficio(oficio: Oficio) -> str:
    return (oficio.motivo or "").strip()


def _dados_servidor(servidor: Viajante) -> dict:
    return {
        "nome_servidor": (servidor.nome or "").strip(),
        "rg_servidor": getattr(servidor, "rg_formatado", "") or "",
        "cpf_servidor": getattr(servidor, "cpf_formatado", "") or "",
        "cargo_servidor": getattr(getattr(servidor, "cargo", None), "nome", "") or "",
    }


@transaction.atomic
def sincronizar_prestacoes_do_oficio(oficio: Oficio) -> List[Tuple[PrestacaoConta, bool]]:
    """
    Garante uma prestação individual por servidor do ofício.

    Regras:
    - idempotente por par (oficio, servidor), via get_or_create;
    - não remove prestações existentes quando um servidor sai do ofício;
    - preserva anexos/documentos já enviados.
    """
    resultados: List[Tuple[PrestacaoConta, bool]] = []
    servidores = list(
        oficio.viajantes.filter(status=Viajante.STATUS_FINALIZADO)
        .select_related("cargo", "unidade_lotacao")
        .order_by("nome", "id")
    )
    for servidor in servidores:
        prestacao, created = PrestacaoConta.objects.get_or_create(
            oficio=oficio,
            servidor=servidor,
            defaults={
                "status": PrestacaoConta.STATUS_EM_ANDAMENTO,
                "descricao_evento": _descricao_evento_oficio(oficio),
                **_dados_servidor(servidor),
            },
        )
        update_fields = []
        if not prestacao.descricao_evento:
            prestacao.descricao_evento = _descricao_evento_oficio(oficio)
            update_fields.append("descricao_evento")
        for field, value in _dados_servidor(servidor).items():
            if getattr(prestacao, field) != value:
                setattr(prestacao, field, value)
                update_fields.append(field)
        if prestacao.status == PrestacaoConta.STATUS_RASCUNHO:
            prestacao.status = PrestacaoConta.STATUS_EM_ANDAMENTO
            update_fields.append("status")
        if update_fields:
            prestacao.save(update_fields=[*update_fields, "updated_at"])
        resultados.append((prestacao, created))
    return resultados
