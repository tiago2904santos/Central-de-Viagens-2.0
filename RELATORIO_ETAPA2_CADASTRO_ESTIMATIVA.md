# Relatório — ETAPA 2 (Roteiros): Cadastro = Edição e Nova Estimativa

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/services/estimativa_local.py` | Fator rodoviário 1.25 → 1.15; velocidade 65 → 75 km/h; nova régua de adicional (até 2h +15, 2h01–5h +30, >5h +45). |
| `eventos/views.py` | `_build_trechos_initial`: inclusão de `origem_cidade_id` e `destino_cidade_id` no JSON; nova view `estimar_km_por_cidades` (POST com origem/destino cidade_id, retorna mesmo formato de `trecho_calcular_km` sem persistir). |
| `eventos/urls.py` | Nova rota `estimar-km-por-cidades/` para a view `estimar_km_por_cidades`. |
| `templates/eventos/guiado/roteiro_form.html` | `getSedeCidadeId`, `getDestinosComCidadeId`; trechos construídos com `origem_cidade_id`/`destino_cidade_id`; cards com `data-origem-cidade-id` e `data-destino-cidade-id`; botão "Estimar km/tempo" sempre visível (desabilitado se faltar origem/destino); clique usa `trecho_calcular_km` se houver `trecho_id`, senão `estimar_km_por_cidades`; `readTrechosValuesFromDOM` lê e preserva os IDs de cidade; placeholder de trechos só quando `numRows === 0`. |
| `eventos/tests/test_eventos.py` | `test_fator_rodoviario_1_25` → `test_fator_rodoviario_1_15`; `test_folga_por_faixa_regua` atualizado para nova régua; `test_velocidade_media_75_kmh`; `test_cadastro_mostra_botao_estimar_km_tempo`; `test_cadastro_trechos_json_tem_origem_destino_cidade_id`; nova classe `EstimarKmPorCidadesEndpointTest` (login, formato de resposta, erro sem IDs). |

---

## 2) Como cadastro e edição foram unificados

- **Template único**: Cadastro e edição usam o mesmo `eventos/guiado/roteiro_form.html` e o mesmo bloco "4) Trechos" com `trechos-gerados-container`.
- **Contexto alinhado**: Em ambos os fluxos o backend envia `trechos`, `trechos_json`, `destinos_atuais`, `estados_json`, `api_cidades_por_estado_url`. No cadastro, `trechos` e `trechos_json` vêm de `_estrutura_trechos(roteiro_virtual, destinos_list)` com sede da config e destinos do evento.
- **JS único**: O mesmo script monta os cards a partir de `getDestinosComCidadeId()` e `getSedeCidadeId()`, com mesma estrutura (origem, destino, saída/chegada data-hora, distância, tempo cru, adicional, total, fonte, botão "Estimar km/tempo").
- **Botão "Estimar km/tempo" no cadastro**: Sempre exibido. Se o trecho já tem ID (edição), chama `trecho_calcular_km` e persiste. Se não tem ID (cadastro ou trecho novo), chama `estimar_km_por_cidades` com `origem_cidade_id` e `destino_cidade_id` do card e apenas atualiza a tela (sem salvar). O botão fica desabilitado quando origem ou destino do trecho não estão definidos.

---

## 3) Como o novo trecho passa a nascer completo

- **Condição de exibição**: Trechos são renderizados sempre que existir ao menos uma linha de destino (`numRows > 0`), mesmo que a cidade ainda não esteja selecionada (linha vazia gera trechos com "—" e botão desabilitado até preencher).
- **Ao adicionar destino**: O JS chama `renderTrechos()` após adicionar/remover linha. `getDestinosComCidadeId()` considera todas as `.destino-row`; cada trecho (ida + retorno) é montado com `origem_cidade_id`, `destino_cidade_id`, nomes, e todos os campos do card (saída/chegada data-hora, distância, tempo cru, adicional, total, "Estimar km/tempo"). Nada de F5 ou salvar para o novo trecho aparecer.
- **Preservação**: `readTrechosValuesFromDOM()` lê dos cards atuais (incluindo `data-origem-cidade-id` e `data-destino-cidade-id`) e `currentValues` é usado na re-renderização, mantendo o que o usuário já preencheu em trechos equivalentes.

---

## 4) Nova fórmula/regra de estimativa

- **Distância rodoviária**: `distância_rodoviária_km = linha_reta_km × 1.15` (antes 1.25).
- **Velocidade média**: 75 km/h (antes 65 km/h).
- **Tempo cru**: `(distância_rodoviária_km / 75) × 60` minutos, arredondado para cima em blocos de 5 min.
- **Adicional padrão (folga)**:
  - até 2h (120 min) de tempo cru: +15 min
  - de 2h01 (121 min) até 5h (300 min): +30 min
  - acima de 5h: +45 min
- **Total**: tempo_cru (arredondado 5 min) + adicional; o total final também é arredondado para cima em blocos de 5 min.
- **Ajuste manual**: O usuário pode alterar o adicional (campo editável e botões -15 / +15); total = cru + adicional; chegada é recalculada ao alterar saída ou adicional.

---

## 5) Como testar manualmente

1. **Cadastro = Edição**
   - Configurar sede em Configurações (cidade sede padrão).
   - Criar evento na Etapa 1 com pelo menos um destino (estado + cidade).
   - Etapa 2 → "Cadastrar roteiro": deve abrir com sede preenchida, destinos do evento e bloco "4) Trechos" com cards (ida + retorno), cada um com saída/chegada, distância, tempo cru, adicional, total e botão "Estimar km/tempo".
   - Clicar em "Estimar km/tempo" em um trecho (com origem e destino definidos): deve preencher distância e tempos sem salvar. Salvar o roteiro; ao editar, o mesmo botão deve persistir os dados no trecho.

2. **Novo trecho ao adicionar destino**
   - No cadastro ou na edição, clicar "Adicionar destino": deve surgir uma nova linha e, na hora, um novo trecho de ida (e o retorno ajustado) com todos os campos e o botão "Estimar km/tempo", sem F5 nem salvar.

3. **Estimativa mais rápida**
   - Em um trecho com duas cidades com coordenadas, clicar "Estimar km/tempo": distância e tempo cru devem ser menores que antes (fator 1.15 e 75 km/h). Comparar mentalmente com Google Maps; o adicional continua editável com -15 / +15.

4. **Chegada automática**
   - Preencher saída (data e hora) em um trecho que já tenha tempo total (ou estimar antes): a chegada deve ser preenchida. Alterar o adicional ou a saída: a chegada deve ser recalculada.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Cadastro usa o mesmo template e blocos da edição | OK |
| Cadastro exibe botão "Estimar km/tempo" e trechos com distância, tempo cru, adicional, total, fonte | OK |
| Adicionar destino gera novo trecho imediatamente (sem salvar/F5) com todos os elementos do card | OK |
| Estimativa usa fator 1.15 e velocidade 75 km/h | OK |
| Adicional padrão: até 2h +15, 2h01–5h +30, >5h +45 | OK |
| Total = cru + adicional; arredondamento em 5 min | OK |
| Chegada recalcula ao alterar saída ou adicional | OK |
| Endpoint `estimar-km-por-cidades` retorna mesmo formato que `trecho_calcular_km` (sem persistir) | OK |
| Testes de estimativa, cadastro/edição e novo endpoint | OK |
