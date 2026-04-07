# Análise de Padronização de Listagens - Central de Viagens 2.0

## MAPA ATUAL DOS TEMPLATES

### LISTA SIMPLES - Já com classe `system-list-page--simple` (9 templates)
Padrão de referência: `cadastros/cargos/lista.html`

1. `templates/cadastros/cargos/lista.html` - ✓ REFERÊNCIA OFICIAL
2. `templates/cadastros/unidades/lista.html` - ✓ 
3. `templates/cadastros/veiculos/combustiveis_lista.html` - ✓
4. `templates/eventos/modelos_justificativa/lista.html` - ✓
5. `templates/eventos/modelos_motivo/lista.html` - ✓
6. `templates/eventos/plano_trabalho_atividades/lista.html` - ✓
7. `templates/eventos/plano_trabalho_coordenadores/lista.html` - ✓
8. `templates/eventos/plano_trabalho_horarios/lista.html` - ✓
9. `templates/eventos/plano_trabalho_solicitantes/lista.html` - ✓
10. `templates/eventos/tipos_demanda/lista.html` - ✓

### LISTA SIMPLES - Estendendo `list_base.html` com mode='simple' (5 templates - PRECISAM DE CLASSE)
1. `templates/cadastros/veiculos/lista.html` - Estende list_base com mode='simple'
2. `templates/cadastros/viajantes/lista.html` - Estende list_base com mode='simple'
3. `templates/eventos/global/roteiros_lista.html` - Estende list_base com mode='simple'
4. `templates/eventos/global/termos_lista.html` - Estende list_base com mode='simple'
5. `templates/eventos/plano_trabalho_atividades/lista.html` - JÁ TEM CLASSE

### LISTA COMPLETA - Já com classe `system-list-page--complete` (7 templates)
Padrão de referência: `eventos/global/oficios_lista.html`

1. `templates/eventos/global/oficios_lista.html` - ✓ REFERÊNCIA OFICIAL
2. `templates/eventos/evento_lista.html` - ✓
3. `templates/eventos/documentos/planos_trabalho_lista.html` - ✓
4. `templates/eventos/documentos/ordens_servico_lista.html` - ✓
5. `templates/eventos/documentos/termos_lista.html` - ✓
6. `templates/eventos/documentos/justificativas_lista.html` - ✓
7. `templates/eventos/global/justificativas_lista.html` - ✓

### ESPECIAL - Contexto guiado (não padronizado para famílias)
1. `templates/eventos/guiado/etapa_2_lista.html` - Fluxo guiado interno, deixa como está

## PADRÃO LISTA SIMPLES - `cadastros/cargos/lista.html`

**Estrutura:**
- Classe: `system-list-page--simple`
- Header: `page-header-cadastro system-list-header system-list-header--standard`
  - Copy section: titulo, subtítulo
  - Meta: contador de registros + contexto auxiliar 
  - Controls: mode_badge + botões de ação
- Filtro: busca, ordenar por, direção, botões filtrar/limpar
- Tabela: table-hover table-cadastro com ações

**Características:**
- Objetividade máxima
- Filtro simples (3 campos basicamente)
- Tabela compacta com poucas colunas
- Visual administrativo mas limpo

## PADRÃO LISTA COMPLETA - `eventos/global/oficios_lista.html`

**Estrutura:**
- Classe: `system-list-page--complete` + data-list-view-root
- Header: `page-header-cadastro system-list-header system-list-header--standard`
  - Copy section: titulo, subtítulo contextual
  - Meta: contador + contexto operacional
  - Controls: mode_badge + toggle rich/basic (quando aplicável) + botão principal
- Filtro: múltiplos campos baseados em contexto
- Conteúdo: cards cascata ou tabela densa com contexto
- Badges/status: presentes e variados

**Características:**
- Contexto documental rico
- Filtro avançado (múltiplos campos, status chips)
- Cards ou tabela com mais colunas informativas
- Visual corporativo e denso

## AÇÕES NECESSÁRIAS

### 1. Adicionar classe `system-list-page--simple` aos 4 templates que faltam
- `templates/cadastros/veiculos/lista.html`
- `templates/cadastros/viajantes/lista.html`
- `templates/eventos/global/roteiros_lista.html`
- `templates/eventos/global/termos_lista.html`

OBSERVAÇÃO: Estes templates estão usando `list_base.html` que não injeta a classe. Precisa encapsular o conteúdo com a classe correta.

### 2. Validar que todo template SIMPLES possui:
- Classe: `system-list-page--simple`
- Header padronizado
- Meta com contexto
- Filtro simples
- Tabela ou lista simples

### 3. Validar que todo template COMPLETA possui:
- Classe: `system-list-page--complete`
- Header com contexto
- Meta operacional
- Filtro avançado
- Cards ou tabela densa com contexto

## REFERÊNCIAS OFICIAIS FINAIS

**LISTA SIMPLES:** `templates/cadastros/cargos/lista.html`
- Herança direta de `base.html`
- Bloco HTML direto com classe
- Padrão Head, Filtro, Tabela

**LISTA COMPLETA:** `templates/eventos/global/oficios_lista.html`
- Herança direta de `base.html`
- Bloco HTML direto com classe
- Padrão Head rico, Filtro avançado, Cards/Tabela contextual

## SAÍDA ESPERADA APÓS TRABALHO

1. Todos os templates SIMPLES com classe `system-list-page--simple`
2. Todos os templates COMPLETA com classe `system-list-page--complete`
3. Headers padronizados visualmente dentro de cada família
4. Filtros adequados para a densidade de cada família
5. Ações e controles coerentes
6. CSS ou estrutura visual consistente sem destruir particularidades

---
Criado em: 2026-04-07
Commit de referência: ea16c08502b5cc80c60e8526535a4d9c13c17193
