# Design System

## Objetivo

O design system define a base visual e estrutural do Central de Viagens 3. Ele deve manter todas as paginas com a mesma linguagem institucional, sobria e limpa, sem estilos avulsos por modulo.

## Identidade visual

A direcao visual e `Azul Operacional Premium`: institucional, moderna e elegante. A base usa azul profundo, fundo claro frio, superficies brancas com profundidade, bordas suaves, sombras controladas e dourado discreto apenas como detalhe de destaque.

O sistema nao deve parecer uma planilha publica, site governamental antigo ou pagina turistica. A sensacao esperada e de produto administrativo bem acabado.

Principios:

- fundo claro com luz suave;
- sidebar escura com profundidade;
- cards brancos com sombra elegante;
- headers com gradiente institucional;
- hover em cards, botoes e navegacao;
- status com cores controladas;
- dourado usado com parcimonia;
- tokens globais, sem cores aleatorias por modulo.

## Status e chips

Status visuais devem usar `.status-chip` com variantes globais:

- `.status-chip--draft`: rascunho ou pendente.
- `.status-chip--active`: ativo ou em andamento.
- `.status-chip--completed`: concluido.
- `.status-chip--danger`: erro, bloqueio ou acao critica.
- `.status-chip--muted`: inativo ou informacao neutra.

Nao criar cores de status por modulo.

## CSS centralizado

Todo CSS deve ficar em `static/css/`. O arquivo `static/css/style.css` e apenas o agregador dos modulos:

- `tokens.css`: cores, espacamentos, raios, sombras, fontes, z-index e larguras globais.
- `base.css`: reset leve, tipografia e elementos HTML basicos.
- `layout.css`: app shell, area de conteudo e cabecalhos de pagina.
- `sidebar.css`: navegacao lateral.
- `buttons.css`: botoes e grupos.
- `forms.css`: formularios, secoes, campos e acoes.
- `lists.css`: paginas de lista, toolbar, filtros, grid e estado vazio.
- `cards.css`: cards genericos, de modulo, documentais e de resumo.
- `steppers.css`: fluxos em etapas.
- `documents.css`: estruturas documentais.
- `utilities.css`: classes utilitarias pequenas.

Nao colocar CSS solto em templates. Excecoes precisam ser justificadas e depois movidas para o modulo correto.

## JS centralizado

JavaScript global deve ficar em `static/js/core/`. Comportamentos reutilizaveis devem ir para `static/js/components/`. Scripts especificos de pagina devem ficar em `static/js/pages/` e so devem ser carregados via bloco `extra_js` quando houver justificativa.

Nao colocar JavaScript solto em templates.

## Components

Templates compartilhados ficam em `templates/components/`:

- `layout`: app shell, sidebar e cabecalho de pagina (`page_header.html`).
- `lists`: pagina de lista, toolbar, filtros, grid e estado vazio.
- `forms`: pagina de formulario, secao, campo e acoes.
- `cards`: card generico, card de modulo, card documental e card de resumo.
- `steppers`: stepper e acoes de stepper.
- `buttons`: botao de acao e grupo de botoes.
- `modals`: estrutura base de modal.
- `feedback`: alertas e estado vazio.

Todo modulo novo deve compor suas paginas usando esses includes antes de criar novos templates estruturais.

## Cabecalho de pagina

O cabecalho oficial de cada tela e o componente `templates/components/layout/page_header.html` (bloco `div.page-header`), com eyebrow, titulo principal, descricao opcional e acoes opcionais. Cada pagina deve ter **um unico** cabecalho principal na area de conteudo para evitar titulos duplicados.

O arquivo `templates/components/layout/topbar.html` existe no projeto como peca reservada para uso futuro e **nao** e renderizado no layout atual (`base.html`). Nao usar `topbar` como cabecalho de pagina.

## Botoes

Classes padrao:

- `.btn`: base obrigatoria.
- `.btn-primary`: acao principal.
- `.btn-secondary`: acao secundaria forte.
- `.btn-muted`: acao neutra.
- `.btn-danger`: excluir ou acao destrutiva.
- `.btn-sm`: botao compacto.
- `.btn-icon`: botao quadrado para icone.
- `.btn-group`: agrupamento de acoes.

Use `templates/components/buttons/action_button.html` para botoes e links de acao.

## Listas

Use `templates/components/lists/list_page.html` para paginas de listagem. Ele compoe:

- cabecalho de pagina;
- toolbar com busca;
- area de filtros;
- botao principal opcional;
- grid de resultados;
- estado vazio;
- area reservada para paginacao futura.

Esse padrao deve atender Oficios, Termos, Justificativas, Planos, Ordens, Roteiros, Eventos, Prestacoes, Diario de Bordo e Cadastros.

Listagens reais devem receber dados de cards ja formatados por presenters. Templates nao devem montar metadados ou decidir status visual.

## Cards

Use:

- `card.html` para conteudo generico.
- `module_card.html` para acesso a modulos.
- `document_card.html` para documentos com titulo, status, metadados e acoes futuras de Abrir, PDF, DOCX e Excluir.
- `summary_card.html` para indicadores e resumos.

Nao criar cards com CSS proprio dentro de paginas.

## Formularios

Use:

- `form_page.html` para a pagina.
- `form_section.html` para blocos logicos.
- `form_field.html` para label, campo, ajuda e erros.
- `form_actions.html` para acoes finais.

Formularios devem usar `.form-grid`, labels consistentes e mensagens de erro padronizadas.

Views devem enviar `form` validado por `ModelForm`; templates renderizam campos por `forms/form_field.html` e acoes por `forms/form_actions.html`. Nao criar markup de formulario fora do padrao salvo necessidade reutilizavel.

## Steppers

Use `templates/components/steppers/stepper.html` para fluxos em etapas. O padrao inicial usa:

1. Dados de viajantes
2. Transporte
3. Roteiros e diarias
4. Resumo

O componente e generico e pode servir para Oficios, Eventos, Prestacoes de Contas, Planos de Trabalho e fluxos futuros.

## Regras

- Toda pagina deve estender `templates/base.html`.
- Toda pagina nova deve usar components.
- CSS e JS devem ser centralizados.
- Estetica e tokens sao globais, nao por app.
- Componentes novos so devem ser criados quando houver padrao reutilizavel.
