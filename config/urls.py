from django.contrib import admin
from django.urls import include
from django.urls import path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("core.urls")),
    path("usuarios/", include("usuarios.urls")),
    path("cadastros/", include("cadastros.urls")),
    path("roteiros/", include("roteiros.urls")),
    path("eventos/", include("eventos.urls")),
    path("documentos/", include("documentos.urls")),
    path("oficios/", include("oficios.urls")),
    path("termos/", include("termos.urls")),
    path("justificativas/", include("justificativas.urls")),
    path("planos-trabalho/", include("planos_trabalho.urls")),
    path("ordens-servico/", include("ordens_servico.urls")),
    path("prestacoes-contas/", include("prestacoes_contas.urls")),
    path("diario-bordo/", include("diario_bordo.urls")),
    path("assinaturas/", include("assinaturas.urls")),
    path("integracoes/google-drive/", include("integracoes.google_drive.urls")),
]
