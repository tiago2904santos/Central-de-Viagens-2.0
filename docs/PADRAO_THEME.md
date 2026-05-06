# Padrao Theme

## Objetivo

Garantir alternancia de tema com persistencia e sem piscar tema incorreto no carregamento inicial.

## Contrato tecnico

- Atributo de tema: `data-theme` no elemento `html`.
- Valores validos: `dark-light`, `dark-dark`, `light-light`, `light-dark`.
- Persistencia: `localStorage` na chave `cv-theme`.
- Inicializacao antecipada: `static/js/core/theme-init.js` no `head` do `base.html`.
- Interacao de usuario: `static/js/theme-toggle.js`.

## Responsabilidades por arquivo

- `templates/base.html`: carrega `theme-init.js` antes do CSS e `theme-toggle.js` com `defer`.
- `static/js/core/theme-init.js`: aplica tema inicial imediatamente.
- `static/js/theme-toggle.js`: sincroniza botoes de tema e persistencia.
- `static/css/tokens.css`: tokens base e variaveis globais.
- `static/css/theme.css`: variaveis por combinacao de tema.

## Regras de manutencao

- Nao usar cores novas hardcoded sem avaliar token.
- Nao mover regra de tema para JS inline em template.
- Nao alterar visual de `roteiros/novo/` ao mexer em tokens/tema.
- Sidebar institucional deve manter identidade azul + destaque dourado.
- Priorizar troca de valor por tema no token (`theme.css`) em vez de override de componente por seletor de tema.
- Override especifico de tema so permanece para casos excepcionais (Leaflet/componentes externos/contraste especial).
- Branco literal em componente deve preferir token (`--color-white` ou semanticos de superficie), nao hex direto.
- Cores de texto de componente devem usar tokens de texto (`--color-text`, `--color-heading`, `--color-label`, `--color-text-muted`, `--color-text-soft`).

## Tokens semanticos obrigatorios por tema

- Superficie: `--color-bg`, `--color-shell`, `--color-surface`, `--color-card`, `--color-panel`.
- Borda: `--color-border`, `--color-border-soft`, `--color-border-strong`.
- Texto: `--color-text`, `--color-text-muted`, `--color-text-soft`, `--color-heading`, `--color-label`, `--color-help`.
- Formulario: `--color-input-bg`, `--color-input-border`, `--color-input-text`, `--color-input-placeholder`, `--color-input-disabled-bg`, `--color-input-disabled-text`.
- Estados: `--color-primary`, `--color-primary-dark`, `--color-accent`, `--color-danger`, `--color-danger-bg`, `--color-danger-text`, `--color-info-bg`, `--color-info-border`, `--color-info-text`.

## Hierarquia de superficies (painel escuro)

Nos temas `dark-dark` e `light-dark`, o objetivo nao e clarear o layout: e separar planos de leitura.

- Plano 1: `--color-bg` (fundo global mais profundo).
- Plano 2: `--color-shell` (casca da pagina).
- Plano 3: `--color-surface` / `--color-panel` (secao externa).
- Plano 4: `--color-card` / `--color-card-soft` (card interno).
- Plano 5: `--color-input-bg` (camada de controle ativo).
- Plano 6: `--color-input-bg-disabled` (controle desabilitado/read-only legivel).

Regra de contraste:

- Labels usam `--color-label`.
- Labels de destaque usam `--color-label-strong`.
- Texto auxiliar usa `--color-help`.
- Descricao secundaria usa `--color-description`.
- Titulos internos usam `--color-heading`, `--color-section-title` ou `--color-card-title`.
- Placeholder usa `--color-input-placeholder`.
- Disabled/read-only usa `--color-input-disabled-text` com `opacity: 1`.
- Estado vazio/info em painel escuro usa `--color-info-bg` + `--color-info-border` + `--color-info-text` (sem branco chapado).
- Leaflet pode manter tiles claros, mas container/painel/metricas devem respeitar tokens escuros.
- Icones usam `--color-icon`, `--color-icon-muted` e `--color-icon-strong` (nunca preto bruto no painel escuro).
- Radios/checkboxes em painel escuro usam `accent-color: var(--color-accent)`.

## Checklist visual por tema

### light-light

- [ ] body/shell
- [ ] sidebar
- [ ] page header
- [ ] cards
- [ ] forms
- [ ] selects
- [ ] selects disabled
- [ ] inputs disabled/readonly
- [ ] botoes
- [ ] toolbar
- [ ] alerts
- [ ] roteiro novo
- [ ] login

### light-dark

- [ ] body/shell
- [ ] sidebar
- [ ] page header
- [ ] cards
- [ ] forms
- [ ] selects
- [ ] selects disabled
- [ ] inputs disabled/readonly
- [ ] botoes
- [ ] toolbar
- [ ] alerts
- [ ] roteiro novo
- [ ] login

### dark-light

- [ ] body/shell
- [ ] sidebar
- [ ] page header
- [ ] cards
- [ ] forms
- [ ] selects
- [ ] selects disabled
- [ ] inputs disabled/readonly
- [ ] botoes
- [ ] toolbar
- [ ] alerts
- [ ] roteiro novo
- [ ] login

### dark-dark

- [ ] body/shell
- [ ] sidebar
- [ ] page header
- [ ] cards
- [ ] forms
- [ ] selects
- [ ] selects disabled
- [ ] inputs disabled/readonly
- [ ] botoes
- [ ] toolbar
- [ ] alerts
- [ ] roteiro novo
- [ ] login

Regra critica: `dark-dark` nao pode ter card branco com texto claro.

## Hardcodes mantidos

- Sidebar e page header institucionais (azul/dourado) mantidos por identidade visual.
- Gradientes de acento e estados de CTA mantidos quando nao representam superficie/texto principal de formularios/cards.
