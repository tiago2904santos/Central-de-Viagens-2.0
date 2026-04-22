"""Pedidos de assinatura para documentos gerados (Oficio, PT, OS, Justificativa, Termo)."""
from __future__ import annotations

import hashlib
import logging
import re
import tempfile
import unicodedata
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.urls import reverse
from django.utils import timezone

from assinaturas.models import AssinaturaDocumento, AssinaturaEtapa
from assinaturas.services.assinatura_estado import EstadoLinkAssinatura, estado_etapa_assinatura
from assinaturas.services.config_assinatura import get_viajante_assinatura_padrao
from assinaturas.services.documento_pdf_gerador import gerar_pdf_bytes_para_assinatura
from assinaturas.services.pdf_assinatura import aplicar_assinatura_data_url
from cadastros.models import AssinaturaConfiguracao, ConfiguracaoSistema
from integracoes.services.google_drive.drive_service import (
    GoogleDriveIntegrationNotConfigured,
    GoogleDriveService,
)

logger = logging.getLogger(__name__)

_ALLOWED: set[str] = {
    "eventos.oficio",
    "eventos.justificativa",
    "eventos.planotrabalho",
    "eventos.ordemservico",
    "eventos.termoautorizacao",
}


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm_tipo(documento_tipo: str) -> str:
    return (documento_tipo or "").strip().lower()


def _tipo_eh_termo(documento_tipo: str) -> bool:
    return _norm_tipo(documento_tipo) == "eventos.termoautorizacao"


def validar_e_normalizar_nome(nome: str) -> tuple[str, str]:
    raw = " ".join((nome or "").strip().split())
    if len(raw) < 4:
        raise ValueError("Indique o nome completo (minimo 4 caracteres).")
    if len(raw) > 200:
        raise ValueError("Nome demasiado longo.")
    letters = sum(1 for ch in raw if ch.isalpha())
    if letters < 2:
        raise ValueError("O nome deve conter pelo menos duas letras.")
    if re.fullmatch(r"[\d\s.\-_]+", raw):
        raise ValueError("Indique um nome valido (nao apenas numeros ou simbolos).")

    normalizado = unicodedata.normalize("NFKC", raw)
    normalizado = " ".join(normalizado.split()).casefold()
    return raw, normalizado


def _cpf_esperado_viajante(viaj) -> str:
    from assinaturas.services.cpf import normalizar_cpf, validar_cpf_digitos

    if not viaj:
        return ""
    n = normalizar_cpf(getattr(viaj, "cpf", "") or "")
    if len(n) == 11 and validar_cpf_digitos(n):
        return n
    return ""


def _resolver_cpf_esperado_chefia(cfg: ConfiguracaoSistema, manual: str | None) -> str:
    from assinaturas.services.cpf import validar_e_normalizar_cpf_digitado

    if manual and str(manual).strip():
        try:
            return validar_e_normalizar_cpf_digitado(manual)
        except ValueError as exc:
            raise ValueError("CPF esperado da chefia invalido.") from exc
    raw = (getattr(cfg, "cpf_chefia_assinatura", "") or "").strip()
    if raw:
        return validar_e_normalizar_cpf_digitado(raw)
    raise ValueError(
        "Informe o CPF esperado da chefia no pedido ou configure o CPF nas configuracoes do sistema."
    )


def criar_pedido_assinatura(
    *,
    documento_tipo: str,
    documento_id: int,
    usuario_drive=None,
    drive_parent_folder_id: str = "",
    drive_target_filename: str = "",
    expires_in_days: int = 7,
    cpf_esperado_chefia: str | None = None,
) -> tuple[AssinaturaDocumento, AssinaturaEtapa | None, str]:
    """
    Cria pedido com PDF gerado e etapa(s) de assinatura.
    Devolve (pedido, primeira_etapa_ou_None, path_relativo_link_primeira_etapa).
    """
    nt = _norm_tipo(documento_tipo)
    if nt not in _ALLOWED:
        raise ValueError("Este tipo de documento nao entra no fluxo de assinatura eletronica.")

    try:
        pdf_bytes = gerar_pdf_bytes_para_assinatura(documento_tipo, documento_id)
    except ObjectDoesNotExist as exc:
        logger.warning(
            "Pedido de assinatura recusado: documento inexistente",
            extra={"documento_tipo": documento_tipo, "documento_id": documento_id},
        )
        raise ValueError("Documento nao encontrado.") from exc
    except Exception as exc:
        logger.exception(
            "Falha ao gerar PDF para assinatura",
            extra={"documento_tipo": documento_tipo, "documento_id": documento_id},
        )
        raise ValueError(f"Nao foi possivel gerar o PDF do documento: {exc}") from exc

    if len(pdf_bytes) < 8 or not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("O PDF gerado e invalido.")

    digest_mem = _sha256_hex(pdf_bytes)
    now = timezone.now()
    exp_days = expires_in_days if expires_in_days and expires_in_days > 0 else 7
    expires_at = now + timedelta(days=exp_days)

    with transaction.atomic():
        # Regra de regeneração: ao solicitar novo link, invalida pedidos ativos anteriores.
        AssinaturaDocumento.objects.filter(
            documento_tipo__iexact=documento_tipo.strip(),
            documento_id=documento_id,
            status__in=[
                AssinaturaDocumento.Status.PENDENTE,
                AssinaturaDocumento.Status.PARCIAL,
                AssinaturaDocumento.Status.CONCLUIDO,
            ],
        ).update(
            status=AssinaturaDocumento.Status.INVALIDADO_ALTERACAO,
            invalidado_em=now,
            invalidado_motivo="Pedido substituido por novo link de assinatura.",
        )

        assin = AssinaturaDocumento(
            documento_tipo=documento_tipo.strip(),
            documento_id=documento_id,
            campo_arquivo="",
            usuario_drive=usuario_drive if usuario_drive and getattr(usuario_drive, "pk", None) else None,
            drive_parent_folder_id=(drive_parent_folder_id or "").strip(),
            drive_target_filename=(drive_target_filename or "").strip(),
            expires_at=expires_at,
            arquivo_original_sha256=digest_mem,
            status=AssinaturaDocumento.Status.PENDENTE,
        )
        assin.arquivo_original.save("original.pdf", ContentFile(pdf_bytes), save=False)
        assin.save()
        with assin.arquivo_original.open("rb") as fh:
            digest_ficheiro = _sha256_hex(fh.read())
        assin.arquivo_original_sha256 = digest_ficheiro
        assin.save(update_fields=["arquivo_original_sha256"])

        if _tipo_eh_termo(documento_tipo):
            from django.apps import apps

            Termo = apps.get_model("eventos", "TermoAutorizacao")
            termo = Termo.objects.select_related("viajante").get(pk=documento_id)
            if not termo.viajante_id:
                raise ValueError("O termo precisa ter o servidor (viajante) definido para assinatura.")
            v1 = termo.viajante
            nome1 = (getattr(v1, "nome", "") or "").strip() or f"Servidor #{v1.pk}"
            cpf1 = _cpf_esperado_viajante(v1)
            if not cpf1:
                raise ValueError(
                    "O servidor do termo nao tem CPF valido no cadastro. Atualize o viajante antes de pedir assinatura."
                )
            cfg = ConfiguracaoSistema.get_singleton()
            nome_chefia = (getattr(cfg, "nome_chefia", "") or "").strip() or "Chefia"
            email_chefia = (getattr(cfg, "email", "") or "").strip()
            cpf_chefia = _resolver_cpf_esperado_chefia(cfg, cpf_esperado_chefia)

            AssinaturaEtapa.objects.create(
                assinatura=assin,
                ordem=1,
                tipo_assinante=AssinaturaEtapa.TipoAssinante.TERMO_SERVIDOR,
                nome_previsto=nome1,
                viajante=v1,
                cpf_esperado_normalizado=cpf1,
                expires_at=expires_at,
            )
            AssinaturaEtapa.objects.create(
                assinatura=assin,
                ordem=2,
                tipo_assinante=AssinaturaEtapa.TipoAssinante.EXTERNO_CHEFIA,
                nome_previsto=nome_chefia,
                email_previsto=email_chefia[:254] if email_chefia else "",
                cpf_esperado_normalizado=cpf_chefia,
                expires_at=expires_at,
            )
        else:
            tipo_cfg = _tipo_para_assinatura_config(nt)
            viaj, nome_prev = get_viajante_assinatura_padrao(tipo_cfg)
            if not viaj:
                raise ValueError(
                    "Configure o servidor de assinatura nas configuracoes do sistema para este tipo de documento."
                )
            cpf_v = _cpf_esperado_viajante(viaj)
            if not cpf_v:
                raise ValueError(
                    "O servidor configurado para assinar nao tem CPF valido no cadastro. Atualize o viajante antes de pedir assinatura."
                )
            AssinaturaEtapa.objects.create(
                assinatura=assin,
                ordem=1,
                tipo_assinante=AssinaturaEtapa.TipoAssinante.INTERNO_CONFIG,
                nome_previsto=nome_prev,
                viajante=viaj,
                cpf_esperado_normalizado=cpf_v,
                expires_at=expires_at,
            )

        primeira = AssinaturaEtapa.objects.filter(assinatura=assin).order_by("ordem").first()
        if not primeira:
            raise ValueError("Nao foi possivel criar etapas de assinatura.")

    rel = reverse("assinaturas:assinar", kwargs={"token": str(primeira.token)})
    return assin, primeira, rel


def _tipo_para_assinatura_config(nt: str) -> str:
    return {
        "eventos.oficio": AssinaturaConfiguracao.TIPO_OFICIO,
        "eventos.justificativa": AssinaturaConfiguracao.TIPO_JUSTIFICATIVA,
        "eventos.planotrabalho": AssinaturaConfiguracao.TIPO_PLANO_TRABALHO,
        "eventos.ordemservico": AssinaturaConfiguracao.TIPO_ORDEM_SERVICO,
    }[nt]


def _sync_drive_replace(
    *,
    user,
    parent_id: str,
    target_filename: str,
    signed_bytes: bytes,
) -> None:
    svc = GoogleDriveService()
    ctx = svc.get_authenticated_service(user)
    mime = "application/pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(signed_bytes)
        path = tmp.name
    try:
        svc.upload_or_replace_file(
            ctx.service,
            parent_id,
            path,
            mime,
            target_filename,
        )
    finally:
        Path(path).unlink(missing_ok=True)


def processar_assinatura_etapa(
    *,
    etapa: AssinaturaEtapa,
    nome_assinante: str,
    cpf_digitado: str,
    signature_data_url: str,
    ip: str | None,
    user_agent: str,
    usuario=None,
) -> None:
    estado = estado_etapa_assinatura(etapa)
    if estado == EstadoLinkAssinatura.JA_ASSINADO:
        raise ValueError("Esta etapa ja foi assinada.")
    if estado == EstadoLinkAssinatura.EXPIRADO:
        raise ValueError("Este link de assinatura expirou.")
    if estado != EstadoLinkAssinatura.VALIDO:
        raise ValueError("Assinatura indisponivel ou fora de ordem.")

    nome, nome_norm = validar_e_normalizar_nome(nome_assinante)

    from assinaturas.services.cpf import cpf_mascarado, cpf_confere, validar_e_normalizar_cpf_digitado

    try:
        cpf_norm = validar_e_normalizar_cpf_digitado(cpf_digitado)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    esperado = (etapa.cpf_esperado_normalizado or "").strip()
    if not esperado:
        raise ValueError(
            "Esta etapa nao tem CPF esperado registado; crie um novo pedido de assinatura apos corrigir o cadastro."
        )
    confere = cpf_confere(esperado, cpf_norm)
    if not confere:
        raise ValueError("CPF nao confere com o assinante esperado para esta etapa.")

    assin_ref = etapa.assinatura
    if etapa.ordem == 1:
        with assin_ref.arquivo_original.open("rb") as f:
            pdf_in = f.read()
    else:
        anterior = assin_ref.etapas.filter(ordem=etapa.ordem - 1).first()
        if not anterior or anterior.status != AssinaturaEtapa.Status.ASSINADO or not anterior.resultado_pdf.name:
            raise ValueError("A etapa anterior ainda nao foi concluida.")
        with anterior.resultado_pdf.open("rb") as f:
            pdf_in = f.read()

    if not pdf_in.startswith(b"%PDF"):
        raise ValueError("PDF de entrada invalido.")

    signed = aplicar_assinatura_data_url(
        pdf_in,
        signature_data_url,
        documento_tipo=assin_ref.documento_tipo,
    )
    digest = _sha256_hex(signed)

    with transaction.atomic():
        etapa = AssinaturaEtapa.objects.select_for_update().get(pk=etapa.pk)
        if estado_etapa_assinatura(etapa) != EstadoLinkAssinatura.VALIDO:
            raise ValueError("Pedido ja processado ou link invalido.")

        etapa.nome_assinante = nome
        etapa.nome_assinante_normalizado = nome_norm
        etapa.cpf_informado = cpf_mascarado(cpf_norm)
        etapa.cpf_normalizado = cpf_norm
        etapa.cpf_confere = True
        etapa.usuario = usuario if usuario and getattr(usuario, "pk", None) else None
        etapa.signed_at = timezone.now()
        etapa.ip = ip
        etapa.user_agent = (user_agent or "")[:2000]
        etapa.arquivo_sha256_apos_etapa = digest
        etapa.status = AssinaturaEtapa.Status.ASSINADO
        etapa.resultado_pdf.save(f"etapa_{etapa.ordem}.pdf", ContentFile(signed), save=False)
        etapa.save(
            update_fields=[
                "nome_assinante",
                "nome_assinante_normalizado",
                "cpf_informado",
                "cpf_normalizado",
                "cpf_confere",
                "usuario",
                "signed_at",
                "ip",
                "user_agent",
                "arquivo_sha256_apos_etapa",
                "status",
                "resultado_pdf",
            ]
        )

        assin = AssinaturaDocumento.objects.select_for_update().get(pk=assin_ref.pk)
        max_ord = assin.etapas.aggregate(m=Max("ordem"))["m"] or 0
        if etapa.ordem == max_ord:
            assin.arquivo_assinado.save("assinado.pdf", ContentFile(signed), save=False)
            with assin.arquivo_assinado.open("rb") as af:
                digest_final = _sha256_hex(af.read())
            assin.arquivo_assinado_sha256 = digest_final
            assin.nome_assinante = nome
            assin.nome_assinante_normalizado = nome_norm
            assin.signed_at = timezone.now()
            assin.ip = ip
            assin.user_agent = (user_agent or "")[:2000]
            assin.usuario_ultima_etapa = usuario if usuario and getattr(usuario, "pk", None) else None
            assin.status = AssinaturaDocumento.Status.CONCLUIDO
            assin.drive_sync_error = ""
            assin.save(
                update_fields=[
                    "arquivo_assinado",
                    "arquivo_assinado_sha256",
                    "nome_assinante",
                    "nome_assinante_normalizado",
                    "signed_at",
                    "ip",
                    "user_agent",
                    "usuario_ultima_etapa",
                    "status",
                    "drive_sync_error",
                ]
            )
        else:
            assin.status = AssinaturaDocumento.Status.PARCIAL
            assin.save(update_fields=["status"])

    assin.refresh_from_db()
    if assin.status == AssinaturaDocumento.Status.CONCLUIDO and (
        assin.usuario_drive_id and assin.drive_parent_folder_id and assin.drive_target_filename
    ):
        try:
            _sync_drive_replace(
                user=assin.usuario_drive,
                parent_id=assin.drive_parent_folder_id,
                target_filename=assin.drive_target_filename,
                signed_bytes=signed,
            )
            AssinaturaDocumento.objects.filter(pk=assin.pk).update(drive_sync_error="")
        except GoogleDriveIntegrationNotConfigured as exc:
            msg = f"Drive nao configurado: {exc}"
            logger.warning("Drive nao configurado ao sincronizar assinatura", exc_info=exc)
            AssinaturaDocumento.objects.filter(pk=assin.pk).update(drive_sync_error=msg[:2000])
        except Exception as exc:
            msg = str(exc) or exc.__class__.__name__
            logger.exception("Falha ao atualizar PDF assinado no Google Drive (assinatura local mantida)")
            AssinaturaDocumento.objects.filter(pk=assin.pk).update(drive_sync_error=msg[:2000])


# Compat: testes antigos chamam processar_assinatura(assin=...)
def processar_assinatura(
    *,
    assin: AssinaturaDocumento,
    nome_assinante: str,
    signature_data_url: str,
    ip: str | None,
    user_agent: str,
    cpf_digitado: str = "",
    usuario=None,
) -> None:
    etapa = assin.etapas.order_by("ordem").first()
    if not etapa:
        raise ValueError("Pedido sem etapas de assinatura.")
    processar_assinatura_etapa(
        etapa=etapa,
        nome_assinante=nome_assinante,
        cpf_digitado=cpf_digitado,
        signature_data_url=signature_data_url,
        ip=ip,
        user_agent=user_agent,
        usuario=usuario,
    )
