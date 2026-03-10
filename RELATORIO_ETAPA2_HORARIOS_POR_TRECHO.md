# Relatório — Etapa 2 (Roteiros): Horários dentro de cada trecho

## Resumo

A Etapa 2 foi ajustada para que **toda a parte de horários fique dentro dos blocos de trechos**: removido o bloco global (Saída ida / Saída retorno / Chegadas calculadas); cada trecho passou a ter campos próprios editáveis (saída data/hora, chegada data/hora); duração permanece como apoio (sugere chegada ao preencher saída). A persistência continua por trecho e ao reabrir a edição os horários salvos voltam em cada trecho.

---

## 1) O que foi removido do bloco global

Removidos da interface e da lógica principal:

- **Saída ida — data**
- **Saída ida — hora**
- **Chegada ida (calculada)**
- **Saída retorno — data**
- **Saída retorno — hora**
- **Chegada retorno (calculada)**

Mantido apenas:

- **3) Duração (apoio)** — campo Duração (HH:MM), com texto explicando que é apoio e que cada trecho tem seus próprios campos abaixo.

No backend, `saida_dt` e `retorno_saida_dt` do modelo `RoteiroEvento` continuam no form (hidden) por compatibilidade; após salvar os trechos, a view preenche esses campos a partir do primeiro e do último trecho, para manter o modelo alinhado.

---

## 2) Como ficou a estrutura por trecho

Cada trecho (Ida 1, Ida 2, …, Retorno) é um card com:

- **Cabeçalho:** rótulo (Ida N ou Retorno) e “Origem → Destino”.
- **Corpo:**
  - **Origem** (texto).
  - **Saída — data** (input `type="date"`, `name="trecho_N_saida_date"`).
  - **Saída — hora** (input `type="time"`, `name="trecho_N_saida_time"`).
  - **Destino** (texto).
  - **Chegada — data** (input `type="date"`, `name="trecho_N_chegada_date"`).
  - **Chegada — hora** (input `type="time"`, `name="trecho_N_chegada_time"`).
  - Hidden: `trecho_N_saida_dt` e `trecho_N_chegada_dt` (valor no formato `YYYY-MM-DDTHH:MM` para o backend).

Não existe mais trecho só com “———” ou placeholder sem campo editável: todo trecho gerado já nasce com os quatro inputs (saída data/hora, chegada data/hora) preenchíveis (vazios ou com valor inicial).

---

## 3) Como o JS passou a gerar inputs completos para novos trechos

- **Fonte da estrutura:** sede (nome da cidade de origem) + lista de destinos (nomes na ordem das linhas). A partir disso o JS monta a sequência de trechos: sede → d1, d1 → d2, …, último destino → sede (retorno).

- **Valores iniciais:**  
  - Na **primeira** renderização, os valores vêm de `initialTrechosData` (JSON enviado pelo servidor em `trechos_json`).  
  - Ao **regenerar** (ex.: após adicionar/remover destino), os valores vêm de `readTrechosValuesFromDOM()`: o script lê os inputs atuais de cada card (saída/chegada data e hora), monta `saida_dt`/`chegada_dt` por trecho e usa essa lista ao montar o novo HTML. Assim, trechos já preenchidos mantêm o que o usuário digitou; trechos **novos** (ex.: novo destino) entram com valores vazios mas já com os quatro inputs e os dois hiddens.

- **HTML gerado por trecho:** para cada item da lista de trechos o JS monta um card com `data-trecho-ordem="N"`, os quatro inputs com `name="trecho_N_saida_date"`, `trecho_N_saida_time`, `trecho_N_chegada_date`, `trecho_N_chegada_time`, e os hidden `trecho_N_saida_dt` e `trecho_N_chegada_dt`. Ou seja, todo trecho (incluindo o recém-criado) já nasce com estrutura completa preenchível.

- **Listeners (delegação):** no container dos trechos, `change` e `input` disparam: (1) `syncTrechoHidden(card)` — junta data + hora de cada trecho e atualiza os hidden do mesmo card; (2) se o campo alterado for de saída, `suggestChegada(card)` — se houver duração preenchida, sugere chegada = saída + duração (o usuário pode editar depois).

---

## 4) Como a persistência dos trechos funciona agora

- **Submit:** o formulário envia os hidden `trecho_0_saida_dt`, `trecho_0_chegada_dt`, …, `trecho_K_saida_dt`, `trecho_K_chegada_dt` (K = número de destinos, pois há K trechos de ida + 1 de retorno). O backend já usava `_parse_trechos_times_post` e `_salvar_trechos_roteiro`: continua igual; os trechos são gravados em `RoteiroEventoTrecho` com `saida_dt` e `chegada_dt` por trecho.

- **Pós-save na view:** depois de `_salvar_trechos_roteiro`, a view preenche `roteiro.saida_dt` e `roteiro.retorno_saida_dt` a partir do primeiro e do último trecho (se o último for de retorno), e chama `roteiro.save(update_fields=['saida_dt', 'retorno_saida_dt'])`, mantendo compatibilidade com o modelo.

- **Reabrir edição:** a view monta `trechos_list` com `_estrutura_trechos(roteiro)` (incluindo `saida_dt`/`chegada_dt` dos registros salvos), serializa em `trechos_json` (formato `YYYY-MM-DDT%H:%M` por trecho) e envia para o template. O template define `initialTrechosData` com esse JSON. Na primeira execução de `renderTrechos()`, não há cards no DOM, então `currentValues` usa `initialTrechosData` e cada trecho é desenhado já com os valores salvos nos quatro inputs. Ou seja, ao reabrir, os horários voltam exatamente por trecho, sem sobrescrever com um bloco global.

---

## 5) Como testar manualmente

1. **Bloco global removido**  
   Abrir cadastro ou edição de roteiro. Verificar que **não** aparecem “Saída ida — data”, “Saída ida — hora”, “Chegada ida (calculada)”, “Saída retorno — data”, “Saída retorno — hora”, “Chegada retorno (calculada)”. Só deve existir “3) Duração (apoio)” e “4) Trechos”.

2. **Cada trecho com campos próprios**  
   Com pelo menos um destino, na seção “4) Trechos” deve haver um card por trecho (Ida 1, Retorno, etc.). Em cada card: Origem, **Saída — data**, **Saída — hora**, Destino, **Chegada — data**, **Chegada — hora**, todos editáveis.

3. **Novo destino → novo trecho completo**  
   Clicar em “Adicionar destino”, escolher UF/cidade. Deve surgir um novo trecho de ida (e o retorno ser “último destino → sede”) com os **mesmos** quatro campos (saída data/hora, chegada data/hora) vazios e preenchíveis.

4. **Remover destino**  
   Remover um destino. A lista de trechos deve ser recalculada (menos um trecho de ida; retorno ajustado). Os trechos que permanecem devem manter os valores já preenchidos (lidos do DOM antes de regenerar).

5. **Duração como apoio**  
   Preencher Duração (ex.: 01:30). Em um trecho, preencher Saída — data e Saída — hora. Ao sair do campo (change), a Chegada do mesmo trecho deve ser preenchida com saída + 01:30. Alterar manualmente a chegada deve continuar permitido.

6. **Persistência**  
   Preencher horários em cada trecho, salvar, reabrir a edição. Os horários devem reaparecer em cada card; nenhum bloco global de ida/retorno deve reaparecer.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Bloco global (Saída ida, Saída retorno, Chegadas calculadas) removido da interface | OK |
| Duração permanece como apoio (campo único, texto explicativo) | OK |
| Cada trecho tem origem, saída (data + hora), destino, chegada (data + hora) editáveis | OK |
| Nenhum trecho aparece só com placeholder sem inputs | OK |
| Adicionar destino gera novo trecho já com os 4 inputs (vazios) | OK |
| Remover destino recalcula trechos e preserva valores dos que permanecem | OK |
| Duração + saída de um trecho sugerem chegada; edição manual permitida | OK |
| Salvar persiste horários por trecho; reabrir exibe os valores salvos em cada card | OK |
| Testes: bloco global ausente, container/script, campos por trecho, múltiplos trechos, persistência | OK |

---

## Arquivos alterados

- **`templates/eventos/guiado/roteiro_form.html`**  
  - Removido o bloco “Ida” e “Retorno” (saída ida/retorno data e hora, chegadas calculadas).  
  - Mantido “3) Duração (apoio)” e “4) Trechos”; adicionado `initialTrechosData` via `trechos_json`.  
  - JS: removidas funções e listeners do bloco global (updateChegada, updateRetornoChegada, saida/retorno data/hora).  
  - `renderTrechos()` reescrito: lê valores atuais do DOM ou `initialTrechosData`, monta apenas a partir de sede + destinos, gera para cada trecho um card com os 4 inputs + 2 hidden; chama `attachTrechosListeners()` para sync dos hidden e sugestão de chegada a partir da duração.

- **`eventos/views.py`**  
  - Em `guiado_etapa_2_editar`: construção de `trechos_initial` a partir de `trechos_list` (saida_dt/chegada_dt em `%Y-%m-%dT%H:%M`), envio de `trechos_json` no context.  
  - Após `_salvar_trechos_roteiro`, preenchimento de `roteiro.saida_dt` e `roteiro.retorno_saida_dt` a partir dos trechos salvos e `save(update_fields=[...])`.  
  - Em `guiado_etapa_2_cadastrar`: inclusão de `trechos_json` (lista vazia) no context.

- **`eventos/tests/test_eventos.py`**  
  - `test_bloco_global_ida_retorno_nao_aparece`: garante que os textos do bloco global não aparecem.  
  - `test_trechos_gerados_container_presente`: atualizado para “4) Trechos” e container.  
  - `test_script_trechos_tem_campos_por_trecho`: verifica que o JS gera `_saida_date`, `_saida_time`, `_chegada_date`, `_chegada_time`.  
  - `test_multiplos_destinos_geram_trechos_no_contexto`: múltiplos destinos geram 3+ itens em `context['trechos']`.  
  - `test_salvar_reabrir_mantem_horarios_por_trecho`: salva horários por trecho, reabre e confere persistência e presença em `trechos_json`.

Nenhuma alteração em models ou em `_parse_trechos_times_post` / `_salvar_trechos_roteiro` além do uso já existente dos hidden por trecho.
