from django.contrib import admin
from .models import Cidade, Motorista, Servidor, Unidade, Viatura


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "updated_at")
    search_fields = ("nome", "sigla")
    ordering = ("nome",)


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "uf", "updated_at")
    search_fields = ("nome", "uf")
    list_filter = ("uf",)
    ordering = ("uf", "nome")


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ("nome", "matricula", "cargo", "unidade", "updated_at")
    search_fields = ("nome", "matricula", "cpf", "cargo")
    list_filter = ("unidade",)
    ordering = ("nome",)


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ("servidor", "cnh", "categoria_cnh", "updated_at")
    search_fields = ("servidor__nome", "cnh")
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
        "updated_at",
    )
    search_fields = ("placa", "modelo", "marca")
    list_filter = ("combustivel", "unidade")
    ordering = ("placa",)
