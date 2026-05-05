from django.contrib import admin

from .models import AssinaturaConfiguracao
from .models import Cargo
from .models import Cidade
from .models import Combustivel
from .models import ConfiguracaoSistema
from .models import Estado
from .models import Servidor
from .models import Unidade
from .models import Viatura


@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    list_display = ("id", "divisao", "unidade", "cidade_endereco", "updated_at")

    def has_add_permission(self, request):
        if ConfiguracaoSistema.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(AssinaturaConfiguracao)
class AssinaturaConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ("configuracao", "tipo", "ordem", "servidor", "ativo", "updated_at")
    list_filter = ("tipo", "ativo")
    ordering = ("tipo", "ordem")


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("nome", "is_padrao")
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(Combustivel)
class CombustivelAdmin(admin.ModelAdmin):
    list_display = ("nome", "is_padrao")
    search_fields = ("nome",)
    ordering = ("nome",)


@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "codigo_ibge")
    search_fields = ("nome", "sigla")
    ordering = ("nome",)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla")
    search_fields = ("nome", "sigla")
    ordering = ("nome",)


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "estado", "uf", "capital", "codigo_ibge")
    search_fields = ("nome", "uf", "estado__nome", "estado__sigla")
    list_filter = ("capital", "uf")
    ordering = ("uf", "nome")


@admin.register(Servidor)
class ServidorAdmin(admin.ModelAdmin):
    list_display = ("nome", "cargo", "cpf", "sem_rg", "telefone", "unidade")
    search_fields = ("nome", "cpf", "rg", "telefone", "cargo__nome", "unidade__nome")
    list_filter = ("cargo", "unidade")
    ordering = ("nome",)


@admin.register(Viatura)
class ViaturaAdmin(admin.ModelAdmin):
    list_display = ("placa", "modelo", "combustivel", "tipo")
    search_fields = ("placa", "modelo", "combustivel__nome", "tipo")
    list_filter = ("combustivel", "tipo")
    ordering = ("placa",)
