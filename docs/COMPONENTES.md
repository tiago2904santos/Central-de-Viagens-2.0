# Componentes

## Uso no cadastros

O app `cadastros` usa listagens globais (`list_page` ou `list_page_simple`), `document_card` onde aplicavel, `form_field` e `form_actions` para os CRUDs de:

- `Unidade`
- `Cidade`
- `Cargo`
- `Combustivel`
- `Servidor`
- `Viatura`

`Motorista` nao possui templates ativos.

## Page header

- Component: `templates/components/layout/page_header.html`.
- Objetivo: titulo forte, descricao clara e acao principal alinhada a direita.
- CSS principal: `static/css/layout.css`.
- Eyebrow e detalhes visuais usam destaque amarelo/dourado do design system.

## Listagem simples vs cards

- **Lista simples**: `list_page_simple.html`, `simple_list.html`, `simple_list_row.html`, estilos em `lists.css`. Para cadastros enxutos: Cargo, Combustivel, Unidade, Cidade. Na inclusao da lista, **nao use** `only` no `{% include %}` da pagina para `list_page_simple` (nem na cadeia ate `simple_list_row`) quando houver formularios POST na linha — caso contrario `csrf_token` some do contexto e `{% csrf_token %}` renderiza vazio.
- **Cards**: `list_page.html` + `document_card` para Servidor, Viatura e listagens ricas futuras.

## Sidebar

- Component: `templates/components/layout/sidebar.html`.
- Dados: `core/navigation.py`, preparados por `core/context_processors.py`.
- CSS principal: `static/css/sidebar.css`.
- JS principal: `static/js/components/sidebar.js`.
- Largura da coluna: token `--sidebar-width` (15%); area principal ~85% via grid em `layout.css`; `--page-max-width: 100%` no shell.
- Somente o grupo **Cadastros** usa botao de expandir/recolher; dentro dele, lista plana com indentacao visual para `Cargos` (sob Servidores) e `Combustiveis` (sob Viaturas), sem segundo toggle por nivel.
- Links principais usam `data-sidebar-root-link`; grupo expansivel usa `data-sidebar-item`, `data-sidebar-group`, `data-sidebar-expandable`; filhos do painel usam `data-sidebar-panel-link`.
- Grupo abre ao alternar o toggle; **fecha ao navegar** para outro item principal (nao-Cadastros). Na carga da pagina: aberto se a rota for `/cadastros/`, fechado caso contrario; `localStorage` nao reabre o submenu fora de Cadastros.
- Ordem: Servidores, Cargos, Viaturas, Combustiveis, Unidades, Cidades.
- `Motoristas` nao aparece no menu porque nao e cadastro independente.

## List toolbar

- Component: `templates/components/lists/list_toolbar.html`.
- Estrutura: busca + espaco para filtros + acoes principais.
- CSS principal: `static/css/lists.css`.

## Forms

- Components: `form_page`, `form_section`, `form_field`, `form_actions`.
- Regras: foco azul consistente, labels legiveis, erros visiveis e grid reutilizavel.
- CSS principal: `static/css/forms.css`.

## Buttons

- Component base: `templates/components/buttons/action_button.html`.
- Variantes: `primary`, `secondary`, `muted`, `danger` e tamanho `sm`.
- CSS principal: `static/css/buttons.css`.

## Form fields

Campos de selecao devem usar `form-select`.
Campos textuais usam `form-control`.
Mascaras globais sao ativadas por atributo:

- `data-mask="cpf"`
- `data-mask="rg"`
- `data-mask="telefone"`
- `data-mask="placa"`

### Toggle (`toggle_field.html`)

Checkboxes booleanos devem preferir `templates/components/forms/toggle_field.html` com widget `CheckboxInput` usando classes `app-toggle__input` + `sr-only`. Inspiracao conceitual: botao **Data unica** do Plano de Trabalho no legacy.

### Campo com acao (`input_with_action.html`)

Para select ao lado de link **Gerenciar** (ex.: Cargo, Unidade, Combustivel em cadastros), usar `templates/components/forms/input_with_action.html` com classes `form-field-with-action` em `static/css/forms.css`.

## Cards

- Components: `card`, `module_card`, `document_card`, `summary_card`.
- Regras: sombra elegante, titulo destacado, metadados compactos e acoes alinhadas.
- CSS principal: `static/css/cards.css`.
- Presenters enviam `title`, `subtitle`, `meta`, `actions`.
- Templates nao montam metadados de negocio e nao formatam regra de dominio.

## Roteiros

A listagem de `roteiros` usa `components/lists/list_page.html`, `components/lists/list_toolbar.html`, `components/lists/list_grid.html`, `components/cards/document_card.html` e empty state global.

O presenter `apresentar_roteiro_card` entrega `title`, `subtitle`, `meta` e `actions` sem HTML. A view apenas le `q`, chama selector, aplica presenter e renderiza o template.

## Alerts e feedback

- Component: `templates/components/feedback/alerts.html`.
- Tags esperadas do Django: `success`, `error`/`danger`, `warning`, `info`.
- CSS principal: `static/css/utilities.css`.

## Empty state

- Components: `templates/components/feedback/empty_state.html` e `templates/components/lists/list_empty.html`.
- Deve ter titulo claro, texto curto e CTA principal quando houver acao.

## Confirmacao de exclusao

- Component global: `templates/components/feedback/confirm_delete_block.html`.
- Mantem contexto de risco com acao `danger` e cancelamento secundario.

## Regra de manutencao

- Nao criar CSS/JS por pagina.
- Qualquer ajuste visual de CRUD deve ser feito no component global correspondente.
- `legacy/` pode inspirar a estetica, mas nunca deve ser dependencia tecnica do projeto novo.
- Nao copiar templates inteiros do legado: recriar a ideia no component atual e manter coesao arquitetural.
