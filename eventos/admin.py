from django.contrib import admin
from .models import Evento, ModeloMotivoViagem, Oficio


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo_demanda', 'status', 'data_inicio', 'data_fim', 'cidade_principal', 'updated_at')
    list_filter = ('status', 'tipo_demanda')
    search_fields = ('titulo',)
    ordering = ('-data_inicio', '-created_at')


@admin.register(Oficio)
class OficioAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero_formatado', 'evento', 'status', 'protocolo', 'created_at')
    list_filter = ('status',)
    search_fields = ('protocolo',)
    raw_id_fields = ('evento',)
    ordering = ('-created_at',)


@admin.register(ModeloMotivoViagem)
class ModeloMotivoViagemAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'nome', 'ordem', 'ativo', 'padrao')
    list_filter = ('ativo', 'padrao')
    search_fields = ('codigo', 'nome', 'texto')
    ordering = ('ordem', 'nome')
