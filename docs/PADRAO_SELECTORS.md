# Padrão de Selectors

## Nomenclatura

- `listar_*`
- `get_*_by_id`
- `listar_*_para_select`
- `buscar_*`
- `queryset_*_base`

## Regras

- Centralizar busca por `q`.
- Aplicar `select_related`/`prefetch_related` quando necessário.
- Ordenação consistente por significado de negócio.
- Evitar N+1 óbvio.
