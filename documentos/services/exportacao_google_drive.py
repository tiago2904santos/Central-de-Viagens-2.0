from __future__ import annotations

import re
import tempfile
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.db.models import Prefetch, Q

from cadastros.models import Viajante
from core.utils.masks import EMPTY_MASK_DISPLAY
from eventos.models import Evento, EventoDestino, Oficio, OrdemServico, PlanoTrabalho, TermoAutorizacao
from eventos.services.documentos import (
    DocumentoFormato,
    DocumentoOficioTipo,
    render_document_bytes,
)
from eventos.services.documentos.ordem_servico import render_ordem_servico_model_docx
from eventos.services.documentos.plano_trabalho import render_plano_trabalho_docx, render_plano_trabalho_model_docx
from eventos.services.documentos.renderer import convert_docx_bytes_to_pdf_bytes
from eventos.services.documentos.termo_autorizacao import render_saved_termo_autorizacao_docx
from integracoes.services.google_drive.drive_service import (
    GoogleDriveIntegrationNotConfigured,
    GoogleDriveService,
)


INVALID_NAME_CHARS = r'[<>:"/\\|?*\x00-\x1F]'
logger = logging.getLogger(__name__)

MAX_DRIVE_FOLDER_NAME = 200
MAX_DRIVE_FILE_NAME = 200
MAX_VIAJANTES_FOLDER_CHARS = 88


def _drive_safe_backslashes(value: str) -> str:
    """Barras `/` em datas são tratadas nos formatadores; aqui só removemos barra invertida inválida."""
    return (value or "").replace("\\", "-")


def sanitize_drive_name(value: str, fallback: str) -> str:
    cleaned = _drive_safe_backslashes(value or "")
    cleaned = re.sub(INVALID_NAME_CHARS, "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    return cleaned or fallback


def _upper_clean(value: str) -> str:
    return (value or "").strip().upper()


def sanitize_drive_name_export(value: str, fallback: str) -> str:
    return _upper_clean(sanitize_drive_name(value, fallback))


def limit_drive_name(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    m = re.match(r"^(\d+\.\d*\s+)", t)
    head = m.group(1) if m else ""
    body = t[len(head) :] if head else t
    budget = max(1, max_len - len(head))
    trimmed = body[:budget].rstrip(" -.")
    return (head + trimmed).strip() or t[:max_len]


@dataclass
class ExportacaoGoogleDriveResultado:
    success: bool = False
    folders_created: int = 0
    files_uploaded: int = 0
    missing_documents: list[str] = field(default_factory=list)
    partial_errors: list[str] = field(default_factory=list)
    oficios_processados: int = 0


class ExportacaoEventoGoogleDriveService:
    """Exportação Google Drive: nomenclatura centralizada nesta classe."""

    DOCX_SUBFOLDER_NAME = "DOCX"

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

    @staticmethod
    def _format_event_date_short(evento: Evento) -> str:
        di = getattr(evento, "data_inicio", None)
        df = getattr(evento, "data_fim", None) or di
        if not di:
            return ""
        if getattr(evento, "data_unica", False) or not df or di == df:
            return f"{di:%d-%m}"
        return f"{di:%d-%m} -> {df:%d-%m}"

    @staticmethod
    def _format_date_short_pair(d1, d2, *, data_unica: bool) -> str:
        if not d1 and not d2:
            return ""
        start = d1 or d2
        end = d2 or d1
        if data_unica or start == end:
            return f"{start:%d-%m}"
        return f"{start:%d-%m} -> {end:%d-%m}"

    @staticmethod
    def _event_destino_principal(evento: Evento) -> str:
        destinos = list(
            evento.destinos.select_related("cidade", "estado").order_by("ordem", "cidade__nome", "pk")
        )
        for d in destinos:
            if d.cidade_id and getattr(d.cidade, "nome", ""):
                return (d.cidade.nome or "").strip()
            if d.estado_id and getattr(d.estado, "sigla", ""):
                return (d.estado.sigla or "").strip()
        cp = getattr(evento, "cidade_principal", None)
        if cp and (cp.nome or "").strip():
            return (cp.nome or "").strip()
        if getattr(evento, "estado_principal", None) and getattr(evento.estado_principal, "sigla", ""):
            return (evento.estado_principal.sigla or "").strip()
        return f"EVENTO {evento.pk}"

    @staticmethod
    def _event_tipos_demanda_concat(evento: Evento) -> str:
        tipos = list(
            evento.tipos_demanda.filter(ativo=True).order_by("ordem", "nome").values_list("nome", flat=True)
        )
        parts = [_upper_clean(n) for n in tipos if (n or "").strip()]
        return " - ".join(parts) if parts else "SEM TIPO"

    @staticmethod
    def _build_event_folder_name(evento: Evento) -> str:
        dest = sanitize_drive_name_export(
            ExportacaoEventoGoogleDriveService._event_destino_principal(evento),
            f"EVENTO {evento.pk}",
        )
        datas = ExportacaoEventoGoogleDriveService._format_event_date_short(evento)
        if not datas:
            datas = "SEM DATA"
        tipos = ExportacaoEventoGoogleDriveService._event_tipos_demanda_concat(evento)
        raw = f"{dest} - {datas} - {tipos}"
        raw = sanitize_drive_name_export(raw, f"EVENTO {evento.pk}")
        return limit_drive_name(raw, MAX_DRIVE_FOLDER_NAME)

    @staticmethod
    def _numero_ano_hifen(numero, ano, draft_pk: int | None, prefix: str) -> str:
        if numero and ano:
            return f"{int(numero):02d}-{int(ano)}"
        if draft_pk is not None:
            return f"RASCUNHO-{draft_pk}"
        return f"{prefix}-0"

    @staticmethod
    def _oficio_numero_hifen(oficio: Oficio) -> str:
        return ExportacaoEventoGoogleDriveService._numero_ano_hifen(
            oficio.numero, oficio.ano, oficio.pk, "OFICIO"
        )

    @staticmethod
    def _protocol_segment_oficio(oficio: Oficio) -> str | None:
        raw = (oficio.protocolo_formatado or "").strip()
        if not raw or raw == EMPTY_MASK_DISPLAY:
            return None
        return f"PROT. {_upper_clean(raw)}"

    @staticmethod
    def _first_name_token(full_name: str) -> str:
        part = (full_name or "").strip().split()
        return _upper_clean(part[0]) if part else ""

    @classmethod
    def _viajantes_primeiros_nomes(cls, oficio: Oficio) -> str:
        viajantes = list(oficio.viajantes.all().order_by("nome", "pk"))
        firsts = [cls._first_name_token(getattr(v, "nome", "") or "") for v in viajantes]
        firsts = [f for f in firsts if f]
        if not firsts:
            return ""
        if len(firsts) == 1:
            base = firsts[0]
        elif len(firsts) == 2:
            base = f"{firsts[0]} E {firsts[1]}"
        else:
            base = " / ".join(firsts)
        if len(base) <= MAX_VIAJANTES_FOLDER_CHARS:
            return base
        acc: list[str] = []
        for n in firsts:
            trial = " / ".join(acc + [n]) if acc else n
            if len(trial) <= MAX_VIAJANTES_FOLDER_CHARS:
                acc.append(n)
            else:
                break
        if acc:
            return " / ".join(acc)
        return firsts[0][:MAX_VIAJANTES_FOLDER_CHARS]

    @classmethod
    def _oficio_folder_core_parts(cls, oficio: Oficio) -> list[str]:
        parts = [f"OFICIO {cls._oficio_numero_hifen(oficio)}"]
        proto = cls._protocol_segment_oficio(oficio)
        if proto:
            parts.append(proto)
        nomes = cls._viajantes_primeiros_nomes(oficio)
        if nomes:
            parts.append(nomes)
        return parts

    @classmethod
    def _build_oficio_folder_name(cls, oficio: Oficio) -> str:
        raw = " - ".join(cls._oficio_folder_core_parts(oficio))
        raw = sanitize_drive_name_export(raw, f"OFICIO {oficio.pk}")
        return limit_drive_name(raw, MAX_DRIVE_FOLDER_NAME)

    @classmethod
    def _build_oficio_arquivo_stem(cls, oficio: Oficio) -> str:
        raw = "1. " + " - ".join(cls._oficio_folder_core_parts(oficio))
        raw = sanitize_drive_name_export(raw, f"1. OFICIO {oficio.pk}")
        return limit_drive_name(raw, MAX_DRIVE_FILE_NAME)

    @staticmethod
    def _labels_from_destinos_json(destinos_json) -> list[str]:
        labels: list[str] = []
        seen: set[str] = set()

        def remember(label: str) -> None:
            value = (label or "").strip()
            if not value or value in seen:
                return
            seen.add(value)
            labels.append(value)

        for destino in destinos_json or []:
            if not isinstance(destino, dict):
                continue
            cidade = (destino.get("cidade_nome") or "").strip()
            uf = (destino.get("estado_sigla") or "").strip().upper()
            if cidade and uf:
                remember(f"{cidade} {uf}")
            elif cidade:
                remember(cidade)

        return labels

    @classmethod
    def _destino_consolidado_documento(
        cls,
        *,
        destinos_json,
        evento: Evento,
        oficio: Oficio,
    ) -> str:
        labels = cls._labels_from_destinos_json(destinos_json)
        if labels:
            return labels[0]
        return cls._event_destino_principal(evento)

    @classmethod
    def _plano_numero_hifen(cls, plano: PlanoTrabalho) -> str:
        return cls._numero_ano_hifen(plano.numero, plano.ano, plano.pk, "PT")

    @classmethod
    def _plano_date_short(cls, plano: PlanoTrabalho, evento: Evento) -> str:
        if plano.evento_data_inicio:
            return cls._format_date_short_pair(
                plano.evento_data_inicio,
                plano.evento_data_fim,
                data_unica=bool(getattr(plano, "evento_data_unica", False)),
            )
        return cls._format_event_date_short(evento)

    @classmethod
    def _build_plano_file_stem(cls, plano: PlanoTrabalho, evento: Evento, oficio: Oficio, block_idx: int) -> str:
        num = cls._plano_numero_hifen(plano)
        dest = sanitize_drive_name_export(
            cls._destino_consolidado_documento(
                destinos_json=plano.destinos_json,
                evento=evento,
                oficio=oficio,
            ),
            cls._event_destino_principal(evento),
        )
        datas = cls._plano_date_short(plano, evento) or cls._format_event_date_short(evento) or "SEM DATA"
        raw = f"2.{block_idx:02d} PLANO DE TRABALHO {num} - {dest} - {datas}"
        raw = sanitize_drive_name_export(raw, f"2.{block_idx:02d} PLANO {plano.pk}")
        return limit_drive_name(raw, MAX_DRIVE_FILE_NAME)

    @classmethod
    def _ordem_numero_hifen(cls, ordem: OrdemServico) -> str:
        return cls._numero_ano_hifen(ordem.numero, ordem.ano, ordem.pk, "OS")

    @classmethod
    def _ordem_date_short(cls, ordem: OrdemServico, evento: Evento) -> str:
        if ordem.data_deslocamento:
            return cls._format_date_short_pair(
                ordem.data_deslocamento,
                ordem.data_deslocamento_fim,
                data_unica=bool(getattr(ordem, "data_unica", True)),
            )
        return cls._format_event_date_short(evento)

    @classmethod
    def _build_ordem_file_stem(cls, ordem: OrdemServico, evento: Evento, oficio: Oficio, block_idx: int) -> str:
        num = cls._ordem_numero_hifen(ordem)
        dest = sanitize_drive_name_export(
            cls._destino_consolidado_documento(
                destinos_json=ordem.destinos_json,
                evento=evento,
                oficio=oficio,
            ),
            cls._event_destino_principal(evento),
        )
        datas = cls._ordem_date_short(ordem, evento) or cls._format_event_date_short(evento) or "SEM DATA"
        raw = f"2.{block_idx:02d} ORDEM DE SERVICO {num} - {dest} - {datas}"
        raw = sanitize_drive_name_export(raw, f"2.{block_idx:02d} OS {ordem.pk}")
        return limit_drive_name(raw, MAX_DRIVE_FILE_NAME)

    @classmethod
    def _build_convite_anexo_stem(cls, block_idx: int, evento: Evento, seq: int, total: int) -> str:
        dest = sanitize_drive_name_export(
            cls._event_destino_principal(evento),
            f"EVENTO {evento.pk}",
        )
        suffix = f" {seq}" if total > 1 else ""
        raw = f"2.{block_idx:02d} CONVITE-OFICIO SOLICITANTE{suffix} - {dest}"
        return limit_drive_name(
            sanitize_drive_name_export(raw, f"2.{block_idx:02d} CONVITE {seq}"),
            MAX_DRIVE_FILE_NAME,
        )

    @classmethod
    def _build_justificativa_stem(cls, oficio: Oficio) -> str:
        nh = cls._oficio_numero_hifen(oficio)
        raw = f"3. JUSTIFICATIVA OFICIO {nh}"
        return limit_drive_name(sanitize_drive_name_export(raw, f"3. JUSTIFICATIVA {oficio.pk}"), MAX_DRIVE_FILE_NAME)

    @classmethod
    def _termo_date_short(cls, termo: TermoAutorizacao, evento: Evento) -> str:
        if termo.data_evento:
            return cls._format_date_short_pair(
                termo.data_evento,
                termo.data_evento_fim,
                data_unica=not (
                    termo.data_evento_fim and termo.data_evento_fim != termo.data_evento
                ),
            )
        return cls._format_event_date_short(evento)

    @classmethod
    def _build_termo_file_stem(cls, termo: TermoAutorizacao, evento: Evento, used: set[str]) -> str:
        dest = (termo.destino or "").strip() or cls._event_destino_principal(evento)
        dest = sanitize_drive_name_export(dest, cls._event_destino_principal(evento))
        datas = cls._termo_date_short(termo, evento) or cls._format_event_date_short(evento) or "SEM DATA"
        if termo.is_termo_generico():
            raw = f"4. TERMO DE AUTORIZACAO {dest} - {datas}"
        else:
            nome = sanitize_drive_name_export(
                (termo.servidor_display or "").strip(),
                "SERVIDOR",
            )
            raw = f"4. TERMO DE AUTORIZACAO {nome} - {dest} - {datas}"
        stem = limit_drive_name(sanitize_drive_name_export(raw, f"4. TERMO {termo.pk}"), MAX_DRIVE_FILE_NAME)
        if stem in used:
            raw_dedup = f"{raw} TA{termo.pk}"
            stem = limit_drive_name(
                sanitize_drive_name_export(raw_dedup, f"4. TERMO {termo.pk}"),
                MAX_DRIVE_FILE_NAME,
            )
        used.add(stem)
        return stem

    def _render_oficio_documento(self, oficio: Oficio, tipo, formato: str) -> bytes:
        return render_document_bytes(oficio, tipo, formato)

    @staticmethod
    def _render_plano_documento(plano: PlanoTrabalho, formato: str) -> bytes:
        oficio_ref = plano.oficio or plano.oficios.order_by("-updated_at", "-created_at").first()
        docx_bytes = render_plano_trabalho_docx(oficio_ref) if oficio_ref else render_plano_trabalho_model_docx(plano)
        if DocumentoFormato(formato).value == DocumentoFormato.PDF.value:
            return convert_docx_bytes_to_pdf_bytes(docx_bytes)
        return docx_bytes

    @staticmethod
    def _render_ordem_documento(ordem: OrdemServico, formato: str) -> bytes:
        docx_bytes = render_ordem_servico_model_docx(ordem)
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
            self.drive_service.upload_or_replace_file(
                service=service,
                parent_id=parent_id,
                local_path=temp_path,
                mime_type=mime_type,
                target_name=file_name,
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _reload_evento_com_contexto(self, evento: Evento) -> Evento:
        if not evento.pk:
            return evento
        ev = (
            Evento.objects.filter(pk=evento.pk)
            .select_related("cidade_principal", "cidade_principal__estado", "estado_principal")
            .prefetch_related(
                Prefetch(
                    "destinos",
                    queryset=EventoDestino.objects.select_related("cidade", "estado").order_by(
                        "ordem", "cidade__nome", "pk"
                    ),
                ),
                "tipos_demanda",
            )
            .first()
        )
        return ev or evento

    def exportar_evento(self, user, evento: Evento, formatos: tuple[str, ...] = ("docx", "pdf")):
        result = ExportacaoGoogleDriveResultado()
        formatos = tuple(
            dict.fromkeys(tuple(DocumentoFormato(item).value for item in formatos))
        )

        evento = self._reload_evento_com_contexto(evento)

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
            self._build_event_folder_name(evento),
        )
        result.folders_created += 1

        anexos_solicitante = list(
            evento.anexos_solicitante.order_by("ordem", "-uploaded_at", "id")
        )
        if getattr(evento, "tem_convite_ou_oficio_evento", False) and not anexos_solicitante:
            result.missing_documents.append(
                "Evento marcado com convite/oficio solicitante, mas sem anexos em anexos_solicitante."
            )

        oficios = list(
            evento.oficios.select_related("justificativa")
            .prefetch_related(Prefetch("viajantes", Viajante.objects.order_by("nome", "pk")))
            .order_by("-updated_at", "-created_at")
        )

        for oficio in oficios:
            result.oficios_processados += 1
            oficio_folder = self.drive_service.ensure_folder(
                context.service,
                event_folder["id"],
                self._build_oficio_folder_name(oficio),
            )
            result.folders_created += 1
            docx_subfolder_id: str | None = None

            def upload_parent_for_format(fmt: str) -> str:
                nonlocal docx_subfolder_id
                if DocumentoFormato(fmt).value == DocumentoFormato.PDF.value:
                    return oficio_folder["id"]
                if docx_subfolder_id is None:
                    docx_folder = self.drive_service.ensure_folder(
                        context.service,
                        oficio_folder["id"],
                        self.DOCX_SUBFOLDER_NAME,
                    )
                    docx_subfolder_id = docx_folder["id"]
                    result.folders_created += 1
                return docx_subfolder_id

            planos = list(
                PlanoTrabalho.objects.filter(Q(oficio_id=oficio.pk) | Q(oficios=oficio))
                .distinct()
                .order_by("numero", "ano", "pk")
            )
            ordens = list(
                OrdemServico.objects.filter(Q(oficio_id=oficio.pk) | Q(evento_id=evento.pk))
                .distinct()
                .order_by("numero", "ano", "pk")
            )
            termos = list(
                TermoAutorizacao.objects.filter(Q(oficio_id=oficio.pk) | Q(oficios=oficio))
                .distinct()
                .order_by("viajante__nome", "pk")
            )

            if not planos:
                result.missing_documents.append(
                    f"Oficio {oficio.numero_formatado or oficio.pk} sem plano de trabalho vinculado."
                )
            if not ordens:
                result.missing_documents.append(
                    f"Oficio {oficio.numero_formatado or oficio.pk} sem ordem de servico vinculada ao evento ou oficio."
                )
            if not termos:
                result.missing_documents.append(
                    f"Oficio {oficio.numero_formatado or oficio.pk} sem termos vinculados."
                )

            if not getattr(oficio, "justificativa", None):
                result.missing_documents.append(
                    f"Oficio {oficio.numero_formatado or oficio.pk} sem justificativa vinculada."
                )

            block2_idx = 1
            plano_entries: list[tuple[PlanoTrabalho, str]] = []
            for plano in planos:
                plano_entries.append((plano, self._build_plano_file_stem(plano, evento, oficio, block2_idx)))
                block2_idx += 1
            ordem_entries: list[tuple[OrdemServico, str]] = []
            for ordem in ordens:
                ordem_entries.append((ordem, self._build_ordem_file_stem(ordem, evento, oficio, block2_idx)))
                block2_idx += 1
            n_anexos = len(anexos_solicitante)
            convite_entries: list[tuple[object, str]] = []
            for seq, anexo in enumerate(anexos_solicitante, start=1):
                convite_entries.append(
                    (anexo, self._build_convite_anexo_stem(block2_idx, evento, seq, n_anexos))
                )
                block2_idx += 1

            termo_stems_used: set[str] = set()
            termo_entries: list[tuple[TermoAutorizacao, str]] = [
                (termo, self._build_termo_file_stem(termo, evento, termo_stems_used)) for termo in termos
            ]

            for formato in formatos:
                upload_parent_id = upload_parent_for_format(formato)
                oficio_stem = self._build_oficio_arquivo_stem(oficio)
                try:
                    payload = self._render_oficio_documento(oficio, DocumentoOficioTipo.OFICIO, formato)
                    self._upload_bytes(
                        context.service,
                        upload_parent_id,
                        payload,
                        limit_drive_name(f"{oficio_stem}.{formato}", MAX_DRIVE_FILE_NAME),
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

                for plano, stem in plano_entries:
                    try:
                        payload = self._render_plano_documento(plano, formato)
                        self._upload_bytes(
                            context.service,
                            upload_parent_id,
                            payload,
                            limit_drive_name(f"{stem}.{formato}", MAX_DRIVE_FILE_NAME),
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

                for ordem, stem in ordem_entries:
                    try:
                        payload = self._render_ordem_documento(ordem, formato)
                        self._upload_bytes(
                            context.service,
                            upload_parent_id,
                            payload,
                            limit_drive_name(f"{stem}.{formato}", MAX_DRIVE_FILE_NAME),
                            formato,
                        )
                        result.files_uploaded += 1
                    except Exception as exc:
                        logger.warning(
                            "Falha exportando ordem de servico para Drive",
                            extra={
                                "evento_id": evento.pk,
                                "oficio_id": oficio.pk,
                                "ordem_id": ordem.pk,
                                "formato": formato,
                            },
                            exc_info=True,
                        )
                        result.partial_errors.append(
                            f"Falha ao exportar ordem de servico {ordem.pk} ({formato}): {exc}"
                        )

                if getattr(oficio, "justificativa", None):
                    jstem = self._build_justificativa_stem(oficio)
                    try:
                        payload = self._render_oficio_documento(oficio, DocumentoOficioTipo.JUSTIFICATIVA, formato)
                        self._upload_bytes(
                            context.service,
                            upload_parent_id,
                            payload,
                            limit_drive_name(f"{jstem}.{formato}", MAX_DRIVE_FILE_NAME),
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

                for termo, tstem in termo_entries:
                    try:
                        payload = self._render_termo_documento(termo, formato)
                        self._upload_bytes(
                            context.service,
                            upload_parent_id,
                            payload,
                            limit_drive_name(f"{tstem}.{formato}", MAX_DRIVE_FILE_NAME),
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

            pdf_parent_id = oficio_folder["id"]
            for anexo, stem in convite_entries:
                try:
                    with anexo.arquivo.open("rb") as file_handle:
                        payload = file_handle.read()
                    if not payload:
                        raise ValueError("Arquivo de anexo vazio ou ilegivel.")
                    self._upload_bytes(
                        context.service,
                        pdf_parent_id,
                        payload,
                        limit_drive_name(f"{stem}.pdf", MAX_DRIVE_FILE_NAME),
                        DocumentoFormato.PDF.value,
                    )
                    result.files_uploaded += 1
                except Exception as exc:
                    logger.warning(
                        "Falha exportando anexo de convite/oficio solicitante para Drive",
                        extra={
                            "evento_id": evento.pk,
                            "oficio_id": oficio.pk,
                            "anexo_id": getattr(anexo, "pk", None),
                        },
                        exc_info=True,
                    )
                    result.partial_errors.append(
                        f"Falha ao exportar anexo solicitante {getattr(anexo, 'pk', '?')} "
                        f"(oficio {oficio.pk}): {exc}"
                    )

        result.missing_documents = list(dict.fromkeys(result.missing_documents))
        result.partial_errors = list(dict.fromkeys(result.partial_errors))
        result.success = len(result.partial_errors) == 0
        return result
