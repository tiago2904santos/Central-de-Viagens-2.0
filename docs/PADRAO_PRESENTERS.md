# Padrão de Presenters

## Contrato

Estrutura padrão de payload:

```python
{
  "title": "...",
  "subtitle": "...",
  "badges": [...],
  "meta": [...],
  "actions": [...],
}
```

## Helpers reutilizáveis

- `core/presenters/actions.py`
- `core/presenters/badges.py`
- `core/presenters/meta.py`

## Regras

- Não retornar HTML.
- Não gerar `href="#"`.
- Não consultar banco pesado.
