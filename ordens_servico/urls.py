from django.urls import path

from . import views


app_name = "ordens_servico"

urlpatterns = [
    path("", views.index, name="index"),
]
