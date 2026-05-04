from django.urls import path

from . import views


app_name = "diario_bordo"

urlpatterns = [
    path("", views.index, name="index"),
]
