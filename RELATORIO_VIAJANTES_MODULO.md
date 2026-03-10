# Relatório — Módulo Viajantes (cadastro de servidores)

## Resumo

Módulo Viajantes implementado com CRUD completo, validações (CPF, telefone), máscaras no frontend, opção "Não possui RG" (sem_rg), lista com busca/filtros, ativar/desativar sem exclusão física, e integração ao menu lateral com submenu Lista e Cadastrar.

---

## A) Model (cadastros/models.py)

**Alterações no Viajante:**

| Campo | Tipo | Observação |
|-------|------|------------|
| nome | CharField(160) | Obrigatório; normalizado no save (strip + colapso de espaços) |
| cargo | CharField(120) | Obrigatório |
| rg | CharField(30, blank, default='') | Se sem_rg=True, salvo como "NÃO POSSUI RG" no save() |
| sem_rg | BooleanField(default=False) | Novo: "Não possui RG" |
| cpf | CharField(14, blank, default='') | Validado no form; armazenado só dígitos; UNIQUE quando preenchido |
| telefone | CharField(20, blank, default='') | Validado 10 ou 11 dígitos; armazenado só dígitos |
| unidade_lotacao | CharField(120, blank, default='') | Opcional |
| is_ascom | BooleanField(default=True) | Usado no domínio |
| ativo | BooleanField(default=True) | |
| created_at, updated_at | DateTimeField | |

**Removido:** email.

**Constraint:** `UniqueConstraint(fields=['cpf'], condition=Q(cpf__gt=''), name='cadastros_viajante_cpf_unique')` — CPF único quando preenchido.

**save():** normaliza nome (strip + espaços simples); se sem_rg=True, define rg = "NÃO POSSUI RG".

---

## B) Migrations

**Arquivo:** `cadastros/migrations/0005_viajante_sem_rg_ajustes.py`

- AddField sem_rg
- AlterField nome (160), cargo (120), rg (30, default=''), cpf (default=''), telefone (default=''), unidade_lotacao (120, default=''), is_ascom (default=True)
- RemoveField email
- AddConstraint cadastros_viajante_cpf_unique (cpf único quando cpf > '')

---

## C) Form (cadastros/forms.py)

**ViajanteForm:**

- **Campos:** nome, cargo, rg, sem_rg, cpf, telefone, unidade_lotacao, is_ascom, ativo.
- **Validações server-side:**
  - nome: obrigatório; normalizado (strip + colapso de espaços).
  - rg: se sem_rg (checkbox marcado), retorna "NÃO POSSUI RG"; senão usa valor informado.
  - cpf: se preenchido, 11 dígitos e validação de dígitos verificadores; salvo só números; validação de duplicidade (clean).
  - telefone: se preenchido, 10 ou 11 dígitos; salvo só números.
- **sem_rg:** checkbox "Não possui RG"; no frontend o input RG é desabilitado e limpo quando marcado; no backend clean_rg usa self.data.get('sem_rg') e retorna "NÃO POSSUI RG" quando marcado.

---

## D) Views e URLs

**Arquivo de views:** `cadastros/views/viajantes.py`

| View | Método | Descrição |
|------|--------|-----------|
| viajante_lista | GET | Lista com busca (nome, cargo, rg, cpf, telefone, unidade_lotacao), filtros ativo e ASCOM, ordenação por nome |
| viajante_cadastrar | GET, POST | Criação |
| viajante_editar | GET, POST | Edição por pk |
| viajante_desativar | POST | Toggle ativo (sem deletar) |

**Rotas (cadastros/urls.py):**

| Rota | Nome | View |
|------|------|------|
| /cadastros/viajantes/ | cadastros:viajante-lista | viajante_lista |
| /cadastros/viajantes/cadastrar/ | cadastros:viajante-cadastrar | viajante_cadastrar |
| /cadastros/viajantes/<pk>/editar/ | cadastros:viajante-editar | viajante_editar |
| /cadastros/viajantes/<pk>/desativar/ | cadastros:viajante-desativar | viajante_desativar |

Todas exigem login (@login_required).

---

## E) Templates

**Diretório:** `templates/cadastros/viajantes/`

- **lista.html:** tabela com Nome, Cargo, RG (badge "NÃO POSSUI RG" quando sem_rg ou rg == "NÃO POSSUI RG"), CPF, ASCOM, Situação (badge Ativo/Inativo); filtros por busca, Situação e ASCOM; ações Editar e Ativar/Desativar (form POST para desativar).
- **form.html:** formulário com máscaras em JS:
  - CPF: 000.000.000-00 (input formatado; salvo só dígitos).
  - Telefone: (##) #####-#### ou (##) ####-####.
  - Checkbox "Não possui RG": ao marcar, desabilita e limpa o input RG.

Layout herdado de base.html.

---

## F) Navegação (core/navigation.py e base.html)

- **Viajantes** habilitado (enabled=True) com submenu:
  - **Lista** → cadastros:viajante-lista
  - **Cadastrar** → cadastros:viajante-cadastrar
- Item "Viajantes" do menu aponta para a lista; abaixo, subitens Lista e Cadastrar (base.html renderiza children em `<ul class="nav flex-column ms-3 small">`).

---

## G) Admin (cadastros/admin.py)

**ViajanteAdmin:**

- list_display: nome, cargo, cpf, telefone, is_ascom, sem_rg, ativo, updated_at
- search_fields: nome, cargo, cpf, rg, telefone, unidade_lotacao
- list_filter: is_ascom, ativo
- list_editable: ativo

---

## H) Testes (cadastros/tests/test_cadastros.py)

**Classe ViajanteViewTest:**

1. **test_viajante_lista_exige_login** — GET lista sem login retorna 302 para login.
2. **test_viajante_criar_ok** — POST cadastrar com nome/cargo redireciona e cria registro.
3. **test_viajante_editar_ok** — POST editar altera nome e redireciona.
4. **test_viajante_cpf_invalido_falha** — CPF inválido (ex.: 11111111111) mantém status 200 e erro no form.
5. **test_viajante_telefone_invalido_falha** — Telefone com menos de 10 dígitos falha com mensagem esperada.
6. **test_viajante_toggle_ativo** — POST desativar desativa; novo POST desativar reativa.
7. **test_viajante_filtro_ascom** — Cria 1 ASCOM e 1 não-ASCOM; ascom=1 mostra só ASCOM; ascom=0 mostra só não-ASCOM.
8. **test_viajante_sem_rg_salva_nao_possui_rg** — Cadastro com sem_rg=True grava rg == "NÃO POSSUI RG".
9. **test_viajante_sem_rg_false_rg_vazio_permitido** — Cadastro com sem_rg=False e rg vazio é aceito.

**Como rodar:**

```bash
python manage.py test cadastros.tests.test_cadastros.ViajanteViewTest
python manage.py test cadastros.tests.test_cadastros
```

---

## Regras e validações implementadas

- **Nome:** obrigatório; no save() do model: strip e colapso de espaços duplos.
- **RG:** se sem_rg=True (checkbox), no form clean_rg retorna "NÃO POSSUI RG" e no save() do model também é definido; se sem_rg=False, rg pode ser vazio ou preenchido.
- **CPF:** se preenchido, 11 dígitos e validação de dígitos verificadores; armazenado só números; único (constraint + validação no form para duplicidade).
- **Telefone:** se preenchido, 10 ou 11 dígitos; armazenado só números.
- **Ativar/Desativar:** POST em /cadastros/viajantes/<pk>/desativar/ inverte ativo; sem exclusão física.

---

## Teste manual (passo a passo)

1. Fazer login.
2. Menu lateral: Cadastros → Viajantes (ou submenu Lista). Acessar lista.
3. Clicar em "Cadastrar". Preencher Nome e Cargo; marcar "Não possui RG"; Salvar. Verificar na lista RG como "NÃO POSSUI RG".
4. Editar o viajante: desmarcar "Não possui RG", informar RG; Salvar. Verificar persistência.
5. Cadastrar outro com CPF válido (ex.: 52998224725). Salvar. Verificar CPF na lista (exibido sem máscara ou com máscara conforme template).
6. Tentar salvar com CPF inválido (ex.: 11111111111). Verificar mensagem "CPF inválido.".
7. Informar telefone inválido (ex.: 123). Verificar mensagem de 10/11 dígitos.
8. Na lista, usar filtros: Situação (Ativos/Inativos), ASCOM (Sim/Não) e busca por texto. Verificar resultados.
9. Clicar em "Desativar" em um viajante ativo; verificar badge "Inativo". Clicar em "Ativar"; verificar "Ativo".
10. Em Configurações, verificar que os selects de assinatura listam apenas viajantes ativos.

---

## Checklist de aceite

| Item | Status |
|------|--------|
| CRUD completo (lista / cadastrar / editar) | OK |
| Filtros e busca funcionando | OK |
| CPF e telefone validados no backend | OK |
| Máscaras no frontend (CPF e telefone) | OK |
| RG com opção "Não possui RG" (salvando "NÃO POSSUI RG") | OK |
| Ativar/Desativar sem deletar | OK |
| Menu lateral com submenu Viajantes (Lista e Cadastrar) | OK |
| Testes passando (9 testes ViajanteViewTest + demais cadastros) | OK |

---

## Arquivos alterados/criados

- **Alterados:** cadastros/models.py, cadastros/forms.py, cadastros/views/viajantes.py, cadastros/views/__init__.py, cadastros/urls.py, cadastros/admin.py, core/navigation.py, templates/base.html, cadastros/tests/test_cadastros.py
- **Criados:** cadastros/migrations/0005_viajante_sem_rg_ajustes.py, templates/cadastros/viajantes/lista.html, templates/cadastros/viajantes/form.html, RELATORIO_VIAJANTES_MODULO.md

Os templates antigos `templates/cadastros/viajante_lista.html` e `viajante_form.html` não são mais usados pelas views de viajantes (as views passaram a usar `cadastros/viajantes/lista.html` e `cadastros/viajantes/form.html`). Podem ser removidos se não forem referenciados em outro lugar.
