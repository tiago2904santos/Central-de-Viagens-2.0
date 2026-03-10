# Relatório: Ajuste fino do fator rodoviário (estimativa local)

**Data:** 10/03/2025  
**Escopo:** Apenas a régua do fator rodoviário por faixa; sem alterar velocidade, tempo adicional, chegada automática ou layout.

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/services/estimativa_local.py` | Constantes `FATOR_101_250_KM`, `FATOR_251_400_KM`, `FATOR_ACIMA_400_KM` e docstrings da régua |
| `eventos/tests/test_eventos.py` | Testes `test_fator_rodoviario_progressivo_por_faixa`, `test_velocidade_600_km_usar_68`, `test_velocidade_1000_km_usar_72`, `test_distancia_longa_nao_subestimada_francisco_beltrao_londrina` ajustados para a nova régua |
| `RELATORIO_ETAPA2_ROTEIROS_CONSOLIDACAO.md` | Tabela do fator rodoviário atualizada |
| `RELATORIO_ESTIMATIVA_DISTANCIA_RODOVIARIA.md` | Tabela do fator atualizada |
| `RELATORIO_AJUSTE_FINO_FATOR_RODOVIARIO.md` | Este relatório |

---

## 2) Função alterada

**`_fator_rodoviario_por_faixa(linha_reta_km: float) -> Decimal`** em `eventos/services/estimativa_local.py`.

Só mudaram os valores retornados por faixa; a lógica (limites 100, 250, 400 km) permanece.

---

## 3) Nova régua final

| Distância em linha reta (km) | Fator | Antes |
|------------------------------|-------|-------|
| até 100                      | **1.18** | 1.18 |
| 101 a 250                    | **1.22** | 1.24 |
| 251 a 400                    | **1.27** | 1.30 |
| acima de 400                 | **1.34** | 1.38 |

Fórmula: `distancia_rodoviaria_estimada = distancia_linha_reta_km * fator_por_faixa`.

---

## 4) Exemplos reais impactados

- **Curitiba → Pontal do Paraná:** trecho curto; faixa até 100 km (1.18) inalterada → mantido razoável.
- **Londrina → Curitiba:** distância rodoviária estimada reduzida (faixas 101–250 e 251–400 com fatores menores) → menor superestimação.
- **Pontal do Paraná → Francisco Beltrão:** idem; fatores 1.22 e 1.27 reduzem um pouco a estimativa em relação à régua anterior.
- **Francisco Beltrão → Londrina:** continua na faixa aceitável (~450–470 km com 1.27 para ~370 km em linha reta), sem subestimar como no cenário antigo (~417 km).

---

## 5) Checklist de aceite

| Item | Status |
|------|--------|
| Fator até 100 km = 1.18 | OK |
| Fator 101–250 km = 1.22 | OK |
| Fator 251–400 km = 1.27 | OK |
| Fator acima de 400 km = 1.34 | OK |
| Testes de faixa passando | OK |
| Rotas longas não infladas como antes | OK |
| Velocidade progressiva não alterada | OK |
| Tempo adicional / chegada / layout não alterados | OK |
| Relatório técnico da estimativa atualizado | OK |
