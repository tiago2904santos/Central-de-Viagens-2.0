# Relatório: Consolidação Etapa 2 (Roteiros) — Evento Guiado

**Data:** 10/03/2025  
**Escopo:** Funcionalidade completa da tela de Roteiros (cadastro = edição, trechos imediatos, velocidade progressiva, tempo cru/adicional, chegada automática)

---

## 1) Arquivos alterados

| Arquivo | Alterações |
|---------|------------|
| `eventos/services/estimativa_local.py` | Fator rodoviário progressivo por faixa; velocidade 62+floor(km/100) max 76; tempo cru sem folga; arredondamento neutro |
| `templates/eventos/guiado/roteiro_form.html` | Preservação de dados por (origem→destino) ao adicionar/remover destino; mesma estrutura para cadastro e edição |
| `eventos/tests/test_eventos.py` | Testes de velocidade progressiva; testes de tempo adicional; teste tempo_cru sem folga atualizado |
| `RELATORIO_ETAPA2_ROTEIROS_CONSOLIDACAO.md` | Este relatório |

---

## 2) Cadastro = Edição (unificação)

**Base única:**
- Cadastro e edição usam o mesmo template: `eventos/guiado/roteiro_form.html`
- Mesmo JS, mesma estrutura de cards de trecho
- Mesmos blocos visuais: Sede, Destinos, Duração (apoio), Trechos, Observações
- Botão "Estimar km/tempo" presente em ambos
- Campos por trecho: origem, destino, saída data/hora, chegada data/hora, distância, tempo cru, tempo adicional, total

**Cadastro novo ao abrir:**
- Sede: `ConfiguracaoSistema.cidade_sede_padrao`
- Destinos: herdados do evento (Etapa 1) via `_destinos_roteiro_para_template(evento)`
- Trechos: montados por `_estrutura_trechos(roteiro_virtual, destinos_list)` com `_build_trechos_initial`
- `initialTrechosData` no JS é populado com a mesma estrutura da edição

**Edição:**
- Sede e destinos do roteiro salvos
- Trechos com dados persistidos (saída, chegada, distância, tempo cru, adicional)
- `initialTrechosData` vem de `trechos_json` (backend)

---

## 3) Trecho ao adicionar destino (imediato)

**Comportamento:**
- Ao clicar "Adicionar destino", `criarRowDestino()` adiciona a linha
- `renderTrechos()` é chamado ao final
- Trechos são recalculados a partir de `getDestinosComCidadeId()`
- Novo trecho aparece com card completo: origem, destino, saída/chegada, distância, tempo cru, adicional, total, botão "Estimar km/tempo"
- Sem necessidade de salvar ou F5

**Preservação de dados:**
- `readTrechosValuesFromDOM()` agora retorna mapa por chave `origem_cidade_id->destino_cidade_id`
- Ao re-renderizar, cada trecho busca seus dados pela chave (origem→destino)
- Trechos equivalentes mantêm saída, chegada, distância, tempo cru, adicional
- Ao remover destino, trechos são recalculados; dados dos trechos que continuam iguais são preservados

---

## 4) Fórmula final da distância rodoviária estimada

**Fator rodoviário progressivo** (por distância em linha reta, km) — régua refinada:

- até 100 km (linha reta) → fator **1.18**
- 101 a 250 km → fator **1.22**
- 251 a 400 km → fator **1.27**
- acima de 400 km → fator **1.34**

```
distancia_rodoviaria_estimada = distancia_linha_reta_km * fator_por_faixa
```

A distância exibida no trecho e usada no tempo cru é essa distância rodoviária estimada (corrige subestimativa em rotas longas/diagonais, ex.: Francisco Beltrão → Londrina).

---

## 5) Fórmula final da velocidade média

```
velocidade_media = min(76, 62 + floor(distancia_estimada_km / 100))
```

**Faixas:**
- 0–99 km → 62 km/h
- 100–199 km → 63 km/h
- 200–299 km → 64 km/h
- 300–399 km → 65 km/h
- 400–499 km → 66 km/h
- 500–599 km → 67 km/h
- 600–699 km → 68 km/h
- 700–799 km → 69 km/h
- 800–899 km → 70 km/h
- 900–999 km → 71 km/h
- 1000–1099 km → 72 km/h
- 1100–1199 km → 73 km/h
- 1200–1299 km → 74 km/h
- 1300–1399 km → 75 km/h
- 1400 km ou mais → 76 km/h (teto)

---

## 6) Fórmula final do tempo cru

```
tempo_cru_min = arredondar_para_multiplo_5_proximo( (distancia_km / velocidade_media) * 60 )
```

- Usa velocidade progressiva acima
- Sem folga, margem ou fator extra

---

## 7) Regra final do arredondamento

**Múltiplo de 5 mais próximo (neutro):**
- 6h02 (362 min) → 360 min (6h00)
- 6h03 (363 min) → 365 min (6h05)
- 6h07 (367 min) → 365 min (6h05)
- 6h08 (368 min) → 370 min (6h10)

Implementado em `arredondar_para_multiplo_5_proximo()`.

---

## 8) Regra final do adicional

- Campo separado, ajuste operacional (trânsito, parada, almoço, etc.)
- Aceita 0
- Nunca fica negativo (clamp no frontend e backend)
- Sem faixa indevida (6–21 removida)
- Input: `min="0"`, `step="15"`, sem `max` rígido
- Botões -15 / +15: nunca abaixo de 0
- Total = tempo_cru + tempo_adicional

---

## 9) Chegada automática

- `suggestChegada(card)` usa saída (data+hora) + tempo total do trecho
- Chamada em: change da saída, change do tempo adicional, atualizarTempoTotalCard
- Chegada permanece editável manualmente
- Ao alterar saída ou adicional, a chegada é recalculada (sugerida)
- `getTempoTotalMin(card)` usa `data-tempo-total-min` do card; se 0, usa duração global (HH:MM) como fallback

---

## 10) Como testar manualmente

1. **Cadastro = Edição**
   - Etapa 1: criar evento com 1+ destinos
   - Etapa 2: Cadastrar roteiro → verificar cards de trechos com sede e destinos
   - Editar roteiro → mesma estrutura e campos

2. **Adicionar destino**
   - Com 1 destino: ida + retorno
   - Clicar "Adicionar destino", escolher cidade → novo trecho deve aparecer sem salvar/F5

3. **Remover destino**
   - Com 2 destinos: ida1, ida2, retorno
   - Remover o segundo → ficar ida1, retorno; dados da ida1 preservados

4. **Velocidade progressiva**
   - Estimar km/tempo em trechos de diferentes distâncias
   - Conferir tempo cru coerente com a faixa (64–76 km/h conforme distância)

5. **Tempo adicional**
   - Usar 0, +15, -15
   - Confirmar que não fica negativo
   - Verificar total = cru + adicional

6. **Chegada automática**
   - Preencher saída data/hora e tempo total
   - Chegada deve ser sugerida
   - Editar chegada manualmente e confirmar que permanece

7. **Persistência**
   - Salvar roteiro com trechos preenchidos
   - Reabrir → dados iguais (saída, chegada, distância, cru, adicional)

---

## 11) Checklist de aceite

| Item | Status |
|------|--------|
| Cadastro e edição usam mesma base funcional | OK |
| Cadastro mostra mesmos cards da edição | OK |
| Cadastro tem botão de estimativa | OK |
| Adicionar destino cria trecho novo completo imediatamente | OK |
| Remover destino recalcula trechos imediatamente | OK |
| Alterar destino atualiza trechos imediatamente | OK |
| Fator rodoviário progressivo (1.18/1.24/1.30/1.38) | OK |
| Distância longa/diagonal não subestimada (ex. FB–Londrina) | OK |
| Velocidade progressiva 62+floor(km/100) max 76 | OK |
| 0-99 km usa 62 km/h | OK |
| 100-199 km usa 63 km/h | OK |
| 300 km usa 65 km/h | OK |
| 600 km usa 68 km/h | OK |
| 1000 km usa 72 km/h | OK |
| 1400 km ou mais teto 76 km/h | OK |
| Tempo cru sem folga embutida | OK |
| Arredondamento múltiplo de 5 mais próximo | OK |
| Total = cru + adicional | OK |
| Adicional aceita 0 | OK |
| Adicional não fica preso a faixa inválida | OK |
| Botões +15 e -15 funcionam | OK |
| Adicional nunca fica negativo | OK |
| Chegada sugerida automaticamente | OK |
| Salvar e reabrir preserva tudo | OK |
