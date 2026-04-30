from django.contrib import admin

from .models import DiarioBordo, DiarioBordoTrecho


class DiarioBordoTrechoInline(admin.TabularInline):
    model = DiarioBordoTrecho
    extra = 0


@admin.register(DiarioBordo)
class DiarioBordoAdmin(admin.ModelAdmin):
    list_display = ("id", "numero_oficio", "e_protocolo", "placa_oficial", "nome_responsavel", "status", "atualizado_em")
    list_filter = ("status",)
    search_fields = ("numero_oficio", "e_protocolo", "placa_oficial", "nome_responsavel")
    inlines = [DiarioBordoTrechoInline]
