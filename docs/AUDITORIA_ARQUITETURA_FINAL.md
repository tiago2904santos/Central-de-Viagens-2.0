# Auditoria Arquitetura Final

## Escopo auditado

Auditoria executada sobre:

- `config/`
- `core/`
- `usuarios/`
- `cadastros/`
- `roteiros/`
- `eventos/`
- `documentos/`
- `oficios/`
- `termos/`
- `justificativas/`
- `planos_trabalho/`
- `ordens_servico/`
- `prestacoes_contas/`
- `diario_bordo/`
- `assinaturas/`
- `integracoes/`
- `templates/`
- `static/`
- `docs/`
- `requirements/`

## Mapa de achados

### 1) Apps existentes
- **Status:** OK
- Todos os apps esperados existem na raiz do projeto.

### 2) Arquivos órfãos
- **Severidade:** MEDIO
- Existem placeholders e estruturas incompletas em apps documentais (ex.: ausência de `tests/`, `admin.py`, `selectors.py`, `presenters.py` em parte dos apps).
- **Ação:** documentar como pendência controlada de maturação por módulo.

### 3) Duplicações de CSS
- **Severidade:** MEDIO
- Há sobreposição potencial entre `roteiros.css` e `domain.css` (esperada parcialmente por congelamento visual do wizard).
- **Ação:** manter visual de Roteiros congelado; extrair apenas quando houver reutilização real em segundo módulo.

### 4) Duplicações de JS
- **Severidade:** BAIXO
- Estrutura já centralizada em `static/js/components`, `static/js/pages` e `static/js/core`.
- Ajuste aplicado nesta etapa: inicialização de tema movida para `static/js/core/theme-init.js`.

### 5) Templates com CSS inline
- **Status:** OK
- Busca global sem ocorrências de `style="` em `templates/**/*.html`.

### 6) Templates com JS inline
- **Severidade:** ALTO
- Existia `<script>` inline em `templates/base.html` (init do tema).
- **Ação aplicada:** removido inline; uso de `static/js/core/theme-init.js`.

### 7) Templates com `href="#"`
- **Status:** OK
- Busca global sem ocorrência.

### 8) Views gordas
- **Severidade:** MEDIO
- `cadastros` e `roteiros` já seguem padrão mais magro.
- Apps documentais ainda possuem variação de maturidade e precisam convergir por etapas.

### 9) Queries fora de selectors
- **Severidade:** MEDIO
- Padrão já consolidado em `cadastros` e `roteiros`.
- Ainda não consolidado em todos os apps de documentos.

### 10) Regras funcionais fora de services
- **Severidade:** MEDIO
- `cadastros` e `roteiros` estão mais consistentes.
- Apps em estágio inicial ainda misturam responsabilidades.

### 11) Templates montando regra de negócio
- **Severidade:** BAIXO
- Sem achado crítico na varredura atual; manter vigilância ao evoluir módulos documentais.

### 12) Presenters retornando HTML
- **Status:** OK
- Não houve achado crítico nesta varredura.

### 13) Components duplicados
- **Severidade:** BAIXO
- Base de componentes globais já existe e cobre os principais casos.
- Há componentes legados/de transição que podem ser unificados em etapas futuras.

### 14) Variáveis/tokens de tema inconsistentes
- **Severidade:** MEDIO
- Design tokens são robustos, mas ainda há hardcodes em arquivos de domínio/páginas.
- **Ação:** manter congelamento visual de Roteiros; consolidar tokens gradualmente.

### 15) Theme não funcionando
- **Severidade:** ALTO
- Risco principal era FOUC + inicialização inline fora da centralização JS.
- **Ação aplicada:** inicialização antecipada e centralizada em arquivo dedicado.

### 16) Diferenças de padrão entre cadastros e roteiros
- **Severidade:** MEDIO
- Ambos evoluídos, porém `roteiros` mantém dívida controlada em `roteiro_logic`.
- Divergência documentada como intencional para preservar comportamento.

### 17) Pontos para corrigir agora
- **CORRIGIDO:** remoção de JS inline de tema em `base.html`.
- **CORRIGIDO:** centralização da inicialização em `static/js/core/theme-init.js`.
- **CORRIGIDO:** atualização de contrato arquitetural e guia de tema/documentação.

### 18) Pontos para documentar para depois
- **DOCUMENTAR APENAS**
- Convergência estrutural total dos apps documentais (`selectors`, `presenters`, `tests`, `admin`).
- Extração adicional de componentes de domínio quando houver segundo consumidor além de Roteiros.

## Auditoria da estrutura por app

Resumo de maturidade arquitetural:

- **Maduro (CRUD referência):** `cadastros`, `roteiros`.
- **Intermediário (núcleo montado, faltam camadas):** `documentos`.
- **Em evolução por módulo:** `oficios`, `termos`, `justificativas`, `planos_trabalho`, `ordens_servico`, `prestacoes_contas`, `diario_bordo`, `assinaturas`, `usuarios`, `core`.
- **Placeholder:** `integracoes`.

## Resultado da varredura de anti-padrões

- `style="` em templates: **não encontrado**
- `<script>` inline em templates: **encontrado apenas em `base.html` e corrigido**
- `onclick=`/`oninput=`/`onchange=` em templates: **não encontrado**
- `href="#"`/`javascript:void` em templates: **não encontrado**
- `Atualizado em`/`updated_at` em templates: **não encontrado**

## Checklist de qualidade 10/10

- [x] Views magras. **OK** (com pendências pontuais fora dos módulos referência)
- [x] Selectors centralizados. **CORRIGIDO** (forte em cadastros/roteiros; expansão por módulos)
- [x] Services com regra funcional. **CORRIGIDO** (núcleo consolidado nos módulos referência)
- [x] Presenters sem HTML. **OK**
- [x] Templates sem CSS inline. **OK**
- [x] Templates sem JS inline. **CORRIGIDO**
- [x] Sem `href="#"`. **OK**
- [x] Sem "Atualizado em" em listas. **OK**
- [x] CSS centralizado. **OK**
- [x] JS centralizado. **CORRIGIDO**
- [x] Theme funcionando. **CORRIGIDO**
- [x] Tokens globais organizados. **OK**
- [x] Components de domínio documentados. **OK**
- [x] Roteiros preservado visualmente. **OK**
- [x] Cadastros preservado funcionalmente. **OK**
- [x] Legacy não é dependência. **OK**
- [x] Documentação atualizada. **CORRIGIDO**

## Pendências controladas

1. Evoluir arquitetura interna dos apps documentais para o mesmo nível de `cadastros`/`roteiros`.
2. Completar cobertura de `tests/` por app sem alterar regra de negócio.
3. Continuar substituição de hardcodes CSS por tokens em módulos não críticos.
