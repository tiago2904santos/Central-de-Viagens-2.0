from django.urls import path
from . import views

app_name = 'documentos'

urlpatterns = [
    path('', views.hub, name='hub'),
    path('oficios/', views.lista_oficios, name='oficios'),
    path('roteiros/', views.lista_roteiros, name='roteiros'),
    path('planos-trabalho/', views.lista_planos, name='planos-trabalho'),
    path('ordens-servico/', views.lista_ordens, name='ordens-servico'),
    path('justificativas/', views.lista_justificativas, name='justificativas'),
    path('termos/', views.lista_termos, name='termos'),
]
