from django.urls import path

from integracoes import views

app_name = "integracoes"

urlpatterns = [
    path("google-drive/conectar/", views.google_drive_connect, name="google-drive-connect"),
    path("google-drive/callback/", views.google_drive_callback, name="google-drive-callback"),
    path("google-drive/desconectar/", views.google_drive_disconnect, name="google-drive-disconnect"),
    path("google-drive/pasta-raiz/", views.google_drive_root_folder_update, name="google-drive-root-folder"),
]
