from django.urls import path

from . import views


app_name = "oficios"

urlpatterns = [
    path("", views.index, name="index"),
]
