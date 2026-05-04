# Padrao CRUD

## Escopo atual

No app `cadastros`, o padrao CRUD esta consolidado para `Unidade`, `Cidade`, `Cargo`, `Combustivel`, `Servidor` e `Viatura`.

`Motorista` nao e entidade de cadastro.

O app `roteiros` ainda nao possui CRUD completo. Nesta etapa existe apenas a base real com models, admin, selectors, presenters e listagem componentizada. A criacao manual inicial acontece pelo Django Admin.

## Estrutura

- `forms.py`: validacao, normalizacao e mascaras de entrada.
- `selectors.py`: consultas e busca por `q`.
- `services.py`: criacao, atualizacao e exclusao fisica.
- `presenters.py`: dados dos cards sem HTML.
- `views.py`: fluxo request/form/service/messages/redirect.
- `urls.py`: rotas nomeadas padronizadas.
- `templates/`: composicao com components globais.

## Roteiros base

- `models.py`: `Roteiro` e `TrechoRoteiro`.
- `admin.py`: cadastro manual de roteiros e trechos.
- `selectors.py`: `listar_roteiros`, `get_roteiro_by_id`, `listar_trechos_do_roteiro`.
- `presenters.py`: `apresentar_roteiro_card`.
- `views.py`: listagem `index`, sem acesso direto aos models.
- `templates/roteiros/index.html`: lista rica com components globais.

CRUD de roteiro, calculos e vinculos documentais ficam para etapas futuras.

## Regras de exclusao

- Exclusao sempre fisica.
- Em vinculo impeditivo, bloquear com:

```text
Não foi possível excluir este cadastro porque ele está vinculado a outros registros.
```

## Regras especificas

- Servidor: nome unico em maiusculo, sem matricula, com cargo selecionavel.
- Viatura: sem marca/unidade, placa validada (AAA1234 ou AAA1A23), combustivel selecionavel e tipo fixo.
- Cargo e Combustivel: nomes unicos em maiusculo.

## Frontend

- Sem CSS inline e sem JS inline.
- Mascaras em `static/js/components/masks.js` via `data-mask="cpf|rg|placa"`.
- Padrao visual global aplicado por components em `templates/components/`.
- Header oficial do CRUD: `components/layout/page_header.html`.
- Confirmacao de exclusao via component global `components/feedback/confirm_delete_block.html`.
- Estados vazios e alertas devem usar os components de feedback reutilizaveis.
