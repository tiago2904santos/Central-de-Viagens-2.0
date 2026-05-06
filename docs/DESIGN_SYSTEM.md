# Design System

## Regras globais

- CSS centralizado em `static/css/`.
- JS centralizado em `static/js/`.
- Proibido CSS e JS soltos por pagina.
- Nao criar estilo especifico por CRUD; corrigir no component global reutilizavel.
- Proibido `style=""` em templates.
- Proibido JS inline em templates.
- Proibido `href="#"` para acao visual.
- Inicializacao de tema deve ocorrer por `static/js/core/theme-init.js` (sem `<script>` inline no `base.html`).
- A **tela de login** usa layout proprio (sem sidebar): classes em `static/css/auth.css` (prefixo `auth-`), importado tambem em `style.css`; ver `docs/AUTENTICACAO.md`.

## Padrao visual premium

- Superficies em camadas claras, com bordas suaves e sombra controlada.
- Cabecalho de pagina com gradiente azul profundo, luz suave e hierarquia forte.
- Inputs, cards e botoes com altura/radius consistentes para manter ritmo visual.
- Estados de sucesso, erro, aviso e info com contraste elegante e sem agressividade.
- Densidade otimizada para CRUD: menos espaco morto e leitura mais rapida.
- Identidade oficial: azul institucional solido com destaque amarelo/dourado.
- Evitar verde/ciano como destaque padrao em labels, chips e elementos de identidade.
- Evitar gradientes acinzentados pesados no header e no fundo global.
- Page header deve manter margem, respiro e contraste forte de titulo/descricao.

## Referência estética do legacy

- O projeto em `legacy/` foi usado como referencia visual e conceitual para sidebar, gradientes, densidade de cards, botoes em pilula e acabamento de toolbar/formularios.
- Foram aproveitadas ideias de identidade: menu lateral escuro com estados ativos mais evidentes, cabecalho com gradiente institucional, cards com acento lateral e superficies em camadas.
- Foram descartados trechos especificos e volumosos de CSS legado, estilos acoplados por pagina e estruturas antigas de template nao componentizadas.
- A reinterpretacao foi aplicada somente no design system novo (`templates/components/` + `static/css/`) com tokens globais.
- Nao existe importacao, dependencia de runtime, ou reaproveitamento tecnico direto de arquivos de `legacy/`.

## Mascaras reutilizaveis

As mascaras do sistema ficam em `static/js/components/masks.js` e devem ser habilitadas por `data-mask` nos campos.

Mascaras padrao:

- CPF: `000.000.000-00`
- RG: `00.000.000-0`
- Telefone: `(00) 0000-0000` ou `(00) 00000-0000`
- Placa: `AAA-1234` ou `AAA1A23`

A normalizacao final ocorre no backend (forms/models).

## Card-toggle (checkbox)

Booleanos visiveis em formularios devem usar o padrao **card-toggle** (`app-card-toggle` em `static/css/forms.css`, componente `card_toggle.html`), inspirado no botao **Data unica** do Plano de Trabalho do legacy.

Regras:

- Checkbox cru do navegador nao deve aparecer na interface final.
- O input real continua no DOM, oculto com tecnica acessivel de visually-hidden.
- O card mostra icone, titulo forte, descricao pequena e badge de estado `LIGADA` / `DESLIGADA`.
- Desligado usa fundo e borda vermelhos suaves, com badge vermelho.
- Ligado usa azul institucional com acento amarelo/dourado, borda destacada e badge premium.
- BooleanFields futuros renderizados manualmente devem usar `templates/components/forms/card_toggle.html`.
- JS de sincronismo em `static/js/components/card-toggle.js` (sem JS inline).

## Cadastros como referencia

As telas de `Unidade`, `Cidade`, `Cargo`, `Combustivel`, `Servidor` e `Viatura` sao a referencia visual e estrutural para os proximos modulos.

## Tipos de listagem

- **Lista simples** (`components/lists/list_page_simple.html`, `simple_list.html`): para cadastros enxutos com poucos campos — `Cargo`, `Combustivel`, `Unidade`, `Cidade`. Visual compacto, estilo tabela premium sem `<table>`, com linhas densas e acoes a direita.
- **Cards ricos** (`list_page.html` + `document_card`): para entidades com mais contexto — `Servidor`, `Viatura` e, no futuro, documentos (Oficios, Termos, etc.).

## Regras para evolucao visual

- Ajustes de header em `templates/components/layout/page_header.html` e `static/css/layout.css`.
- Ajustes de sidebar em `templates/components/layout/sidebar.html`, `static/css/sidebar.css` e `static/js/components/sidebar.js`.
- Ajustes de toolbar de lista em `templates/components/lists/list_toolbar.html` e `static/css/lists.css`.
- Ajustes de formularios em `templates/components/forms/*.html` e `static/css/forms.css`.
- Ajustes de cards em `templates/components/cards/*.html` e `static/css/cards.css`.
- Ajustes de feedback em `templates/components/feedback/*.html` e `static/css/utilities.css`.
- Nunca copiar CSS bruto do legado em bloco; extrair o conceito e reconstruir no sistema atual.

## CSS de dominio (`domain.css`)

- Arquivo: `static/css/domain.css`.
- Uso: blocos compartilhados de **roteiros, trechos, destinos, retorno, calculadora e resumo de rota** — classes semanticas como `.domain-block`, `.domain-block__title`, `.route-summary`, `.route-card`.
- Regra: estilos que servem a **qualquer modulo** com o mesmo tipo de bloco ficam aqui; o que for **exclusivo do wizard avulso** (densidade, hero, grids do `roteiro-editor`) permanece em `static/css/roteiros.css`.
- Paginas que incluem `templates/components/domain/*` devem importar `domain.css` no `extra_css` (alem de `style.css` via `base.html`).
- Proibido `style=""` nos templates; proibido variar o mesmo tipo de bloco com classes duplicadas em outro arquivo sem motivo.

## Layout do shell

Tokens em `static/css/tokens.css`:

- `--sidebar-width: 15%` — largura da coluna da sidebar em relacao ao viewport.
- `--page-max-width: 100%` — conteudo principal sem teto artificial de largura.

O `grid` em `static/css/layout.css` usa `var(--sidebar-width)` + `minmax(0, 1fr)` para a area principal ocupar o restante (~85%) sem estourar overflow.

## Sidebar hierarquica

A sidebar e a unica navegacao lateral. O menu **Cadastros** e o unico bloco com botao de expandir/recolher; dentro dele, os itens sao uma lista plana com **indentacao visual** (e opcional indicador) para `Cargos` sob `Servidores` e `Combustiveis` sob `Viaturas`, **sem** sub-submenus com segundo toggle.

A hierarquia e declarada em `core/navigation.py` (filhos de Cadastros com `sidebar_indent`), renderizada em `templates/components/layout/sidebar.html`, estilizada em `static/css/sidebar.css` e o grupo Cadastros e aberto via `static/js/components/sidebar.js` (incluindo `localStorage`).

Ordem sob Cadastros: Servidores, Cargos (subordinado visual), Viaturas, Combustiveis (subordinado visual), Unidades, Cidades. `Motoristas` nao aparece.

### Comportamento do grupo expansivel (Cadastros)

- O usuario abre/fecha o grupo pelo botao **Cadastros** (toggle).
- Ao clicar em qualquer **link principal** fora do grupo (Dashboard, Roteiros, modulos, marca no topo), os grupos expansiveis **fecham** e o estado e removido do `localStorage`, para nao reabrir em rotas erradas.
- Se a URL atual for sob `/cadastros/` (ou `/cadastros`), o grupo **Cadastros** carrega **aberto**; fora desse prefixo, carrega **fechado** e o `localStorage` nao mantem o submenu aberto.
