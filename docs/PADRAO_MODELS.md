# Padrão de Models

## Regras

- `Meta.ordering`, `verbose_name` e `verbose_name_plural` obrigatórios.
- `__str__` objetivo e legível.
- `related_name` explícito, evitar default implícito.
- `on_delete` definido por regra de domínio (`PROTECT`, `SET_NULL`, `CASCADE`).
- Normalização simples em `save()` pode existir, mas deve ser reutilizável.

## Padrões reutilizáveis

- Normalizadores globais em `core/normalizers.py`:
  - `normalize_upper`
  - `normalize_spaces`
  - `normalize_digits`
  - `normalize_plate`
  - `remove_accents`

## Estado atual

- `TimeStampedModel` existe em `cadastros.models`.
- Pendência controlada: centralizar em `core` apenas quando for possível sem risco de migration/regressão.
