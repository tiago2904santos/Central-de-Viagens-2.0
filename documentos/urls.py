from django.urls import path
from . import views

app_name = 'documentos'

urlpatterns = [
    path('', views.hub, name='hub'),

    path('oficios/', views.oficio_lista, name='oficios'),
    path('oficios/novo/step1/', views.oficio_step1, name='oficio-novo-step1'),
    path('oficios/<int:pk>/step1/', views.oficio_step1, name='oficio-step1'),
    path('oficios/<int:pk>/step2/', views.oficio_step2, name='oficio-step2'),
    path('oficios/<int:pk>/step3/', views.oficio_step3, name='oficio-step3'),
    path('oficios/<int:pk>/step4/', views.oficio_step4, name='oficio-step4'),
    path('oficios/<int:pk>/justificativa/', views.oficio_justificativa, name='oficio-justificativa'),
    path('oficios/<int:pk>/excluir/', views.oficio_excluir, name='oficio-excluir'),

    path('roteiros/', views.roteiro_lista, name='roteiros'),
    path('roteiros/novo/', views.roteiro_form, name='roteiro-novo'),
    path('roteiros/<int:pk>/editar/', views.roteiro_form, name='roteiro-editar'),
    path('roteiros/<int:pk>/excluir/', views.roteiro_excluir, name='roteiro-excluir'),

    path('termos/', views.termo_lista, name='termos'),
    path('termos/novo/', views.termo_form, name='termo-novo'),
    path('termos/<int:pk>/editar/', views.termo_form, name='termo-editar'),
    path('termos/<int:pk>/excluir/', views.termo_excluir, name='termo-excluir'),

    path('justificativas/', views.justificativa_lista, name='justificativas'),
    path('justificativas/novo/', views.justificativa_form, name='justificativa-nova'),
    path('justificativas/<int:pk>/editar/', views.justificativa_form, name='justificativa-editar'),
    path('justificativas/<int:pk>/excluir/', views.justificativa_excluir, name='justificativa-excluir'),

    path('planos-trabalho/', views.plano_lista, name='planos-trabalho'),
    path('planos-trabalho/novo/', views.plano_form, name='plano-novo'),
    path('planos-trabalho/<int:pk>/editar/', views.plano_form, name='plano-editar'),
    path('planos-trabalho/<int:pk>/excluir/', views.plano_excluir, name='plano-excluir'),

    path('ordens-servico/', views.ordem_lista, name='ordens-servico'),
    path('ordens-servico/novo/', views.ordem_form, name='ordem-nova'),
    path('ordens-servico/<int:pk>/editar/', views.ordem_form, name='ordem-editar'),
    path('ordens-servico/<int:pk>/excluir/', views.ordem_excluir, name='ordem-excluir'),

    path('eventos/', views.evento_lista, name='eventos'),
    path('eventos/novo/', views.evento_form, name='evento-novo'),
    path('eventos/<int:pk>/', views.evento_detalhe, name='evento-detalhe'),
    path('eventos/<int:pk>/editar/', views.evento_form, name='evento-editar'),
    path('eventos/<int:pk>/excluir/', views.evento_excluir, name='evento-excluir'),

    path('modelos-motivo/', views.modelo_motivo_lista, name='modelos-motivo'),
    path('modelos-motivo/novo/', views.modelo_motivo_form, name='modelo-motivo-novo'),
    path('modelos-motivo/<int:pk>/editar/', views.modelo_motivo_form, name='modelo-motivo-editar'),
    path('modelos-motivo/<int:pk>/excluir/', views.modelo_motivo_excluir, name='modelo-motivo-excluir'),

    path('modelos-justificativa/', views.modelo_justificativa_lista, name='modelos-justificativa'),
    path('modelos-justificativa/novo/', views.modelo_justificativa_form, name='modelo-justificativa-novo'),
    path('modelos-justificativa/<int:pk>/editar/', views.modelo_justificativa_form, name='modelo-justificativa-editar'),
    path('modelos-justificativa/<int:pk>/excluir/', views.modelo_justificativa_excluir, name='modelo-justificativa-excluir'),
]
