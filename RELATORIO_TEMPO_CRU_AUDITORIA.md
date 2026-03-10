# Relatório — Auditoria e Correção da Lógica de Tempo dos Trechos

## 1) Onde estava o erro

**Auditoria realizada:**
- O tempo cru em `estimativa_local.py` **já estava correto** em princípio: era calculado como `(distância / velocidade) * 60` arredondado para cima em blocos de 5 min, sem folga embutida.
- **Problemas encontrados:**
  1. **Total com arredondamento extra**: O total era calculado como `arredondar_minutos_para_cima_5(cru + folga)`, o que podia divergir da soma exata (ex.: cru=372, adicional=30 → soma 402, mas arredondado 405). O usuário exige `total = cru + adicional` (soma exata).
  2. **Velocidade alta demais**: 75 km/h deixava a estimativa rápida demais, tornando o tempo cru menor que o esperado na prática.
  3. **Documentação pouco clara**: A separação cru/adicional/total não estava explícita e sem risco de confusão.

---

## 2) Fórmula final do tempo cru

```
tempo_cru = arredondar_para_cima_5( (distância_rodoviária_km / VELOCIDADE_MEDIA_KMH) * 60 )
```

Onde:
- `distância_rodoviária_km` = linha_reta_km × 1.15
- `arredondar_para_cima_5` = arredondar para cima em blocos de 5 minutos

**O tempo cru NÃO contém:**
- Folga
- Margem extra
- Fator conservador além da velocidade média
- Qualquer parcela do adicional

---

## 3) Fórmula final do total

```
total = tempo_cru + tempo_adicional
```

Soma exata, **sem arredondamento adicional** no total.

---

## 4) Velocidade média final adotada

**68 km/h**

- **Motivo**: A velocidade anterior (75 km/h) gerava estimativas curtas demais comparadas à realidade (Google Maps, relatos). Com 68 km/h, o tempo cru aumenta e aproxima melhor viagens reais em rodovias.
- **Alternativas consideradas**: 70 km/h também é coerente; 68 km/h foi escolhido por ser mais conservador e evitar subestimar o tempo.

---

## 5) Confirmação de que o cru não tem folga embutida

- O tempo cru usa **apenas**:
  1. Distância estimada (haversine × 1.15)
  2. Velocidade média base (68 km/h)
  3. Arredondamento para cima em blocos de 5 minutos

- A folga vai **sempre** para `tempo_adicional_sugerido_min` (campo adicional).
- Teste `test_tempo_cru_nao_contem_folga` garante que tempo_cru = `(distância / velocidade) * 60` arredondado e que `total = cru + adicional`.

---

## 6) Exemplos reais

### Exemplo 1: Curitiba → Maringá
| Campo       | Valor                         |
|------------|-------------------------------|
| Distância  | 402,26 km                     |
| Tempo cru  | 355 min (5h55)               |
| Adicional  | 45 min                        |
| Total      | 400 min (6h40)               |

*(cru 355 + adicional 45 = 400)*

### Exemplo 2: ~100 km em linha reta (~115 km rodoviário)
| Campo       | Valor                         |
|------------|-------------------------------|
| Distância  | 115,2 km                      |
| Tempo cru  | 105 min (1h45)               |
| Adicional  | 15 min                        |
| Total      | 120 min (2h00)               |

*(cru 105 + adicional 15 = 120)*

---

## 7) Arquivos alterados

| Arquivo                             | Alteração                                                                 |
|-------------------------------------|---------------------------------------------------------------------------|
| `eventos/services/estimativa_local.py` | VELOCIDADE_MEDIA_KMH 75→68; total = cru + adicional (soma exata); docstrings e comentários atualizados. |
| `eventos/tests/test_eventos.py`     | Novos/ajustes: `test_tempo_cru_nao_contem_folga`, `test_total_igual_cru_mais_adicional_na_estimativa`, `test_velocidade_media_68_kmh`, `test_tempo_cru_multiplo_5_minutos`; `test_duracao_estimada_multiplo_5` removido; TrechoCalcularKmEndpointTest passa a verificar tempo_cru múltiplo de 5. |

---

## 8) UI e comportamento (verificado)

- Na tela de trechos: tempo cru, adicional, total, botões -15/+15, chegada recalculada.
- Ao alterar o adicional: só o total muda; o cru permanece inalterado.
- O cru só muda quando origem, destino ou parâmetros reais do cálculo mudam (ex.: nova estimativa).
- A chegada usa `getTempoTotalMin(card)` = cru + adicional (total).

---

## 9) Checklist de aceite

| Item                                              | Status |
|---------------------------------------------------|--------|
| Tempo cru não contém folga                         | OK     |
| Total = cru + adicional                            | OK     |
| Adicional altera total sem alterar cru             | OK     |
| Velocidade média base 68 km/h em uso               | OK     |
| Arredondamento de 5 em 5 no tempo cru              | OK     |
| Chegada recalculada pelo total                     | OK     |
| Testes atualizados e passando                      | OK     |
