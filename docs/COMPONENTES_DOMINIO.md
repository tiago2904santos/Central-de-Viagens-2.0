# Componentes de Dominio

## Roteiros como modulo referencia

Componentes criados em `templates/components/domain/`:

- `sede_destinos.html`
- `destinos.html`
- `trechos.html`
- `trecho_card.html`
- `retorno.html`
- `calculadora_rota.html`
- `resumo_rota.html`

## Regras

- Nao duplicar HTML de destinos, trechos e calculadora em cada modulo.
- Nao usar CSS inline ou JS inline.
- Nao usar `href="#"`.
- Nao renderizar acao fake: se nao existe rota funcional, nao exibir botao.
- Nao exibir dado tecnico sem valor de negocio na UI.
