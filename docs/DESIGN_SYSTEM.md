# Design System

## Regras globais

- CSS centralizado em `static/css/`.
- JS centralizado em `static/js/`.
- Proibido CSS e JS soltos por pagina.
- Nao criar estilo especifico por CRUD; corrigir no component global reutilizavel.

## Padrao visual premium

- Superficies em camadas claras, com bordas suaves e sombra controlada.
- Cabecalho de pagina com gradiente azul profundo, luz suave e hierarquia forte.
- Inputs, cards e botoes com altura/radius consistentes para manter ritmo visual.
- Estados de sucesso, erro, aviso e info com contraste elegante e sem agressividade.
- Densidade otimizada para CRUD: menos espaco morto e leitura mais rapida.

## Referência estética do legacy

- O projeto em `legacy/` foi usado como referencia visual e conceitual para sidebar, gradientes, densidade de cards, botoes em pilula e acabamento de toolbar/formularios.
- Foram aproveitadas ideias de identidade: menu lateral escuro com estados ativos mais evidentes, cabecalho com gradiente institucional, cards com acento lateral e superficies em camadas.
- Foram descartados trechos especificos e volumosos de CSS legado, estilos acoplados por pagina e estruturas antigas de template nao componentizadas.
- A reinterpretacao foi aplicada somente no design system novo (`templates/components/` + `static/css/`) com tokens globais.
- Nao existe importacao, dependencia de runtime, ou reaproveitamento tecnico direto de arquivos de `legacy/`.

## Mascaras reutilizaveis

As mascaras do sistema ficam em `static/js/components/masks.js` e devem ser habilitadas por `data-mask` nos campos.

Mascaras padrao:

- CPF: `000.000.000-00`
- RG: `00.000.000-0`
- Placa: `AAA-1234` ou `AAA1A23`

A normalizacao final ocorre no backend (forms/models).

## Cadastros como referencia

As telas de `Unidade`, `Cidade`, `Cargo`, `Combustivel`, `Servidor` e `Viatura` sao a referencia visual e estrutural para os proximos modulos.

## Regras para evolucao visual

- Ajustes de header em `templates/components/layout/page_header.html` e `static/css/layout.css`.
- Ajustes de sidebar em `templates/components/layout/sidebar.html`, `static/css/sidebar.css` e `static/js/components/sidebar.js`.
- Ajustes de toolbar de lista em `templates/components/lists/list_toolbar.html` e `static/css/lists.css`.
- Ajustes de formularios em `templates/components/forms/*.html` e `static/css/forms.css`.
- Ajustes de cards em `templates/components/cards/*.html` e `static/css/cards.css`.
- Ajustes de feedback em `templates/components/feedback/*.html` e `static/css/utilities.css`.
- Nunca copiar CSS bruto do legado em bloco; extrair o conceito e reconstruir no sistema atual.

## Sidebar hierarquica

A sidebar suporta itens aninhados e deve ser a unica fonte visual de navegacao lateral. A hierarquia e declarada em `core/navigation.py`, renderizada por `templates/components/layout/sidebar.html`, estilizada em `static/css/sidebar.css` e controlada por JS centralizado em `static/js/components/sidebar.js`.

Em `Cadastros`, a estrutura visual e:

- `Servidores`
  - `Cargos`
- `Viaturas`
  - `Combustiveis`
- `Unidades`
- `Cidades`

`Cidades` continua sendo cadastro persistido em banco e pode receber importacao CSV em etapa futura. `Motoristas` nao deve aparecer como cadastro independente. Nao criar cores por submodulo nem CSS/JS em templates para controlar menu.
