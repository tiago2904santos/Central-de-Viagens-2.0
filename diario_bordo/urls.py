from django.urls import path

from . import views

app_name = "diario_bordo"

urlpatterns = [
    path("", views.diario_lista, name="lista"),
    path("novo/", views.diario_novo, name="novo"),
    path("novo/oficio/<int:oficio_id>/", views.diario_novo_oficio, name="novo-oficio"),
    path("novo/prestacao/<int:prestacao_id>/", views.diario_novo_prestacao, name="novo-prestacao"),
    path("<int:pk>/", views.diario_editar, name="editar"),
    path("<int:pk>/step/<int:step>/", views.diario_step, name="step"),
    path("<int:pk>/pdf/", views.diario_pdf, name="pdf"),
    path("<int:pk>/xlsx/", views.diario_xlsx, name="xlsx"),
    path("<int:pk>/excluir/", views.diario_excluir, name="excluir"),
]
