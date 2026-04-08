from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views, views_global

app_name = 'eventos'

urlpatterns = [
    path('', login_required(views.evento_lista), name='lista'),
    path('oficios/', login_required(views_global.oficio_global_lista), name='oficios-global'),
    path('roteiros/', login_required(views_global.roteiro_global_lista), name='roteiros-global'),
    path('documentos/', login_required(views_global.documentos_hub), name='documentos-hub'),
    path('documentos/planos-trabalho/', login_required(views_global.planos_trabalho_global), name='documentos-planos-trabalho'),
    path('documentos/planos-trabalho/coordenadores/', login_required(views_global.plano_trabalho_coordenadores_api), name='documentos-planos-trabalho-coordenadores-api'),
    path('api/calcular-diarias/', login_required(views_global.plano_trabalho_calcular_diarias_api), name='documentos-planos-trabalho-calcular-diarias-api'),
    path('documentos/planos-trabalho/autosave/', login_required(views_global.plano_trabalho_autosave), name='documentos-planos-trabalho-autosave'),
    path('documentos/planos-trabalho/novo/', login_required(views_global.plano_trabalho_novo), name='documentos-planos-trabalho-novo'),
    path('documentos/planos-trabalho/<int:pk>/', login_required(views_global.plano_trabalho_detalhe), name='documentos-planos-trabalho-detalhe'),
    path('documentos/planos-trabalho/<int:pk>/editar/', login_required(views_global.plano_trabalho_editar), name='documentos-planos-trabalho-editar'),
    path('documentos/planos-trabalho/<int:pk>/excluir/', login_required(views_global.plano_trabalho_excluir), name='documentos-planos-trabalho-excluir'),
    path('documentos/planos-trabalho/<int:pk>/download/<str:formato>/', login_required(views_global.plano_trabalho_download), name='documentos-planos-trabalho-download'),
    path('documentos/ordens-servico/', login_required(views_global.ordens_servico_global), name='documentos-ordens-servico'),
    path('documentos/ordens-servico/novo/', login_required(views_global.ordem_servico_novo), name='documentos-ordens-servico-novo'),
    path('documentos/ordens-servico/<int:pk>/', login_required(views_global.ordem_servico_detalhe), name='documentos-ordens-servico-detalhe'),
    path('documentos/ordens-servico/<int:pk>/editar/', login_required(views_global.ordem_servico_editar), name='documentos-ordens-servico-editar'),
    path('documentos/ordens-servico/<int:pk>/excluir/', login_required(views_global.ordem_servico_excluir), name='documentos-ordens-servico-excluir'),
    path('documentos/ordens-servico/<int:pk>/download/<str:formato>/', login_required(views_global.ordem_servico_download), name='documentos-ordens-servico-download'),
    path('documentos/justificativas/', login_required(views_global.justificativas_global), name='documentos-justificativas'),
    path('documentos/justificativas/nova/', login_required(views_global.justificativa_nova), name='documentos-justificativas-nova'),
    path('documentos/justificativas/<int:pk>/', login_required(views_global.justificativa_detalhe), name='documentos-justificativas-detalhe'),
    path('documentos/justificativas/<int:pk>/editar/', login_required(views_global.justificativa_editar), name='documentos-justificativas-editar'),
    path('documentos/justificativas/<int:pk>/excluir/', login_required(views_global.justificativa_excluir), name='documentos-justificativas-excluir'),
    path('documentos/termos/', login_required(views_global.termos_global), name='documentos-termos'),
    path('documentos/termos/novo/', login_required(views_global.termo_autorizacao_novo), name='documentos-termos-novo'),
    path('documentos/termos/preview/', login_required(views_global.termo_autorizacao_preview), name='documentos-termos-preview'),
    path('documentos/termos/api/oficios-por-evento/', login_required(views_global.termo_autorizacao_oficios_por_evento), name='documentos-termos-api-oficios-por-evento'),
    path('documentos/termos/novo/rapido/', login_required(views_global.termo_autorizacao_novo_rapido), name='documentos-termos-novo-rapido'),
    path('documentos/termos/novo/automatico-com-viatura/', login_required(views_global.termo_autorizacao_novo_automatico_com_viatura), name='documentos-termos-novo-automatico-com-viatura'),
    path('documentos/termos/novo/automatico-sem-viatura/', login_required(views_global.termo_autorizacao_novo_automatico_sem_viatura), name='documentos-termos-novo-automatico-sem-viatura'),
    path('documentos/termos/<int:pk>/', login_required(views_global.termo_autorizacao_detalhe), name='documentos-termos-detalhe'),
    path('documentos/termos/<int:pk>/editar/', login_required(views_global.termo_autorizacao_editar), name='documentos-termos-editar'),
    path('documentos/termos/<int:pk>/excluir/', login_required(views_global.termo_autorizacao_excluir), name='documentos-termos-excluir'),
    path('documentos/termos/<int:pk>/download/<str:formato>/', login_required(views_global.termo_autorizacao_download), name='documentos-termos-download'),
    path('simulacao-diarias/', login_required(views_global.simulacao_diarias_global), name='simulacao-diarias'),
    path('cadastrar/', login_required(views.evento_cadastrar), name='cadastrar'),
    path('<int:pk>/', login_required(views.evento_detalhe), name='detalhe'),
    path('<int:pk>/editar/', login_required(views.evento_editar), name='editar'),
    path('<int:pk>/excluir/', login_required(views.evento_excluir), name='excluir'),
    # Tipos de demanda (eventos)
    path('tipos-demanda/', login_required(views.tipos_demanda_lista), name='tipos-demanda-lista'),
    path('tipos-demanda/cadastrar/', login_required(views.tipos_demanda_cadastrar), name='tipos-demanda-cadastrar'),
    path('tipos-demanda/<int:pk>/editar/', login_required(views.tipos_demanda_editar), name='tipos-demanda-editar'),
    path('tipos-demanda/<int:pk>/excluir/', login_required(views.tipos_demanda_excluir), name='tipos-demanda-excluir'),
    # Atividades do Plano de Trabalho
    path('plano-trabalho-atividades/', login_required(views.plano_trabalho_atividades_lista), name='plano-trabalho-atividades-lista'),
    path('plano-trabalho-atividades/cadastrar/', login_required(views.plano_trabalho_atividades_cadastrar), name='plano-trabalho-atividades-cadastrar'),
    path('plano-trabalho-atividades/<int:pk>/editar/', login_required(views.plano_trabalho_atividades_editar), name='plano-trabalho-atividades-editar'),
    path('plano-trabalho-atividades/<int:pk>/excluir/', login_required(views.plano_trabalho_atividades_excluir), name='plano-trabalho-atividades-excluir'),
    path('coordenadores-operacionais/', login_required(views.plano_trabalho_coordenadores_lista), name='coordenadores-operacionais-lista'),
    path('coordenadores-operacionais/cadastrar/', login_required(views.plano_trabalho_coordenadores_cadastrar), name='coordenadores-operacionais-cadastrar'),
    path('coordenadores-operacionais/<int:pk>/editar/', login_required(views.plano_trabalho_coordenadores_editar), name='coordenadores-operacionais-editar'),
    path('coordenadores-operacionais/<int:pk>/excluir/', login_required(views.plano_trabalho_coordenadores_excluir), name='coordenadores-operacionais-excluir'),
    path('plano-trabalho-solicitantes/', login_required(views.plano_trabalho_solicitantes_lista), name='plano-trabalho-solicitantes-lista'),
    path('plano-trabalho-solicitantes/cadastrar/', login_required(views.plano_trabalho_solicitantes_cadastrar), name='plano-trabalho-solicitantes-cadastrar'),
    path('plano-trabalho-solicitantes/<int:pk>/editar/', login_required(views.plano_trabalho_solicitantes_editar), name='plano-trabalho-solicitantes-editar'),
    path('plano-trabalho-solicitantes/<int:pk>/excluir/', login_required(views.plano_trabalho_solicitantes_excluir), name='plano-trabalho-solicitantes-excluir'),
    path('plano-trabalho-horarios/', login_required(views.plano_trabalho_horarios_lista), name='plano-trabalho-horarios-lista'),
    path('plano-trabalho-horarios/cadastrar/', login_required(views.plano_trabalho_horarios_cadastrar), name='plano-trabalho-horarios-cadastrar'),
    path('plano-trabalho-horarios/<int:pk>/editar/', login_required(views.plano_trabalho_horarios_editar), name='plano-trabalho-horarios-editar'),
    path('plano-trabalho-horarios/<int:pk>/excluir/', login_required(views.plano_trabalho_horarios_excluir), name='plano-trabalho-horarios-excluir'),
    # Modelos de motivo (ofício step 1)
    path('modelos-motivo/', login_required(views.modelos_motivo_lista), name='modelos-motivo-lista'),
    path('modelos-motivo/cadastrar/', login_required(views.modelos_motivo_cadastrar), name='modelos-motivo-cadastrar'),
    path('modelos-motivo/<int:pk>/editar/', login_required(views.modelos_motivo_editar), name='modelos-motivo-editar'),
    path('modelos-motivo/<int:pk>/excluir/', login_required(views.modelos_motivo_excluir), name='modelos-motivo-excluir'),
    path('modelos-motivo/<int:pk>/definir-padrao/', login_required(views.modelos_motivo_definir_padrao), name='modelos-motivo-definir-padrao'),
    path('modelos-motivo/<int:pk>/texto/', login_required(views.modelo_motivo_texto_api), name='modelos-motivo-texto-api'),
    # Modelos de justificativa (ofício)
    path('modelos-justificativa/', login_required(views.modelos_justificativa_lista), name='modelos-justificativa-lista'),
    path('modelos-justificativa/cadastrar/', login_required(views.modelos_justificativa_cadastrar), name='modelos-justificativa-cadastrar'),
    path('modelos-justificativa/<int:pk>/editar/', login_required(views.modelos_justificativa_editar), name='modelos-justificativa-editar'),
    path('modelos-justificativa/<int:pk>/excluir/', login_required(views.modelos_justificativa_excluir), name='modelos-justificativa-excluir'),
    path('modelos-justificativa/<int:pk>/definir-padrao/', login_required(views.modelos_justificativa_definir_padrao), name='modelos-justificativa-definir-padrao'),
    path('modelos-justificativa/<int:pk>/texto/', login_required(views.modelo_justificativa_texto_api), name='modelos-justificativa-texto-api'),
    # Fluxo guiado — ordem funcional real (1 a 7):
    # 1 Dados do evento   -> guiado-etapa-1
    # 2 Roteiros          -> guiado-etapa-2
    # 3 Termos            -> guiado-etapa-3
    # 4 PT / OS           -> guiado-etapa-4
    # 5 Ofícios           -> guiado-etapa-5
    # 6 Justificativa     -> guiado-etapa-6
    # 7 Finalização       -> guiado-etapa-7
    path('guiado/novo/', views.guiado_novo, name='guiado-novo'),
    path('<int:pk>/guiado/etapa-1/', login_required(views.guiado_etapa_1), name='guiado-etapa-1'),
    path('anexos-convite/<int:anexo_id>/visualizar/', login_required(views.evento_anexo_visualizar), name='evento-anexo-visualizar'),
    path('anexos-convite/<int:anexo_id>/baixar/', login_required(views.evento_anexo_baixar), name='evento-anexo-baixar'),
    path('anexos-convite/<int:anexo_id>/remover/', login_required(views.evento_anexo_remover), name='evento-anexo-remover'),
    path('<int:pk>/guiado/painel/', login_required(views.guiado_painel), name='guiado-painel'),
    # Etapa 3: Termos (função guiado_etapa_5 é o handler histórico de Termos)
    path('<int:evento_id>/guiado/etapa-3/', login_required(views.guiado_etapa_5), name='guiado-etapa-3'),
    path(
        '<int:evento_id>/guiado/etapa-3/termo/padrao/<str:formato>/',
        login_required(views.guiado_etapa_5_termo_padrao_download),
        name='guiado-etapa-3-termo-padrao-download',
    ),
    path(
        '<int:evento_id>/guiado/etapa-3/termo/viatura/<str:formato>/',
        login_required(views.guiado_etapa_5_termo_viatura_lote_download),
        name='guiado-etapa-3-termo-viatura-download',
    ),
    path(
        '<int:evento_id>/guiado/etapa-3/termo/<int:viajante_id>/<str:formato>/',
        login_required(views.guiado_etapa_5_termo_download),
        name='guiado-etapa-3-termo-download',
    ),
    # Etapa 4: PT / OS
    path('<int:evento_id>/guiado/etapa-4/', login_required(views.guiado_etapa_4), name='guiado-etapa-4'),
    # Etapa 5: Ofícios (função guiado_etapa_3 é o handler histórico de Ofícios)
    path('<int:evento_id>/guiado/etapa-5/', login_required(views.guiado_etapa_3), name='guiado-etapa-5'),
    path('<int:evento_id>/guiado/etapa-5/criar-oficio/', login_required(views.guiado_etapa_3_criar_oficio), name='guiado-etapa-5-criar-oficio'),
    # Etapa 6: Justificativa (evento; exigida quando prazo < 10 dias)
    path('<int:evento_id>/guiado/etapa-6/', login_required(views.guiado_etapa_6_justificativa), name='guiado-etapa-6'),
    # Etapa 7: Finalização
    path('<int:evento_id>/guiado/etapa-7/', login_required(views.guiado_etapa_6), name='guiado-etapa-7'),
    # Wizard do Ofício (Steps 1–4)
    path('oficio/novo/', login_required(views.oficio_novo), name='oficio-novo'),
    path('oficio/<int:pk>/editar/', login_required(views.oficio_editar), name='oficio-editar'),
    path('oficio/<int:pk>/excluir/', login_required(views.oficio_excluir), name='oficio-excluir'),
    path('oficio/<int:pk>/step1/', login_required(views.oficio_step1), name='oficio-step1'),
    path('oficio/step1/viajantes/', login_required(views.oficio_step1_viajantes_api), name='oficio-step1-viajantes-api'),
    path('oficio/step2/motoristas/', login_required(views.oficio_step2_motoristas_api), name='oficio-step2-motoristas-api'),
    path('oficio/step2/veiculos/', login_required(views.oficio_step2_veiculos_busca_api), name='oficio-step2-veiculos-busca-api'),
    path('oficio/step2/veiculo/', login_required(views.oficio_step2_veiculo_api), name='oficio-step2-veiculo-api'),
    path('oficio/<int:pk>/step2/', login_required(views.oficio_step2), name='oficio-step2'),
    path('oficio/<int:pk>/step3/', login_required(views.oficio_step3), name='oficio-step3'),
    path('oficio/<int:pk>/step3/calcular-diarias/', login_required(views.oficio_step3_calcular_diarias), name='oficio-step3-calcular-diarias'),
    path('oficio/<int:pk>/justificativa/', login_required(views.oficio_justificativa), name='oficio-justificativa'),
    path('oficio/<int:pk>/documentos/', login_required(views.oficio_documentos), name='oficio-documentos'),
    path('oficio/<int:pk>/documentos/<str:tipo_documento>/<str:formato>/', login_required(views.oficio_documento_download), name='oficio-documento-download'),
    path('oficio/<int:pk>/step4/', login_required(views.oficio_step4), name='oficio-step4'),
    # Etapa 2 (negócio): Roteiros
    path('<int:evento_id>/guiado/etapa-2/', login_required(views.guiado_etapa_2_lista), name='guiado-etapa-2'),
    path('<int:evento_id>/guiado/etapa-2/cadastrar/', login_required(views.guiado_etapa_2_cadastrar), name='guiado-etapa-2-cadastrar'),
    path('<int:evento_id>/guiado/etapa-2/<int:pk>/editar/', login_required(views.guiado_etapa_2_editar), name='guiado-etapa-2-editar'),
    path('<int:evento_id>/guiado/etapa-2/<int:pk>/excluir/', login_required(views.guiado_etapa_2_excluir), name='guiado-etapa-2-excluir'),
    # Estimativa local de km/tempo do trecho (sem API externa)
    path('trechos/<int:pk>/calcular-km/', login_required(views.trecho_calcular_km), name='trecho-calcular-km'),
    # Estimativa por cidades (trecho ainda não salvo; não depende de pk)
    path('trechos/estimar/', login_required(views.estimar_km_por_cidades), name='trechos-estimar'),
    # Roteiros avulsos (sem vínculo com evento)
    path('roteiros/avulso/novo/', login_required(views.roteiro_avulso_cadastrar), name='roteiro-avulso-cadastrar'),
    path('roteiros/avulso/<int:pk>/editar/', login_required(views.roteiro_avulso_editar), name='roteiro-avulso-editar'),
]
