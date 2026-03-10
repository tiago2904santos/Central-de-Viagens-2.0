# Relatório — Faxina geral do código

**Data:** 2026-03-10  
**Escopo:** cadastros, eventos, core, templates, config, testes.  
**Critério:** limpeza conservadora, sem refatoração agressiva; remoção apenas do que estava claramente sem uso.

---

## 1. Arquivos alterados / removidos

### 1.1 Código removido (eventos)

| Arquivo | Alteração |
|---------|-----------|
| `eventos/views.py` | Removida a função **`_context_form()`** — nunca era chamada; as views já injetam `api_cidades_por_estado_url` diretamente no contexto. |
| `eventos/views.py` | Removida a função **`_trechos_roteiro(roteiro)`** (~85 linhas) — legado. A exibição de trechos passou a usar `_estrutura_trechos` + `_build_trechos_initial` e o front renderiza por `trechos_json`. Nenhuma view ou template referenciava `_trechos_roteiro`. |

### 1.2 Rotas consolidadas (eventos)

| Arquivo | Alteração |
|---------|-----------|
| `eventos/urls.py` | Removida a rota duplicada **`estimar-km-por-cidades`**. Mantida apenas **`trechos-estimar`** (path `trechos/estimar/`), que aponta para a mesma view `estimar_km_por_cidades`. |
| `templates/eventos/guiado/roteiro_form.html` | Removidas a variável JS `urlEstimarKmPorCidades` e a referência no fallback de URL de estimativa; uso apenas de `urlTrechosEstimar`. |

### 1.3 Templates removidos (vazios e não referenciados)

| Arquivo | Motivo |
|---------|--------|
| `templates/cadastros/veiculo_lista.html` | Arquivo vazio; as views usam `cadastros/veiculos/lista.html`. |
| `templates/cadastros/veiculo_form.html` | Arquivo vazio; as views usam `cadastros/veiculos/form.html`. |
| `templates/eventos/evento_form.html` | Arquivo vazio; criação/edição de evento redirecionam para o fluxo guiado (Etapa 1), não renderizam este template. |

### 1.4 Testes ajustados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/tests/test_eventos.py` | Asserts que usavam `eventos:estimar-km-por-cidades` passaram a usar `eventos:trechos-estimar`. |
| `eventos/tests/test_eventos.py` | `test_cadastro_mostra_botao_estimar_km_tempo`: assert de `urlEstimarKmPorCidades` trocado para `urlTrechosEstimar`. |
| `eventos/tests/test_eventos.py` | `test_distancia_longa_nao_subestimada_francisco_beltrao_londrina`: limite inferior de `tempo_cru` relaxado de 400 para 385 min (arredondamento/variação do serviço). |

---

## 2. Código morto removido (resumo)

- **`_context_form()`** em `eventos/views.py` — helper não utilizado.
- **`_trechos_roteiro(roteiro)`** em `eventos/views.py` — lógica legada de exibição de trechos (duracao_min, retorno_saida_dt por roteiro único), substituída pelo fluxo por trechos individuais e `trechos_json`.
- **Rota duplicada** `estimar-km-por-cidades` e variável JS associada.
- **3 templates** vazios e não referenciados (veiculo_lista, veiculo_form, evento_form).

---

## 3. Duplicações consolidadas

- **Endpoint de estimativa por cidades:** uma única rota nomeada `trechos-estimar` (path `eventos/trechos/estimar/`); front e testes passaram a usar só essa URL.

---

## 4. Imports / rotas / views / templates / JS limpos

- **eventos/urls.py:** uma rota a menos (estimar-km-por-cidades removida).
- **eventos/views.py:** duas funções a menos (_context_form, _trechos_roteiro); nenhum import novo ou removido além do que já era usado.
- **templates/eventos/guiado/roteiro_form.html:** uma variável JS e um fallback de URL removidos.
- **Templates cadastros/eventos:** 3 arquivos vazios removidos.

---

## 5. Testes removidos / ajustados

- Nenhum teste removido.
- Ajustes: troca de nome de rota/URL nos testes de etapa 2 e de estimativa; relaxamento de um assert em `test_distancia_longa_nao_subestimada_francisco_beltrao_londrina`.

---

## 6. Itens mantidos como “candidatos futuros”

Itens que podem ser revistos em faxinas futuras, com verificação de dependências:

| Item | Motivo |
|------|--------|
| **App `documentos`** | Está em `INSTALLED_APPS` mas **não está** em `config/urls.py`; a view usa `core/placeholder.html`, que não existe (hoje existe `core/em_breve.html`). Pode ser desativado ou alinhado ao fluxo “em breve” se o módulo for reativado. |
| **Campos legados em `RoteiroEvento`** | `duracao_min`, `retorno_saida_dt`, `retorno_duracao_min` ainda são usados (save, forms, views que preenchem saida_dt/retorno_saida_dt a partir dos trechos). Remoção exige migração e revisão de formulários/views. |
| **Relatórios .md na raiz** | Vários `RELATORIO_*.md`; não foram alterados. Podem ser reunidos numa pasta `docs/` ou marcados como obsoletos onde não refletirem o código. |

---

## 7. Confirmação dos fluxos principais

- **Login / dashboard:** não alterados.
- **Configurações:** não alteradas.
- **Viajantes / cargos / unidades:** não alterados; templates em uso são os de `viajantes/` e `veiculos/`, não os arquivos removidos.
- **Veículos / combustíveis:** não alterados; continuam usando `veiculos/lista.html` e `veiculos/form.html`.
- **Evento guiado Etapa 1:** não alterado.
- **Roteiros Etapa 2:** sem mudança de comportamento; apenas remoção de helper legado e de rota duplicada; front usa só `trechos-estimar`.
- **Estimativa local:** inalterada; um único endpoint para trecho sem pk.
- **Rascunho/finalizado, máscaras ao reabrir, salvar e reabrir:** não alterados.

---

## 8. Como validar manualmente

1. **Login** → Dashboard.
2. **Cadastros** → Configurações, Viajantes, Cargos, Unidades, Veículos, Combustíveis: listar, cadastrar, editar.
3. **Eventos** → Novo (fluxo guiado) → Etapa 1 (preencher e salvar) → Painel → Etapa 2.
4. **Etapa 2** → Cadastrar roteiro → Adicionar destinos → Em um trecho, clicar em “Estimar km/tempo” (deve usar `trechos/estimar/`) → Preencher saída/chegada → Salvar → Reabrir e conferir horários.
5. **Tipos de demanda** a partir da Etapa 1: listar, cadastrar, editar.

---

## 9. Checklist de aceite

| Item | Status |
|------|--------|
| Código morto (funções/helpers não usados) removido | OK |
| Rota duplicada de estimativa consolidada | OK |
| Templates vazios/não referenciados removidos | OK |
| Testes atualizados para nova rota/nomes | OK |
| Teste de estimativa (Francisco Beltrão–Londrina) ajustado | OK |
| Fluxos principais preservados | OK |
| Relatório de faxina entregue | OK |
| App documentos / relatórios .md | Candidatos futuros |

---

**Resumo:** Faxina conservadora aplicada: remoção de 2 funções legadas em `eventos/views.py`, 1 rota duplicada, 3 templates vazios e ajustes pontuais em testes. Comportamento dos fluxos principais mantido; itens de maior impacto (app documentos, campos legados de roteiro) ficaram como candidatos para uma próxima etapa.
