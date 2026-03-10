# Relatório — Etapa 2: Perfil de rota, adicional sugerido e redirecionamento

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/services/estimativa_local.py` | Perfis de rota (`classificar_perfil_rota`, `_adicional_sugerido_por_perfil`, `_no_quadrado_litoral_pr`); adicional sugerido 15/30/45 por perfil; retorno `perfil_rota` na estimativa. |
| `eventos/views.py` | Redirect pós-salvar roteiro novo: de `guiado-etapa-2-editar` para `guiado-etapa-2` (lista). Resposta JSON dos endpoints de estimativa passa a incluir `perfil_rota`. |
| `eventos/tests/test_eventos.py` | Testes de perfil, adicional sugerido e redirect; ajuste de `test_adicional_inicial_zero` para `test_adicional_sugerido_nao_zero_por_perfil`; assert de redirect em `test_cadastro_novo_persistir_trechos_conforme_formulario`. |

---

## 2) Heurística e perfis implementados

### Perfis

- **EIXO_PRINCIPAL** — rota longa e mais reta (razão rodoviária/linha_reta baixa).
- **DIAGONAL_LONGA** — rota longa e torta/diagonal (razão alta).
- **LITORAL_SERRA** — um dos extremos na região aproximada do litoral/serra paranaense.
- **PADRAO** — demais casos.

### Heurísticas (em ordem de aplicação)

1. **LITORAL_SERRA**  
   - Um dos pontos em “quadrado” aproximado do litoral PR:  
     lat ∈ [-26.2, -25.0], lon ∈ [-48.95, -48.2].  
   - Distância em linha reta ≥ 50 km.  
   - Avaliado primeiro; se bater, retorna LITORAL_SERRA.

2. **DIAGONAL_LONGA**  
   - Distância em linha reta ≥ 250 km.  
   - Razão = distância_rodoviária / distância_linha_reta ≥ 1,25.  
   - Indica rota longa e torta/diagonal.

3. **EIXO_PRINCIPAL**  
   - Distância em linha reta ≥ 150 km.  
   - Razão ≤ 1,21.  
   - Indica rota longa e mais reta.

4. **PADRAO**  
   - Qualquer caso que não se enquadre nos anteriores.

A função `classificar_perfil_rota(origem_lat, origem_lon, destino_lat, destino_lon, distancia_linha_reta_km, distancia_rodoviaria_km)` retorna uma dessas constantes.  
O perfil **não** altera distância nem tempo cru; é usado **apenas** para definir o tempo adicional sugerido.

---

## 3) Como o perfil afeta a sugestão do adicional

| Perfil / faixa de distância | Adicional sugerido (min) |
|-----------------------------|---------------------------|
| Qualquer perfil, distância rodoviária &lt; 250 km | 15 |
| Distância ≥ 250 km e perfil PADRAO ou EIXO_PRINCIPAL | 30 |
| Distância ≥ 250 km e perfil DIAGONAL_LONGA ou LITORAL_SERRA | 45 |

Regra implementada em `_adicional_sugerido_por_perfil(perfil, distancia_rodoviaria_km)`.

---

## 4) Regra final do adicional sugerido automático

- **Trechos curtos** (&lt; 100 km rod): **15 min**.  
- **Trechos médios** (100–250 km rod): **15 min**.  
- **Trechos longos** (≥ 250 km rod):  
  - **30 min** se perfil PADRAO ou EIXO_PRINCIPAL;  
  - **45 min** se perfil DIAGONAL_LONGA ou LITORAL_SERRA.

O valor é apenas sugestão inicial: o usuário pode alterar (digitação, botões +15 / -15).  
Total continua: **total = tempo_cru + tempo_adicional**.  
A chegada sugerida usa esse adicional (cru + sugerido).

---

## 5) Redirecionamento ao salvar roteiro novo

- **Antes:** ao salvar em “Cadastrar novo roteiro”, o sistema redirecionava para a **edição** do roteiro recém-criado (`guiado-etapa-2-editar`).  
- **Agora:** ao salvar um roteiro **novo**, o redirect vai para a **lista da Etapa 2** do evento (`guiado-etapa-2`), ou seja, a tela da etapa 2 / lista de roteiros.  
- **Edição:** ao salvar na edição de um roteiro existente, o redirect continua para a lista da Etapa 2 (já era assim).

Alteração em `eventos/views.py`, em `guiado_etapa_2_cadastrar`:  
`return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)`.

---

## 6) Como testar manualmente

1. **Perfil e adicional sugerido**  
   - Abrir evento guiado → Etapa 2 → Cadastrar novo roteiro (ou editar um existente).  
   - Em um trecho, clicar em “Estimar km/tempo”.  
   - Verificar: distância, tempo cru, **tempo adicional** preenchido (15, 30 ou 45 conforme perfil/distância).  
   - Trecho curto (ex.: sede → cidade próxima): esperar 15 min.  
   - Trecho longo “reto” (ex.: eixo principal): esperar 30 min.  
   - Trecho longo diagonal ou litoral/serra (ex.: Francisco Beltrão → Londrina): esperar 45 min.

2. **Adicional editável**  
   - Alterar o adicional manualmente (ex.: 0, 30, 60).  
   - Usar +15 e -15: valor sobe/desce de 15 em 15, sem ficar negativo.  
   - Chegada sugerida deve refletir total = cru + adicional.

3. **Redirect ao salvar roteiro novo**  
   - Etapa 2 → “Cadastrar novo roteiro”.  
   - Preencher sede, destinos e trechos (ou o mínimo exigido).  
   - Clicar em Salvar.  
   - Verificar: volta para a **lista da Etapa 2** (lista de roteiros do evento), e **não** para a tela de edição do roteiro criado.

4. **Edição**  
   - Editar um roteiro existente e salvar: deve continuar redirecionando para a lista da Etapa 2.

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Fórmula base (velocidade, fator rodoviário, tempo cru, arredondamento) mantida | OK |
| Perfil de rota classificado (EIXO_PRINCIPAL, DIAGONAL_LONGA, LITORAL_SERRA, PADRAO) | OK |
| Adicional sugerido automático 15/30/45 por perfil e distância | OK |
| Total = cru + adicional; chegada sugerida usa adicional | OK |
| Adicional editável (digitação, +15, -15); min=0, step=15; nunca negativo | OK |
| Salvar roteiro novo redireciona para lista Etapa 2 (não para editar) | OK |
| Salvar edição redireciona para lista Etapa 2 | OK |
| Testes: perfil, adicional sugerido, total, redirect | OK |
