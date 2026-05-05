import re

from django.db import models, transaction
from django.db.models import Q, UniqueConstraint
from django.utils import timezone

from core.utils.masks import RG_NAO_POSSUI_CANONICAL, format_masked_display, format_placa


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


class Estado(TimeStampedModel):
    nome = models.CharField(max_length=128)
    sigla = models.CharField(max_length=2, unique=True)
    codigo_ibge = models.PositiveSmallIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Estado"
        verbose_name_plural = "Estados"
        constraints = [
            models.UniqueConstraint(fields=["nome"], name="unique_estado_nome"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.sigla})"

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        self.sigla = (self.sigla or "").strip().upper()[:2]
        super().save(*args, **kwargs)


class Cidade(TimeStampedModel):
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, related_name="cidades")
    nome = models.CharField(max_length=255)
    uf = models.CharField(max_length=2)
    codigo_ibge = models.PositiveIntegerField(null=True, blank=True)
    capital = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        ordering = ["estado__sigla", "nome"]
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        constraints = [
            models.UniqueConstraint(fields=["nome", "estado"], name="unique_cidade_nome_estado"),
            models.UniqueConstraint(
                fields=["codigo_ibge"],
                name="unique_cidade_codigo_ibge_nn",
                condition=models.Q(codigo_ibge__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.nome}/{self.uf}"

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        if self.estado_id:
            self.uf = self.estado.sigla
        else:
            self.uf = (self.uf or "").strip().upper()[:2]
        super().save(*args, **kwargs)


class Cargo(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)
    is_padrao = models.BooleanField(default=False)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Cargo"
        verbose_name_plural = "Cargos"

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = " ".join(self.nome.strip().upper().split())
        super().save(*args, **kwargs)
        if self.is_padrao:
            Cargo.objects.select_for_update().exclude(pk=self.pk).filter(is_padrao=True).update(is_padrao=False)

    def __str__(self):
        return self.nome


class Combustivel(TimeStampedModel):
    nome = models.CharField(max_length=120, unique=True)
    is_padrao = models.BooleanField(default=False)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Combustível"
        verbose_name_plural = "Combustíveis"

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = " ".join(self.nome.strip().upper().split())
        super().save(*args, **kwargs)
        if self.is_padrao:
            Combustivel.objects.select_for_update().exclude(pk=self.pk).filter(is_padrao=True).update(is_padrao=False)

    def __str__(self):
        return self.nome


class Servidor(TimeStampedModel):
    nome = models.CharField(max_length=255)
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="servidores",
    )
    cpf = models.CharField(max_length=11, blank=True, default="")
    rg = models.CharField(max_length=30, blank=True, default="")
    sem_rg = models.BooleanField(default=False)
    telefone = models.CharField(max_length=11, blank=True, default="")
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
        constraints = [
            UniqueConstraint(fields=["nome"], name="cadastros_servidor_nome_unique"),
            UniqueConstraint(
                fields=["cpf"],
                condition=Q(cpf__gt=""),
                name="cadastros_servidor_cpf_unique_nn",
            ),
            UniqueConstraint(
                fields=["rg"],
                condition=Q(rg__gt="") & ~Q(rg=RG_NAO_POSSUI_CANONICAL),
                name="cadastros_servidor_rg_unique_nn",
            ),
            UniqueConstraint(
                fields=["telefone"],
                condition=Q(telefone__gt=""),
                name="cadastros_servidor_telefone_unique_nn",
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def cpf_formatado(self):
        return format_masked_display("cpf", self.cpf)

    @property
    def rg_formatado(self):
        if self.sem_rg:
            return format_masked_display("rg", RG_NAO_POSSUI_CANONICAL)
        return format_masked_display("rg", self.rg)

    @property
    def telefone_formatado(self):
        return format_masked_display("telefone", self.telefone)

    def esta_completo(self) -> bool:
        """Útil para fluxos futuros; não bloqueia CRUD."""
        if not (self.nome or "").strip():
            return False
        if not self.cargo_id:
            return False
        cpf = (self.cpf or "").strip()
        if len(cpf) != 11 or not cpf.isdigit():
            return False
        if self.sem_rg:
            return True
        rg = (self.rg or "").strip()
        return bool(rg and rg != RG_NAO_POSSUI_CANONICAL)

    def save(self, *args, **kwargs):
        self.nome = " ".join((self.nome or "").strip().split()).upper()
        self.cpf = "".join(c for c in (self.cpf or "") if c.isdigit())
        if self.sem_rg:
            self.rg = RG_NAO_POSSUI_CANONICAL
        else:
            self.rg = "".join(c for c in (self.rg or "").upper() if c.isalnum())
        self.telefone = "".join(c for c in (self.telefone or "") if c.isdigit())
        super().save(*args, **kwargs)


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
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, blank=True, default="")
    motoristas = models.ManyToManyField(
        Servidor,
        blank=True,
        related_name="viaturas_que_dirige",
        verbose_name="Motoristas",
    )

    class Meta:
        ordering = ["placa"]
        verbose_name = "Viatura"
        verbose_name_plural = "Viaturas"

    def __str__(self):
        return self.placa

    @property
    def placa_formatada(self):
        return format_placa(self.placa)

    def _placa_valida(self) -> bool:
        p = (self.placa or "").strip()
        if not p or len(p) != 7:
            return False
        return bool(
            re.match(r"^[A-Z]{3}[0-9]{4}$", p) or re.match(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$", p)
        )

    def esta_completo(self) -> bool:
        if not self._placa_valida():
            return False
        if not (self.modelo or "").strip():
            return False
        if not self.combustivel_id:
            return False
        return bool((self.tipo or "").strip())

    def save(self, *args, **kwargs):
        self.placa = "".join(c for c in (self.placa or "").upper() if c.isalnum())
        self.modelo = " ".join((self.modelo or "").strip().split()).upper()
        self.tipo = (self.tipo or "").strip().upper()
        super().save(*args, **kwargs)


class ConfiguracaoSistema(TimeStampedModel):
    """Singleton (pk=1): dados institucionais para documentos e regras globais."""

    cidade_sede_padrao = models.ForeignKey(
        Cidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Cidade sede padrão",
    )
    prazo_justificativa_dias = models.PositiveIntegerField(default=10)
    nome_orgao = models.CharField(max_length=200, blank=True)
    sigla_orgao = models.CharField(max_length=20, blank=True)
    divisao = models.CharField(max_length=120, blank=True, default="")
    unidade = models.CharField(max_length=120, blank=True, default="")
    cep = models.CharField(max_length=9, blank=True, default="")
    logradouro = models.CharField(max_length=160, blank=True, default="")
    bairro = models.CharField(max_length=120, blank=True, default="")
    cidade_endereco = models.CharField(max_length=120, blank=True, default="")
    uf = models.CharField(max_length=2, blank=True, default="")
    numero = models.CharField(max_length=20, blank=True, default="")
    telefone = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    sede = models.CharField(max_length=200, blank=True, default="")
    nome_chefia = models.CharField(max_length=120, blank=True, default="")
    cargo_chefia = models.CharField(max_length=120, blank=True, default="")
    coordenador_adm_plano_trabalho = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Coordenador administrativo padrão (Plano de Trabalho)",
    )
    pt_ultimo_numero = models.PositiveIntegerField(default=0)
    pt_ano = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Configuração do sistema"
        verbose_name_plural = "Configurações do sistema"

    def __str__(self):
        return "Configurações do sistema"

    @property
    def cep_formatado(self):
        return format_masked_display("cep", self.cep)

    @property
    def telefone_formatado(self):
        return format_masked_display("telefone", self.telefone)

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={"prazo_justificativa_dias": 10})
        return obj

    def save(self, *args, **kwargs):
        def norm_upper_words(val):
            val = (val or "").strip()
            return " ".join(val.split()).upper() if val else ""

        self.nome_orgao = norm_upper_words(self.nome_orgao)
        self.sigla_orgao = norm_upper_words(self.sigla_orgao)
        self.divisao = norm_upper_words(self.divisao)
        self.unidade = norm_upper_words(self.unidade)
        self.sede = norm_upper_words(self.sede)
        self.nome_chefia = norm_upper_words(self.nome_chefia)
        self.cargo_chefia = norm_upper_words(self.cargo_chefia)
        self.cidade_endereco = norm_upper_words(self.cidade_endereco)
        self.logradouro = norm_upper_words(self.logradouro)
        self.bairro = norm_upper_words(self.bairro)
        self.numero = norm_upper_words(self.numero)
        self.uf = (self.uf or "").strip().upper()[:2]
        self.cep = "".join(c for c in (self.cep or "") if c.isdigit())
        self.telefone = "".join(c for c in (self.telefone or "") if c.isdigit())
        # Mantém compatível com código que ainda lê `sede`: mesmo valor que cidade_endereco.
        self.sede = self.cidade_endereco
        super().save(*args, **kwargs)


class AssinaturaConfiguracao(TimeStampedModel):
    TIPO_OFICIO = "OFICIO"
    TIPO_JUSTIFICATIVA = "JUSTIFICATIVA"
    TIPO_PLANO_TRABALHO = "PLANO_TRABALHO"
    TIPO_ORDEM_SERVICO = "ORDEM_SERVICO"
    TIPO_TERMO_AUTORIZACAO = "TERMO_AUTORIZACAO"
    TIPO_CHOICES = [
        (TIPO_OFICIO, "Ofício"),
        (TIPO_JUSTIFICATIVA, "Justificativa"),
        (TIPO_PLANO_TRABALHO, "Plano de Trabalho"),
        (TIPO_ORDEM_SERVICO, "Ordem de Serviço"),
        (TIPO_TERMO_AUTORIZACAO, "Termo de Autorização"),
    ]

    configuracao = models.ForeignKey(
        ConfiguracaoSistema,
        on_delete=models.CASCADE,
        related_name="assinaturas",
    )
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    ordem = models.PositiveSmallIntegerField(default=1)
    servidor = models.ForeignKey(
        Servidor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Assinatura (configuração)"
        verbose_name_plural = "Assinaturas (configuração)"
        constraints = [
            UniqueConstraint(
                fields=["configuracao", "tipo", "ordem"],
                name="uniq_assinatura_cfg_tipo_ordem",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} (ordem {self.ordem})"
