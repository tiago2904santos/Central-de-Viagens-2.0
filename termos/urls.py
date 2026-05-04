from django.urls import path

from . import views


app_name = "termos"

urlpatterns = [
    path("", views.index, name="index"),
]
