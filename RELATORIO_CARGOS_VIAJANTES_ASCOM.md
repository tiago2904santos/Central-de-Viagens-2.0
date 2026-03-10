# Relatório: Cadastro de Cargos, integração com Viajantes e remoção de ASCOM

## Resumo

- **Cargos:** CRUD completo (lista, cadastrar, editar, excluir) com validação de exclusão quando o cargo está em uso.
- **Viajantes:** Campo `cargo` passou de `CharField` para `ForeignKey(Cargo)`; campo `is_ascom` removido do modelo e de todo o sistema.
- **Máscaras:** CPF e telefone são salvos como dígitos no banco; ao abrir/editar o formulário de viajante, os valores aparecem já formatados (backend + frontend).

---

## 1. Arquivos alterados / criados

| Arquivo | Alteração |
|--------|-----------|
| `cadastros/models.py` | Criado model `Cargo` (nome, ativo, created_at, updated_at). Viajante: `cargo` virou `ForeignKey(Cargo, null=True, blank=True, on_delete=SET_NULL)`; removido `is_ascom`. |
| `cadastros/forms.py` | Criado `CargoForm` (nome normalizado em uppercase, validação de duplicidade). `ViajanteForm`: removido `is_ascom`; `cargo` como select (Cargos ativos); funções `_format_cpf` e `_format_telefone`; em `__init__`, quando há instance e não é POST, define `self.initial['cpf']` e `self.initial['telefone']` formatados. |
| `cadastros/views/cargos.py` | **Novo.** Views: `cargo_lista`, `cargo_cadastrar`, `cargo_editar`, `cargo_excluir` (bloqueia se cargo tiver viajantes). |
| `cadastros/views/viajantes.py` | Removido filtro por `ascom`; busca por `cargo__nome` em vez de `cargo` (texto). |
| `cadastros/views/__init__.py` | Export de `cargo_lista`, `cargo_cadastrar`, `cargo_editar`, `cargo_excluir`. |
| `cadastros/urls.py` | Rotas para cargos: lista, cadastrar, editar, excluir. |
| `cadastros/admin.py` | Registrado `CargoAdmin` (search, list_filter ativo). ViajanteAdmin: removidos `is_ascom` de list_display e list_filter; `search_fields` com `cargo__nome`. |
| `core/navigation.py` | Menu Cadastros: item Cargos (submenu Lista / Cadastrar); Viajantes mantido; ordens ajustadas. |
| `templates/cadastros/cargos/lista.html` | **Novo.** Lista de cargos com busca por nome e badge ativo/inativo. |
| `templates/cadastros/cargos/form.html` | **Novo.** Formulário de cargo (nome, ativo). |
| `templates/cadastros/cargos/excluir_confirm.html` | **Novo.** Confirmação de exclusão de cargo. |
| `templates/cadastros/viajantes/lista.html` | Removido filtro e coluna ASCOM; cargo exibido como `obj.cargo.nome`. |
| `templates/cadastros/viajantes/form.html` | Removido bloco do campo `is_ascom`; em `DOMContentLoaded`, aplica máscara ao valor atual de CPF e telefone. |
| `templates/cadastros/viajante_lista.html` | Alinhado ao modelo atual: removidos filtros Situação e ASCOM, colunas ASCOM e Situação; cargo como `obj.cargo.nome`. |
| `templates/cadastros/viajante_form.html` | Removidos blocos `is_ascom`, `ativo` e `email`. |
| `cadastros/tests/test_cadastros.py` | Import de `Cargo`; nova classe `CargoViewTest`; `ViajanteViewTest` atualizado (cargo FK, sem is_ascom); testes de máscara e busca por cargo; removido `test_viajante_filtro_ascom`. Configurações: criação de viajantes com `Cargo` para assinaturas. |

---

## 2. Migrations

| Migration | Descrição |
|-----------|-----------|
| `0007_cargo.py` | Cria o model `Cargo` (nome unique, ativo, created_at, updated_at). |
| `0008_viajante_cargo_fk_remove_is_ascom.py` | Adiciona `Viajante.cargo_fk` (FK Cargo); data migration: para cada viajante com cargo texto, cria/obtém `Cargo` com nome normalizado (uppercase) e associa; remove o campo antigo `cargo` (CharField); renomeia `cargo_fk` para `cargo`; altera `cargo` para `related_name='viajantes'`; remove `is_ascom`. |

A data migration preenche o novo FK a partir do cargo em texto; o reverso da RunPython não repopula o campo texto (noop).

---

## 3. Rotas adicionadas

| Rota | Nome | Descrição |
|------|------|-----------|
| `GET /cadastros/cargos/` | `cadastros:cargo-lista` | Lista de cargos (com busca por nome). |
| `GET+POST /cadastros/cargos/cadastrar/` | `cadastros:cargo-cadastrar` | Cadastro de cargo. |
| `GET+POST /cadastros/cargos/<pk>/editar/` | `cadastros:cargo-editar` | Edição de cargo. |
| `GET+POST /cadastros/cargos/<pk>/excluir/` | `cadastros:cargo-excluir` | Confirmação e exclusão (POST); bloqueia se houver viajantes vinculados. |

---

## 4. Confirmação: ASCOM removido completamente

| Camada | Status |
|--------|--------|
| **Model** | `is_ascom` removido de `Viajante` (migration 0008). |
| **Forms** | `ViajanteForm`: campo e widget `is_ascom` removidos. |
| **Views** | Filtro `ascom` removido da lista de viajantes. |
| **Templates** | Em `viajantes/lista.html` e `viajantes/form.html`: sem filtro/coluna/campo ASCOM. Templates antigos `viajante_lista.html` e `viajante_form.html` alinhados (sem ASCOM). |
| **Admin** | `ViajanteAdmin`: removidos `list_display` e `list_filter` de `is_ascom`. |
| **Testes** | Removido `test_viajante_filtro_ascom`; criação/edição de viajante sem `is_ascom`. |
| **Menu / filtros** | Nenhum item de menu ou filtro relacionado a ASCOM. |

Não restou uso de `is_ascom` em código ativo. Migrations antigas (0001, 0005) e relatórios (.md) podem ainda citar o campo por histórico.

---

## 5. Máscara ao carregar (CPF e telefone)

- **Backend:** No `ViajanteForm.__init__`, quando há `instance` e não há `self.data` (GET de edição), são definidos `self.initial['cpf']` e `self.initial['telefone']` com `_format_cpf()` e `_format_telefone()`. O formulário renderiza esses valores nos inputs.
- **Persistência:** `clean_cpf` e `clean_telefone` mantêm apenas dígitos; o modelo armazena só dígitos.
- **Frontend:** No template do form de viajante, em `DOMContentLoaded`, o script aplica `formatCpf` e `formatTel` ao valor atual dos inputs `id_cpf` e `id_telefone`, garantindo máscara após F5 ou ao voltar na tela.

---

## 6. Como testar manualmente

1. **Cargos**  
   - Acessar Cadastros → Cargos → Lista e Cadastrar.  
   - Cadastrar cargo (ex.: "ANALISTA"); editar; excluir um cargo não usado.  
   - Tentar excluir cargo que tenha viajante vinculado: deve aparecer mensagem de impedimento.

2. **Viajantes**  
   - Cadastros → Viajantes → Cadastrar: escolher um cargo no select; salvar.  
   - Lista: conferir coluna Cargo e busca por nome de cargo.  
   - Editar viajante com CPF e telefone: abrir a tela e dar F5; CPF e telefone devem aparecer mascarados.  
   - Confirmar que não existe filtro nem coluna ASCOM em nenhuma tela.

3. **Configurações**  
   - Abrir Configurações; selecionar viajantes nas assinaturas; salvar.  
   - Verificar que não há referência a ASCOM.

---

## 7. Checklist de aceite

| Item | Status |
|------|--------|
| CRUD de Cargos (lista, cadastrar, editar, excluir) | OK |
| Exclusão de cargo bloqueada quando em uso por viajante | OK |
| Viajantes com cargo via FK (select de Cargos ativos) | OK |
| Campo ASCOM inexistente (model, form, views, templates, admin, testes, menu) | OK |
| CPF e telefone mascarados ao abrir/editar formulário de viajante | OK |
| CPF e telefone salvos apenas com dígitos no banco | OK |
| Busca na lista de viajantes por cargo (nome do cargo) | OK |
| Menu Cadastros com Cargos (Lista, Cadastrar) e Viajantes (Lista, Cadastrar) | OK |
| Testes Cargo e Viajante passando | OK |

---

## 8. Observações

- **Cargo:** Nome é normalizado no model (`save`: strip + uppercase) e no form (`clean_nome`: validação e duplicidade).
- **Data migration:** Viajantes existentes com cargo em texto tiveram o FK preenchido com Cargos criados/obtidos pelo nome normalizado; cargo vazio vira "SEM CARGO".
- **Templates antigos:** `viajante_lista.html` e `viajante_form.html` (sem "s") foram ajustados para não usar `is_ascom`, `ativo` nem `email`; as views atuais usam `viajantes/lista.html` e `viajantes/form.html`.
