from .cargos import cargo_lista, cargo_cadastrar, cargo_editar, cargo_excluir, cargo_definir_padrao
from .viajantes import (
    viajante_lista, viajante_cadastrar, viajante_editar, viajante_excluir,
    viajante_salvar_rascunho_ir_cargos, viajante_salvar_rascunho_ir_unidades,
)
from .unidades import unidade_lotacao_lista, unidade_lotacao_cadastrar, unidade_lotacao_editar, unidade_lotacao_excluir
from .veiculos import (
    veiculo_lista, veiculo_cadastrar, veiculo_editar, veiculo_excluir,
    veiculo_salvar_rascunho_ir_combustiveis,
    combustivel_lista, combustivel_cadastrar, combustivel_editar, combustivel_excluir, combustivel_definir_padrao,
)
from .configuracoes import configuracoes_editar
from .api import api_cidades_por_estado, api_consulta_cep

__all__ = [
    'cargo_lista', 'cargo_cadastrar', 'cargo_editar', 'cargo_excluir', 'cargo_definir_padrao',
    'viajante_lista', 'viajante_cadastrar', 'viajante_editar', 'viajante_excluir',
    'viajante_salvar_rascunho_ir_cargos', 'viajante_salvar_rascunho_ir_unidades',
    'unidade_lotacao_lista', 'unidade_lotacao_cadastrar', 'unidade_lotacao_editar', 'unidade_lotacao_excluir',
    'veiculo_lista', 'veiculo_cadastrar', 'veiculo_editar', 'veiculo_excluir',
    'veiculo_salvar_rascunho_ir_combustiveis',
    'combustivel_lista', 'combustivel_cadastrar', 'combustivel_editar', 'combustivel_excluir', 'combustivel_definir_padrao',
    'configuracoes_editar',
    'api_cidades_por_estado',
    'api_consulta_cep',
]
