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

## AÇÕES REALIZADAS

### ✅ 1. Editar lista_base.html para permitir classe dinâmica
- Criado bloco `list_page_class` que permite override
- Default: `system-list-page--standard`
- Permite que templates herdem com classe correta

### ✅ 2. Adicionar classe `system-list-page--simple` aos 4 templates que faltavam
Implementação: Editado `list_base.html` + override de `list_page_class` em:
- `templates/cadastros/veiculos/lista.html` - FEITO
- `templates/cadastros/viajantes/lista.html` - FEITO
- `templates/eventos/global/roteiros_lista.html` - FEITO
- `templates/eventos/global/termos_lista.html` - FEITO

### ✅ 3. Validação realizada
- Django check: OK (System check identified no issues)
- git diff --check: OK (sem problemas de espaçamento)
- Estrutura de headers: Padronizados em todas as listas
- Filtros: Apropriados para cada família
- Herança: Todos usando padrão correto

## STATUS FINAL

**LISTA SIMPLES - 14 templates com classe `system-list-page--simple`:**
1. ✅ cadastros/cargos/lista.html (REFERÊNCIA OFICIAL)
2. ✅ cadastros/unidades/lista.html
3. ✅ cadastros/veiculos/combustiveis_lista.html
4. ✅ cadastros/veiculos/lista.html (PADRONIZADO)
5. ✅ cadastros/viajantes/lista.html (PADRONIZADO)
6. ✅ eventos/modelos_justificativa/lista.html
7. ✅ eventos/modelos_motivo/lista.html
8. ✅ eventos/plano_trabalho_atividades/lista.html
9. ✅ eventos/plano_trabalho_coordenadores/lista.html
10. ✅ eventos/plano_trabalho_horarios/lista.html
11. ✅ eventos/plano_trabalho_solicitantes/lista.html
12. ✅ eventos/tipos_demanda/lista.html
13. ✅ eventos/global/roteiros_lista.html (PADRONIZADO)
14. ✅ eventos/global/termos_lista.html (PADRONIZADO)

**LISTA COMPLETA - 7 templates com classe `system-list-page--complete`:**
1. ✅ eventos/global/oficios_lista.html (REFERÊNCIA OFICIAL)
2. ✅ eventos/evento_lista.html
3. ✅ eventos/documentos/planos_trabalho_lista.html
4. ✅ eventos/documentos/ordens_servico_lista.html
5. ✅ eventos/documentos/termos_lista.html
6. ✅ eventos/documentos/justificativas_lista.html
7. ✅ eventos/global/justificativas_lista.html

## REFERÊNCIAS OFICIAIS FINAIS

**LISTA SIMPLES:** `templates/cadastros/cargos/lista.html`
- Estrutura: page-header-cadastro, system-list-header--standard
- Filtro: busca, ordenar, direção
- Conteúdo: tabela simples com ações
- Visual: administrativo, compacto, eficiente

**LISTA COMPLETA:** `templates/eventos/global/oficios_lista.html`
- Estrutura: page-header-cadastro, system-list-header--standard, com modo toggle
- Filtro: múltiplos campos contextuais, chips de status
- Conteúdo: cards cascata com contexto documental
- Visual: corporativo, denso, informativo

## PARTICULARIDADES PRESERVADAS

- Listas simples mantêm objetividade máxima
- Listas completas mantêm contexto documental
- Toggles de visualização preservados (ricos/simples)
- Badges e status contextuais mantidos
- Vínculos documentais preservados
- Funcionalidades específicas de cada lista intactas

---
Criado em: 2026-04-07
Atualizado em: 2026-04-07
Commit de referência: ea16c08502b5cc80c60e8526535a4d9c13c17193
Status: ✅ CONCLUÍDO
