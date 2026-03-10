from django.contrib import admin
from .models import Estado, Cidade, Cargo, Viajante, Veiculo, ConfiguracaoSistema, AssinaturaConfiguracao, UnidadeLotacao, CombustivelVeiculo
from .forms import _viajantes_operacionais_queryset


class AssinaturaConfiguracaoInline(admin.TabularInline):
    model = AssinaturaConfiguracao
    extra = 0
    autocomplete_fields = ('viajante',)
    ordering = ('tipo', 'ordem')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'viajante':
            kwargs['queryset'] = _viajantes_operacionais_queryset()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(AssinaturaConfiguracao)
class AssinaturaConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ('configuracao', 'tipo', 'ordem', 'viajante', 'ativo', 'updated_at')
    list_filter = ('tipo', 'ativo')
    search_fields = ('viajante__nome',)
    autocomplete_fields = ('viajante',)
    ordering = ('configuracao', 'tipo', 'ordem')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'viajante':
            kwargs['queryset'] = _viajantes_operacionais_queryset()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Estado)
class EstadoAdmin(admin.ModelAdmin):
    list_display = ('codigo_ibge', 'nome', 'sigla', 'ativo', 'updated_at')
    search_fields = ('nome', 'sigla', 'codigo_ibge')
    list_filter = ('ativo',)
    list_editable = ('ativo',)
    readonly_fields = ('codigo_ibge', 'created_at', 'updated_at')


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ('codigo_ibge', 'nome', 'estado', 'ativo', 'updated_at')
    search_fields = ('nome', 'codigo_ibge')
    list_filter = ('estado', 'ativo')
    list_editable = ('ativo',)
    readonly_fields = ('codigo_ibge', 'created_at', 'updated_at')


@admin.register(UnidadeLotacao)
class UnidadeLotacaoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'updated_at')
    search_fields = ('nome',)
    ordering = ('nome',)

    def has_add_permission(self, request):
        return False  # Cadastro apenas via importação CSV

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'is_padrao', 'updated_at')
    search_fields = ('nome',)
    list_filter = ('is_padrao',)


@admin.register(Viajante)
class ViajanteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'status', 'cargo', 'cpf', 'telefone', 'sem_rg', 'updated_at')
    search_fields = ('nome', 'cargo__nome', 'cpf', 'rg', 'telefone', 'unidade_lotacao__nome')
    list_filter = ('status',)


@admin.register(CombustivelVeiculo)
class CombustivelVeiculoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'is_padrao', 'updated_at')
    search_fields = ('nome',)
    list_filter = ('is_padrao',)


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('placa', 'modelo', 'combustivel', 'tipo', 'status', 'updated_at')
    search_fields = ('placa', 'modelo', 'combustivel__nome')
    list_filter = ('tipo', 'status')


@admin.register(ConfiguracaoSistema)
class ConfiguracaoSistemaAdmin(admin.ModelAdmin):
    list_display = ('pk', 'nome_orgao', 'sigla_orgao', 'prazo_justificativa_dias', 'updated_at')
    inlines = (AssinaturaConfiguracaoInline,)

    def has_add_permission(self, request):
        return not ConfiguracaoSistema.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
