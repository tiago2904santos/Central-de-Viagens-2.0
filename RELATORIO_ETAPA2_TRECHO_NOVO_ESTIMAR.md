# Relatório: Etapa 2 – Trecho novo estimar km/tempo sem salvar

## 1. Causa real do bug

O cálculo de distância/tempo para um **trecho novo** (criado ao adicionar um destino na Etapa 2) só funcionava após salvar ou dar F5 porque:

- O **único endpoint** usado pelo botão "Estimar km/tempo" era **`trechos/<pk>/calcular-km/`**, que exige um trecho **já persistido** (pk).
- Trechos criados dinamicamente ao adicionar destino **não têm pk** até o formulário ser salvo; o card é gerado no front com `data-trecho-id` vazio.
- O front tentava chamar o endpoint por pk mesmo para esses cards; sem pk, a requisição falhava ou não era feita corretamente, e o botão ficava desabilitado ou ineficaz até haver um trecho salvo (após submit ou F5).

Ou seja: **a estimativa dependia de trecho salvo no banco (pk)**. Para trecho novo, não havia fluxo por origem/destino (cidade_id) sem persistência.

---

## 2. Arquivos alterados

| Arquivo | Alteração |
|--------|------------|
| `eventos/urls.py` | Nova rota `path('trechos/estimar/', ..., name='trechos-estimar')` apontando para `estimar_km_por_cidades`. |
| `templates/eventos/guiado/roteiro_form.html` | Variável JS `urlTrechosEstimar`; no handler do botão "Estimar km/tempo": se não há `data-trecho-id`, usa `urlTrechosEstimar` com body `{ origem_cidade_id, destino_cidade_id }` (lidos do card); validação de cidade origem/destino; após resposta ok, preenchimento do card (distância, tempo cru, adicional, total, fonte) e `syncTrechoHidden(card)`. |
| `eventos/tests/test_eventos.py` | `EstimarKmPorCidadesEndpointTest`: novo `test_trechos_estimar_trecho_novo_sem_pk` (POST em `trechos-estimar` retorna mesmo formato e não persiste). `EventoEtapa2RoteirosTest`: novo `test_cadastro_inclui_url_trechos_estimar_para_trecho_novo` (página contém `urlTrechosEstimar` e path `trechos/estimar/`). |

Nenhuma alteração em `eventos/views.py`: a view `estimar_km_por_cidades` já existia e já retornava o formato esperado pelo card.

---

## 3. Endpoint novo criado

- **URL name:** `eventos:trechos-estimar`
- **Path:** `POST /eventos/trechos/estimar/`
- **View:** mesma `estimar_km_por_cidades` (não persiste; só calcula).
- **Body (JSON):** `{ "origem_cidade_id": int, "destino_cidade_id": int }`
- **Resposta (sucesso):** mesmo formato de `trecho_calcular_km`: `ok`, `distancia_km`, `duracao_estimada_min`, `duracao_estimada_hhmm`, `tempo_cru_estimado_min`, `tempo_adicional_sugerido_min`, `perfil_rota`, `rota_fonte`, etc.

O front usa **este** endpoint para trechos **sem** pk (card novo); continua usando **`trechos/<pk>/calcular-km/`** para trechos já salvos.

---

## 4. Como o front passou a estimar trechos novos sem save

- **Variável global:** no template, `urlTrechosEstimar = "{% url 'eventos:trechos-estimar' %}"`.
- **Escolha de URL no click:** no listener (event delegation no container de trechos), ao clicar em "Estimar km/tempo":
  - Lê `data-trecho-id`, `data-origem-cidade-id` e `data-destino-cidade-id` do card.
  - Se **há** `trecho-id**: usa `urlTrechoCalcularKmBase` + `pk` (trecho salvo).
  - Se **não há** `trecho-id**: exige `origem_cidade_id` e `destino_cidade_id` válidos; usa `urlTrechosEstimar` e body `{ origem_cidade_id, destino_cidade_id }`.
- **Cards novos:** `renderTrechos()` monta os cards com `data-origem-cidade-id` e `data-destino-cidade-id` a partir de sede + destinos (incluindo o destino recém-adicionado quando a cidade é escolhida). O botão fica desabilitado só quando falta origem ou destino.
- **Resposta:** o mesmo handler que já preenchia o card (distância, tempo cru, adicional, total, fonte) e chamava `atualizarTempoTotalCard` e `suggestChegada` agora também chama `syncTrechoHidden(card)` após preencher, para manter os hidden em sync.

Assim, um trecho **novo** (sem pk) passa a ser estimado **na hora**, sem salvar e sem F5, usando apenas origem/destino por cidade_id.

---

## 5. Como testar manualmente

1. **Login** e abrir um evento na **Etapa 1** com pelo menos um destino (UF + cidade) e seguir para a **Etapa 2**.
2. Na Etapa 2, **cadastrar** um novo roteiro (ou editar um existente).
3. **Adicionar um destino:** clicar em "Adicionar destino", escolher UF e cidade do novo destino.
4. Verificar que um **novo card de trecho** aparece (sem ter clicado em Salvar).
5. No **novo card**, clicar em **"Estimar km/tempo"** (sem salvar e sem F5).
6. **Esperado:** distância, tempo cru, adicional sugerido, total e fonte são preenchidos no card; se houver saída preenchida, a chegada sugerida é atualizada.
7. **Salvar** o roteiro e reabrir: trechos e valores devem permanecer; para trechos já salvos, o botão "Estimar km/tempo" continua usando o endpoint por pk e persistindo.

Cenários a conferir:

- Trecho **salvo** (edição): "Estimar km/tempo" continua calculando e gravando no banco (comportamento anterior).
- Trecho **novo** (após adicionar destino): "Estimar km/tempo" calcula na hora e preenche o card; não exige save nem F5.
- Remover destino: a estrutura de trechos é recalculada (comportamento já existente).

---

## 6. Checklist de aceite

| Item | Status |
|------|--------|
| Novo trecho (ao adicionar destino) aparece imediatamente | OK |
| Novo trecho vem com card completo (origem/destino, botão) | OK |
| Botão "Estimar km/tempo" do novo trecho funciona sem salvar | OK |
| Cálculo não depende de pk (usa endpoint por origem/destino) | OK |
| Resposta preenche distância, tempo cru, adicional, total, fonte | OK |
| Com saída preenchida, chegada sugerida funciona no trecho novo | OK |
| Trecho salvo continua estimando por pk e persistindo | OK |
| Cadastro = edição; adicional sugerido; total = cru + adicional | OK (mantido) |
| Salvar e reabrir mantém dados | OK (mantido) |
| Testes: trecho salvo, trecho novo sem pk, página com urlTrechosEstimar | OK |

---

## Testes automatizados

- **Trecho salvo:** `TrechoCalcularKmEndpointTest` (ex.: `test_endpoint_retorna_km_e_duracao_estimativa_local`).
- **Trecho novo sem pk:** `EstimarKmPorCidadesEndpointTest.test_trechos_estimar_trecho_novo_sem_pk` (POST `trechos-estimar`, mesmo formato, não persiste).
- **Front tem URL:** `EventoEtapa2RoteirosTest.test_cadastro_inclui_url_trechos_estimar_para_trecho_novo` (página contém `urlTrechosEstimar` e `trechos/estimar/`).
- **Trechos initial com cidade_id:** `EventoEtapa2RoteirosTest.test_cadastro_trechos_json_tem_origem_destino_cidade_id`.

Execução:

```bash
python manage.py test eventos.tests.test_eventos.EstimarKmPorCidadesEndpointTest eventos.tests.test_eventos.TrechoCalcularKmEndpointTest eventos.tests.test_eventos.EventoEtapa2RoteirosTest.test_cadastro_mostra_botao_estimar_km_tempo eventos.tests.test_eventos.EventoEtapa2RoteirosTest.test_cadastro_trechos_json_tem_origem_destino_cidade_id eventos.tests.test_eventos.EventoEtapa2RoteirosTest.test_cadastro_inclui_url_trechos_estimar_para_trecho_novo -v 2
```
