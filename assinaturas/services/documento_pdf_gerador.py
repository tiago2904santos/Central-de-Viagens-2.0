"""Gera bytes PDF para pedido de assinatura, reutilizando renderizadores do app eventos."""
from __future__ import annotations

from django.apps import apps

from eventos.services.documentos import render_document_bytes
from eventos.services.documentos.renderer import convert_docx_bytes_to_pdf_bytes
from eventos.services.documentos.termo_autorizacao import render_saved_termo_autorizacao_docx
from eventos.services.documentos.types import DocumentoFormato, DocumentoOficioTipo
from eventos.services.documentos.plano_trabalho import render_plano_trabalho_docx, render_plano_trabalho_model_docx
from eventos.services.documentos.ordem_servico import render_ordem_servico_docx, render_ordem_servico_model_docx

_DOC_KEYS = {
    "eventos.oficio": ("eventos", "Oficio"),
    "eventos.justificativa": ("eventos", "Justificativa"),
    "eventos.planotrabalho": ("eventos", "PlanoTrabalho"),
    "eventos.ordemservico": ("eventos", "OrdemServico"),
    "eventos.termoautorizacao": ("eventos", "TermoAutorizacao"),
}


def _model(documento_tipo: str):
    key = (documento_tipo or "").strip().lower()
    pair = _DOC_KEYS.get(key)
    if not pair:
        raise ValueError(f"Tipo documental nao suportado para PDF: {documento_tipo!r}")
    return apps.get_model(pair[0], pair[1])


def gerar_pdf_bytes_para_assinatura(documento_tipo: str, documento_id: int) -> bytes:
    tipo = (documento_tipo or "").strip()
    key = tipo.lower()
    model = _model(tipo)
    obj = model.objects.get(pk=documento_id)

    if key == "eventos.oficio":
        return render_document_bytes(obj, DocumentoOficioTipo.OFICIO, DocumentoFormato.PDF)

    if key == "eventos.justificativa":
        if not getattr(obj, "oficio_id", None):
            raise ValueError("Justificativa sem oficio vinculado.")
        oficio = obj.oficio
        return render_document_bytes(oficio, DocumentoOficioTipo.JUSTIFICATIVA, DocumentoFormato.PDF)

    if key == "eventos.planotrabalho":
        related_oficios = (
            obj.get_oficios_relacionados() if hasattr(obj, "get_oficios_relacionados") else list(obj.oficios.all())
        )
        oficio_ref = related_oficios[0] if len(related_oficios) == 1 else None
        docx = render_plano_trabalho_docx(oficio_ref) if oficio_ref else render_plano_trabalho_model_docx(obj)
        return convert_docx_bytes_to_pdf_bytes(docx)

    if key == "eventos.ordemservico":
        oficios = obj.get_oficios_vinculados() if hasattr(obj, "get_oficios_vinculados") else []
        oficio_ref = oficios[0] if len(oficios) == 1 else None
        docx = render_ordem_servico_docx(oficio_ref) if oficio_ref else render_ordem_servico_model_docx(obj)
        return convert_docx_bytes_to_pdf_bytes(docx)

    if key == "eventos.termoautorizacao":
        docx = render_saved_termo_autorizacao_docx(obj)
        return convert_docx_bytes_to_pdf_bytes(docx)

    raise ValueError(f"Tipo nao implementado: {tipo}")
