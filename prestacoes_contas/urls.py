from django.urls import path

from . import views


app_name = "prestacoes_contas"

urlpatterns = [
    path("", views.index, name="index"),
]
