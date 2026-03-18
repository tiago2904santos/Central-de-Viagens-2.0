from django.contrib import admin
from .models import (
    Oficio, OficioViajante, OficioTrecho,
    Roteiro, RoteiroTrecho,
    TermoAutorizacao, Justificativa, PlanoTrabalho, OrdemServico,
    Evento, ModeloMotivo, ModeloJustificativa,
)

for model in [
    Oficio, OficioViajante, OficioTrecho,
    Roteiro, RoteiroTrecho,
    TermoAutorizacao, Justificativa, PlanoTrabalho, OrdemServico,
    Evento, ModeloMotivo, ModeloJustificativa,
]:
    admin.site.register(model)
