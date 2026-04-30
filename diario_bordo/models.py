from __future__ import annotations

import uuid
from pathlib import Path

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify


def _db_upload_path(instance, filename, subfolder, default_name):
    base = Path(filename or "").name.strip() or default_name
    ext = Path(base).suffix.lower() or Path(default_name).suffix
    stem = slugify(Path(base).stem) or Path(default_name).stem
    return f"diario_bordo/{subfolder}/{instance.pk or 'novo'}/{stem}-{uuid.uuid4().hex[:10]}{ext}"


def diario_pdf_upload_to(instance, filename):
    return _db_upload_path(instance, filename, "pdf", "diario-bordo.pdf")


def diario_docx_upload_to(instance, filename):
    return _db_upload_path(instance, filename, "docx", "diario-bordo.docx")


def diario_xlsx_upload_to(instance, filename):
    return _db_upload_path(instance, filename, "xlsx", "diario-bordo.xlsx")


def diario_assinado_upload_to(instance, filename):
    return _db_upload_path(instance, filename, "assinados", "diario-bordo-assinado.pdf")


class DiarioBordo(models.Model):
    STATUS_RASCUNHO = "rascunho"
    STATUS_GERADO = "gerado"
    STATUS_ASSINADO = "assinado"
    STATUS_CANCELADO = "cancelado"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_GERADO, "Gerado"),
        (STATUS_ASSINADO, "Assinado"),
        (STATUS_CANCELADO, "Cancelado"),
    ]

    oficio = models.ForeignKey(
        "eventos.Oficio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_bordo",
        verbose_name="Oficio vinculado",
    )
    prestacao = models.ForeignKey(
        "prestacao_contas.PrestacaoConta",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_bordo",
        verbose_name="Prestacao de contas",
    )
    roteiro = models.ForeignKey(
        "eventos.RoteiroEvento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_bordo",
        verbose_name="Roteiro vinculado",
    )
    veiculo = models.ForeignKey(
        "cadastros.Veiculo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_bordo",
        verbose_name="Viatura/veiculo",
    )
    motorista = models.ForeignKey(
        "cadastros.Viajante",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="diarios_bordo_motorista",
        verbose_name="Motorista/responsavel",
    )

    numero_oficio = models.CharField("Numero do oficio", max_length=80, blank=True, default="")
    e_protocolo = models.CharField("E-protocolo", max_length=80, blank=True, default="")
    divisao = models.CharField("Divisao", max_length=160, blank=True, default="")
    unidade_cabecalho = models.CharField("Unidade", max_length=180, blank=True, default="")
    tipo_veiculo = models.CharField("Tipo do veiculo", max_length=80, blank=True, default="")
    combustivel = models.CharField("Combustivel", max_length=80, blank=True, default="")
    placa_oficial = models.CharField("Placa oficial", max_length=20, blank=True, default="")
    placa_reservada = models.CharField("Placa reservada", max_length=20, blank=True, default="")
    nome_responsavel = models.CharField("Nome do responsavel", max_length=160, blank=True, default="")
    rg_responsavel = models.CharField("RG do responsavel", max_length=40, blank=True, default="")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO, db_index=True)
    arquivo_pdf = models.FileField(
        upload_to=diario_pdf_upload_to,
        validators=[FileExtensionValidator(["pdf"])],
        blank=True,
        null=True,
    )
    arquivo_docx = models.FileField(upload_to=diario_docx_upload_to, blank=True, null=True)
    arquivo_xlsx = models.FileField(upload_to=diario_xlsx_upload_to, blank=True, null=True)
    arquivo_assinado = models.FileField(
        upload_to=diario_assinado_upload_to,
        validators=[FileExtensionValidator(["pdf"])],
        blank=True,
        null=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-atualizado_em", "-criado_em"]
        verbose_name = "Diario de Bordo"
        verbose_name_plural = "Diarios de Bordo"

    def __str__(self):
        referencia = self.numero_oficio or f"#{self.pk or 'novo'}"
        return f"Diario de Bordo {referencia}"

    @property
    def total_trechos(self):
        return self.trechos.count() if self.pk else 0


class DiarioBordoTrecho(models.Model):
    diario = models.ForeignKey(DiarioBordo, on_delete=models.CASCADE, related_name="trechos")
    ordem = models.PositiveIntegerField(default=0)
    data_saida = models.DateField("Data de saida", null=True, blank=True)
    hora_saida = models.TimeField("Hora de saida", null=True, blank=True)
    km_inicial = models.PositiveIntegerField("KM inicial", null=True, blank=True)
    data_chegada = models.DateField("Data de chegada", null=True, blank=True)
    hora_chegada = models.TimeField("Hora de chegada", null=True, blank=True)
    km_final = models.PositiveIntegerField("KM final", null=True, blank=True)
    origem = models.CharField(max_length=160)
    destino = models.CharField(max_length=160)
    necessidade_abastecimento = models.BooleanField("Necessidade de abastecimento", default=False)
    observacao = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["ordem", "id"]
        verbose_name = "Trecho do Diario de Bordo"
        verbose_name_plural = "Trechos do Diario de Bordo"

    def __str__(self):
        return f"{self.ordem + 1}. {self.origem} -> {self.destino}"
