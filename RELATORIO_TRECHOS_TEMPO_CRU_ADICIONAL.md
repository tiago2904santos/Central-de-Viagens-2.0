# Relatório — Tempo cru, adicional e final nos trechos dos roteiros

## 1) Arquivos alterados

| Arquivo | Alterações |
|---------|------------|
| `eventos/services/estimativa_local.py` | Retorno de `tempo_cru_estimado_min` e `tempo_adicional_sugerido_min` em `estimar_distancia_duracao`. |
| `eventos/models.py` | Campos `tempo_cru_estimado_min` e `tempo_adicional_min` em `RoteiroEventoTrecho`; propriedade `tempo_total_final_min`. |
| `eventos/migrations/0008_add_tempo_cru_adicional_trecho.py` | Migração que adiciona os novos campos. |
| `eventos/views.py` | `_estrutura_trechos` inclui tempo_cru e tempo_adicional; `_build_trechos_initial` envia esses valores; `_parse_trechos_times_post` lê do POST; `_salvar_trechos_roteiro` persiste; `trecho_calcular_km` grava e retorna tempo_cru e tempo_adicional. |
| `templates/eventos/guiado/roteiro_form.html` | UI com tempo cru (somente leitura), tempo adicional (editável), tempo total (calculado), botões -15 e +15; `atualizarTempoTotalCard`; `getTempoTotalMin`; listeners para tempo adicional e botões. |
| `eventos/tests/test_eventos.py` | Testes para persistência de tempo_cru/adicional, `tempo_total_final_min`, botões ±15 e endpoint retornando tempo_cru/adicional. |

---

## 2) Model / Form / Template / JS alterados

### Model (`RoteiroEventoTrecho`)
- **`tempo_cru_estimado_min`** (PositiveIntegerField, null=True): tempo base da viagem (estimativa local).
- **`tempo_adicional_min`** (IntegerField, null=True, default=0): folga editável pelo usuário.
- **`tempo_total_final_min`** (propriedade): `tempo_cru_estimado_min + tempo_adicional_min`; fallback para `duracao_estimada_min` quando não houver cru/adicional.

### Form
- Sem alterações. Campos de trecho são tratados via POST e não fazem parte do `ModelForm` principal.

### Template / JS
- **Tempo cru**: exibido em `<span class="trecho-tempo-cru">` (somente leitura).
- **Tempo adicional**: `<input type="number" class="trecho-tempo-adicional">` com step 15, min -999, max 999.
- **Botões -15 e +15**: alteram o tempo adicional e disparam `atualizarTempoTotalCard`.
- **Tempo total**: `<span class="trecho-tempo-total">` calculado (somente leitura).
- **`atualizarTempoTotalCard(card)`**: recalcula total = cru + adicional, atualiza span, `data-tempo-total-min`, hidden `duracao_estimada_min` e chama `suggestChegada`.
- **`getTempoTotalMin(card)`**: usa `data-tempo-total-min` se > 0; senão usa a duração global (campo HH:MM).
- **Chegada**: calculada com base em saída + tempo total (cru + adicional) quando disponível.

---

## 3) Lógica do tempo cru / adicional / final

1. **Tempo cru**: vem da estimativa local (tempo base arredondado em 5 min, sem folga).  
2. **Tempo adicional sugerido**: folga por faixa (até 45min +15; 46min–2h30 +30; etc.).  
3. **Fórmula**: `tempo_total_final = tempo_cru_estimado_min + tempo_adicional_min`.  
4. **Fluxo**:  
   - Usuário clica em "Estimar km/tempo" → API retorna `tempo_cru` e `tempo_adicional_sugerido`; o frontend preenche os campos e o total.  
   - Usuário pode alterar o tempo adicional (input ou botões ±15).  
   - Ao mudar tempo adicional ou saída, a chegada é recalculada automaticamente.  
   - Chegada permanece editável manualmente.

---

## 4) Como testar manualmente

1. **Tempo cru, adicional e total**
   - Criar/editar roteiro com trecho (sede → cidade com coordenadas).
   - Clicar em "Estimar km/tempo".
   - Conferir: tempo cru (ex.: 2h35), tempo adicional sugerido (ex.: 30 min) e tempo total (ex.: 3h05).

2. **Botões ±15**
   - Com tempo adicional em 30, clicar em +15 → passa a 45; total atualiza.
   - Clicar em -15 → volta a 30.
   - Verificar que o total sempre é cru + adicional.

3. **Chegada**
   - Preencher saída (data e hora) em um trecho com tempo total definido.
   - Chegada deve ser preenchida automaticamente.
   - Alterar tempo adicional (ex.: +15) e confirmar que a chegada é recalculada.
   - Editar a chegada manualmente e garantir que o valor persiste.

4. **Novo trecho ao adicionar destino**
   - Adicionar um destino.
   - Verificar que o novo trecho aparece imediatamente, com campos de tempo cru, adicional e total (vazios até usar "Estimar km/tempo").

5. **Salvar e reabrir**
   - Preencher tempo adicional (ou deixar o sugerido), saída e chegada.
   - Salvar.
   - Reabrir o roteiro e conferir que tempo cru, adicional, total e horários permanecem.

---

## 5) Checklist de aceite

| Item | Status |
|------|--------|
| Model com tempo_cru_estimado_min e tempo_adicional_min | OK |
| Fórmula tempo_total = cru + adicional | OK |
| Tempo cru vindo da estimativa local | OK |
| Tempo adicional sugerido automaticamente (folga) | OK |
| Tempo adicional editável | OK |
| Botões -15 e +15 por trecho | OK |
| Chegada preenchida com base em saída + tempo total | OK |
| Chegada recalculada ao alterar tempo adicional | OK |
| Chegada editável manualmente | OK |
| Novo trecho ao adicionar destino aparece imediatamente com todos os campos | OK |
| Remover destino recalcula trechos imediatamente | OK |
| Salvar e reabrir preserva os valores | OK |
| Testes: tempo_total = cru + adicional | OK |
| Testes: botões ±15 presentes | OK |
| Testes: persistência de tempo_cru e tempo_adicional | OK |
