from decimal import Decimal, InvalidOperation

from django.db import models
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import TimeStampedModel


class Roteiro(models.Model):
    """
    Roteiro avulso (e futuramente vinculado a evento), alinhado ao legacy `RoteiroEvento`.
    """

    STATUS_RASCUNHO = "RASCUNHO"
    STATUS_FINALIZADO = "FINALIZADO"
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, "Rascunho"),
        (STATUS_FINALIZADO, "Finalizado"),
    ]

    ROTA_STATUS_PENDENTE = "pendente"
    ROTA_STATUS_CALCULADA = "calculada"
    ROTA_STATUS_MANUAL = "manual"
    ROTA_STATUS_ERRO = "erro"
    ROTA_STATUS_DESATUALIZADA = "desatualizada"
    ROTA_STATUS_CHOICES = [
        (ROTA_STATUS_PENDENTE, "Pendente"),
        (ROTA_STATUS_CALCULADA, "Calculada"),
        (ROTA_STATUS_MANUAL, "Manual"),
        (ROTA_STATUS_ERRO, "Erro"),
        (ROTA_STATUS_DESATUALIZADA, "Desatualizada"),
    ]

    ROTA_FONTE_OPENROUTESERVICE = "openrouteservice"
    ROTA_FONTE_MANUAL = "manual"
    ROTA_FONTE_CACHE = "cache"

    TIPO_EVENTO = "EVENTO"
    TIPO_AVULSO = "AVULSO"
    TIPO_CHOICES = [
        (TIPO_EVENTO, "Vinculado a evento"),
        (TIPO_AVULSO, "Avulso"),
    ]

    origem_estado = models.ForeignKey(
        Estado,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Estado sede",
    )
    origem_cidade = models.ForeignKey(
        Cidade,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Cidade sede",
    )
    saida_dt = models.DateTimeField("Data/hora saída", null=True, blank=True)
    duracao_min = models.PositiveIntegerField("Duração (min)", null=True, blank=True)
    chegada_dt = models.DateTimeField("Data/hora chegada", null=True, blank=True)
    retorno_saida_dt = models.DateTimeField("Retorno - saída", null=True, blank=True)
    retorno_duracao_min = models.PositiveIntegerField("Retorno - duração (min)", null=True, blank=True)
    retorno_chegada_dt = models.DateTimeField("Retorno - chegada", null=True, blank=True)
    quantidade_diarias = models.CharField("Quantidade de diárias", max_length=120, blank=True, default="")
    valor_diarias = models.DecimalField(
        "Valor das diárias", max_digits=12, decimal_places=2, null=True, blank=True
    )
    valor_diarias_extenso = models.TextField("Valor das diárias por extenso", blank=True, default="")
    observacoes = models.TextField("Observações", blank=True, default="")
    rota_geojson = models.JSONField("Geometria da rota (GeoJSON)", null=True, blank=True)
    rota_distancia_calculada_km = models.DecimalField(
        "Distância calculada (km)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rota_duracao_calculada_min = models.PositiveIntegerField(
        "Duração calculada (min)", null=True, blank=True
    )
    rota_fonte = models.CharField(
        "Fonte do cálculo da rota",
        max_length=40,
        blank=True,
        default="",
    )
    rota_status = models.CharField(
        "Status da rota no mapa",
        max_length=20,
        choices=ROTA_STATUS_CHOICES,
        default=ROTA_STATUS_PENDENTE,
    )
    rota_assinatura = models.CharField(
        "Assinatura para cache da rota", max_length=128, blank=True, default=""
    )
    rota_calculada_em = models.DateTimeField(
        "Rota consolidada calculada em", null=True, blank=True
    )
    rota_distancia_manual_km = models.DecimalField(
        "Distância ajustada manualmente (km)",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    rota_duracao_manual_min = models.PositiveIntegerField(
        "Duração ajustada manualmente (min)", null=True, blank=True
    )
    rota_ajuste_justificativa = models.TextField(
        "Justificativa do ajuste manual da rota", blank=True, default=""
    )
    status = models.CharField(
        "Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO
    )
    tipo = models.CharField(
        "Tipo de roteiro",
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_AVULSO,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Roteiro"
        verbose_name_plural = "Roteiros"

    def __str__(self):
        orig = self.origem_cidade or self.origem_estado
        return str(orig) if orig else f"Roteiro #{self.pk or ''}"

    def aplicar_diarias_calculadas(self, resultado):
        totais = (resultado or {}).get("totais") or {}
        self.quantidade_diarias = totais.get("total_diarias") or ""

        valor_decimal = totais.get("total_valor_decimal")
        if valor_decimal is None:
            valor_texto = (totais.get("total_valor") or "").strip()
            if valor_texto:
                try:
                    valor_decimal = Decimal(valor_texto.replace(".", "").replace(",", "."))
                except (InvalidOperation, TypeError, ValueError):
                    valor_decimal = None
        self.valor_diarias = valor_decimal
        self.valor_diarias_extenso = totais.get("valor_extenso") or ""


class RoteiroDestino(models.Model):
    roteiro = models.ForeignKey(
        Roteiro,
        on_delete=models.CASCADE,
        related_name="destinos",
        verbose_name="Roteiro",
    )
    estado = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        related_name="roteiro_destinos",
        verbose_name="Estado",
    )
    cidade = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="roteiro_destinos",
        verbose_name="Cidade",
    )
    ordem = models.PositiveIntegerField("Ordem", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["roteiro", "ordem"]
        verbose_name = "Destino do roteiro"
        verbose_name_plural = "Destinos do roteiro"

    def __str__(self):
        return f"{self.cidade} ({self.estado.sigla})"


class RoteiroTrecho(models.Model):
    TIPO_IDA = "IDA"
    TIPO_RETORNO = "RETORNO"
    TIPO_CHOICES = [
        (TIPO_IDA, "Ida"),
        (TIPO_RETORNO, "Retorno"),
    ]

    roteiro = models.ForeignKey(
        Roteiro,
        on_delete=models.CASCADE,
        related_name="trechos",
        verbose_name="Roteiro",
    )
    ordem = models.PositiveIntegerField("Ordem", default=0)
    tipo = models.CharField("Tipo", max_length=10, choices=TIPO_CHOICES, default=TIPO_IDA)
    origem_estado = models.ForeignKey(
        Estado,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Estado origem",
    )
    origem_cidade = models.ForeignKey(
        Cidade,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Cidade origem",
    )
    destino_estado = models.ForeignKey(
        Estado,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Estado destino",
    )
    destino_cidade = models.ForeignKey(
        Cidade,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Cidade destino",
    )
    saida_dt = models.DateTimeField("Saída", null=True, blank=True)
    chegada_dt = models.DateTimeField("Chegada", null=True, blank=True)
    distancia_km = models.DecimalField(
        "Distância (km)",
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    duracao_estimada_min = models.PositiveIntegerField(
        "Duração estimada (min)", null=True, blank=True
    )
    tempo_cru_estimado_min = models.PositiveIntegerField(
        "Tempo cru estimado (min)", null=True, blank=True
    )
    tempo_adicional_min = models.IntegerField(
        "Tempo adicional (min)", null=True, blank=True, default=0
    )
    rota_fonte = models.CharField("Fonte da rota", max_length=30, blank=True, default="")
    rota_calculada_em = models.DateTimeField("Rota calculada em", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["roteiro", "ordem"]
        verbose_name = "Trecho do roteiro"
        verbose_name_plural = "Trechos do roteiro"

    def __str__(self):
        orig = self.origem_cidade or self.origem_estado
        dest = self.destino_cidade or self.destino_estado
        return f"{orig} -> {dest} ({self.get_tipo_display()})"
