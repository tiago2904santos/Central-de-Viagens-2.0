from django.contrib import admin
from .models import (
    CoordenadorOperacional,
    EfetivoPlanoTrabalho,
    Evento,
    EventoFinalizacao,
    EventoTermoParticipante,
    ModeloJustificativa,
    ModeloMotivoViagem,
    OrdemServico,
    Oficio,
    PlanoTrabalho,
    EfetivoPlanoTrabalhoDocumento,
    HorarioAtendimentoPlanoTrabalho,
    SolicitantePlanoTrabalho,
    TermoAutorizacao,
)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'get_tipos_demanda_display', 'status', 'data_inicio', 'data_fim', 'cidade_principal', 'updated_at')
    list_filter = ('status', 'tipos_demanda')
    search_fields = ('titulo',)
    ordering = ('-data_inicio', '-created_at')

    @admin.display(description='Tipos de demanda')
    def get_tipos_demanda_display(self, obj):
        return ', '.join(t.nome for t in obj.tipos_demanda.all()) or '—'


@admin.register(SolicitantePlanoTrabalho)
class SolicitantePlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'ordem', 'is_padrao', 'updated_at')
    list_filter = ('ativo', 'is_padrao')
    search_fields = ('nome',)
    ordering = ('ordem', 'nome')


@admin.register(HorarioAtendimentoPlanoTrabalho)
class HorarioAtendimentoPlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'ativo', 'ordem', 'is_padrao', 'updated_at')
    list_filter = ('ativo', 'is_padrao')
    search_fields = ('descricao',)
    ordering = ('ordem', 'descricao')


@admin.register(CoordenadorOperacional)
class CoordenadorOperacionalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cargo', 'cidade', 'unidade', 'ativo', 'ordem', 'updated_at')
    list_filter = ('ativo',)
    search_fields = ('nome', 'cargo', 'cidade')
    ordering = ('ordem', 'nome')


@admin.register(EfetivoPlanoTrabalho)
class EfetivoPlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('evento', 'cargo', 'quantidade')
    list_filter = ('cargo',)
    raw_id_fields = ('evento',)
    ordering = ('evento', 'cargo__nome')


@admin.register(PlanoTrabalho)
class PlanoTrabalhoAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero_formatado', 'status', 'evento', 'oficio', 'updated_at')
    list_filter = ('status',)
    search_fields = ('objetivo', 'observacoes')
    raw_id_fields = ('evento', 'oficio', 'solicitante', 'coordenador_operacional', 'coordenador_administrativo')
    ordering = ('-updated_at',)


@admin.register(OrdemServico)
class OrdemServicoAdmin(admin.ModelAdmin):
    list_display = ('id', 'numero_formatado', 'status', 'evento', 'oficio', 'updated_at')
    list_filter = ('status',)
    search_fields = ('finalidade', 'motivo_texto', 'responsaveis')
    raw_id_fields = ('evento', 'oficio')
    ordering = ('-updated_at',)


@admin.register(EfetivoPlanoTrabalhoDocumento)
class EfetivoPlanoTrabalhoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('plano_trabalho', 'cargo', 'quantidade')
    list_filter = ('cargo',)
    raw_id_fields = ('plano_trabalho',)
    ordering = ('plano_trabalho', 'cargo__nome')


@admin.register(EventoTermoParticipante)
class EventoTermoParticipanteAdmin(admin.ModelAdmin):
    list_display = ('evento', 'viajante', 'status', 'updated_at')
    list_filter = ('status',)
    search_fields = ('viajante__nome',)
    raw_id_fields = ('evento', 'viajante')


@admin.register(EventoFinalizacao)
class EventoFinalizacaoAdmin(admin.ModelAdmin):
    list_display = ('evento', 'concluido', 'finalizado_em', 'finalizado_por', 'updated_at')
    list_filter = ('finalizado_em',)
    search_fields = ('observacoes_finais',)
    raw_id_fields = ('evento', 'finalizado_por')


@admin.register(TermoAutorizacao)
class TermoAutorizacaoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'numero_formatado',
        'modo_geracao',
        'status',
        'servidor_display',
        'destino',
        'evento',
        'oficio',
        'updated_at',
    )
    list_filter = ('modo_geracao', 'status')
    search_fields = ('servidor_nome', 'destino', 'evento__titulo', 'oficio__protocolo')
    raw_id_fields = ('evento', 'roteiro', 'oficio', 'viajante', 'veiculo', 'criado_por')
    ordering = ('-updated_at',)


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


@admin.register(ModeloJustificativa)
class ModeloJustificativaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'padrao', 'ativo', 'updated_at')
    list_filter = ('padrao', 'ativo')
    search_fields = ('nome', 'texto')
    ordering = ('nome',)
