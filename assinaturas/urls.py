from django.urls import path

from assinaturas import views

app_name = "assinaturas"

urlpatterns = [
    path("interno/pedido/criar/", views.pedido_assinatura_criar, name="pedido_criar"),
    path("verificar/<uuid:token>/", views.verificar_documento_assinado, name="verificar"),
    path("verificar/<uuid:token>/pdf/", views.verificar_documento_pdf, name="verificar_pdf"),
    path("assinar/<str:token>/", views.assinar_documento, name="assinar"),
    path("assinar/<str:token>/pdf/", views.assinar_preview_pdf, name="preview_pdf"),
    path("assinar/<str:token>/enviar/", views.assinar_documento_submit, name="assinar_enviar"),
    path("assinar/<str:token>/resultado/", views.assinar_resultado, name="resultado"),
]
