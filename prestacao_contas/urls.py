from django.urls import path

from . import views

app_name = "prestacao_contas"

urlpatterns = [
    path("", views.prestacao_lista, name="lista"),
    path("<int:prestacao_id>/", views.prestacao_detalhe, name="detalhe"),
    path("<int:prestacao_id>/relatorio-tecnico/", views.relatorio_tecnico_form, name="relatorio-tecnico"),
    path("<int:prestacao_id>/relatorio-tecnico/docx/", views.relatorio_tecnico_docx, name="relatorio-tecnico-docx"),
    path("<int:prestacao_id>/relatorio-tecnico/pdf/", views.relatorio_tecnico_pdf, name="relatorio-tecnico-pdf"),
]
