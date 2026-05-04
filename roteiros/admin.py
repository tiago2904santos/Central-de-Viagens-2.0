from django.contrib import admin

from .models import Roteiro
from .models import TrechoRoteiro


@admin.register(Roteiro)
class RoteiroAdmin(admin.ModelAdmin):
    list_display = ("nome", "origem", "destino", "data_inicio", "data_fim", "updated_at")
    search_fields = ("nome", "descricao", "origem__nome", "destino__nome")
    list_filter = ("origem__estado", "destino__estado", "data_inicio")
    ordering = ("-updated_at", "nome")


@admin.register(TrechoRoteiro)
class TrechoRoteiroAdmin(admin.ModelAdmin):
    list_display = ("roteiro", "ordem", "origem", "destino", "data_saida", "data_chegada")
    search_fields = ("roteiro__nome", "origem__nome", "destino__nome")
    list_filter = ("origem__estado", "destino__estado")
    ordering = ("roteiro", "ordem")
