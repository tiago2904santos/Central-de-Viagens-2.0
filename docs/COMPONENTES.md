# Componentes

## Layout

- `templates/components/layout/app_shell.html`: estrutura base de shell para composicoes futuras. Variavel esperada: `content`.
- `templates/components/layout/sidebar.html`: navegacao principal. Usa `navigation_items` do context processor.
- `templates/components/layout/topbar.html`: barra superior. Usa `page_section` e `page_title`.
- `templates/components/layout/page_header.html`: cabecalho de pagina. Variaveis: `title`, `description`, `eyebrow`, `action_label`, `action_url`.

Exemplo:

```django
{% include "components/layout/page_header.html" with title=page_title description=page_description only %}
```

## Lists

- `lists/list_page.html`: estrutura completa de lista. Variaveis: `title`, `description`, `eyebrow`, `search_placeholder`, `empty_message`, `action_label`, `action_url`.
- `lists/list_toolbar.html`: busca, filtros e acao principal.
- `lists/list_filters.html`: area reservada para filtros.
- `lists/list_grid.html`: grid de resultados e paginacao futura. Recebe `cards`, uma lista de dicionarios preparada por presenters.
- `lists/list_empty.html`: estado vazio da lista.

Exemplo:

```django
{% include "components/lists/list_page.html" with title="Oficios" description="Lista de oficios." only %}
```

Em listagens reais, a view deve usar selectors e presenters:

```python
objetos = listar_servidores()
cards = [apresentar_servidor_card(objeto) for objeto in objetos]
```

## Forms

- `forms/form_page.html`: pagina de formulario.
- `forms/form_section.html`: bloco logico de formulario. Variaveis: `title`, `description`, `content`.
- `forms/form_field.html`: campo padrao. Variaveis: `field_id`, `label`, `field`, `help_text`, `errors`.
- `forms/form_actions.html`: acoes finais. Variaveis: `primary_label`, `secondary_label`, `secondary_url`.

## Steppers

- `steppers/stepper.html`: etapas padrao para fluxos.
- `steppers/stepper_actions.html`: acoes de navegacao do fluxo.

## Cards

- `cards/card.html`: card generico.
- `cards/module_card.html`: acesso a modulo. Variaveis: `title`, `description`, `href`, `action_label`.
- `cards/document_card.html`: documento com status, metadados e acoes. Variaveis: `title`, `status`, `document_type`, `updated_at`, `open_url`, `pdf_url`, `docx_url`, `delete_url`.
- `cards/document_card.html`: tambem aceita `card`, com `title`, `subtitle`, `status`, `meta`, `body` e `actions`.
- `cards/summary_card.html`: resumo numerico ou textual. Variaveis: `label`, `value`, `description`.

## Buttons

- `buttons/action_button.html`: renderiza link ou button. Variaveis: `href`, `label`, `variant`, `size`, `icon`, `type`.
- `buttons/button_group.html`: agrupa acoes.

## Feedback e Modal

- `feedback/alerts.html`: renderiza mensagens do Django.
- `feedback/empty_state.html`: estado vazio reutilizavel. Variaveis: `title`, `message`.
- `modals/modal.html`: estrutura base de modal. Variaveis: `modal_id`, `title`, `content`.
