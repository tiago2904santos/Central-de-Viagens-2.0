# Relatório — Módulo Eventos (base)

## 1. Model criado

O model **Evento** foi criado em `eventos/models.py` com os campos:

| Campo | Tipo | Observação |
|-------|------|------------|
| `titulo` | CharField(200) | Obrigatório |
| `tipo_demanda` | CharField(30) | Choices: PCPR_NA_COMUNIDADE, OPERACAO_POLICIAL, PARANA_EM_ACAO, OUTRO |
| `descricao` | TextField | Opcional |
| `data_inicio` | DateField | Obrigatório |
| `data_fim` | DateField | Obrigatório (validado: >= data_inicio) |
| `estado_principal` | FK(Estado) | Opcional |
| `cidade_principal` | FK(Cidade) | Opcional; validado para pertencer ao estado_principal |
| `cidade_base` | FK(Cidade) | Opcional; valor inicial sugerido por ConfiguracaoSistema.cidade_sede_padrao |
| `tem_convite_ou_oficio_evento` | BooleanField | Default False |
| `status` | CharField(20) | Choices: RASCUNHO, EM_ANDAMENTO, FINALIZADO, ARQUIVADO; default RASCUNHO |
| `created_at` / `updated_at` | DateTimeField | auto_now_add / auto_now |

- **Meta**: `ordering = ['-data_inicio', '-created_at']`
- **Migração**: `eventos/migrations/0001_initial.py` (depende de `cadastros.0002_add_codigo_ibge`)

---

## 2. Rotas criadas

Em `eventos/urls.py` (prefixo `/eventos/` em `config/urls.py`):

| Rota | Nome | View |
|------|------|------|
| `''` | `eventos:lista` | Lista de eventos (filtros e busca) |
| `cadastrar/` | `eventos:cadastrar` | Formulário de criação |
| `<int:pk>/` | `eventos:detalhe` | Página de detalhe do evento |
| `<int:pk>/editar/` | `eventos:editar` | Formulário de edição |

**Importante:** Em `config/urls.py`, `path('eventos/', include('eventos.urls'))` foi colocado **antes** de `path('', include('core.urls'))` para que `/eventos/<pk>/` seja atendido pelo app eventos e não pelo placeholder `eventos/<slug:action>/` do core.

---

## 3. Templates implementados

| Template | Uso |
|----------|-----|
| `templates/eventos/evento_lista.html` | Lista com page header, filtros (título, status, tipo_demanda), tabela e botão "Cadastrar evento" |
| `templates/eventos/evento_form.html` | Formulário em card (criar/editar): título, tipo, descrição, datas, estado/cidade principal, cidade base, status, checkbox "Tem convite/ofício" |
| `templates/eventos/evento_detalhe.html` | Detalhe do evento com dados, status, datas, localização, tipo e links "Editar" e "Voltar para lista" |

- Listagem: ordenação mais recente primeiro; busca por título; filtros por status e tipo_demanda.
- Formulário: grid responsivo; estado_principal e cidade_principal com seleção dependente (JS); cidade_base com select de cidades ativas.

---

## 4. Integração Estado/Cidade

- **Endpoint usado:** `GET /cadastros/api/cidades-por-estado/<estado_id>/` (já existente), retornando JSON `[{"id": ..., "nome": "..."}, ...]` ordenado por nome.
- **No formulário do Evento:**
  - Ao escolher `estado_principal`, o select `cidade_principal` é preenchido via JavaScript (fetch na API).
  - Valor atual de `cidade_principal` é preservado ao recarregar as cidades (ex.: ao abrir a edição).
  - `cidade_base` é um select normal com todas as cidades ativas (sem dependência de estado no formulário).
- **Validação no servidor:** no `EventoForm.clean()`:
  - `data_fim >= data_inicio`; em caso contrário, erro em `data_fim`.
  - Se `estado_principal` e `cidade_principal` forem informados, verifica-se se a cidade pertence ao estado; caso contrário, erro em `cidade_principal`.
- **Contexto da view:** as views de cadastrar e editar passam `api_cidades_por_estado_url` ao template para o JS montar a URL da API (substituindo o `0` pelo id do estado selecionado).

---

## 5. Testes criados

Em `eventos/tests/test_eventos.py`:

| Classe | Testes |
|--------|--------|
| **EventoListaAuthTest** | Lista redireciona sem login; lista OK com login |
| **EventoCRUDTest** | Criação de evento (POST com campos obrigatórios e opcionais vazios); edição de evento |
| **EventoValidacaoTest** | data_fim < data_inicio rejeitado com mensagem; cidade_principal fora do estado_principal rejeitado com mensagem |
| **EventoDetalheTest** | Detalhe redireciona sem login; detalhe OK autenticado (título, Editar, Voltar para lista) |

**Execução:** `python manage.py test eventos.tests` (8 testes).  
**Suíte completa:** `python manage.py test core cadastros eventos` (36 testes).

---

## 6. Como testar manualmente

1. **Ambiente:** ativar o venv, `python manage.py migrate`, ter um usuário (ou `createsuperuser`) e, se quiser seleção de cidades, importar a base geográfica (`importar_base_geografica`).
2. **Login:** acessar `/`, fazer login.
3. **Lista:** menu **Eventos → Lista** (ou `/eventos/`). Verificar busca por título, filtros por status e tipo, ordenação, botão "Cadastrar evento".
4. **Cadastrar:** **Eventos → Cadastrar** (ou `/eventos/cadastrar/`). Preencher título, tipo, datas (data_fim >= data_inicio), opcionalmente estado/cidade principal (trocar estado e ver cidade principal atualizar), cidade base, status e checkbox. Salvar e conferir redirecionamento para a lista.
5. **Detalhe:** na lista, clicar em "Ver" em um evento. Conferir dados, "Editar" e "Voltar para lista".
6. **Editar:** na lista ou no detalhe, "Editar". Alterar campos, salvar e conferir redirecionamento para o detalhe.
7. **Validações:** tentar salvar com data_fim anterior a data_inicio; com estado principal SP e cidade principal do RJ (se houver dados). Deve aparecer mensagem de erro no formulário.
8. **Admin:** `/admin/` → Eventos; list_display, filtros e busca por título devem funcionar.

---

## 7. O que já fica pronto para evoluir para o fluxo guiado

- **Model estável:** campos de evento (título, tipo, datas, localização, status) permitem depois vincular ofícios, termos, justificativas, roteiros e plano de trabalho por FK ou relação reversa.
- **CRUD e listagem:** base para incluir colunas/links para “próximo passo” (ex.: “Criar ofício”, “Abrir plano de trabalho”) e filtros adicionais.
- **Estado/Cidade:** integração já feita no formulário e na API; reutilizável em outros módulos (roteiros, ofícios, termos).
- **Status e tipo_demanda:** choices centralizados no model; fácil estender (novos status ou tipos) e usar em regras do wizard (ex.: só permitir ofício se status = EM_ANDAMENTO).
- **Navegação:** sidebar já aponta Eventos → Lista e Cadastrar para as views reais; detalhe e editar ficam fora do menu, acessíveis por botões.

---

## 8. Checklist de aceite

| Item | Status |
|------|--------|
| Model Evento com todos os campos e choices | OK |
| Validação data_fim >= data_inicio | OK |
| Validação cidade_principal no estado_principal | OK |
| cidade_base inicial por ConfiguracaoSistema.cidade_sede_padrao | OK |
| Lista com busca, filtros (status, tipo) e ordenação | OK |
| Cadastrar / Editar / Detalhe | OK |
| Formulário com seleção dependente estado/cidade (JS + API) | OK |
| Validação no servidor para cidade/estado | OK |
| Navegação: Eventos → Lista e Cadastrar (rotas reais) | OK |
| Admin com list_display, filtros e busca | OK |
| Testes: lista exige login, criar, editar, validações, detalhe | OK |
| URL `/eventos/<pk>/` atendida pelo app eventos (ordem em config/urls) | OK |

**Não implementado nesta etapa (conforme combinado):** wizard de 6 etapas, roteiros, ofícios, plano de trabalho, ordem de serviço, termos, justificativas, uploads, pacote final.
