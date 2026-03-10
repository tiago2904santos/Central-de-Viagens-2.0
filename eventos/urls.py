from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'eventos'

urlpatterns = [
    path('', login_required(views.evento_lista), name='lista'),
    path('cadastrar/', login_required(views.evento_cadastrar), name='cadastrar'),
    path('<int:pk>/', login_required(views.evento_detalhe), name='detalhe'),
    path('<int:pk>/editar/', login_required(views.evento_editar), name='editar'),
    path('<int:pk>/excluir/', login_required(views.evento_excluir), name='excluir'),
    # Tipos de demanda (eventos)
    path('tipos-demanda/', login_required(views.tipos_demanda_lista), name='tipos-demanda-lista'),
    path('tipos-demanda/cadastrar/', login_required(views.tipos_demanda_cadastrar), name='tipos-demanda-cadastrar'),
    path('tipos-demanda/<int:pk>/editar/', login_required(views.tipos_demanda_editar), name='tipos-demanda-editar'),
    path('tipos-demanda/<int:pk>/excluir/', login_required(views.tipos_demanda_excluir), name='tipos-demanda-excluir'),
    # Modelos de motivo (ofício step 1)
    path('modelos-motivo/', login_required(views.modelos_motivo_lista), name='modelos-motivo-lista'),
    path('modelos-motivo/cadastrar/', login_required(views.modelos_motivo_cadastrar), name='modelos-motivo-cadastrar'),
    path('modelos-motivo/<int:pk>/editar/', login_required(views.modelos_motivo_editar), name='modelos-motivo-editar'),
    path('modelos-motivo/<int:pk>/excluir/', login_required(views.modelos_motivo_excluir), name='modelos-motivo-excluir'),
    path('modelos-motivo/<int:pk>/definir-padrao/', login_required(views.modelos_motivo_definir_padrao), name='modelos-motivo-definir-padrao'),
    path('modelos-motivo/<int:pk>/texto/', login_required(views.modelo_motivo_texto_api), name='modelos-motivo-texto-api'),
    # Fluxo guiado
    path('guiado/novo/', views.guiado_novo, name='guiado-novo'),
    path('<int:pk>/guiado/etapa-1/', login_required(views.guiado_etapa_1), name='guiado-etapa-1'),
    path('<int:pk>/guiado/painel/', login_required(views.guiado_painel), name='guiado-painel'),
    # Etapa 3: Ofícios do evento
    path('<int:evento_id>/guiado/etapa-3/', login_required(views.guiado_etapa_3), name='guiado-etapa-3'),
    path('<int:evento_id>/guiado/etapa-3/criar-oficio/', login_required(views.guiado_etapa_3_criar_oficio), name='guiado-etapa-3-criar-oficio'),
    # Wizard do Ofício (Steps 1–4)
    path('oficio/<int:pk>/editar/', login_required(views.oficio_editar), name='oficio-editar'),
    path('oficio/<int:pk>/excluir/', login_required(views.oficio_excluir), name='oficio-excluir'),
    path('oficio/<int:pk>/step1/', login_required(views.oficio_step1), name='oficio-step1'),
    path('oficio/<int:pk>/step2/', login_required(views.oficio_step2), name='oficio-step2'),
    path('oficio/<int:pk>/step3/', login_required(views.oficio_step3), name='oficio-step3'),
    path('oficio/<int:pk>/step4/', login_required(views.oficio_step4), name='oficio-step4'),
    # Etapa 2: Roteiros
    path('<int:evento_id>/guiado/etapa-2/', login_required(views.guiado_etapa_2_lista), name='guiado-etapa-2'),
    path('<int:evento_id>/guiado/etapa-2/cadastrar/', login_required(views.guiado_etapa_2_cadastrar), name='guiado-etapa-2-cadastrar'),
    path('<int:evento_id>/guiado/etapa-2/<int:pk>/editar/', login_required(views.guiado_etapa_2_editar), name='guiado-etapa-2-editar'),
    path('<int:evento_id>/guiado/etapa-2/<int:pk>/excluir/', login_required(views.guiado_etapa_2_excluir), name='guiado-etapa-2-excluir'),
    # Estimativa local de km/tempo do trecho (sem API externa)
    path('trechos/<int:pk>/calcular-km/', login_required(views.trecho_calcular_km), name='trecho-calcular-km'),
    # Estimativa por cidades (trecho ainda não salvo; não depende de pk)
    path('trechos/estimar/', login_required(views.estimar_km_por_cidades), name='trechos-estimar'),
]
