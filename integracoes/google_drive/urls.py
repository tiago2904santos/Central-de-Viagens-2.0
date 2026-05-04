from django.urls import path

from . import views


app_name = "google_drive"

urlpatterns = [
    path("", views.index, name="index"),
]
