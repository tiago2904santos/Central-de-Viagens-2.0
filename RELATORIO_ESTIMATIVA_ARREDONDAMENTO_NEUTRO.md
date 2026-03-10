# Relatório — Estimativa: Arredondamento Neutro e Adicional Inicial Zero

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/services/estimativa_local.py` | Novo helper `arredondar_para_multiplo_5_proximo`; tempo cru usa arredondamento neutro; VELOCIDADE_MEDIA_KMH = 65; adicional sugerido = 0; removida `_folga_por_faixa_minutos`. |
| `eventos/tests/test_eventos.py` | Novo `test_arredondamento_multiplo_5_proximo`; removido `test_folga_por_faixa_regua`; `test_tempo_cru_nao_contem_folga` usa novo helper; `test_velocidade_media_65_kmh`; novo `test_adicional_inicial_zero`. |

---

## 2) Helper novo de arredondamento

```python
def arredondar_para_multiplo_5_proximo(minutos: Union[int, float]) -> int:
    """
    Arredonda para o múltiplo de 5 minutos mais próximo (arredondamento neutro).
    Ex.: 362 (6h02) -> 360 (6h00); 363 (6h03) -> 365 (6h05); 367 (6h07) -> 365 (6h05); 368 (6h08) -> 370 (6h10).
    """
    if minutos is None or (isinstance(minutos, (int, float)) and minutos <= 0):
        return 0
    m = float(minutos)
    return int(round(m / 5) * 5)
```

---

## 3) Fórmula final do tempo cru

```
tempo_cru = arredondar_para_multiplo_5_proximo( (distância_rodoviária_km / 65) * 60 )
```

- Distância rodoviária = linha_reta_km × 1.15
- Velocidade média base: 65 km/h
- Arredondamento: múltiplo de 5 mais próximo (não mais "sempre para cima")

O tempo cru **não** contém folga nem margem.

---

## 4) Regra final do adicional inicial

**Adicional sugerido inicial = 0**

O usuário ajusta manualmente o adicional com os botões +15 e -15. O campo adicional continua sendo a única camada de ajuste operacional. Não há mais folga automática por faixa.

---

## 5) Exemplos de entrada/saída do arredondamento

| Entrada (min) | Saída (min) |
|---------------|-------------|
| 362 (6h02) | 360 (6h00) |
| 363 (6h03) | 365 (6h05) |
| 367 (6h07) | 365 (6h05) |
| 368 (6h08) | 370 (6h10) |
| 372 | 370 |
| 377 | 375 |

---

## 6) Exemplo real: Curitiba → Maringá

| Campo | Valor |
|-------|-------|
| Distância | 402,26 km |
| Tempo cru | 370 min (6h10) |
| Adicional | 0 min |
| Total | 370 min (6h10) |

*(Com arredondamento sempre para cima, o cru seria ~375 min. Com arredondamento neutro, 370 min.)*

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Arredondamento para múltiplo de 5 mais próximo | OK |
| Tempo cru baseado em 65 km/h | OK |
| Tempo cru sem folga embutida | OK |
| Total = cru + adicional | OK |
| Chegada usa total | OK |
| Adicional altera total sem alterar cru | OK |
| Adicional inicial = 0 | OK |
| Botões ±15 continuam funcionando | OK |
| Testes passando | OK |
