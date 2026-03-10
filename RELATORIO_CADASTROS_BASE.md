# Relatório — Cadastros base (Estados, Cidades, Viajantes, Veículos, Configurações)

## 1. Models criados

| Model | Campos principais | Observações |
|-------|-------------------|-------------|
| **Estado** | nome, sigla, ativo, created_at, updated_at | sigla única; ordering por nome |
| **Cidade** | nome, estado (FK), ativo, created_at, updated_at | ordering por nome |
| **Viajante** | nome, cargo, rg, cpf, telefone, email, unidade_lotacao, is_ascom, ativo, created_at, updated_at | email e unidade_lotacao opcionais |
| **Veiculo** | prefixo, placa, modelo, combustivel, ativo, created_at, updated_at | placa única; prefixo opcional |
| **ConfiguracaoSistema** | cidade_sede_padrao (FK Cidade, opcional), prazo_justificativa_dias (default 10), nome_orgao, sigla_orgao, updated_at | Singleton: `get_singleton()` garante um único registro (pk=1) |

---

## 2. Rotas criadas

Todas em `cadastros/urls.py`, com `login_required`:

| Nome da rota | URL | Descrição |
|--------------|-----|-----------|
| estado-lista | /cadastros/estados/ | Lista de estados |
| estado-cadastrar | /cadastros/estados/cadastrar/ | Formulário de criação |
| estado-editar | /cadastros/estados/<pk>/editar/ | Formulário de edição |
| cidade-lista | /cadastros/cidades/ | Lista de cidades |
| cidade-cadastrar | /cadastros/cidades/cadastrar/ | Formulário de criação |
| cidade-editar | /cadastros/cidades/<pk>/editar/ | Formulário de edição |
| viajante-lista | /cadastros/viajantes/ | Lista de viajantes |
| viajante-cadastrar | /cadastros/viajantes/cadastrar/ | Formulário de criação |
| viajante-editar | /cadastros/viajantes/<pk>/editar/ | Formulário de edição |
| veiculo-lista | /cadastros/veiculos/ | Lista de veículos |
| veiculo-cadastrar | /cadastros/veiculos/cadastrar/ | Formulário de criação |
| veiculo-editar | /cadastros/veiculos/<pk>/editar/ | Formulário de edição |
| configuracoes | /cadastros/configuracoes/ | Página única de edição (singleton) |

A navegação em `core/navigation.py` foi atualizada para usar essas rotas reais e incluir **Estados** e **Cidades** no grupo Cadastros (Estados, Cidades, Viajantes, Veículos, Configurações).

---

## 3. Templates implementados

- **cadastros/estado_lista.html** — Page header, busca (nome/sigla), filtro ativo/inativo, tabela, link Cadastrar e Editar.
- **cadastros/estado_form.html** — Card com formulário (nome, sigla, ativo), Salvar / Cancelar / Voltar.
- **cadastros/cidade_lista.html** — Busca por nome, filtro por estado e ativo, tabela.
- **cadastros/cidade_form.html** — Nome, estado (select), ativo.
- **cadastros/viajante_lista.html** — Busca (nome, cargo, RG, CPF), filtros ativo e ASCOM, tabela.
- **cadastros/viajante_form.html** — Todos os campos do viajante em grid.
- **cadastros/veiculo_lista.html** — Busca (placa, modelo, prefixo), filtro ativo, tabela.
- **cadastros/veiculo_form.html** — Prefixo, placa, modelo, combustível, ativo.
- **cadastros/configuracao_form.html** — Cidade sede padrão, prazo justificativa, nome/sigla do órgão, Salvar / Cancelar.

Padrão: listagem com filtros em card, tabela responsiva, formulário em card com botões Salvar, Cancelar e Voltar à lista (exceto Configurações).

---

## 4. Admin configurado

Em `cadastros/admin.py`:

- **EstadoAdmin**: list_display (nome, sigla, ativo, updated_at), search_fields (nome, sigla), list_filter (ativo), list_editable (ativo).
- **CidadeAdmin**: list_display (nome, estado, ativo, updated_at), search_fields (nome), list_filter (estado, ativo), list_editable (ativo).
- **ViajanteAdmin**: list_display (nome, cargo, cpf, is_ascom, ativo, updated_at), search_fields (nome, cargo, rg, cpf), list_filter (ativo, is_ascom), list_editable (ativo).
- **VeiculoAdmin**: list_display (placa, prefixo, modelo, combustivel, ativo, updated_at), search_fields (placa, modelo, prefixo), list_filter (ativo), list_editable (ativo).
- **ConfiguracaoSistemaAdmin**: list_display (pk, nome_orgao, sigla_orgao, prazo_justificativa_dias, updated_at); `has_add_permission` retorna False se já existir registro; `has_delete_permission` retorna False.

---

## 5. Testes criados

Em `cadastros/tests/test_cadastros.py`:

- **CadastrosListasAutenticadasTest**: estado/cidade/viajante/veiculo lista exigem login; listas e página de configurações retornam 200 quando autenticado.
- **EstadoCRUDTest**: criação de estado (POST) redireciona para lista e persiste no banco.
- **CidadeCRUDTest**: criação de cidade com estado associado.
- **ViajanteCRUDTest**: criação de viajante.
- **VeiculoCRUDTest**: criação de veículo com placa.
- **ConfiguracaoSingletonTest**: edição da configuração singleton (prazo, nome_orgao, sigla_orgao) e garantia de um único registro.

Execução: `python manage.py test cadastros` (11 testes).

---

## 6. Como testar manualmente

1. **Migrar e usuário**  
   `python manage.py migrate`  
   `python manage.py createsuperuser` (se ainda não existir).

2. **Subir o servidor**  
   `python manage.py runserver`

3. **Login**  
   Acessar http://127.0.0.1:8000/ e fazer login.

4. **Menu**  
   No grupo **Cadastros** da sidebar: Estados, Cidades, Viajantes, Veículos, Configurações, cada um com subitens Lista e Cadastrar (exceto Configurações, que é um único link).

5. **Estados**  
   Cadastros → Estados → Lista: conferir busca e filtro ativo/inativo. Cadastrar: novo estado. Editar: alterar um estado da lista.

6. **Cidades**  
   Cadastrar pelo menos um estado antes. Lista de cidades com busca, filtro por estado e ativo. Cadastrar e editar cidade.

7. **Viajantes**  
   Lista com busca (nome, cargo, RG, CPF) e filtros ativo/ASCOM. Cadastrar e editar viajante.

8. **Veículos**  
   Lista com busca (placa, modelo, prefixo) e filtro ativo. Cadastrar e editar (placa única).

9. **Configurações**  
   Cadastros → Configurações: editar cidade sede padrão (select de cidades), prazo justificativa (dias), nome e sigla do órgão; salvar e ver mensagem de sucesso.

---

## 7. O que já está pronto para integrar com Eventos depois

- **Estado** e **Cidade**: FKs disponíveis para endereços, sede, origem/destino de viagens.
- **Viajante**: model pronto para vincular a termos, ofícios e eventos (ex.: FK em “solicitante”, “viajante”).
- **Veiculo**: model pronto para vincular a roteiros/eventos (veículo da viagem).
- **ConfiguracaoSistema**: `cidade_sede_padrao` para padrões de evento; `prazo_justificativa_dias` para regras de justificativa; `nome_orgao`/`sigla_orgao` para cabeçalhos de documentos. Acesso via `ConfiguracaoSistema.get_singleton()`.

Nenhuma API, autocomplete ou integração com evento/ofício foi implementada; apenas a base de dados e telas de cadastro.

---

## 8. Checklist de aceite

| Item | Status |
|------|--------|
| Model Estado (nome, sigla, ativo, timestamps) | OK |
| Model Cidade (nome, estado FK, ativo, timestamps) | OK |
| Model Viajante (todos os campos solicitados) | OK |
| Model Veiculo (prefixo opcional, placa única) | OK |
| Model ConfiguracaoSistema singleton | OK |
| CRUD Estados (lista, cadastrar, editar) | OK |
| CRUD Cidades (lista, cadastrar, editar) | OK |
| CRUD Viajantes (lista, cadastrar, editar) | OK |
| CRUD Veículos (lista, cadastrar, editar) | OK |
| Página única de Configurações (edição) | OK |
| Busca e filtros nas listagens | OK |
| Rotas reais na navegação (sem placeholder) | OK |
| Estados e Cidades no menu (grupo Cadastros) | OK |
| UI: page header, busca, filtros, tabela, card no form | OK |
| Admin com list_display, search_fields, list_filter | OK |
| Testes: listas autenticadas, criação, config singleton | OK |
| Arquitetura limpa (views por módulo, forms centralizados) | OK |
