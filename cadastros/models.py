from django.db import models


class Unidade(models.Model):
    nome = models.CharField(max_length=255)
    sigla = models.CharField(max_length=50, blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Unidade"
        verbose_name_plural = "Unidades"

    def __str__(self):
        return self.sigla or self.nome


class Cidade(models.Model):
    nome = models.CharField(max_length=255)
    uf = models.CharField(max_length=2, default="PR")
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["uf", "nome"]
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"

    def __str__(self):
        return f"{self.nome}/{self.uf}"


class Servidor(models.Model):
    nome = models.CharField(max_length=255)
    matricula = models.CharField(max_length=50, blank=True)
    cargo = models.CharField(max_length=120, blank=True)
    cpf = models.CharField(max_length=14, blank=True)
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servidores",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Servidor"
        verbose_name_plural = "Servidores"

    def __str__(self):
        return self.nome


class Motorista(models.Model):
    servidor = models.OneToOneField(
        Servidor,
        on_delete=models.CASCADE,
        related_name="motorista",
    )
    cnh = models.CharField(max_length=50, blank=True)
    categoria_cnh = models.CharField(max_length=10, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Motorista"
        verbose_name_plural = "Motoristas"

    def __str__(self):
        return self.servidor.nome


class Viatura(models.Model):
    placa = models.CharField(max_length=20, unique=True)
    modelo = models.CharField(max_length=120, blank=True)
    marca = models.CharField(max_length=120, blank=True)
    tipo = models.CharField(max_length=120, blank=True)
    combustivel = models.CharField(max_length=120, blank=True)
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="viaturas",
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["placa"]
        verbose_name = "Viatura"
        verbose_name_plural = "Viaturas"

    def __str__(self):
        return self.placa