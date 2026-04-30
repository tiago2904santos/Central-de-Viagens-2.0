from django.urls import path

from . import views

app_name = "prestacao_contas"

urlpatterns = [
    path("", views.prestacao_lista, name="lista"),
    path("nova/", views.prestacao_nova, name="nova"),
    path("textos-padrao/", views.texto_padrao_lista, name="textos-padrao"),
    path("textos-padrao/novo/", views.texto_padrao_form, name="textos-padrao-novo"),
    path("textos-padrao/<int:pk>/editar/", views.texto_padrao_form, name="textos-padrao-editar"),
    path("<int:prestacao_id>/", views.prestacao_detalhe, name="detalhe"),
    path("<int:prestacao_id>/editar/", views.prestacao_editar, name="editar"),
    path("<int:prestacao_id>/step/<int:step>/", views.prestacao_step, name="step"),
    path("<int:prestacao_id>/resumo/", views.prestacao_resumo, name="resumo"),
    path("<int:prestacao_id>/excluir/", views.prestacao_excluir, name="excluir"),
    path("<int:prestacao_id>/relatorio-tecnico/", views.relatorio_tecnico_form, name="relatorio-tecnico"),
    path("<int:prestacao_id>/relatorio-tecnico/docx/", views.relatorio_tecnico_docx, name="relatorio-tecnico-docx"),
    path("<int:prestacao_id>/relatorio-tecnico/pdf/", views.relatorio_tecnico_pdf, name="relatorio-tecnico-pdf"),
]
