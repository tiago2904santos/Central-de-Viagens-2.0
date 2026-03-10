from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'cadastros'

urlpatterns = [
    path('cargos/', login_required(views.cargo_lista), name='cargo-lista'),
    path('cargos/cadastrar/', login_required(views.cargo_cadastrar), name='cargo-cadastrar'),
    path('cargos/<int:pk>/editar/', login_required(views.cargo_editar), name='cargo-editar'),
    path('cargos/<int:pk>/excluir/', login_required(views.cargo_excluir), name='cargo-excluir'),
    path('cargos/<int:pk>/definir-padrao/', login_required(views.cargo_definir_padrao), name='cargo-definir-padrao'),
    path('viajantes/', login_required(views.viajante_lista), name='viajante-lista'),
    path('viajantes/cadastrar/', login_required(views.viajante_cadastrar), name='viajante-cadastrar'),
    path('viajantes/<int:pk>/editar/', login_required(views.viajante_editar), name='viajante-editar'),
    path('viajantes/<int:pk>/excluir/', login_required(views.viajante_excluir), name='viajante-excluir'),
    path('viajantes/salvar-rascunho-ir-cargos/', login_required(views.viajante_salvar_rascunho_ir_cargos), name='viajante-rascunho-ir-cargos'),
    path('viajantes/salvar-rascunho-ir-unidades/', login_required(views.viajante_salvar_rascunho_ir_unidades), name='viajante-rascunho-ir-unidades'),
    path('unidades-lotacao/', login_required(views.unidade_lotacao_lista), name='unidade-lotacao-lista'),
    path('unidades-lotacao/cadastrar/', login_required(views.unidade_lotacao_cadastrar), name='unidade-lotacao-cadastrar'),
    path('unidades-lotacao/<int:pk>/editar/', login_required(views.unidade_lotacao_editar), name='unidade-lotacao-editar'),
    path('unidades-lotacao/<int:pk>/excluir/', login_required(views.unidade_lotacao_excluir), name='unidade-lotacao-excluir'),
    path('veiculos/', login_required(views.veiculo_lista), name='veiculo-lista'),
    path('veiculos/cadastrar/', login_required(views.veiculo_cadastrar), name='veiculo-cadastrar'),
    path('veiculos/<int:pk>/editar/', login_required(views.veiculo_editar), name='veiculo-editar'),
    path('veiculos/<int:pk>/excluir/', login_required(views.veiculo_excluir), name='veiculo-excluir'),
    path('veiculos/salvar-rascunho-ir-combustiveis/', login_required(views.veiculo_salvar_rascunho_ir_combustiveis), name='veiculo-rascunho-ir-combustiveis'),
    path('veiculos/combustiveis/', login_required(views.combustivel_lista), name='combustivel-lista'),
    path('veiculos/combustiveis/cadastrar/', login_required(views.combustivel_cadastrar), name='combustivel-cadastrar'),
    path('veiculos/combustiveis/<int:pk>/editar/', login_required(views.combustivel_editar), name='combustivel-editar'),
    path('veiculos/combustiveis/<int:pk>/excluir/', login_required(views.combustivel_excluir), name='combustivel-excluir'),
    path('veiculos/combustiveis/<int:pk>/definir-padrao/', login_required(views.combustivel_definir_padrao), name='combustivel-definir-padrao'),
    path('api/cidades-por-estado/<int:estado_id>/', login_required(views.api_cidades_por_estado), name='api-cidades-por-estado'),
    path('api/cep/<str:cep>/', login_required(views.api_consulta_cep), name='api-consulta-cep'),
    path('configuracoes/', login_required(views.configuracoes_editar), name='configuracoes'),
]
