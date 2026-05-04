from django.urls import path
from . import views

app_name = "cadastros"

urlpatterns = [
    path("", views.index, name="index"),
    path("unidades/", views.unidades_index, name="unidades_index"),
    path("unidades/novo/", views.unidade_create, name="unidade_create"),
    path("unidades/<int:pk>/editar/", views.unidade_update, name="unidade_update"),
    path("unidades/<int:pk>/excluir/", views.unidade_delete, name="unidade_delete"),
    path("cidades/", views.cidades_index, name="cidades_index"),
    path("cidades/nova/", views.cidade_create, name="cidade_create"),
    path("cidades/<int:pk>/editar/", views.cidade_update, name="cidade_update"),
    path("cidades/<int:pk>/excluir/", views.cidade_delete, name="cidade_delete"),
    path("servidores/", views.servidores_index, name="servidores_index"),
    path("motoristas/", views.motoristas_index, name="motoristas_index"),
    path("viaturas/", views.viaturas_index, name="viaturas_index"),
]
