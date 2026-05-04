# Design System

## Regras globais

- CSS centralizado em `static/css/`.
- JS centralizado em `static/js/`.
- Proibido CSS e JS soltos por pagina.

## Mascaras reutilizaveis

As mascaras do sistema ficam em `static/js/components/masks.js` e devem ser habilitadas por `data-mask` nos campos.

Mascaras padrao:

- CPF: `000.000.000-00`
- RG: `00.000.000-0`
- Placa: `AAA-1234` ou `AAA1A23`

A normalizacao final ocorre no backend (forms/models).

## Cadastros como referencia

As telas de `Unidade`, `Cidade`, `Cargo`, `Combustivel`, `Servidor` e `Viatura` sao a referencia visual e estrutural para os proximos modulos.
