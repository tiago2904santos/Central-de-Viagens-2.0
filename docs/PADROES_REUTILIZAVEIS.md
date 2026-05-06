# Padroes Reutilizaveis

## Objetivo

Centralizar contratos reutilizaveis para evitar duplicacao entre modulos.

## Backend

### 1) Organizacao por camadas
- Queries relevantes em `selectors.py`.
- Regras funcionais e transacoes em `services.py` ou `services/`.
- Dados de tela em `presenters.py`.
- Views apenas orquestram fluxo HTTP.

### 2) Exclusao protegida
- Tratamento padrao de `ProtectedError` com mensagem unica:
  - `Não foi possível excluir este cadastro porque ele está vinculado a outros registros.`

### 3) Configuracao do sistema
- Fonte de verdade em `cadastros`.
- Reuso por `get_configuracao_sistema` e `build_configuracao_context` (selectors/services).

## Frontend

### 1) Components globais
- Lista, formulario, cards, feedback e layout vivem em `templates/components/`.
- Evitar variacoes locais quando componente global ja cobre o caso.

### 2) Components de dominio
- Blocos em `templates/components/domain/` nao podem:
  - consultar banco;
  - calcular rota/diarias;
  - salvar dados;
  - depender de `request`.

### 3) Tokens e tema
- Usar variaveis CSS em `tokens.css` + `theme.css`.
- Evitar hardcode de cor quando existir token equivalente.

## Regras de nao regressao

- Sem `href="#"`.
- Sem CSS inline.
- Sem JS inline.
- Sem dependencia runtime de `legacy/`.
- Sem alterar visual da tela `roteiros/novo/`.
