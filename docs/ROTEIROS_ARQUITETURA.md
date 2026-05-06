# Roteiros Arquitetura

## Revisao critica pos-refatoracao

### 1. O que ficou bom

- Separacao clara: `selectors.py` para consultas, `services/roteiro_editor.py` para fluxo de persistencia e validacao de POST, `presenters.py` para dados de tela, views apenas orquestrando.
- Componentes de dominio em `templates/components/domain/` centralizam includes do wizard sem duplicar o HTML dos partials em `roteiros/partials/roteiro/`.
- `get_roteiro_by_id` com `select_related` / `prefetch_related` evita N+1 em detalhe e edicao.
- API `api_cidades_por_estado` usa selector com filtro opcional `q`.
- Exclusao com `ProtectedError` tratada no service `excluir_roteiro`.
- Scripts do formulario carregados via `extra_js` na pagina, nao embutidos no meio do partial (exceto `json_script` necessario ao lado dos dados).

### 2. O que ainda ficou acoplado

- `roteiro_logic._build_roteiro_form_context` ainda concentra montagem pesada de contexto (diarias, JSON, URLs de API). O presenter apenas delega; evolucao natural e fatiar essa funcao em partes menores sem mudar contrato do template.
- Partials em `roteiros/partials/roteiro/` continuam com HTML e classes `roteiro-editor__*` especificas do fluxo legacy; os components de dominio sao wrappers finos ate outro modulo precisar dos mesmos blocos.

### 3. O que ainda e especifico demais de Roteiros

- Nomes de campos, `step3`, rotas `roteiros:*` e textos do wizard sao do modulo Roteiros.
- `roteiros.css` permanece grande porque o visual do editor avulso e denso; `domain.css` traz tokens e aliases semanticos para blocos reutilizaveis.

### 4. O que ainda esta duplicado

- `_build_roteiro_diarias_from_request` reparsing interno do POST (ja era assim na logica legacy); nao foi alterado para nao mudar comportamento.

### 5. O que ainda nao e reutilizavel sem trabalho extra

- `trecho_card.html` usa labels e formato de datas do modelo `RoteiroTrecho`; outro modulo precisaria de presenter ou partial alternativo se o modelo diferir.
- `destinos.html` / `trechos.html` apenas incluem partials de Roteiros: contrato reutilizavel documentado, implementacao ainda amarrada aos partials.

### 6. O que foi corrigido nesta etapa

- Conflito `roteiros/services.py` vs pacote `roteiros/services/`: orquestracao movida para `services/roteiro_editor.py` e reexportada em `services/__init__.py`.
- `views.py` integrada aos services e presenters (sem duplicar persistencia nem initial da config).
- `retorno.html` (domain) incluia o partial duas vezes; corrigido.
- Consultas de cidade/estado no setup do form e no mapa de roteiros avulsos passam por `selectors` onde aplicavel.
- `api_cidades_por_estado` aceita `?q=` via selector.
- `trechos_estimar` usa `obter_cidades_origem_destino_estimativa`.
- Detalhe: destinos renderizados a partir de `destinos_detalhe` no presenter (sem loop ORM no template).
- Card de listagem: uma unica avaliacao de `destinos` para preview e contagem.
- Removidos JS vazios `static/js/components/destinos.js`, `trechos.js`, `calculadora-rota.js` (sem referencias).
- Encoding do fallback "Parana (PR)" corrigido em `roteiro_logic`.
- Paginas de roteiro carregam `domain.css` onde usam components de dominio.

## Auditoria antes da refatoracao

- View com regra funcional acoplada ao fluxo de step3 (validacao e persistencia).
- Consulta direta de cidades em endpoint de API fora de selector.
- Template de formulario com composicao misturada entre blocos de dominio e parciais de pagina.
- CSS extenso e especifico de Roteiros sem camada de dominio reutilizavel explicita.
- Componentes de dominio inexistentes em `templates/components/domain/`.

## Contrato de arquitetura

- Roteiro e avulso e reutilizavel; nao depende de Evento nem de Oficio.
- Trecho pertence a um roteiro, com ordem, origem e destino.
- Destinos, trechos, retorno e calculadora devem ser blocos de dominio reutilizaveis.
- Views ficam magras: orquestram form/selectors/services/presenters.
- Sem `href="#"`, sem CSS inline, sem JS inline, sem exibir "Atualizado em".

## Camada de services (roteiro_editor)

| Funcao | Papel |
|--------|--------|
| `obter_initial_roteiro` | Le singleton de configuracao para sede padrao (somente dados iniciais). |
| `preparar_querysets_formulario_roteiro` | Preenche querysets do form (sem template). |
| `carregar_opcoes_rotas_avulsas_salvas` | Opcoes de duplicacao + mapa de estado (delega `roteiro_logic`). |
| `preparar_estado_editor_roteiro_para_get` | Destinos/trechos/step3 para GET. |
| `normalizar_destinos_e_trechos_apos_erro_post` | Reexibe form apos POST invalido. |
| `validar_submissao_editor_roteiro` | Parse step3 + validacao + diarias (sem HTTP). |
| `criar_roteiro` / `atualizar_roteiro` / `excluir_roteiro` | Transacao e persistencia. |

**Nota:** `calcular_diarias` na view continua chamando `roteiro_logic._build_roteiro_diarias_from_request(request)` porque o endpoint exige o objeto request completo do Django; documentado para nao confundir com “view gorda” de regra nova — e o mesmo caminho ja usado antes.

## View `calcular_diarias` e `request`

A view repassa `request` ao `roteiro_logic` porque o parser de diarias espera `request.POST` nativo e o comportamento foi mantido intencionalmente.

## Decisoes de refatoracao

- Extraida orquestracao de fluxo de criacao/edicao para `roteiros/services/roteiro_editor.py`.
- Centralizada consulta de cidades/estados relevantes em `roteiros/selectors.py`.
- Mantida regra funcional existente via reutilizacao de `roteiro_logic`.
- Criada camada de componentes de dominio em `templates/components/domain/`.
