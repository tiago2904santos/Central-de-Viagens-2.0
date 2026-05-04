from django.urls import path

from . import views


app_name = "planos_trabalho"

urlpatterns = [
    path("", views.index, name="index"),
]
