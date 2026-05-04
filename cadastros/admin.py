from django.contrib import admin
from .models import Cidade, Motorista, Servidor, Unidade, Viatura


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "ativa")
    search_fields = ("nome", "sigla")
    list_filter = ("ativa",)


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "uf", "ativa")
    search_fields = ("nome", "uf")
    list_filter = ("uf", "ativa")


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ("nome", "matricula", "cargo", "unidade", "ativo")
    search_fields = ("nome", "matricula", "cpf", "cargo")
    list_filter = ("ativo", "unidade")


@admin.register(Motorista)
class MotoristaAdmin(admin.ModelAdmin):
    list_display = ("servidor", "cnh", "categoria_cnh", "ativo")
    search_fields = ("servidor__nome", "cnh")
    list_filter = ("ativo",)


@admin.register(Viatura)
class ViaturaAdmin(admin.ModelAdmin):
    list_display = ("placa", "modelo", "marca", "tipo", "combustivel", "unidade", "ativa")
    search_fields = ("placa", "modelo", "marca")
    list_filter = ("ativa", "combustivel", "unidade")