from django.contrib import admin

from .models import Cargo
from .models import Cidade
from .models import Estado
from .models import Combustivel
from .models import Servidor
from .models import Unidade
from .models import Viatura


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("nome", "updated_at")
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(Combustivel)
class CombustivelAdmin(admin.ModelAdmin):
    list_display = ("nome", "updated_at")
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "codigo_ibge", "updated_at")
    search_fields = ("nome", "sigla")
    ordering = ("nome",)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "updated_at")
    search_fields = ("nome", "sigla")
    ordering = ("nome",)


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "estado", "uf", "capital", "codigo_ibge", "updated_at")
    search_fields = ("nome", "uf", "estado__nome", "estado__sigla")
    list_filter = ("capital", "uf")
    ordering = ("uf", "nome")


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ("nome", "cargo", "cpf", "rg", "unidade", "updated_at")
    search_fields = ("nome", "cpf", "rg", "cargo__nome", "unidade__nome")
    list_filter = ("cargo", "unidade")
    ordering = ("nome",)


@admin.register(Viatura)
class ViaturaAdmin(admin.ModelAdmin):
    list_display = ("placa", "modelo", "combustivel", "tipo", "updated_at")
    search_fields = ("placa", "modelo", "combustivel__nome", "tipo")
    list_filter = ("combustivel", "tipo")
    ordering = ("placa",)
