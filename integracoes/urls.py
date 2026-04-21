from django.urls import path

from integracoes import views

app_name = "integracoes"

urlpatterns = [
    path("google-drive/conectar/", views.google_drive_connect, name="google-drive-connect"),
    path("google-drive/callback/", views.google_drive_callback, name="google-drive-callback"),
]
