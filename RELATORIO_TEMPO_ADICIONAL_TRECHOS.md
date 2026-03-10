# Relatório: Correção do Campo Tempo Adicional dos Trechos

**Data:** 09/03/2025  
**Escopo:** Campo "Tempo adicional" nos trechos dos roteiros

---

## 1) Causa real do bug

A restrição indevida (ex.: valores entre 6–21 minutos) não foi encontrada como validação explícita no código. O comportamento problemático provavelmente tinha origem em:

- **Input HTML**: `min="-999" max="999"` permitia valores negativos, gerando inconsistência com a regra de negócio (ajuste operacional ≥ 0).
- **Botões -15/+15**: O botão `-15` permitia resultados negativos (`v - 15` sem limite mínimo).
- **Ausência de clamp**: Nem o frontend nem o backend garantiam que o valor fosse sempre ≥ 0.
- **Possível confusão**: O campo `id_duracao_hhmm` (`type="time"`) usa HH:MM; valores como `00:06` e `00:21` podem ter sido interpretados como restrições indevidas ao “tempo adicional”.

---

## 2) Arquivos alterados

| Arquivo | Alterações |
|---------|------------|
| `templates/eventos/guiado/roteiro_form.html` | Input adicional, botões -15/+15, `atualizarTempoTotalCard`, montagem inicial e resposta à API |
| `eventos/views.py` | `_parse_trechos_times_post`: clamp `tempo_adicional_min >= 0` |
| `eventos/tests/test_eventos.py` | Novos testes: aceita 0, negativo clampeado, sem restrição absurda |
| `RELATORIO_TEMPO_ADICIONAL_TRECHOS.md` | Este relatório |

---

## 3) Input do adicional

**Antes:**
```html
<input type="number" ... min="-999" max="999" step="15" placeholder="0">
```

**Depois:**
```html
<input type="number" ... min="0" step="15" placeholder="0" title="Ajuste operacional em minutos (0 ou mais)">
```

- `min="0"`: impede valores negativos na validação HTML5
- `max` removido: sem limite superior arbitrário
- `step="15"`: incrementos de 15 minutos
- `title`: ajuda a explicar o campo

---

## 4) Botões +15 / -15

**Antes:**
```javascript
var v = parseInt(inp.value, 10) || 0;
inp.value = btnMenos ? (v - 15) : (v + 15);
```

**Depois:**
```javascript
var v = Math.max(0, parseInt(inp.value, 10) || 0);
inp.value = btnMenos ? Math.max(0, v - 15) : (v + 15);
```

- `-15`: nunca reduz abaixo de 0
- `+15`: soma 15 minutos
- Leitura do input com `Math.max(0, ...)` para evitar valores negativos vindos de digitação

---

## 5) Garantias contra restrições indevidas

- Não há validação que limite o tempo adicional à faixa 6–21.
- Input aceita 0 e qualquer valor ≥ 0.
- Backend usa `max(0, int(tempo_adic))` ao interpretar o POST.
- Em `atualizarTempoTotalCard`, o valor é clampeado e o input corrigido quando negativo.
- O valor sugerido pela API é normalizado com `Math.max(0, ...)`.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Adicional aceita 0 | OK |
| Botão +15 funciona | OK |
| Botão -15 funciona | OK |
| Adicional nunca fica negativo | OK |
| total = cru + adicional | OK |
| Sem restrição indevida (ex.: 6..21) | OK |
| Input com min=0, step=15, sem max estranho | OK |
| Backend valida/clamp adicional ≥ 0 | OK |
| Testes automatizados | OK |

---

## Testes adicionados

1. **test_tempo_adicional_aceita_zero** – POST com `tempo_adicional_min=0`; total = cru + 0.
2. **test_tempo_adicional_negativo_clamped_para_zero** – POST com valor negativo; salvo como 0.
3. **test_tempo_adicional_sem_restricao_absurda** – POST com 60 minutos; aceito e salvo corretamente.
