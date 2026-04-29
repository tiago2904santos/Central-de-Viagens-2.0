from django.urls import path
from . import views

app_name = 'documentos'

urlpatterns = [
    path('', views.assinatura_gestao, name='assinatura-gestao'),
    path('exportar/', views.assinatura_gestao, name='assinatura-exportar'),
    path('verificar/<str:token>/', views.assinatura_verificar, name='assinatura-verificar'),
    path('<str:referencia>/', views.assinatura_detalhe, name='assinatura-detalhe'),
    path('verificar/', views.assinatura_verificador, name='assinatura-verificador'),
    path('verificar/codigo/<str:codigo>/', views.assinatura_verificar_codigo, name='assinatura-verificar-codigo'),
    path('verificar-upload/', views.assinatura_verificar_upload, name='assinatura-verificar-upload'),
]
