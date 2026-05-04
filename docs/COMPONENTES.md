# Componentes

## Uso no cadastros

O app `cadastros` usa `list_page`, `document_card`, `form_field` e `form_actions` para os CRUDs de:

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

## Sidebar

- Component: `templates/components/layout/sidebar.html`.
- Dados: `core/navigation.py`, preparados por `core/context_processors.py`.
- CSS principal: `static/css/sidebar.css`.
- JS principal: `static/js/components/sidebar.js`.
- Suporta ate tres niveis: modulo, subgrupo e item interno.
- O botao lateral de expansao abre/fecha submenus; o texto do item continua sendo link quando houver URL.
- O estado aberto considera a pagina atual e tambem persiste grupos abertos em `localStorage`.
- A estrutura atual de `Cadastros` e:
  - `Servidores`
    - `Cargos`
  - `Viaturas`
    - `Combustiveis`
  - `Unidades`
  - `Cidades`
- `Motoristas` nao aparece no menu porque nao e cadastro independente.

## List toolbar

- Component: `templates/components/lists/list_toolbar.html`.
- Estrutura: busca + espaco para filtros + acoes principais.
- CSS principal: `static/css/lists.css`.

## Cards

- Components: `card`, `module_card`, `document_card`, `summary_card`.
- Regras: sombra elegante, titulo destacado, metadados compactos e acoes alinhadas.
- CSS principal: `static/css/cards.css`.

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
- `data-mask="placa"`

## Cards

Presenters enviam `title`, `subtitle`, `meta`, `actions`.
Templates nao montam metadados de negocio e nao formatam regra de dominio.

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
