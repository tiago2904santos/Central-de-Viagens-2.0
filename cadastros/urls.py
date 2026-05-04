from django.urls import path
from . import views

app_name = "cadastros"

urlpatterns = [
    path("", views.index, name="index"),
    path("servidores/", views.servidores_index, name="servidores_index"),
    path("motoristas/", views.motoristas_index, name="motoristas_index"),
    path("viaturas/", views.viaturas_index, name="viaturas_index"),
    path("cidades/", views.cidades_index, name="cidades_index"),
    path("unidades/", views.unidades_index, name="unidades_index"),
]