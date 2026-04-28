from django.urls import path
from . import views

app_name = 'documentos'

urlpatterns = [
    path('', views.placeholder_view, name='lista'),
    path('verificar/<str:codigo>/', views.assinatura_verificar_codigo, name='assinatura-verificar-codigo'),
    path('verificar-upload/', views.assinatura_verificar_upload, name='assinatura-verificar-upload'),
]
