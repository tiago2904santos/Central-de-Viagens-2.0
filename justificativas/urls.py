from django.urls import path

from . import views


app_name = "justificativas"

urlpatterns = [
    path("", views.index, name="index"),
]
