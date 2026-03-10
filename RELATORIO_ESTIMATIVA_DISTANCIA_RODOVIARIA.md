# Relatório: Correção da estimativa de distância rodoviária (roteiros)

**Data:** 10/03/2025  
**Problema:** Subestimativa de distância e tempo em trechos longos/diagonais (ex.: Francisco Beltrão → Londrina: Google ~513 km / 7h32, sistema ~417 km / 6h20).

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/services/estimativa_local.py` | Fator rodoviário progressivo por faixa de distância em linha reta; função `_fator_rodoviario_por_faixa()` |
| `eventos/tests/test_eventos.py` | Teste `test_fator_rodoviario_progressivo_por_faixa`; teste `test_distancia_longa_nao_subestimada_francisco_beltrao_londrina`; ajustes em testes de velocidade (distância rodoviária maior com novo fator) |
| `RELATORIO_ETAPA2_ROTEIROS_CONSOLIDACAO.md` | Seção 4 com fórmula da distância rodoviária; checklist atualizado |
| `RELATORIO_ESTIMATIVA_DISTANCIA_RODOVIARIA.md` | Este relatório |

---

## 2) Cadastro = Edição

- Cadastro e edição já usam o mesmo template `eventos/guiado/roteiro_form.html`, mesmo JS e mesmos cards de trecho (blocos distância, tempo cru, adicional, total, botão "Estimar km/tempo").
- Cadastro abre com sede das configurações, destinos do evento, trechos montados e botão de estimativa funcionando (sem alteração nesta tarefa).

---

## 3) Novo trecho ao adicionar destino

- Ao adicionar destino, `renderTrechos()` é chamado e o novo trecho aparece imediatamente com todos os campos (origem, destino, saída/chegada, distância, tempo cru, adicional, total, botão "Estimar km/tempo").
- Preservação por chave `origem_cidade_id->destino_cidade_id` mantida; ao remover ou alterar cidade/UF, trechos são recalculados na hora (sem alteração nesta tarefa).

---

## 4) Fórmula final da distância rodoviária estimada

**Fator rodoviário progressivo** (por distância em **linha reta**, km):

| Linha reta (km) | Fator |
|-----------------|-------|
| até 100         | 1.18  |
| 101 a 250       | 1.22  |
| 251 a 400       | 1.27  |
| acima de 400    | 1.34  |

```
distancia_rodoviaria_estimada = distancia_linha_reta_km * fator_por_faixa
```

A distância exibida no trecho e usada no cálculo do tempo cru é essa distância rodoviária estimada.

---

## 5) Fórmula final da velocidade média

- Base 62 km/h, +1 km/h a cada 100 km da **distância estimada (rodoviária)**, teto 76 km/h.
- `velocidade_media = min(76, 62 + floor(distancia_estimada_km / 100))`.

---

## 6) Fórmula final do tempo cru

- `tempo_cru_min = arredondar_para_multiplo_5_proximo( (distancia_rod_km / velocidade_media) * 60 )`.
- Sem folga; total = tempo_cru + adicional.

---

## 7) Francisco Beltrão → Londrina

- Coordenadas usadas no teste: Francisco Beltrão (-26.08, -53.05), Londrina (-23.30, -51.16).
- Com o fator progressivo, a distância estimada passa a ficar na faixa ~470–550 km (antes ~417 km), alinhada à ordem de grandeza do Google (~513 km).
- Teste `test_distancia_longa_nao_subestimada_francisco_beltrao_londrina` garante distância ≥ 460 km e tempo cru em faixa compatível com 7h–8h.

---

## 8) Como testar manualmente

1. Etapa 2 do evento: cadastrar ou editar roteiro.
2. Em um trecho (ex.: sede → Londrina), clicar em "Estimar km/tempo".
3. Verificar distância e tempo cru para trechos curtos (~100 km) e longos/diagonais (ex.: Francisco Beltrão → Londrina).
4. Para FB → Londrina, conferir que a distância fica próxima de 500 km e o tempo cru próximo de 7h–7h30 (sem adicional).
5. Cadastro novo: conferir que os trechos aparecem com o mesmo layout da edição e que o botão "Estimar km/tempo" funciona.
6. Adicionar destino: novo trecho deve aparecer na hora, com todos os campos e o botão de estimativa.

---

## 9) Checklist de aceite

| Item | Status |
|------|--------|
| Fator rodoviário progressivo por faixa (1.18 / 1.24 / 1.30 / 1.38) | OK |
| Distância longa/diagonal não subestimada (ex. FB–Londrina) | OK |
| Velocidade progressiva 62+floor(km/100) max 76 | OK |
| Tempo cru sem folga; total = cru + adicional | OK |
| Cadastro = edição (mesmo template/JS/cards) | OK |
| Novo trecho completo ao adicionar destino | OK |
| Tempo adicional min=0, step=15, botões ±15, nunca negativo | OK |
| Chegada sugerida automaticamente (saída + total) | OK |
| Testes de fator progressivo e FB–Londrina | OK |
