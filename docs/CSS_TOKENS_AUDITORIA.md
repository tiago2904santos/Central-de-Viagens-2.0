# Auditoria de Tokens CSS

## Fechamento 10/10 — auditoria antes

| Valor | Antes | Depois | Decisão |
|---|---:|---:|---|
| `border-radius: 999px` | 3 | 0 | ELIMINADO |
| `border-radius: 18px` | 1 | 0 | ELIMINADO |
| `border-radius: 22px` | 0 | 0 | ELIMINADO |
| `border-radius: 14px` | 0 | 0 | ELIMINADO |
| `border-radius: 12px` | 1 | 0 | ELIMINADO |
| `min-height: 44px` | 8 | 0 | ELIMINADO |
| `height: 44px` | 9 | 0 | ELIMINADO |
| `#ffffff` | 39 | 2 | REDUZIDO |
| `#fff` | 0 | 0 | ELIMINADO |
| `white` | 0 | 0 | ELIMINADO |
| `#f8fbff` | 7 | 7 | MANTIDO JUSTIFICADO |
| `#f7fbff` | 5 | 5 | MANTIDO JUSTIFICADO |
| `#f4f8fc` | 1 | 1 | MANTIDO JUSTIFICADO |
| `#1c3148` | 0 | 0 | ELIMINADO |
| `#58708a` | 0 | 0 | ELIMINADO |
| `rgba(255` | 137 | 137 | MANTIDO JUSTIFICADO |
| `sombras repetidas` (`box-shadow`) | 93 | 0 hardcoded de timing | REDUZIDO VIA TOKENS |
| `transições hardcoded (140/150/160/180/200ms)` | 40 | 0 | ELIMINADO |

## Fechamento 10/10 — auditoria depois

| Valor | Antes | Depois | Status |
|---|---:|---:|---|
| `border-radius: 999px` | 3 | 0 | ELIMINADO |
| `#ffffff/#fff/white` | 39 | 2 | REDUZIDO |
| `min-height/height: 44px` | 17 | 0 | ELIMINADO |
| `transições 140-200ms hardcoded` | 40 | 0 | ELIMINADO |
| `cores de texto #1c3148/#58708a/#24394f/#17324d/#14304a` | 5 | 0 | ELIMINADO |

## Hardcodes restantes autorizados

- `static/css/theme.css` | `:root` e temas `html[data-theme=*]` | `#ffffff` | branco absoluto usado como valor de token de tema (fonte de verdade para superfícies claras), mantendo compatibilidade entre combinações de tema.
- `static/css/roteiros.css` | `.roteiro-editor__map-card` e blocos de destaque do wizard | `#f8fbff`, `#f7fbff`, `#f4f8fc` | gradientes institucionais únicos do wizard e mapa, congelados por contrato visual da tela `roteiros/novo/`.
- `static/css/roteiros.css` e `theme.css` | efeitos de brilho/vidro | `rgba(255, ...)` | highlights de luz e translucidez de camada; não representam cor semântica de superfície/texto reutilizável.

## Regras operacionais (fase 2)

- `border-radius: 999px` é proibido; usar `var(--radius-pill)`.
- Branco literal em componente comum deve usar `var(--color-white)` ou token semântico (`--color-card`, `--color-surface`, `--color-input-bg`).
- Cor de texto em componente não usa hex fixo; usar `--color-text`, `--color-heading`, `--color-label`, `--color-text-muted`, `--color-text-soft`.
- Sombra repetida deve virar token (`--shadow-*`).
- Transição repetida deve virar token (`--transition-*`).
- CSS deve ser organizado por seções com comentários de intenção.
