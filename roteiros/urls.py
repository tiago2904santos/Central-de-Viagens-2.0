from django.urls import path

from . import views


app_name = "roteiros"

urlpatterns = [
    path("", views.index, name="index"),
    path("novo/", views.novo, name="novo"),
    path("api/cidades/<int:estado_id>/", views.api_cidades_por_estado, name="api_cidades_por_estado"),
    path("calcular-diarias/", views.calcular_diarias, name="calcular_diarias"),
    path("trechos/estimar/", views.trechos_estimar, name="trechos_estimar"),
    path("api/calcular-rota/", views.calcular_rota, name="calcular_rota"),
    path("api/calcular-rota-preview/", views.calcular_rota_preview, name="calcular_rota_preview"),
    path("<int:pk>/", views.detalhe, name="detalhe"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
]
