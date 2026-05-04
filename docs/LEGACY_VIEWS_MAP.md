# Mapa de views funcionais do legacy vs migração para o projeto novo

Guia para migração funcional **sem inventar comportamento**: toda regra descrita aqui existe no código legacy em `legacy/central de viagens 2.0/`. O projeto novo **não importa** legacy em runtime.

---

## Arquivos de views analisados (legacy)

| Arquivo | Observação |
|---------|------------|
| `eventos/views.py` | Monólito principal: eventos, fluxo guiado, ofício (wizard + APIs), roteiros (evento + avulso), trechos/km, tipos de demanda, catálogos PT/OS (atividades, coordenadores, solicitantes, horários), modelos motivo/justificativa, termos guiados (variantes legadas). |
| `eventos/views_global.py` | Listagens globais e formulários “hub documentos”: ofícios, roteiros, PT, OS, justificativas, termos, simulação diárias, autosave PT, APIs auxiliares; **dois `def termos_global`** no arquivo — o segundo sobrescreve o primeiro (risco de manutenção). |
| `eventos/views_assinatura.py` | Assinatura pública de ofício (token, PDF, validação). |
| `cadastros/views/__init__.py` | Agrega submódulos (não contém views próprias). |
| `cadastros/views/cargos.py` | CRUD cargos + definir padrão. |
| `cadastros/views/viajantes.py` | CRUD viajantes + atalhos rascunho. |
| `cadastros/views/unidades.py` | CRUD unidades de lotação. |
| `cadastros/views/veiculos.py` | CRUD veículos + combustíveis + rascunho. |
| `cadastros/views/configuracoes.py` | Singleton config + upsert `AssinaturaConfiguracao`. |
| `cadastros/views/hubs.py` | Hub cadastros. |
| `cadastros/views/api.py` | `api_cidades_por_estado`, `api_consulta_cep`. |
| **Não existem** `views_oficio.py` nem `views_documentos.py` **dentro de eventos** — ofício está em `eventos/views.py`; documentos genéricos estão no app `documentos`. |
| `documentos/views.py` | Gestão de assinaturas genéricas (`AssinaturaDocumento`), validação por token/upload, export CSV. |
| `prestacao_contas/views.py` | Wizard prestação, RT, DB, comprovantes, PDF final (arquivo grande). |
| `diario_bordo/views.py` | Lista, novo (genérico/ofício/prestação), wizard steps, PDF/XLSX, exclusão. |
| `integracoes/views.py` | OAuth Google Drive (connect/callback/disconnect/root folder). |
| `core/views.py` (via `core/urls.py`) | Login, logout, redirect dashboard → hub documentos. |

**URLs raiz:** `config/urls.py` monta `cadastros/`, `eventos/`, `assinaturas/` → app **`documentos`** (nome URL `documentos`), `integracoes/`, `prestacao-contas/`, `diarios-bordo/`, `core` (`''`).

---

## Montagem por módulo novo (visão geral)

| Módulo novo | Principais fontes legacy |
|-------------|-------------------------|
| `cadastros` | `cadastros/views/*` — espelha CRUD e APIs; **Estado/Cidade** não têm CRUD público no novo (base interna). |
| `roteiros` | `eventos/views.py` (`roteiro_avulso_*`, `guiado_etapa_2_*`, `trecho_*`, `estimar_*`), `views_global.roteiro_global_lista`. Model legacy: `RoteiroEvento`. |
| `eventos` | `eventos/views.py` (lista, detalhe, guiado etapas, tipos demanda, export drive). |
| `oficios` | `eventos/views.py` (`oficio_*`, steps, justificativa, documentos download), `views_assinatura.py`, listagem `oficio_global_lista`. |
| `justificativas` | `views_global` (lista global, nova, detalhe, editar, excluir) + `modelos_justificativa_*` em `views.py` + `oficio_justificativa`. |
| `termos` | `views_global` (`termo_autorizacao_*`, `termos_global`) + guiado etapa 5 downloads em `views.py`. |
| `planos_trabalho` | `views_global` (lista, novo, editar, detalhe, excluir, download, autosave, API diárias/coordenadores) + CRUD catálogos em `views.py`. |
| `ordens_servico` | `views_global` (lista, novo, detalhe, editar, excluir, download). |
| `prestacoes_contas` | `prestacao_contas/views.py`. |
| `diario_bordo` | `diario_bordo/views.py`. |
| `assinaturas` / `documentos` | `documentos/views.py` + fluxo ofício em `views_assinatura.py`. |
| `integracoes` | `integracoes/views.py`. |
| `core` | Login e dashboard. |

---

## PARTE 3 — Cadastros (legacy → novo)

### Convenção de nomes

| Legacy | Novo (quando existir) |
|--------|------------------------|
| Viajante | Servidor |
| Veiculo | Viatura |
| CombustivelVeiculo | Combustível |
| UnidadeLotacao | Unidade |

### Hub e APIs

| View legacy | Arquivo | URL (`/cadastros/...`) | Template | Model / Forms | Notas |
|-------------|---------|-------------------------|----------|---------------|--------|
| `cadastros_hub` | `views/hubs.py` | `''` → `hub` | `cadastros/hub.html` (inferido) | — | Ponto de entrada módulo. |
| `api_cidades_por_estado` | `views/api.py` | `api/cidades-por-estado/<id>/` | JSON | Estado/Cidade | **ADAPTAR**: novo pode usar selectors internos sem expor IGUAL se produto fechar API pública. |
| `api_consulta_cep` | `views/api.py` | `api/cep/<cep>/` | JSON | Configura endereço | Usado em configurações. |

### Cargos

| View | URL name | Template | GET | POST | Redirect / messages |
|------|-----------|----------|-----|------|---------------------|
| `cargo_lista` | `cargo-lista` | `cadastros/cargos/lista.html` | `q`, ordenação | — | — |
| `cargo_cadastrar` | `cargo-cadastrar` | `cadastros/cargos/form.html` | Form vazio | `CargoForm` válido | success → lista |
| `cargo_editar` | `cargo-editar` | idem | instância | save | success → lista |
| `cargo_excluir` | `cargo-excluir` | `excluir_confirm.html` | confirmação | POST delete | success → lista |
| `cargo_definir_padrao` | `cargo-definir-padrao` | redirect | POST | — | **REVER** no novo (sem `is_padrao` hoje). |

**Destino:** `cadastros/views.py` + templates componentizados — **JÁ MIGRADO** parcialmente (sem “definir padrão”).

### Viajantes → Servidor

| View | URL | Templates | Regras principais |
|------|-----|-----------|-------------------|
| `viajante_lista` | `viajante-lista` | `viajantes/lista.html` | Busca, paginação, sessão `RETURN_URL_KEY` para voltar após cargo. |
| `viajante_cadastrar` / `editar` | — | `viajantes/form.html` | `ViajanteForm`, status rascunho/finalizado, `esta_completo()`. |
| `viajante_excluir` | — | `excluir_confirm.html` | POST físico. |
| `viajante_salvar_rascunho_ir_cargos` | — | redirect | Salva rascunho e vai para cargos. |
| `viajante_salvar_rascunho_ir_unidades` | — | idem | Para unidades. |

**Copiar:** validações de unicidade, fluxo opcional rascunho. **Adaptar:** telefone e sem_rg se política do novo cadastro simplificado.

### Unidades de lotação

| View | URL prefix `unidades-lotacao/` | Templates `cadastros/unidades/` | CRUD padrão `UnidadeLotacaoForm`. |

**Destino:** `cadastros.Unidade` — **ADAPTAR** (novo tem sigla).

### Veículos e combustíveis

| View | URL | Templates |
|------|-----|-----------|
| `veiculo_lista` etc. | `veiculos/` | `veiculos/lista.html`, `form.html`, `excluir_confirm.html` |
| `combustivel_*` | `veiculos/combustiveis/` | `combustiveis_lista/form/excluir` |
| `veiculo_salvar_rascunho_ir_combustiveis` | — | redirect |

**Destino:** `Viatura` / `Combustivel` — **ADAPTAR**.

### Configurações do sistema + assinaturas de configuração

| View | URL | Template | POST |
|------|-----|----------|------|
| `configuracoes_editar` | `configuracoes/` | `cadastros/configuracao_form.html` | `ConfiguracaoSistemaForm`; resolve `cidade_sede_padrao` por UF + cidade texto; **upsert** `AssinaturaConfiguracao` por tipo (ofício, justificativa, PT, OS) ordem 1. |

**Destino:** config futura em `core` ou app dedicado; assinaturas política → `assinaturas` — **ADAPTAR** / **REVER**.

---

## PARTE 4 — Roteiros (`RoteiroEvento`)

### Listagem global

| View | Arquivo | URL legacy | Template |
|------|---------|------------|----------|
| `roteiro_global_lista` | `views_global.py` | `/eventos/roteiros/` `roteiros-global` | `eventos/global/roteiros_lista.html` |

**Queryset:** `RoteiroEvento` com `select_related` evento/origem, `prefetch` destinos e ofícios. **Filtros:** `q`, `status`, `evento_id`, `tipo` (AVULSO/EVENTO), datas, ordenação. **Contexto:** URLs novo roteiro guiado (se evento selecionado), novo avulso, lista eventos.

**Projeto novo:** roteiro **avulso reutilizável** sem obrigar evento — **ADAPTAR**: filtros e cartões podem separar “Biblioteca” vs “Por evento”.

### Roteiro no fluxo guiado (Etapa 2)

| View | URL | Template |
|------|-----|----------|
| `guiado_etapa_2_lista` | `<evento_id>/guiado/etapa-2/` | Lista roteiros do evento + wizard steps V2 |
| `guiado_etapa_2_cadastrar` | `.../cadastrar/` | `eventos/guiado/roteiro_form.html` |
| `guiado_etapa_2_editar` | `.../<pk>/editar/` | idem |
| `guiado_etapa_2_excluir` | `.../<pk>/excluir/` | POST + redirect |

**Lógica:** `_build_roteiro_form_context`, `_salvar_roteiro_com_destinos_e_trechos`, mesma base que Step3 ofício — destinos múltiplos + trechos com km/tempo/diárias.

**Classificação:**

| Regra | Classificação |
|-------|----------------|
| Vínculo obrigatório a evento neste fluxo | **ADAPTAR** (no novo, evento opcional fora do guiado) |
| Destinos ordem + trechos IDA/RETORNO | **copiar/adaptar** para `TrechoRoteiro` / modelo eventual |
| Cálculo diárias em POST (`_build_roteiro_diarias_from_request`) | **etapa futura** (serviço compartilhado) |
| Prefill sede via `ConfiguracaoSistema` | **copiar** conceito (singleton novo) |

### Roteiro avulso (URLs dedicadas)

| View | URL | Template |
|------|-----|----------|
| `roteiro_avulso_cadastrar` | `/eventos/roteiros/avulso/novo/` | `eventos/global/roteiro_avulso_form.html` |
| `roteiro_avulso_editar` | `/roteiros/avulso/<pk>/editar/` | idem |
| `roteiro_avulso_excluir` | `.../excluir/` | confirmação |
| `roteiro_avulso_calcular_diarias` | POST API | JSON diárias |

Reutiliza `_validate_step3_state` com `SimpleNamespace` fake ofício — espelha **oficio_step3**.

### APIs trecho / estimativa

| View | URL | Método |
|------|-----|--------|
| `trecho_calcular_km` | `trechos/<pk>/calcular-km/` | POST |
| `estimar_km_por_cidades` | `trechos/estimar/` | POST |

**Destino:** serviços de rota no novo — **etapa futura** (não mudar modelo novo agora).

---

## PARTE 5 — Ofícios

### Listagem global

`oficio_global_lista` → `_render_oficio_list` → `eventos/global/oficios_lista.html`. **Prefetch massivo:** trechos, viajantes, eventos, PT, OS, assinaturas, termos. **Filtros avançados** (status viagem, justificativa, termo, datas). **Cartões enriquecidos** (`_oficio_list_card`).

**Destino:** `oficios` + presenters — **ADAPTAR** (simplificar query inicialmente).

### Wizard

| View | URL name | Template |
|------|----------|----------|
| `oficio_novo` | `oficio-novo` | redirect cria rascunho → step1 |
| `oficio_editar` | `oficio-editar` | redirect step1 |
| `oficio_step1` | `oficio-step1` | `eventos/oficio/wizard_step1.html` |
| APIs step1/2 | `oficio-step1-viajantes-api`, motoristas, veículos | JSON |
| `oficio_step2` | `oficio-step2` | `wizard_step2.html` |
| `oficio_step3` | `oficio-step3` | `wizard_step3.html` + autosave JSON |
| `oficio_step3_calcular_diarias` | POST | retorno cálculo |
| `oficio_justificativa` | `oficio-justificativa` | `justificativa.html` |
| `oficio_documentos` | `oficio-documentos` | lista DOCX/PDF + termo |
| `oficio_documento_download` | download | render PDF/DOCX via services |
| `oficio_step4` | `oficio-step4` | `wizard_step4.html` resumo |
| `oficio_excluir` | — | `excluir_confirm.html` |

**Serviços legacy:** `eventos/services/documentos/*`, renderers. **Assinatura:** `views_assinatura` (gestão interna + fluxo público token).

**Essencial a migrar:** numeração, protocolo, vínculo evento N:N, trechos ida, retorno no modelo Ofício, justificativa, geração documental — **COPIAR/ADAPTAR** em `oficios/services.py`.

---

## PARTE 6 — Justificativas (globais + modelo + ofício)

### Listagem / CRUD global (`views_global`)

| View | URL path (`/eventos/documentos/justificativas/`) |
|------|--------------------------------------------------|
| `justificativas_global` | lista |
| `justificativa_nova` | `nova/` |
| `justificativa_detalhe` | `<pk>/` |
| `justificativa_editar` | `<pk>/editar/` |
| `justificativa_excluir` | `<pk>/excluir/` |

Templates sob `eventos/documentos/justificativas_*.html` (padrão lista/form conforme grep similares PT).

### Catálogo modelos (`views.py`)

`modelos_justificativa_lista|cadastrar|editar|excluir|definir_padrao|texto_api` — templates `eventos/modelos_justificativa/`.

### Por ofício

`oficio_justificativa` — edição texto + modelo, integração prazo (`DEFAULT_PRAZO_JUSTIFICATIVA_DIAS`).

**Destino:** `justificativas/` — **ADAPTAR** URLs globais (hoje legacy sob prefixo `documentos/`).

---

## PARTE 7 — Termos (`TermoAutorizacao`, guiado)

### Globais (`views_global`)

| View | Função |
|------|--------|
| `termos_global` | Lista (segunda def no arquivo — sobrescreve a primeira) |
| `termo_autorizacao_novo` | Criação |
| `termo_autorizacao_novo_rapido` | Atalho |
| `termo_autorizacao_novo_automatico_*` | Com/sem viatura |
| `termo_autorizacao_preview` | Preview |
| `termo_autorizacao_oficios_por_evento` | API |
| `termo_autorizacao_detalhe` / `editar` / `excluir` / `download` | CRUD + arquivo |

### Guiado evento (`views.py`)

`guiado_etapa_5_v2`, downloads por viajante / padrão / viatura lote; status `EventoTermoParticipante`.

**Destino:** `termos/` — **COPIAR** máquina de estados e modos de geração.

---

## PARTE 8 — Planos de trabalho

| View | URL (`documentos/planos-trabalho/...`) | Destaque |
|------|----------------------------------------|----------|
| `planos_trabalho_global` | lista | `planos_trabalho_lista.html` |
| `plano_trabalho_novo` | `novo/` | GET cria rascunho e **redirect** editar |
| `plano_trabalho_editar` | `<pk>/editar/` | form + efetivo + diárias |
| `plano_trabalho_detalhe` | `<pk>/` | leitura |
| `plano_trabalho_excluir` | excluir | POST |
| `plano_trabalho_download` | download docx/pdf | geração |
| `plano_trabalho_autosave` | autosave | JSON |
| `plano_trabalho_calcular_diarias_api` | API POST | |
| `plano_trabalho_coordenadores_api` | API GET | |

Catálogos em `views.py`: atividades, coordenadores, solicitantes, horários — URLs `eventos/plano-trabalho-*` e `coordenadores-operacionais/`.

**Destino:** `planos_trabalho/` — **ADAPTAR** (URLs novas sem obrigar prefixo `documentos/`).

---

## PARTE 9 — Ordens de serviço

| View | URL `documentos/ordens-servico/` |
|------|----------------------------------|
| `ordens_servico_global` | lista |
| `ordem_servico_novo` | novo |
| `ordem_servico_editar` | editar |
| `ordem_servico_detalhe` | detalhe |
| `ordem_servico_excluir` | excluir |
| `ordem_servico_download` | download |

**Destino:** `ordens_servico/` — **COPIAR** regras vínculo ofício/evento do form (`_render_ordem_servico_form`).

---

## PARTE 10 — Prestação de contas e diário de bordo

### Prestação (`prestacao_contas/views.py`)

URLs em `prestacao_contas/urls.py`: lista, nova, wizard steps 1–4, resumo, excluir, RT (form, autosave, docx, pdf), DB (autosave, reimportar, xlsx, pdf, assinado), comprovantes, pdf final, textos padrão CRUD.

**Templates:** `prestacao_contas/lista.html`, `nova.html`, `wizard_step*.html`, `wizard_resumo.html`, `textos_padrao_*`, etc.

**Destino:** `prestacoes_contas/` — **ADAPTAR**.

### Diário de bordo (`diario_bordo/views.py`)

Lista, novo (genérico / por ofício / por prestação), wizard steps, PDF/XLSX, excluir.

**Destino:** `diario_bordo/` — **ADAPTAR**.

---

## PARTE 11 — Demais: documentos (assinaturas genéricas), integrações, core

| Área | Views principais |
|------|-------------------|
| `documentos` (URL `/assinaturas/`) | `assinatura_gestao`, `assinatura_verificar*`, export CSV |
| `views_assinatura` | Fluxo ofício público + gestão pedidos |
| `integracoes` | `google_drive_connect`, `callback`, `disconnect`, `root_folder_update` |
| `core` | `login_view`, `logout_view`; dashboard → `eventos:documentos-hub` |

---

## Matriz resumo (entradas expostas em `urls.py`)

| View legacy | Arquivo legacy | URL legacy (path relativo ao prefixo) | App novo | View nova sugerida | Status | Observação |
|-------------|----------------|----------------------------------------|----------|---------------------|--------|------------|
| `cadastros_hub` | cadastros/views/hubs.py | `/cadastros/` | cadastros | `cadastros_index` ou hub | JÁ MIGRADO / ADAPTAR | Novo usa índice diferente |
| `cargo_*` (5) | views/cargos.py | `/cadastros/cargos/...` | cadastros | CRUD cargo | JÁ MIGRADO | Sem “padrão” no novo |
| `viajante_*` | views/viajantes.py | `/cadastros/viajantes/...` | cadastros | CRUD servidor | ADAPTAR | Nomes e campos |
| `unidade_lotacao_*` | views/unidades.py | `/cadastros/unidades-lotacao/...` | cadastros | CRUD unidade | ADAPTAR | Sigla no novo |
| `veiculo_*` / `combustivel_*` | views/veiculos.py | `/cadastros/veiculos/...` | cadastros | CRUD viatura/combustível | JÁ MIGRADO / ADAPTAR | |
| `configuracoes_editar` | views/configuracoes.py | `/cadastros/configuracoes/` | core ou config | `configuracao_editar` | REVER | Assinaturas inline |
| `api_cidades_por_estado` | views/api.py | `/cadastros/api/...` | cadastros | API ou selector-only | ADAPTAR | |
| `evento_lista` | eventos/views.py | `/eventos/` | eventos | `evento_list` | ADAPTAR | Placeholder novo |
| `evento_detalhe` | views.py | `/eventos/<pk>/` | eventos | `evento_detail` | COPIAR | |
| `guiado_*` (várias) | views.py | `/eventos/.../guiado/...` | eventos (+ outros) | wizard por etapa | ADAPTAR | Domínio cruza apps |
| `roteiro_global_lista` | views_global.py | `/eventos/roteiros/` | roteiros | `roteiro_list_global` | ADAPTAR | Novo modelo mais simples |
| `roteiro_avulso_*` | views.py | `/eventos/roteiros/avulso/...` | roteiros | `roteiro_*` avulso | ADAPTAR | Usa `RoteiroEvento` |
| `guiado_etapa_2_*` | views.py | `/eventos/<id>/guiado/etapa-2/...` | eventos + roteiros | etapa roteiro evento | ADAPTAR | |
| `trecho_calcular_km` / `estimar_km_por_cidades` | views.py | `/eventos/trechos/...` | roteiros (services) | API estimativa | REVER | Futuro |
| `oficio_global_lista` | views_global.py | `/eventos/oficios/` | oficios | `oficio_list` | ADAPTAR | Lista rica |
| `oficio_novo` … `oficio_step4` | views.py | `/eventos/oficio/...` | oficios | wizard steps | COPIAR / ADAPTAR | Núcleo grande |
| `oficio_justificativa` | views.py | `.../justificativa/` | oficios + justificativas | `oficio_justificativa` | ADAPTAR | |
| `oficio_documento_download` | views.py | `.../documentos/.../download` | oficios | download service | COPIAR | |
| `oficio_assinatura_*` | views_assinatura.py | `/eventos/oficio/<pk>/assinatura/...` + públicas `/assinatura/oficio/<token>/...` | assinaturas / oficios | fluxo assinatura | ADAPTAR | |
| `plano_trabalho_*` global | views_global.py | `/eventos/documentos/planos-trabalho/...` | planos_trabalho | CRUD + autosave | COPIAR / ADAPTAR | |
| `ordem_servico_*` global | views_global.py | `/eventos/documentos/ordens-servico/...` | ordens_servico | CRUD | COPIAR / ADAPTAR | |
| `justificativas_global` + CRUD | views_global.py | `/eventos/documentos/justificativas/...` | justificativas | lista CRUD | COPIAR / ADAPTAR | |
| `modelos_justificativa_*` | views.py | `/eventos/modelos-justificativa/...` | justificativas | catálogo modelo | ADAPTAR | |
| `termo_autorizacao_*` | views_global.py | `/eventos/documentos/termos/...` | termos | CRUD termo | COPIAR / ADAPTAR | Duplicata `termos_global` |
| `guiado_etapa_5_*` | views.py | guiado termos | termos + eventos | downloads guiados | ADAPTAR | |
| `documentos_hub` | views_global.py | `/eventos/documentos/` | core ou vários | `documentos_hub` | ADAPTAR | Dashboard docs |
| `simulacao_diarias_global` | views_global.py | `/eventos/simulacao-diarias/` | roteiros ou tool | simulação | REVER | |
| `assinatura_gestao` | documentos/views.py | `/assinaturas/` | assinaturas | gestão genérica | ADAPTAR | |
| `prestacao_*` | prestacao_contas/views.py | `/prestacao-contas/...` | prestacoes_contas | wizard | ADAPTAR | |
| `diario_*` | diario_bordo/views.py | `/diarios-bordo/...` | diario_bordo | wizard | ADAPTAR | |
| `google_drive_*` | integracoes/views.py | `/integracoes/google-drive/...` | integracoes | oauth views | ADAPTAR | |

*(Matriz condensada: CRUDs repetitivos de catálogo PT em `views.py` seguem o mesmo padrão lista/form/excluir — **ADAPTAR** para `planos_trabalho` como cadastros auxiliares.)*

---

## Regras para migração funcional

1. **Nenhuma view nova deve ser inventada** sem consultar o legacy ou este mapa.
2. Se o legacy já resolve a regra funcional, **copiar ou adaptar** (services primeiro).
3. Views novas seguem o padrão do projeto novo: **view orquestra; selector consulta; service executa regra; presenter formata UI**.
4. **Não importar** pacotes sob `legacy/` em runtime.
5. **Não copiar HTML antigo** como estrutura final; usar **components** do novo design system.
6. Templates novos apenas **referência visual** do legacy.
7. **Testes pesados** ao final do bloco funcional; durante migração, **`python manage.py check`** e validação manual pontual.
8. APIs internas (`autosave`, calcular diárias) devem virar **services** testáveis isolados ao migrar.

---

## Próximo passo recomendado

1. Priorizar leitura dirigida de **`eventos/services/`** (documentos, diárias, ofício) em paralelo a este mapa — a view legacy delega muito para esses módulos.
2. Definir **URLs estáveis** no projeto novo (`/oficios/`, `/planos-trabalho/`, …) sem prefixo `documentos/` onde o produto não exigir equivalência literal.
3. Para **roteiros**, decidir explicitamente como mapear **`RoteiroEvento`** (evento + destinos múltiplos + diárias) para **`Roteiro` + `TrechoRoteiro`** do novo antes de codificar telas finais.

---

*Documento gerado na auditoria Fase 2. Validar com `python manage.py check` após uso.*
