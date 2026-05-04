from django.db import models

from cadastros.models import Cidade
from cadastros.models import TimeStampedModel


class Roteiro(TimeStampedModel):
    """
    Roteiro avulso e reutilizável. Não depende de Evento, Ofício ou outros documentos.

    Origem e destino usam a base interna de municípios (`cadastros.Cidade`).
    """

    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    origem = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="roteiros_como_origem",
    )
    destino = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="roteiros_como_destino",
    )
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["-updated_at", "nome"]
        verbose_name = "Roteiro"
        verbose_name_plural = "Roteiros"

    def __str__(self):
        return f"{self.nome} ({self.origem} -> {self.destino})"


class TrechoRoteiro(TimeStampedModel):
    """
    Trecho de deslocamento vinculado a um `Roteiro` (cascade na exclusão do roteiro).
    Sem distância, tempo ou diária nesta etapa.
    """

    roteiro = models.ForeignKey(Roteiro, on_delete=models.CASCADE, related_name="trechos")
    ordem = models.PositiveIntegerField(default=1)
    origem = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="trechos_como_origem",
    )
    destino = models.ForeignKey(
        Cidade,
        on_delete=models.PROTECT,
        related_name="trechos_como_destino",
    )
    data_saida = models.DateTimeField(null=True, blank=True)
    data_chegada = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["roteiro", "ordem"]
        verbose_name = "Trecho de roteiro"
        verbose_name_plural = "Trechos de roteiro"

    def __str__(self):
        return f"{self.roteiro.nome} - trecho {self.ordem}: {self.origem} -> {self.destino}"
