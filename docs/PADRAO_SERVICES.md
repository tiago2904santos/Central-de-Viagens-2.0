# Padrão de Services

## Responsabilidades

- Executar regra funcional.
- Persistir dados e coordenar transações.
- Tratar `ProtectedError` e regras de exclusão.

## Reuso criado

- `core/deletion.py` com:
  - `excluir_com_protecao`
  - `DelecaoProtegidaError`
  - `DEFAULT_DELETE_BLOCKED_MESSAGE`

## Regras

- Service não retorna HTML.
- Service não depende de template.
- Service não manipula `request`, salvo exceção explícita e documentada.
