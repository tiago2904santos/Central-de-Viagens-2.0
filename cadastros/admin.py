from django.contrib import admin
from .models import Cidade, Motorista, Servidor, Unidade, Viatura


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "ativa", "updated_at")
    search_fields = ("nome", "sigla")
    list_filter = ("ativa",)
    ordering = ("nome",)


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "uf", "ativa", "updated_at")
    search_fields = ("nome", "uf")
    list_filter = ("uf", "ativa")
    ordering = ("uf", "nome")


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ("nome", "matricula", "cargo", "unidade", "ativo", "updated_at")
    search_fields = ("nome", "matricula", "cpf", "cargo")
    list_filter = ("ativo", "unidade")
    ordering = ("nome",)


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ("servidor", "cnh", "categoria_cnh", "ativo", "updated_at")
    search_fields = ("servidor__nome", "cnh")
    list_filter = ("ativo",)
    ordering = ("servidor__nome",)


@admin.register(Viatura)
class ViaturaAdmin(admin.ModelAdmin):
    list_display = (
        "placa",
        "modelo",
        "marca",
        "tipo",
        "combustivel",
        "unidade",
        "ativa",
        "updated_at",
    )
    search_fields = ("placa", "modelo", "marca")
    list_filter = ("ativa", "combustivel", "unidade")
    ordering = ("placa",)
