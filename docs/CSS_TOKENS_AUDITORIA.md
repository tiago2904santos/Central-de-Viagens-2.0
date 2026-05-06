# Auditoria de Tokens CSS

## Objetivo

Refatorar CSS para semantica por tokens, reduzindo hardcodes repetidos e mantendo o contrato visual da tela `roteiros/novo/`.

## Tabela de auditoria

| Valor repetido | Ocorrências | Significado | Token criado | Arquivos afetados |
|---|---:|---|---|---|
| `999px` | varios | pill para botoes/chips/tooltips | `--radius-pill` | `roteiros.css`, `buttons.css`, `utilities.css` |
| `18px` | varios | bloco de secao/painel | `--radius-section`, `--radius-panel` | `roteiros.css` |
| `22px` | 1+ | container shell principal | `--radius-shell` | `roteiros.css` |
| `14px` | varios | controle grande/campo denso | `--radius-control-lg` | `roteiros.css` |
| `12px` | varios | campo e card interno | `--radius-control` | `forms.css`, `cards.css`, `roteiros.css` |
| `44px` | varios | altura padrao de controle | `--control-height-md` | `forms.css`, `roteiros.css` |
| `16px` | varios | espaco de card interno | `--space-card-y` | `roteiros.css` |
| `20px` | varios | espaco de secao | `--space-section-y`, `--space-5` | `roteiros.css` |
| `140ms/160ms` | varios | transicoes padrao | `--transition-fast`, `--transition-base` | `buttons.css`, `cards.css`, `forms.css` |
| `0 18px 40px rgba(...)` | varios | hover de card/painel | `--shadow-panel` | `cards.css` |
| `0 20px 44px rgba(...)` | varios | elevacao shell forte | `--shadow-strong` | `tokens.css`, `roteiros.css` |
| `#ffffff` / `#fff` / `white` | varios | superficie/texto claro | `--color-card`, `--color-white` | `buttons.css`, `roteiros.css`, `theme.css` |
| `#f8fbff` / `#f7fbff` | varios | superficie clara suave | `--color-surface-soft` | `buttons.css`, `roteiros.css`, `theme.css` |
| `#1c3148` | poucos | heading contextual | `--color-heading` | `roteiros.css` |
| `#58708a` | poucos | texto auxiliar | `--color-text-muted` | `roteiros.css` |

## Hardcodes remanescentes e justificativa

- Gradientes institucionais (ex.: cabecalho de referencia e mapa em `roteiros.css`) foram mantidos para preservar contraste e identidade visual congelada.
- Cores de componentes de terceiros/Leaflet continuam com ajustes locais quando o token global nao cobre o caso sem risco visual.
- Alguns `rgba(...)` de brilho/sombra continuam inline por serem ajustes pontuais de efeito (nao de semantica de superficie/texto).

## Buscas obrigatorias apos refactor

- `border-radius: 999px`: reduzido; substituido por `var(--radius-pill)` nos pontos novos/refatorados.
- `border-radius: 18px` e `border-radius: 22px`: reduzidos; migrados para `--radius-section`/`--radius-shell`.
- `#ffffff`/`#fff`/`white`: reduzidos em botoes e blocos de roteiro; remanescentes concentrados em gradientes e contratos visuais legados.

## Contrato de nao regressao

- Nao alterar layout, comportamento ou fluxo funcional.
- Nao alterar Python, views, forms, services ou models.
- Roteiros permanece visualmente equivalente no tema padrao; tema escuro segue legivel por tokenizacao de cor e contraste.
