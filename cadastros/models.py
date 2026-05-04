from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Unidade(TimeStampedModel):
    nome = models.CharField(max_length=255)
    sigla = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"

    def __str__(self):
        return self.sigla or self.nome

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        self.sigla = " ".join((self.sigla or "").strip().split()).upper()
        super().save(*args, **kwargs)


class Cidade(TimeStampedModel):
    nome = models.CharField(max_length=255)
    uf = models.CharField(max_length=2, default="PR")

    class Meta:
        ordering = ["uf", "nome"]
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        constraints = [
            models.UniqueConstraint(fields=["nome", "uf"], name="unique_cidade_nome_uf"),
        ]

    def __str__(self):
        return f"{self.nome}/{self.uf}"

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        self.uf = (self.uf or "").strip().upper()
        super().save(*args, **kwargs)


class Cargo(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Combustivel(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Combustível"
        verbose_name_plural = "Combustíveis"

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Servidor(TimeStampedModel):
    nome = models.CharField(max_length=255, unique=True)
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="servidores",
    )
    cpf = models.CharField(max_length=11, blank=True)
    rg = models.CharField(max_length=20, blank=True)
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="servidores",
    )

    class Meta:
        ordering = ["nome"]
        verbose_name = "Servidor"
        verbose_name_plural = "Servidores"

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        self.cpf = "".join(c for c in (self.cpf or "") if c.isdigit())
        self.rg = "".join(c for c in (self.rg or "").upper() if c.isalnum())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome


class Viatura(TimeStampedModel):
    TIPO_CARACTERIZADA = "CARACTERIZADA"
    TIPO_DESCARACTERIZADA = "DESCARACTERIZADA"
    TIPO_CHOICES = [
        (TIPO_CARACTERIZADA, "Caracterizada"),
        (TIPO_DESCARACTERIZADA, "Descaracterizada"),
    ]

    placa = models.CharField(max_length=7, unique=True)
    modelo = models.CharField(max_length=120, blank=True)
    combustivel = models.ForeignKey(
        Combustivel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="viaturas",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True)

    class Meta:
        ordering = ["placa"]
        verbose_name = "Viatura"
        verbose_name_plural = "Viaturas"

    def save(self, *args, **kwargs):
        self.placa = "".join(c for c in (self.placa or "").upper() if c.isalnum())
        self.modelo = " ".join((self.modelo or "").strip().split()).upper()
        self.tipo = (self.tipo or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.placa
