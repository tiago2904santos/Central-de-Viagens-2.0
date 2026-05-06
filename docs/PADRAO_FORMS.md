# Padrão de Forms

## Responsabilidades

- Validar entrada do usuário.
- Normalizar dados simples (maiúsculo, dígitos, placa).
- Definir widgets e classes de campo.

## Não permitido

- Regra de negócio pesada no form.
- HTML/CSS no form.

## Convenções

- Texto: `form-control`.
- Select: `form-select`.
- Máscaras com `data-mask`.
- Repetição de normalização deve usar helper global (`core/normalizers.py`).
