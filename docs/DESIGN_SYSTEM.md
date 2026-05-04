# Design System

## CSS centralizado

Todo CSS deve ficar em `static/css/`. O arquivo `static/css/style.css` e o agregador principal e importa os modulos de tokens, base, layout, sidebar, botoes, forms, listas, cards, steppers, documentos e utilitarios.

## Tokens

`tokens.css` concentra cores, espacamentos, raios, sombras e fonte base. Novos componentes devem consumir tokens antes de criar valores locais.

## Componentes reutilizaveis

Templates compartilhados ficam em `templates/components/`:

- `layout`: estrutura de navegacao e cabecalho.
- `lists`: listas e estados vazios.
- `forms`: componentes de formularios.
- `cards`: blocos de conteudo reutilizaveis.
- `steppers`: fluxos em etapas.
- `buttons`: padroes de botoes.
- `modals`: dialogos e sobreposicoes.
- `feedback`: alertas, erros e mensagens.

## Regras

Nao colocar CSS solto em templates. Nao colocar JavaScript solto em templates. Excecoes devem ser raras, justificadas em comentario tecnico e preferencialmente convertidas depois em componente, CSS ou JS modular.

Paginas de app devem estender `templates/base.html` e usar componentes quando houver padrao reutilizavel.
