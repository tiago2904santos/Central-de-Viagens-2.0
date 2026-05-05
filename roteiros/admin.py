from django.contrib import admin

from .models import Roteiro
from .models import RoteiroDestino
from .models import RoteiroTrecho


class RoteiroDestinoInline(admin.TabularInline):
    model = RoteiroDestino
    extra = 0


class RoteiroTrechoInline(admin.TabularInline):
    model = RoteiroTrecho
    extra = 0


@admin.register(Roteiro)
class RoteiroAdmin(admin.ModelAdmin):
    list_display = (
        "pk",
        "origem_cidade",
        "origem_estado",
        "status",
        "tipo",
        "saida_dt",
        "updated_at",
    )
    list_filter = ("status", "tipo", "origem_estado")
    search_fields = ("observacoes", "origem_cidade__nome", "origem_estado__sigla")
    inlines = (RoteiroDestinoInline, RoteiroTrechoInline)
    ordering = ("-updated_at",)


@admin.register(RoteiroDestino)
class RoteiroDestinoAdmin(admin.ModelAdmin):
    list_display = ("roteiro", "ordem", "cidade", "estado")
    ordering = ("roteiro", "ordem")


@admin.register(RoteiroTrecho)
class RoteiroTrechoAdmin(admin.ModelAdmin):
    list_display = ("roteiro", "ordem", "tipo", "origem_cidade", "destino_cidade", "saida_dt", "chegada_dt")
    list_filter = ("tipo",)
    ordering = ("roteiro", "ordem")
