# Relatório — Estimativa local de km/tempo (substituição da Google Routes API)

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|------------|
| `cadastros/models.py` | Campos `latitude` e `longitude` (DecimalField, null=True) no model `Cidade`. |
| `cadastros/migrations/0020_cidade_latitude_longitude.py` | Nova migration. |
| `cadastros/management/commands/importar_base_geografica.py` | Leitura opcional de colunas LAT/LON (ou LATITUDE/LONGITUDE) no CSV de municípios. |
| `eventos/services/estimativa_local.py` | **Novo.** Serviço de estimativa: haversine, fator 1.25, folga, acréscimos, arredondamento 15 min. |
| `eventos/views.py` | `trecho_calcular_km` passa a usar `estimar_distancia_duracao` (estimativa local); removido uso de Google e de `settings`. |
| `eventos/models.py` | `help_text` de `distancia_km`, `duracao_estimada_min` e `rota_fonte` atualizados para “estimativa local”. |
| `eventos/urls.py` | Comentário da rota de trechos atualizado para “estimativa local”. |
| `templates/eventos/guiado/roteiro_form.html` | Botão “Calcular km” → “Estimar km/tempo”; labels “Distância” → “Distância estimada”; exibição “Fonte: estimativa local”; mensagens de erro “estimar”. |
| `eventos/tests/test_eventos.py` | Nova classe `EstimativaLocalServiceTest`; `TrechoCalcularKmEndpointTest` com cidades com coordenadas, testes de sucesso, erro sem coordenadas e erro da estimativa. |

**Removido em limpeza posterior:**  
`eventos/services/google_routes.py` foi excluído; `GOOGLE_MAPS_API_KEY` foi removida de `config/settings.py`, `.env.example` e `README.md`. Não há mais dependência da Google no projeto.

---

## 2) Migrations

- **`cadastros.0020_cidade_latitude_longitude`**  
  Adiciona em `Cidade` os campos opcionais `latitude` e `longitude` (DecimalField, 9 dígitos, 6 decimais).

Aplicar:

```bash
python manage.py migrate cadastros
```

---

## 3) Fórmula usada

1. **Distância em linha reta (km):** Haversine entre (lat1, lon1) e (lat2, lon2), raio da Terra 6371 km.
2. **Distância rodoviária estimada (km):**  
   `distancia_rodoviaria_km = distancia_linha_reta_km * 1.25`
3. **Duração base (min):**  
   `(distancia_rodoviaria_km / 65) * 60 + 20`  
   (65 km/h + 20 min de folga fixa).
4. **Acréscimos:**  
   - se `distancia_rodoviaria_km > 250`: +15 min  
   - se `distancia_rodoviaria_km > 500`: +15 min  
5. **Duração final:** arredondada **para cima** em blocos de 15 min (ex.: 302 min → 315 min, 316 min → 330 min).

---

## 4) Arredondamento

- Função interna: `_arredondar_cima_bloco_15(minutos)`.
- Fórmula: `ceil(minutos / 15) * 15`.
- Exemplos: 5h02 (302 min) → 5h15 (315 min); 5h16 (316 min) → 5h30 (330 min).

---

## 5) Como preencher latitude/longitude das cidades

**Opção 1 — CSV na importação da base geográfica**

No CSV de municípios, inclua colunas **LAT** e **LON** (ou **LATITUDE** e **LONGITUDE**). Exemplo:

```text
COD UF,COD,NOME,LAT,LON
35,3550308,São Paulo,-23.550520,-46.633308
41,4106902,Curitiba,-25.4284,-49.2733
```

Depois:

```bash
python manage.py importar_base_geografica --estados data/geografia/estados.csv --cidades data/geografia/municipios.csv
```

Se o CSV não tiver LAT/LON, a importação segue normal; apenas `latitude` e `longitude` ficam vazios.

**Opção 2 — Atualização manual**

Definir `latitude` e `longitude` nos registros de `Cidade` (admin ou script), em graus decimais (ex.: -25.4284, -49.2733).

---

## 6) Como testar manualmente

1. **Coordenadas no banco**  
   Garantir que as cidades usadas no roteiro (sede e destinos) tenham `latitude` e `longitude` preenchidos (via CSV ou admin).

2. **Etapa 2 — Roteiro**  
   Abrir um evento → Etapa 2 → cadastrar ou editar roteiro, com pelo menos um trecho (sede → destino ou destino → sede).

3. **Botão “Estimar km/tempo”**  
   No card do trecho, clicar em “Estimar km/tempo”.  
   - Com coordenadas: o card deve exibir “Distância estimada: X km”, “Tempo estimado: HH:MM”, “Fonte: estimativa local”.  
   - Sem coordenadas em alguma cidade: mensagem “Cidade sem coordenadas para estimativa.” no trecho.

4. **Persistência**  
   Após estimar, salvar o roteiro. Reabrir o roteiro e conferir se distância, duração e fonte permanecem.

5. **Validação no shell (opcional)**  
   ```python
   from eventos.services.estimativa_local import estimar_distancia_duracao
   out = estimar_distancia_duracao(-25.43, -49.27, -23.42, -51.94)
   print(out)  # ok, distancia_km, duracao_estimada_min, duracao_estimada_hhmm, rota_fonte
   ```

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Cálculo 100% local (sem API externa) | OK |
| Sem uso de billing / Google no fluxo principal | OK |
| Distância rodoviária = linha reta × 1.25 | OK |
| Velocidade média 65 km/h + folga 20 min | OK |
| Acréscimos >250 km e >500 km | OK |
| Arredondamento para cima em blocos de 15 min | OK |
| Modelo `Cidade` com latitude/longitude | OK |
| Importação CSV opcional LAT/LON | OK |
| Trecho: distancia_km, duracao_estimada_min, rota_fonte (ESTIMATIVA_LOCAL), rota_calculada_em | OK |
| Botão “Estimar km/tempo” na UI | OK |
| Card: “Distância estimada”, “Tempo estimado”, “Fonte: estimativa local” | OK |
| Erro amigável quando cidade sem coordenadas | OK |
| Google Routes / GOOGLE_MAPS_API_KEY removidos por completo do projeto | OK |
| Testes: serviço, endpoint, persistência, erro sem coordenadas | OK |

---

## Resumo

- A estimativa de distância e tempo entre cidades passou a ser feita **só com dados locais** (coordenadas no banco + haversine + regras de negócio).
- Não há mais dependência de internet, API externa ou billing para esse cálculo.
- O botão na tela de trechos foi renomeado para “Estimar km/tempo” e o card deixa explícito que os valores são “estimados” e de “fonte: estimativa local”.
- Coordenadas podem ser carregadas pelo CSV da base geográfica (colunas LAT/LON) ou preenchidas manualmente.
- O arquivo `eventos/services/google_routes.py` foi removido; não há mais código ou configuração relacionada à Google no projeto.
