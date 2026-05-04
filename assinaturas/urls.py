from django.urls import path

from . import views


app_name = "assinaturas"

urlpatterns = [
    path("", views.index, name="index"),
]
