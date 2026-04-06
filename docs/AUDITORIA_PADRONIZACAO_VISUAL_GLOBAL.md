# Auditoria Técnica Global — Padronização Visual, Estrutural e Comportamental

## Escopo auditado
- Base global (`templates/base.html`), dashboard/home, login, página placeholder, sidebar/menu.
- Todos os templates de `documentos` (ofícios, planos, ordens, termos, roteiros, justificativas, eventos, modelos e hub).
- Todos os templates de `cadastros` (viajantes, veículos, combustíveis, cargos, unidades, configurações e hub).
- Includes e partials (`templates/includes/*`, `templates/cadastros/_aviso_rascunho.html`, stepper de ofícios).
- CSS global (`static/css/style.css`).
- JS global (`static/js/masks.js`) e JS específico (`static/js/oficio_wizard.js`).

## Diagnóstico resumido
Inconsistência **sistêmica**: existe base visual comum (Bootstrap + classes internas), mas coexistem padrões concorrentes por módulo e por tela.

### Principais causas estruturais
1. Centralização de CSS parcial: `style.css` contém design system global e, ao mesmo tempo, regras altamente específicas de Ofício (stepper/resumo), concentrando governança em um único módulo.
2. JS compartilhado insuficiente: há `masks.js` e `oficio_wizard.js`, porém vários comportamentos equivalentes continuam embutidos em templates (toggle, uppercase, auto-fill, manipulação de listas dinâmicas).
3. Reuso de componentes incompleto: exclusão está bem reutilizada (`includes/_confirmar_exclusao.html`), mas cabeçalhos de listagem, filtros, cabeçalhos de formulário, blocos de ação e cartões de resumo ainda são repetidos e recriados.
4. Divergência de linguagem visual entre áreas: `cadastros` adota um micro-padrão (`page-header-cadastro`, `form-card`), enquanto parte de `documentos` usa blocos utilitários avulsos (`d-flex ... mb-3`, `border-0 shadow-sm`) sem um include/base de listagem.

## Evidências objetivas
- 59 templates no total, 1 CSS global, 2 JS globais/módulo.
- Inline JS presente em múltiplos formulários de cadastros e documentos.
- Inline `style=""` presente em detalhe de evento e em etapas do wizard de ofício.
- O próprio `base.html` contém JS inline extenso para sidebar + autodismiss de alertas.

## Prioridades recomendadas
1. Extrair inline JS/CSS para módulos estáveis em `static/js` e `static/css`.
2. Criar includes compartilhados para:
   - cabeçalho de listagens,
   - card de filtros,
   - ações padrão de formulário,
   - blocos de status/summary.
3. Definir padrão visual único para listagens e formulários (adotando o padrão mais estável já existente em `cadastros` + `table-cadastro` + `card-header-form`).
4. Refatorar módulos por ondas para reduzir risco funcional.
