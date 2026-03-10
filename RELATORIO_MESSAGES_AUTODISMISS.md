# Relatório — Mensagens (Django messages) com auto-dismiss

## Arquivos alterados

1. **templates/base.html**
   - Container de mensagens: adicionado `id="django-messages-container"`.
   - Cada `alert`: adicionado `data-autodismiss="true"`.
   - Script no final (antes de `{% block extra_js %}`): em `DOMContentLoaded`, seleciona `.alert[data-autodismiss="true"]`, aguarda 3000 ms, aplica a classe `fade-out`, e após 500 ms remove o elemento do DOM.

2. **static/css/style.css**
   - Classe `.alert.fade-out`: `opacity: 0; transition: opacity 0.4s ease;`

## Comportamento

- Só os alerts de messages do Django (no container de messages) têm `data-autodismiss="true"`.
- Após 3 s, o alert recebe a classe `fade-out` e some em 0,4 s (fade).
- 0,5 s depois do início do fade, o elemento é removido do DOM.
- O botão de fechar do Bootstrap continua funcionando (fechamento manual).
- Nenhuma regra de negócio foi alterada; apenas a parte visual.

## Testes

- **ConfiguracoesViewTest:** 10 testes executados, todos passando.

## Como testar manualmente

1. Fazer login na aplicação.
2. Ir em **Configurações** (menu Cadastros → Configurações ou `/cadastros/configuracoes/`).
3. Alterar qualquer campo (ex.: Sigla do órgão) e clicar em **Salvar**.
4. Verificar que a mensagem verde “Configurações salvas com sucesso.” aparece no topo do conteúdo.
5. Aguardar cerca de 3 segundos sem fechar a mensagem manualmente.
6. Verificar que a mensagem faz fade-out (some em ~0,4 s) e depois some por completo (removida do DOM).
7. Opcional: salvar de novo e fechar a mensagem com o botão ✕ antes de 3 s; o fechamento manual do Bootstrap deve continuar funcionando.
