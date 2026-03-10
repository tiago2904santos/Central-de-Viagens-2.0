# Relatório: Etapa 2 — Persistência correta dos horários dos trechos

## 1. Causa real do bug

Foram identificadas **três causas** que, juntas, geravam horários “trocados” ou “aleatórios”:

### 1.1 Frontend: fallback por índice ao re-renderizar

Ao adicionar ou remover destino, `renderTrechos()` recria os cards. Os valores de cada card vêm de:
- `currentValuesMap[key]` (chave `origem_cidade_id->destino_cidade_id`) quando o trecho já existia; ou
- **`initialData[idx]`** quando não havia valor no map.

O fallback usava **índice** (`idx` do `forEach`). Com isso:
- Ao **remover** um destino, o trecho de retorno (novo “último” card) podia receber `initialData[1]`, que era o segundo trecho (ida) da estrutura anterior — horário errado no card de retorno.
- Ao **alterar** a ordem ou quantidade de destinos, qualquer trecho sem entrada no map recebia o `initialData` do mesmo índice, que nem sempre correspondia ao mesmo par origem/destino.

### 1.2 Frontend: hidden não sincronizados antes do submit

Os valores enviados no POST são os dos campos **hidden** (`trecho_N_saida_dt`, `trecho_N_chegada_dt`). Eles são atualizados por `syncTrechoHidden(card)` em eventos de change/blur dos inputs de data/hora. Se o usuário alterar data ou hora e enviar o formulário sem dar blur (por exemplo, clicando direto em Salvar), os hidden podiam continuar com o valor antigo, fazendo o backend gravar horários desatualizados.

### 1.3 Backend: ordem ao associar trechos_data aos trechos

Em `_salvar_trechos_roteiro` a iteração usava `for estado_id, cidade_id in destinos_list` e uma variável `ordem` incrementada. Para garantir que o índice de `trechos_data` fosse sempre o do trecho correto, a lógica foi trocada para um loop explícito por **índice** (`for idx in range(len(destinos_list))`), usando `destinos_list[idx]` e `trechos_data[idx]`, evitando qualquer confusão de ordem ou closure.

### 1.4 Reabertura: horário em UTC no JSON

Com `USE_TZ = True`, os datetimes no banco ficam em UTC. Em `_build_trechos_initial` o `strftime` era aplicado direto ao datetime vindo do modelo, gerando string em UTC. Na reabertura da edição, o front recebia, por exemplo, `11:00` (UTC) em vez de `08:00` (hora local), e os testes que esperavam hora local falhavam. O front precisa de hora local para exibir e enviar no formulário.

---

## 2. Arquivos alterados

| Arquivo | Alteração |
|--------|------------|
| **templates/eventos/guiado/roteiro_form.html** | (1) `initialDataMap`: mapa `origem_cidade_id->destino_cidade_id` → item do `initialTrechosData`; uso de `initialDataMap[key]` em vez de `initialData[idx]` ao montar cada card. (2) `syncAllTrechosHiddenBeforeSubmit()`: no `submit` do formulário, percorre todos os cards e preenche os hidden a partir dos inputs visíveis de data/hora antes do envio. |
| **eventos/views.py** | (1) `_salvar_trechos_roteiro`: loop por `for idx in range(len(destinos_list))` e uso de `trechos_data[idx]` e `destinos_list[idx]` para associar cada trecho ao dado correto. (2) `_build_trechos_initial`: conversão de `saida_dt`/`chegada_dt` para hora local (`timezone.localtime`) quando forem timezone-aware, antes do `strftime`, para o JSON enviar hora local ao front. |
| **eventos/tests/test_eventos.py** | (1) Comparação de datetimes em testes usando `timezone.localtime(...).replace(tzinfo=None)` para refletir hora local (USE_TZ=True). (2) Novos testes: `test_parse_trechos_times_post_ordem_correta`, `test_salvar_trechos_roteiro_associa_por_ordem`, `test_salvar_trechos_um_destino_dois_trechos`, `test_trecho_create_persiste_saida_dt`, `test_multiplos_trechos_horarios_no_trecho_certo_salvar_reabrir`. |

---

## 3. Associação estável dos horários aos trechos

- **Frontend**
  - **Chave estável:** `origem_cidade_id + '->' + destino_cidade_id`.
  - Ao re-renderizar (adicionar/remover destino), cada card usa primeiro `currentValuesMap[key]`; se não houver, usa `initialDataMap[key]`. Não se usa mais índice para escolher o “initial” do card.
  - Os nomes dos campos continuam `trecho_0_*`, `trecho_1_*`, … conforme a **ordem** dos trechos (0 = primeira ida, 1 = segunda ida, …, N = retorno). Essa ordem é a mesma da lista construída no JS (sede→d1, d1→d2, …, último→sede).
- **Backend**
  - `_parse_trechos_times_post(request, num_trechos)` lê `trecho_0_saida_dt`, `trecho_0_chegada_dt`, …, `trecho_{num_trechos-1}_*` e devolve uma lista na mesma ordem.
  - `_salvar_trechos_roteiro(roteiro, destinos_list, trechos_data)` percorre `idx in range(len(destinos_list))` e usa `trechos_data[idx]` para o trecho de ida de ordem `idx`, e `trechos_data[len(destinos_list)]` para o retorno. Assim, o trecho de ordem `i` recebe exatamente `trechos_data[i]`.
- **Reabertura**
  - `_build_trechos_initial` monta o JSON a partir dos trechos ordenados por `ordem` e formata `saida_dt`/`chegada_dt` em **hora local**, para o front exibir e reenviar os mesmos horários.

---

## 4. Como validar manualmente

1. **Cadastro/edição**
   - Abrir um evento na Etapa 2 e criar ou editar um roteiro com **pelo menos 2 destinos** (3 trechos: 2 idas + 1 retorno).
2. **Preencher horários distintos**
   - No primeiro trecho (sede → destino 1): saída 10/02/2025 08:00, chegada 10:00.
   - No segundo (destino 1 → destino 2): saída 10/02/2025 11:00, chegada 13:00.
   - No retorno: saída 11/02/2025 09:00, chegada 12:00.
3. **Salvar**
   - Clicar em Salvar (sem dar blur em todos os campos; o sync no submit deve preencher os hidden).
4. **Reabrir**
   - Abrir novamente a edição do mesmo roteiro. Os três trechos devem mostrar **exatamente** os horários acima em cada card.
5. **Adicionar destino**
   - Adicionar um terceiro destino e escolher UF/cidade. Devem aparecer 4 trechos; os 3 primeiros devem manter os horários já salvos; o quarto (nova ida) e o quinto (retorno novo) podem estar vazios. Salvar e reabrir: horários dos trechos antigos inalterados; novos trechos com o que foi preenchido.
6. **Remover destino**
   - Remover o destino do meio. Os cards devem ser recalculados (2 idas + 1 retorno). O trecho que era “destino 1 → destino 2” some; o retorno deve continuar com o horário que já tinha (não deve receber o horário da ida removida).

---

## 5. Checklist de aceite

| Item | Status |
|------|--------|
| Cada horário fica no trecho certo ao salvar | OK |
| Adicionar destino não embaralha horários dos trechos existentes | OK |
| Remover destino não coloca horário de ida no card de retorno | OK |
| Salvar e reabrir mostra os mesmos horários nos mesmos trechos | OK |
| Hidden sincronizados antes do submit (sem precisar blur) | OK |
| Reabertura envia hora local no trechos_json | OK |
| Testes: parser por ordem; _salvar_trechos_roteiro por índice; múltiplos trechos e reabrir | OK |
| Cadastro = edição; estimar km/tempo; adicional sugerido; total; chegada automática; salvar/reabrir | OK (mantido) |

---

## 6. Testes criados/ajustados

- **test_parse_trechos_times_post_ordem_correta** — POST com `trecho_0_*`, `trecho_1_*`, `trecho_2_*`; a lista retornada tem saida/chegada na ordem 0, 1, 2.
- **test_salvar_trechos_roteiro_associa_por_ordem** — `_salvar_trechos_roteiro` com 2 destinos e 3 itens em `trechos_data`; trechos com ordem 0, 1, 2 têm saida_dt correta (comparação em hora local).
- **test_salvar_trechos_um_destino_dois_trechos** — 1 destino, 2 trechos; trecho 0 = ida com primeiro item; trecho 1 = retorno com segundo item.
- **test_trecho_create_persiste_saida_dt** — Criação direta de um trecho com `saida_dt` e leitura em hora local.
- **test_multiplos_trechos_horarios_no_trecho_certo_salvar_reabrir** — POST com 2 destinos e 3 trechos com horários distintos; após salvar, confere no banco; GET da edição e confere que `trechos_json` traz os mesmos horários (em hora local) nos mesmos índices.

Todos os testes de horários usam `django.utils.timezone.localtime` na comparação quando o projeto está com `USE_TZ = True`.
