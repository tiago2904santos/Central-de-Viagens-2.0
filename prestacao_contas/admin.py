from django.contrib import admin

from .models import PrestacaoConta, RelatorioTecnicoPrestacao


@admin.register(PrestacaoConta)
class PrestacaoContaAdmin(admin.ModelAdmin):
    list_display = ("id", "oficio", "nome_servidor", "status_rt", "rt_atualizado_em")
    list_filter = ("status_rt",)
    search_fields = ("nome_servidor", "rg_servidor", "oficio__numero", "oficio__ano")


@admin.register(RelatorioTecnicoPrestacao)
class RelatorioTecnicoPrestacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "prestacao", "nome_servidor", "status", "data_geracao")
    list_filter = ("status",)
    search_fields = ("nome_servidor", "rg_servidor")
