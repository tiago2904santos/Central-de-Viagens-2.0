from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify


def _rt_upload_to(instance, filename):
    base = Path(filename or "").name.strip() or "relatorio-tecnico.docx"
    ext = Path(base).suffix.lower() or ".docx"
    stem = slugify(Path(base).stem) or "relatorio-tecnico"
    return f"prestacao_contas/rt/{instance.prestacao_id}/{stem}-{uuid.uuid4().hex[:10]}{ext}"


class PrestacaoConta(models.Model):
    STATUS_RT_PENDENTE = "pendente"
    STATUS_RT_RASCUNHO = "rascunho"
    STATUS_RT_GERADO = "gerado"
    STATUS_RT_CHOICES = [
        (STATUS_RT_PENDENTE, "Pendente"),
        (STATUS_RT_RASCUNHO, "Rascunho"),
        (STATUS_RT_GERADO, "Gerado"),
    ]

    oficio = models.ForeignKey("eventos.Oficio", on_delete=models.CASCADE, related_name="prestacoes_contas")
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
    status_rt = models.CharField(
        "Status do RT",
        max_length=20,
        choices=STATUS_RT_CHOICES,
        default=STATUS_RT_PENDENTE,
        db_index=True,
    )
    rt_atualizado_em = models.DateTimeField("RT atualizado em", null=True, blank=True)
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

    diaria = models.CharField(max_length=80, blank=True, default="")
    translado = models.CharField(max_length=80, blank=True, default="")
    passagem = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
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
