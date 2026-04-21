from __future__ import annotations

import re
import tempfile
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.db.models import Q

from eventos.models import Evento, Oficio, PlanoTrabalho, TermoAutorizacao
from eventos.services.documentos import (
    DocumentoFormato,
    DocumentoOficioTipo,
    build_document_filename,
    render_document_bytes,
)
from eventos.services.documentos.plano_trabalho import render_plano_trabalho_docx, render_plano_trabalho_model_docx
from eventos.services.documentos.renderer import convert_docx_bytes_to_pdf_bytes
from eventos.services.documentos.termo_autorizacao import render_saved_termo_autorizacao_docx
from integracoes.services.google_drive.drive_service import (
    GoogleDriveIntegrationNotConfigured,
    GoogleDriveService,
    GoogleDriveServiceError,
)


INVALID_NAME_CHARS = r'[<>:"/\\|?*\x00-\x1F]'
logger = logging.getLogger(__name__)


def sanitize_drive_name(value: str, fallback: str) -> str:
    cleaned = re.sub(INVALID_NAME_CHARS, "", (value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned or fallback


@dataclass
class ExportacaoGoogleDriveResultado:
    success: bool = False
    folders_created: int = 0
    files_uploaded: int = 0
    missing_documents: list[str] = field(default_factory=list)
    partial_errors: list[str] = field(default_factory=list)
    oficios_processados: int = 0


class ExportacaoEventoGoogleDriveService:
    def __init__(self):
        self.drive_service = GoogleDriveService()

    @staticmethod
    def _mime_and_suffix(formato: str) -> tuple[str, str]:
        normalized = DocumentoFormato(formato).value
        if normalized == DocumentoFormato.PDF.value:
            return "application/pdf", ".pdf"
        return (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        )

    def _render_oficio_documento(self, oficio: Oficio, tipo, formato: str) -> bytes:
        return render_document_bytes(oficio, tipo, formato)

    @staticmethod
    def _build_termo_filename(termo: TermoAutorizacao, formato: str) -> str:
        return sanitize_drive_name(
            f"termo_{termo.pk:02d}.{formato}",
            f"termo_{termo.pk}.{formato}",
        )

    @staticmethod
    def _build_plano_filename(plano: PlanoTrabalho, formato: str, idx: int) -> str:
        base = "plano_trabalho"
        if plano.numero and plano.ano:
            base = f"plano_trabalho_{int(plano.numero):02d}_{int(plano.ano)}"
        if idx > 1:
            base = f"{base}_{idx:02d}"
        return sanitize_drive_name(f"{base}.{formato}", f"plano_trabalho_{plano.pk}.{formato}")

    @staticmethod
    def _render_plano_documento(plano: PlanoTrabalho, formato: str) -> bytes:
        oficio_ref = plano.oficio or plano.oficios.order_by("-updated_at", "-created_at").first()
        docx_bytes = render_plano_trabalho_docx(oficio_ref) if oficio_ref else render_plano_trabalho_model_docx(plano)
        if DocumentoFormato(formato).value == DocumentoFormato.PDF.value:
            return convert_docx_bytes_to_pdf_bytes(docx_bytes)
        return docx_bytes

    @staticmethod
    def _render_termo_documento(termo: TermoAutorizacao, formato: str) -> bytes:
        docx_bytes = render_saved_termo_autorizacao_docx(termo)
        if DocumentoFormato(formato).value == DocumentoFormato.PDF.value:
            return convert_docx_bytes_to_pdf_bytes(docx_bytes)
        return docx_bytes

    def _upload_bytes(
        self,
        service,
        parent_id: str,
        file_bytes: bytes,
        file_name: str,
        formato: str,
    ) -> None:
        mime_type, suffix = self._mime_and_suffix(formato)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name
        try:
            self.drive_service.upload_file(
                service=service,
                parent_id=parent_id,
                local_path=temp_path,
                mime_type=mime_type,
                target_name=file_name,
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def exportar_evento(self, user, evento: Evento, formatos: tuple[str, ...] = ("docx", "pdf")):
        result = ExportacaoGoogleDriveResultado()
        formatos = tuple(DocumentoFormato(item).value for item in formatos)

        context = self.drive_service.get_authenticated_service(user)
        integration = context.integration
        if not integration.root_folder_name:
            raise GoogleDriveIntegrationNotConfigured(
                "Configure a pasta raiz do Google Drive antes de exportar."
            )
        integration = self.drive_service.ensure_user_root_folder(
            user=user, root_folder_name=integration.root_folder_name
        )
        root_folder_id = integration.root_folder_id
        event_folder = self.drive_service.ensure_folder(
            context.service,
            root_folder_id,
            sanitize_drive_name(evento.titulo, f"Evento {evento.pk}"),
        )
        result.folders_created += 1

        oficios = list(evento.oficios.select_related("justificativa").order_by("-updated_at", "-created_at"))
        for oficio in oficios:
            result.oficios_processados += 1
            oficio_folder_name = sanitize_drive_name(
                f"Oficio {oficio.numero_formatado or oficio.pk}",
                f"Oficio {oficio.pk}",
            )
            oficio_folder = self.drive_service.ensure_folder(
                context.service, event_folder["id"], oficio_folder_name
            )
            result.folders_created += 1
            for formato in formatos:
                try:
                    payload = self._render_oficio_documento(oficio, DocumentoOficioTipo.OFICIO, formato)
                    self._upload_bytes(
                        context.service,
                        oficio_folder["id"],
                        payload,
                        sanitize_drive_name(
                            build_document_filename(oficio, DocumentoOficioTipo.OFICIO, formato),
                            f"oficio_{oficio.pk}.{formato}",
                        ),
                        formato,
                    )
                    result.files_uploaded += 1
                except Exception as exc:
                    logger.warning(
                        "Falha exportando oficio para Drive",
                        extra={"evento_id": evento.pk, "oficio_id": oficio.pk, "formato": formato},
                        exc_info=True,
                    )
                    result.partial_errors.append(f"Falha ao exportar oficio {oficio.pk} ({formato}): {exc}")

                if getattr(oficio, "justificativa", None):
                    try:
                        payload = self._render_oficio_documento(oficio, DocumentoOficioTipo.JUSTIFICATIVA, formato)
                        self._upload_bytes(
                            context.service,
                            oficio_folder["id"],
                            payload,
                            sanitize_drive_name(
                                build_document_filename(oficio, DocumentoOficioTipo.JUSTIFICATIVA, formato),
                                f"justificativa_{oficio.pk}.{formato}",
                            ),
                            formato,
                        )
                        result.files_uploaded += 1
                    except Exception as exc:
                        logger.warning(
                            "Falha exportando justificativa para Drive",
                            extra={"evento_id": evento.pk, "oficio_id": oficio.pk, "formato": formato},
                            exc_info=True,
                        )
                        result.partial_errors.append(
                            f"Falha ao exportar justificativa do oficio {oficio.pk} ({formato}): {exc}"
                        )
                else:
                    result.missing_documents.append(
                        f"Oficio {oficio.numero_formatado or oficio.pk} sem justificativa vinculada."
                    )

                planos = (
                    PlanoTrabalho.objects.filter(Q(oficio_id=oficio.pk) | Q(oficios=oficio))
                    .distinct()
                    .order_by("-updated_at", "-created_at")
                )
                if not planos.exists():
                    result.missing_documents.append(
                        f"Oficio {oficio.numero_formatado or oficio.pk} sem plano de trabalho vinculado."
                    )
                for idx, plano in enumerate(planos, start=1):
                    try:
                        payload = self._render_plano_documento(plano, formato)
                        base = "plano_trabalho" if idx == 1 else f"plano_trabalho_{idx:02d}"
                        self._upload_bytes(
                            context.service,
                            oficio_folder["id"],
                            payload,
                            self._build_plano_filename(plano, formato, idx),
                            formato,
                        )
                        result.files_uploaded += 1
                    except Exception as exc:
                        logger.warning(
                            "Falha exportando plano de trabalho para Drive",
                            extra={
                                "evento_id": evento.pk,
                                "oficio_id": oficio.pk,
                                "plano_id": plano.pk,
                                "formato": formato,
                            },
                            exc_info=True,
                        )
                        result.partial_errors.append(
                            f"Falha ao exportar plano de trabalho {plano.pk} ({formato}): {exc}"
                        )

                termos = (
                    TermoAutorizacao.objects.filter(Q(oficio_id=oficio.pk) | Q(oficios=oficio))
                    .distinct()
                    .order_by("-updated_at", "-created_at")
                )
                if not termos.exists():
                    result.missing_documents.append(
                        f"Oficio {oficio.numero_formatado or oficio.pk} sem termos vinculados."
                    )
                for idx, termo in enumerate(termos, start=1):
                    try:
                        payload = self._render_termo_documento(termo, formato)
                        self._upload_bytes(
                            context.service,
                            oficio_folder["id"],
                            payload,
                            self._build_termo_filename(termo, formato),
                            formato,
                        )
                        result.files_uploaded += 1
                    except Exception as exc:
                        logger.warning(
                            "Falha exportando termo para Drive",
                            extra={
                                "evento_id": evento.pk,
                                "oficio_id": oficio.pk,
                                "termo_id": termo.pk,
                                "formato": formato,
                            },
                            exc_info=True,
                        )
                        result.partial_errors.append(
                            f"Falha ao exportar termo {termo.pk} ({formato}): {exc}"
                        )

        result.success = len(result.partial_errors) == 0
        return result
