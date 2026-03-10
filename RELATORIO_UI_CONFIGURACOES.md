# Relatório — Reinício da camada UI/rotas e módulo Configurações

## 1. O que foi removido (rotas/views/templates placeholders)

### Rotas removidas (config/urls.py)
- `path('eventos/', include('eventos.urls'))` — removido (módulo não implementado nesta entrega).
- `path('documentos/', include('documentos.urls'))` — removido.

### Rotas removidas (core/urls.py)
- `path('placeholder/<str:modulo>/', ...)` (name=`core:placeholder`).
- `path('simulacao-diarias/', ...)` (name=`core:simulacao-diarias`).
- `path('eventos/<slug:action>/', ...)` (name=`core:eventos-sub`).
- `path('roteiros/<slug:action>/', ...)` (name=`core:roteiros-sub`).
- `path('oficios/<slug:action>/', ...)` (name=`core:oficios-sub`).
- `path('planos-trabalho/<slug:action>/', ...)` (name=`core:planos-trabalho-sub`).
- `path('ordens-servico/<slug:action>/', ...)` (name=`core:ordens-servico-sub`).
- `path('justificativas/<slug:action>/', ...)` (name=`core:justificativas-sub`).
- `path('termos/<slug:action>/', ...)` (name=`core:termos-sub`).
- `path('oficios/', ...)`, `path('planos-trabalho/', ...)`, `path('ordens-servico/', ...)`, `path('justificativas/', ...)`, `path('termos/', ...)`, `path('roteiros/', ...)` (placeholders por nome).

### Views removidas (core/views)
- `placeholder_view`, `placeholder_by_name_view`, `placeholder_module_action_view` — substituídas por uma única `em_breve_view` que renderiza `core/em_breve.html`.

### Templates removidos
- `templates/core/placeholder.html` — substituído por `templates/core/em_breve.html` (página única “Em breve”).

### Rotas removidas (cadastros/urls.py)
- Rotas de Viajantes e Veículos (lista, cadastrar, editar) — módulos desabilitados nesta entrega; apenas Configurações e a API de cidades permanecem.

---

## 2. Como ficou a sidebar (ativos x desabilitados, sem links quebrados)

- **Fonte:** `core/navigation.py` — menu continua configurável por dados.
- **Itens ativos (com URL e clicáveis):**
  - **Painel** — `core:dashboard` → `/dashboard/`.
  - **Configurações** — `cadastros:configuracoes` → `/cadastros/configuracoes/`.
- **Itens desabilitados (sem link, badge “Em breve”):**
  - Simulação de Diárias, Eventos, Roteiros, Ofícios, Planos de Trabalho, Ordens de Serviço, Justificativas, Termos de Autorização (grupo principal).
  - Viajantes, Veículos (grupo cadastros).
- **Comportamento:** Itens desabilitados são renderizados como `<span class="nav-link sidebar-item-disabled">` com badge “Em breve”; não há submenus (Cadastrar/Lista) para módulos não implementados. Nenhum link leva a 404.

---

## 3. Rotas reais após a limpeza

| Rota | Nome (reverse) | Descrição |
|------|-----------------|-----------|
| `/` | `core:login` | Página de login |
| `/login/` | `core:login` | Login |
| `/logout/` | `core:logout` | Logout |
| `/dashboard/` | `core:dashboard` | Painel (autenticado) |
| `/em-breve/` | `core:em-breve` | Página “Em breve” (autenticado) |
| `/cadastros/configuracoes/` | `cadastros:configuracoes` | Configurações do sistema |
| `/cadastros/api/cidades-por-estado/<id>/` | `cadastros:api-cidades-por-estado` | API cidades por estado (GET JSON) |
| `/admin/` | — | Django Admin |

---

## 4. Implementação da tela de Configurações (template + JS)

### Model
- **ConfiguracaoSistema** (singleton): `cidade_sede_padrao` (FK Cidade, opcional), `prazo_justificativa_dias` (default 10), `nome_orgao`, `sigla_orgao`.

### Template (`templates/cadastros/configuracao_form.html`)
- Título: “Configurações do sistema”; subtítulo: “Parâmetros globais do processo de viagens”.
- **Seção 1 — Base do sistema:** `prazo_justificativa_dias` (min 0), `nome_orgao`, `sigla_orgao`.
- **Seção 2 — Local padrão (sede):** Select Estado (carrega estados do banco); Select Cidade dependente do estado (preenchido via API ao mudar o estado).
- JS mínimo (sem framework): ao mudar o Estado, chama `GET /cadastros/api/cidades-por-estado/<estado_id>/` e preenche o select de Cidade; mantém valor atual ao carregar em edição.
- Mensagem de sucesso: “Configurações salvas com sucesso.” (Django messages).
- Validação no servidor: `prazo_justificativa_dias >= 0`; se cidade informada, deve pertencer ao estado escolhido (form `clean()`).

### Form
- **ConfiguracaoSistemaForm:** campo auxiliar `estado` (não persistido) para seleção dependente; validação em `clean()` para cidade × estado; `clean_prazo_justificativa_dias` para valor ≥ 0.

### View
- `configuracoes_editar`: define querysets de `estado` e `cidade_sede_padrao` conforme GET/POST; passa `api_cidades_por_estado_url` e `estado_id_atual` para o template.

---

## 5. Como testar manualmente

1. **Subir o projeto**
   ```bash
   py -3 manage.py runserver
   ```
2. **Login:** acessar `/` ou `/login/`, entrar com usuário válido → redirecionamento para `/dashboard/`.
3. **Sidebar:** Painel e Configurações são links; demais itens aparecem com “Em breve” e não são clicáveis (sem 404).
4. **Configurações:** menu “Configurações” → `/cadastros/configuracoes/`. Alterar prazo, nome/sigla do órgão; escolher Estado e depois Cidade (cidades carregam ao mudar estado). Salvar → mensagem “Configurações salvas com sucesso.” e dados persistidos no singleton.
5. **API:** autenticado, `GET /cadastros/api/cidades-por-estado/<id_estado>/` retorna JSON com lista de cidades (id, nome) ordenadas por nome.

---

## 6. Checklist de aceite

| Critério | Status |
|----------|--------|
| Não existe mais rota genérica de placeholder por módulo/ação | OK |
| Sidebar sem links quebrados; itens não implementados desabilitados com “Em breve” | OK |
| Configurações funciona, com Estado → Cidade dependente e UX adequada | OK |
| Testes passam (core + cadastros) | OK |
| Login e dashboard funcionando | OK |

---

## 7. Observações

- **Apps e models:** Nenhum model foi apagado; apps `eventos` e `documentos` continuam em `INSTALLED_APPS` (e o dashboard ainda usa `Evento.objects.count()` se o app eventos estiver instalado). Apenas as rotas públicas desses módulos foram removidas.
- **Testes:** Foram removidos/ajustados testes que dependiam de rotas placeholder ou de viajantes/veículos. Os testes atuais cobrem: auth, dashboard, em-breve, configurações (login, GET 200, POST atualiza singleton), API cidades por estado, importação de base geográfica e sidebar sem estados/cidades no menu cadastros.
- **Próximos passos:** Reativar módulos (Eventos, Viajantes, etc.) na sidebar e em `config/urls.py` quando forem implementados, e adicionar de volta os children/submenus em `core/navigation.py` conforme necessário.
