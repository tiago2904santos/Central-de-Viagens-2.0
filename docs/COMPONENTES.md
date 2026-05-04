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
