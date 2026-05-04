# Regras de Negocio

## Cadastros

O app `cadastros` centraliza dados-base reutilizados por documentos e fluxos futuros.

Entidades ativas do modulo:

- `Unidade`: nome e sigla.
- `Cidade`: nome e UF; combinação nome + UF é única; nome e UF normalizados em maiúsculas (UF com 2 caracteres). Cidades podem ser carregadas em lote via CSV (`python manage.py importar_cidades`), conforme `docs/IMPORTACAO_CIDADES.md`.
- `Cargo`: nome unico e em maiusculo.
- `Combustivel`: nome unico e em maiusculo.
- `Servidor`: nome unico e em maiusculo, cargo, CPF, RG opcional e unidade opcional.
- `Viatura`: placa unica (AAA1234 ou AAA1A23), modelo, combustivel e tipo (`CARACTERIZADA`/`DESCARACTERIZADA`).

## Regras obrigatorias

- Nao existe cadastro de `Motorista`.
- `Servidor` nao possui matricula.
- `Viatura` nao possui marca nem unidade.
- Cadastros nao possuem ativo/inativo.
- Exclusao e fisica.
- Quando existir vinculo relevante, exclusao deve ser bloqueada com mensagem clara.

Mensagem padrao de bloqueio:

```text
Não foi possível excluir este cadastro porque ele está vinculado a outros registros.
```

## Mascaras visuais

- CPF: `000.000.000-00` (armazenado em digitos).
- RG: `00.000.000-0` (armazenado normalizado).
- Placa: `AAA-1234` ou `AAA1A23` na tela; armazenada sem hifen e em maiusculo.
