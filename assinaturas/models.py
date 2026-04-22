import uuid

from django.conf import settings
from django.db import models


def _upload_original(instance, filename):
    return f"assinaturas/{instance.pk}/original.pdf"


def _upload_assinado(instance, filename):
    return f"assinaturas/{instance.pk}/assinado.pdf"


def _upload_backup(instance, filename):
    return f"assinaturas/{instance.pk}/backup_antes_assinatura.pdf"


def _upload_etapa_resultado(instance, filename):
    return f"assinaturas/{instance.assinatura_id}/etapa_{instance.ordem}_resultado.pdf"


class AssinaturaDocumento(models.Model):
    """Pedido de assinatura eletronica (documento gerado pelo sistema)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        PARCIAL = "parcial", "Parcialmente assinado"
        CONCLUIDO = "concluido", "Concluido"
        INVALIDADO_ALTERACAO = "invalidado_alteracao", "Invalidado por alteracao"

    documento_tipo = models.CharField(
        "Tipo do documento",
        max_length=120,
        help_text="Ex.: eventos.Oficio (app_label.ModelName)",
    )
    documento_id = models.PositiveIntegerField("ID do registo")
    campo_arquivo = models.CharField(
        "Campo ficheiro no model (legado / opcional)",
        max_length=80,
        blank=True,
        default="",
    )

    token = models.UUIDField(
        "Token legado do link",
        null=True,
        blank=True,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Antes da multi-etapa; usar AssinaturaEtapa.token.",
    )

    verificacao_token = models.UUIDField(
        "Token publico de verificacao",
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="URL de verificacao do documento assinado (nao assina).",
    )

    arquivo_original = models.FileField(
        "Copia do PDF original (gerado)",
        upload_to=_upload_original,
    )
    arquivo_assinado = models.FileField(
        "PDF assinado final (todas as etapas)",
        upload_to=_upload_assinado,
        blank=True,
        null=True,
    )
    arquivo_backup_documento = models.FileField(
        "Backup do ficheiro no documento antes de substituir",
        upload_to=_upload_backup,
        blank=True,
        null=True,
    )

    arquivo_original_sha256 = models.CharField(
        "SHA-256 do PDF original (envio)",
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    arquivo_assinado_sha256 = models.CharField(
        "SHA-256 do PDF assinado final",
        max_length=64,
        blank=True,
        default="",
    )

    nome_assinante = models.CharField("Nome do ultimo assinante", max_length=200, blank=True, default="")
    nome_assinante_normalizado = models.CharField(
        "Nome normalizado (auditoria)",
        max_length=220,
        blank=True,
        default="",
        help_text="NFKC, espacos colapsados, casefold — comparacao e registo.",
    )
    status = models.CharField(
        "Estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )

    ip = models.GenericIPAddressField("IP (ultima etapa)", null=True, blank=True)
    user_agent = models.TextField("User-Agent (ultima etapa)", blank=True, default="")

    usuario_drive = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_drive_sync",
        verbose_name="Utilizador para sincronizar Drive",
        help_text="Se preenchido com parent e nome, tenta substituir o PDF no Drive apos concluir.",
    )
    drive_parent_folder_id = models.CharField(
        "ID pasta pai no Drive",
        max_length=255,
        blank=True,
        default="",
    )
    drive_target_filename = models.CharField(
        "Nome do ficheiro no Drive",
        max_length=255,
        blank=True,
        default="",
    )
    drive_sync_error = models.TextField(
        "Ultimo erro de sincronizacao com o Drive",
        blank=True,
        default="",
        help_text="Preenchido se a assinatura local tiver sucesso mas o Drive falhar.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        "Expira em",
        null=True,
        blank=True,
        db_index=True,
        help_text="Apos esta data o link deixa de aceitar assinatura.",
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    invalidado_em = models.DateTimeField("Invalidado em", null=True, blank=True)
    invalidado_motivo = models.CharField(
        "Motivo da invalidacao",
        max_length=280,
        blank=True,
        default="",
    )

    usuario_ultima_etapa = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_documento_ultima_etapa",
        verbose_name="Utilizador autenticado (ultima etapa)",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Assinatura de documento"
        verbose_name_plural = "Assinaturas de documentos"

    def __str__(self):
        return f"Assinatura {self.pk} ({self.get_status_display()})"


class AssinaturaEtapa(models.Model):
    """Uma etapa de assinatura (um assinante, um token, ordem sequencial)."""

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        ASSINADO = "assinado", "Assinado"

    class TipoAssinante(models.TextChoices):
        INTERNO_CONFIG = "interno_config", "Servidor (configuracao do sistema)"
        TERMO_SERVIDOR = "termo_servidor", "Servidor do termo"
        EXTERNO_CHEFIA = "externo_chefia", "Chefia (externa)"

    assinatura = models.ForeignKey(
        AssinaturaDocumento,
        on_delete=models.CASCADE,
        related_name="etapas",
        verbose_name="Pedido",
    )
    ordem = models.PositiveSmallIntegerField("Ordem", db_index=True)
    token = models.UUIDField("Token do link", default=uuid.uuid4, unique=True, editable=False, db_index=True)

    tipo_assinante = models.CharField(
        "Tipo de assinante",
        max_length=24,
        choices=TipoAssinante.choices,
    )
    nome_previsto = models.CharField(
        "Nome previsto (exibicao)",
        max_length=200,
        blank=True,
        default="",
    )
    email_previsto = models.CharField("E-mail previsto", max_length=254, blank=True, default="")
    telefone_previsto = models.CharField("Telefone previsto", max_length=40, blank=True, default="")
    viajante = models.ForeignKey(
        "cadastros.Viajante",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_etapas",
        verbose_name="Viajante (interno)",
    )

    cpf_esperado_normalizado = models.CharField(
        "CPF esperado (11 digitos, auditoria)",
        max_length=11,
        blank=True,
        default="",
        help_text="Vazio para etapas sem CPF conhecido no cadastro (assinatura recusada ate corrigir).",
    )
    cpf_informado = models.CharField(
        "CPF informado (ultimos digitos / registo interno)",
        max_length=14,
        blank=True,
        default="",
        help_text="Armazena apenas digitos normalizados quando aplicavel.",
    )
    cpf_normalizado = models.CharField(
        "CPF normalizado informado",
        max_length=11,
        blank=True,
        default="",
    )
    cpf_confere = models.BooleanField("CPF confere com o esperado", default=False)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assinaturas_etapas_realizadas",
        verbose_name="Utilizador autenticado na assinatura",
    )

    status = models.CharField(
        "Estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDENTE,
        db_index=True,
    )
    expires_at = models.DateTimeField(
        "Expira em",
        null=True,
        blank=True,
        db_index=True,
    )

    nome_assinante = models.CharField("Nome declarado na assinatura", max_length=200, blank=True, default="")
    nome_assinante_normalizado = models.CharField(max_length=220, blank=True, default="")
    signed_at = models.DateTimeField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    arquivo_sha256_apos_etapa = models.CharField(max_length=64, blank=True, default="")

    resultado_pdf = models.FileField(
        "PDF apos esta etapa",
        upload_to=_upload_etapa_resultado,
        blank=True,
        null=True,
        help_text="Saida PDF apos assinar nesta etapa (entrada da etapa seguinte).",
    )

    class Meta:
        ordering = ["assinatura_id", "ordem"]
        verbose_name = "Etapa de assinatura"
        verbose_name_plural = "Etapas de assinatura"
        constraints = [
            models.UniqueConstraint(fields=["assinatura", "ordem"], name="uniq_assinatura_etapa_ordem"),
        ]

    def __str__(self):
        return f"Etapa {self.ordem} pedido {self.assinatura_id}"
