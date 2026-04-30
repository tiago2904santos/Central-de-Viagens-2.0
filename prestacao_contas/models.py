from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


def _rt_upload_to(instance, filename):
    base = Path(filename or "").name.strip() or "relatorio-tecnico.docx"
    ext = Path(base).suffix.lower() or ".docx"
    stem = slugify(Path(base).stem) or "relatorio-tecnico"
    return f"prestacao_contas/rt/{instance.prestacao_id}/{stem}-{uuid.uuid4().hex[:10]}{ext}"


# Funções de upload definidas no nível do módulo para migração
def _despacho_upload_to(instance, filename):
    base = Path(filename or "").name.strip() or "despacho.pdf"
    ext = Path(base).suffix.lower() or ".pdf"
    stem = slugify(Path(base).stem) or "despacho"
    return f"prestacao_contas/despachos/{instance.pk or 'nova'}/{stem}-{uuid.uuid4().hex[:10]}{ext}"


def _comprovante_upload_to(instance, filename):
    base = Path(filename or "").name.strip() or "comprovante.pdf"
    ext = Path(base).suffix.lower() or ".pdf"
    stem = slugify(Path(base).stem) or "comprovante"
    return f"prestacao_contas/comprovantes/{instance.pk or 'nova'}/{stem}-{uuid.uuid4().hex[:10]}{ext}"


class PrestacaoConta(models.Model):
    STATUS_RASCUNHO = "rascunho"
    STATUS_EM_ANDAMENTO = "em_andamento"
    STATUS_CONCLUIDA = "concluida"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_EM_ANDAMENTO, "Em andamento"),
        (STATUS_CONCLUIDA, "Concluida"),
    ]

    STATUS_RT_PENDENTE = "pendente"
    STATUS_RT_RASCUNHO = "rascunho"
    STATUS_RT_GERADO = "gerado"
    STATUS_RT_CHOICES = [
        (STATUS_RT_PENDENTE, "Pendente"),
        (STATUS_RT_RASCUNHO, "Rascunho"),
        (STATUS_RT_GERADO, "Gerado"),
    ]
    STATUS_DB_PENDENTE = "pendente"
    STATUS_DB_RASCUNHO = "rascunho"
    STATUS_DB_GERADO = "gerado"
    STATUS_DB_CHOICES = [
        (STATUS_DB_PENDENTE, "Pendente"),
        (STATUS_DB_RASCUNHO, "Rascunho"),
        (STATUS_DB_GERADO, "Gerado"),
    ]

    oficio = models.ForeignKey("eventos.Oficio", on_delete=models.CASCADE, related_name="prestacoes_contas")
    descricao_evento = models.CharField("Descricao do evento", max_length=255, blank=True, default="")
    despacho_pdf = models.FileField(
        "Despacho PDF",
        upload_to=_despacho_upload_to,
        validators=[FileExtensionValidator(["pdf"])],
        blank=True,
        null=True,
    )
    comprovante_transferencia = models.FileField(
        "Comprovante de transferencia",
        upload_to=_comprovante_upload_to,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"])],
        blank=True,
        null=True,
    )
    servidor = models.ForeignKey(
        "cadastros.Viajante",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prestacoes_contas",
    )
    nome_servidor = models.CharField("Nome do servidor", max_length=180, blank=True, default="")
    rg_servidor = models.CharField("RG do servidor", max_length=30, blank=True, default="")
    cpf_servidor = models.CharField("CPF do servidor", max_length=14, blank=True, default="")
    cargo_servidor = models.CharField("Cargo do servidor", max_length=120, blank=True, default="")
    status = models.CharField(
        "Status da prestacao",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RASCUNHO,
        db_index=True,
    )
    status_rt = models.CharField(
        "Status do RT",
        max_length=20,
        choices=STATUS_RT_CHOICES,
        default=STATUS_RT_PENDENTE,
        db_index=True,
    )
    dados_db = models.JSONField("Dados do DB", blank=True, default=dict)
    status_db = models.CharField(
        "Status do DB",
        max_length=20,
        choices=STATUS_DB_CHOICES,
        default=STATUS_DB_PENDENTE,
        db_index=True,
    )
    rt_atualizado_em = models.DateTimeField("RT atualizado em", null=True, blank=True)
    db_atualizado_em = models.DateTimeField("DB atualizado em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["oficio", "servidor"],
                condition=Q(servidor__isnull=False),
                name="prestacao_conta_oficio_servidor_unique",
            )
        ]

    def __str__(self):
        return f"Prestação {self.oficio.numero_formatado} - {self.nome_servidor or self.pk}"


class RelatorioTecnicoPrestacao(models.Model):
    STATUS_RASCUNHO = "rascunho"
    STATUS_GERADO = "gerado"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_GERADO, "Gerado"),
    ]

    prestacao = models.OneToOneField(PrestacaoConta, on_delete=models.CASCADE, related_name="relatorio_tecnico")
    oficio = models.ForeignKey("eventos.Oficio", on_delete=models.CASCADE, related_name="relatorios_tecnicos_prestacao")
    servidor = models.ForeignKey(
        "cadastros.Viajante",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relatorios_tecnicos_prestacao",
    )
    nome_servidor = models.CharField(max_length=180, blank=True, default="")
    rg_servidor = models.CharField(max_length=30, blank=True, default="")
    cpf_servidor = models.CharField(max_length=14, blank=True, default="")
    cargo_servidor = models.CharField(max_length=120, blank=True, default="")
    unidade_servidor = models.CharField(max_length=160, blank=True, default="")

    diaria = models.CharField(max_length=80, blank=True, default="")
    combustivel = models.CharField(max_length=80, blank=True, default="Cartao Prime")
    teve_translado = models.BooleanField(default=False)
    valor_translado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    translado = models.CharField(max_length=80, blank=True, default="")
    teve_passagem = models.BooleanField(default=False)
    valor_passagem = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    passagem = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    atividade_codigos = models.CharField(max_length=500, blank=True, default="")
    atividade = models.TextField(blank=True, default="")
    conclusao = models.TextField(blank=True, default="")
    medidas = models.TextField(blank=True, default="")
    informacoes_complementares = models.TextField(blank=True, default="")

    arquivo_docx = models.FileField(upload_to=_rt_upload_to, blank=True, null=True)
    arquivo_pdf = models.FileField(upload_to=_rt_upload_to, blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO, db_index=True)
    data_geracao = models.DateTimeField(null=True, blank=True)
    gerado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="relatorios_tecnicos_gerados",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def marcar_como_gerado(self, usuario=None):
        self.status = self.STATUS_GERADO
        self.data_geracao = timezone.now()
        if usuario:
            self.gerado_por = usuario
        self.save(update_fields=["status", "data_geracao", "gerado_por", "updated_at"])
        self.prestacao.status_rt = PrestacaoConta.STATUS_RT_GERADO
        self.prestacao.rt_atualizado_em = timezone.now()
        self.prestacao.save(update_fields=["status_rt", "rt_atualizado_em", "updated_at"])


class TextoPadraoDocumento(models.Model):
    CATEGORIA_OFICIO_MOTIVO = "oficio_motivo_viagem"
    CATEGORIA_RT_CONCLUSAO = "relatorio_tecnico_conclusao"
    CATEGORIA_RT_MEDIDAS = "relatorio_tecnico_medidas"
    CATEGORIA_RT_INFO = "relatorio_tecnico_informacoes_complementares"
    CATEGORIA_CHOICES = [
        (CATEGORIA_OFICIO_MOTIVO, "Oficio - Motivo de viagem"),
        (CATEGORIA_RT_CONCLUSAO, "RT - Conclusao"),
        (CATEGORIA_RT_MEDIDAS, "RT - Medidas"),
        (CATEGORIA_RT_INFO, "RT - Informacoes complementares"),
    ]

    categoria = models.CharField(max_length=60, choices=CATEGORIA_CHOICES, db_index=True)
    titulo = models.CharField(max_length=160)
    texto = models.TextField()
    is_padrao = models.BooleanField(default=False)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveIntegerField(default=0)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="textos_padrao_documento_criados",
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["categoria", "ordem", "titulo"]
        constraints = [
            models.UniqueConstraint(
                fields=["categoria", "titulo"],
                name="texto_padrao_documento_categoria_titulo_unique",
            )
        ]

    def __str__(self):
        return f"{self.get_categoria_display()} - {self.titulo}"
