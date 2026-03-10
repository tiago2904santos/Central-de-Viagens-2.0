# Relatório — Cálculo de duração/chegada dos roteiros e atualização imediata dos trechos

## 1) Arquivos alterados

| Arquivo | Alterações |
|---------|------------|
| `eventos/services/estimativa_local.py` | Helpers `arredondar_minutos_para_cima_5` e `minutos_para_hhmm`; régua de folga por faixa; duração com arredondamento 5 em 5 min. |
| `eventos/views.py` | `_parse_trechos_times_post` passa a retornar lista de dicts (saída, chegada, distancia_km, duracao_estimada_min); `_salvar_trechos_roteiro` persiste distância e duração por trecho; `_build_trechos_initial` inclui `duracao_estimada_min`. |
| `templates/eventos/guiado/roteiro_form.html` | `getDestinosNomes()` considera todas as linhas (trecho novo ao adicionar destino); `suggestChegada()` usa duração do trecho (`data-duracao-min`) ou global; hidden `trecho_N_distancia_km` e `trecho_N_duracao_estimada_min`; cards com `data-duracao-min`; atualização dos hidden após "Estimar km/tempo". |
| `eventos/tests/test_eventos.py` | Testes de arredondamento 5 min; folga por faixa; duração múltiplo de 5; ajuste do teste do endpoint (módulo 5). |

---

## 2) Helpers criados para arredondamento/folga

- **`arredondar_minutos_para_cima_5(minutos)`**  
  Arredonda para cima em blocos de 5 minutos.  
  Ex.: 153 → 155, 156 → 160, 361 → 365.

- **`minutos_para_hhmm(minutos)`**  
  Já existia; mantido. Converte minutos em string `HH:MM`.

- **`_folga_por_faixa_minutos(minutos_base)`** (interno):  
  - até 45 min → +15 min  
  - 46 min até 2h30 → +30 min  
  - 2h31 até 4h30 → +30 min  
  - 4h31 até 8h30 → +45 min  
  - acima de 8h30 → +45 min  

---

## 3) Regra final implementada (estimativa local)

1. Duração base = (distância rodoviária / 65 km/h) em minutos.  
2. Arredondar a base para cima em blocos de 5 min.  
3. Aplicar a folga conforme a faixa acima.  
4. Arredondar o total (base + folga) para cima em blocos de 5 min.  

Exemplo: base 2h33 → base arredondada 2h35 → folga +30 → total 3h05.

---

## 4) Como o auto-preenchimento de chegada funciona

- Cada trecho pode ter **duração estimada** (do “Estimar km/tempo” ou vinda do backend).  
- A duração do trecho fica em **`data-duracao-min`** no card.  
- Ao alterar **saída (data ou hora)** de um trecho, o script chama `suggestChegada(card)`:  
  - usa `data-duracao-min` do card, se existir;  
  - senão usa a duração global (campo HH:MM do formulário).  
- Calcula **chegada = saída + duração** e preenche data e hora de chegada (editáveis).  
- Os campos de chegada continuam editáveis; o usuário pode alterar manualmente.  
- Se o usuário clicar em “Estimar km/tempo”, a duração do trecho é atualizada e o `data-duracao-min` do card também; a próxima mudança de saída usará essa duração para sugerir a chegada.

---

## 5) Como o bug de adicionar destino foi corrigido

- **Antes:** `getDestinosNomes()` só considerava linhas com cidade selecionada. Ao clicar em “Adicionar destino”, a nova linha (sem cidade) não entrava na lista e os trechos não eram recriados.  
- **Agora:** `getDestinosNomes()` devolve **uma entrada por linha** de destino: nome da cidade se houver, ou `"—"` se a linha estiver vazia.  
- Assim, ao adicionar uma nova linha:  
  - a lista de “destinos” tem um item a mais (com nome `"—"`);  
  - `renderTrechos()` é chamado (já era chamado ao adicionar linha);  
  - a estrutura de trechos é montada de novo (N idas + 1 retorno);  
  - o novo trecho de ida e o retorno atualizado aparecem **na hora**, sem F5.  
- Ao **remover** um destino, há uma linha a menos, `renderTrechos()` roda de novo e os trechos são reduzidos.  
- Ao **alterar UF/cidade** de um destino, os listeners já chamam `renderTrechos()`, e a preservação por índice mantém os valores já preenchidos nos trechos equivalentes.

---

## 6) Como testar manualmente

1. **Arredondamento e folga**  
   - Em um roteiro com trecho (sede → cidade com coordenadas), clicar em “Estimar km/tempo”.  
   - Verificar que “Tempo estimado” aparece em múltiplos de 5 min (ex.: 2h35, 3h05).  

2. **Auto-preenchimento da chegada**  
   - Preencher “Saída — data” e “Saída — hora” de um trecho que já tenha duração (após “Estimar km/tempo” ou vindo do servidor).  
   - Verificar que “Chegada — data” e “Chegada — hora” são preenchidos automaticamente.  
   - Alterar a chegada manualmente e conferir que o valor permanece.  

3. **Adicionar destino → trecho na hora**  
   - Abrir cadastro/edição de roteiro com pelo menos um destino já preenchido.  
   - Clicar em “Adicionar destino”.  
   - Verificar que surge **na hora** um novo bloco de trecho (ida) e que o retorno segue correto, sem dar F5.  

4. **Remover destino**  
   - Remover um destino (deixando ao menos um).  
   - Verificar que a lista de trechos é atualizada na hora (um trecho de ida a menos e o retorno ajustado).  

5. **Salvar e reabrir**  
   - Preencher saída/chegada (e, se quiser, usar “Estimar km/tempo”) em cada trecho.  
   - Salvar.  
   - Reabrir o roteiro e conferir que horários e duração/distância por trecho permanecem.

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Arredondamento para cima em blocos de 5 min | OK |
| Régua de folga por faixa (até 45min +15; 46–2h30 +30; etc.) | OK |
| Duração estimada final em múltiplos de 5 min | OK |
| Chegada preenchida automaticamente a partir da saída + duração do trecho | OK |
| Chegada editável manualmente | OK |
| Adicionar destino faz o novo trecho aparecer imediatamente | OK |
| Remover destino recalcula trechos imediatamente | OK |
| Alterar cidade/UF do destino atualiza trechos imediatamente | OK |
| Preservar valores ao regenerar trechos (por índice) | OK |
| Persistir saída, chegada, distância e duração por trecho ao salvar | OK |
| Reabrir edição mostra dados salvos por trecho | OK |
| Testes: arredondamento 5 min, folga por faixa, duração múltiplo 5, salvar/reabrir | OK |
