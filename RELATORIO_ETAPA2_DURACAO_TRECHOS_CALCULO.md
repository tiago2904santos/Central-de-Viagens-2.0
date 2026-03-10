# Relatório — Etapa 2 (Roteiros): Duração, Trechos na Hora e Cálculo Automático

## Resumo

Correções objetivas em três pontos da Etapa 2 (Roteiros): **(1)** duração como campo de hora (HH:MM, `type="time"`), **(2)** trechos gerados imediatamente no frontend ao alterar destinos e **(3)** cálculo automático de saída/chegada dos trechos a partir de duração, saída ida e saída retorno. O backend mantém a persistência correta (roteiro + trechos).

---

## 1) O que foi alterado no form/template

### Duração (Problema 1)
- **Antes:** `<input type="text" name="duracao_hhmm" ...>` com máscara em JS (ex.: 330 → 03:30).
- **Depois:** `<input type="time" name="duracao_hhmm" id="id_duracao_hhmm" class="form-control" value="{{ form.duracao_hhmm.value|default:'' }}" step="60">`
- Comportamento igual ao dos campos “Saída ida — hora” e “Saída retorno — hora”: formato HH:MM nativo do navegador, sem máscara por dígitos.
- Na edição, o valor inicial continua vindo do backend em HH:MM (`minutes_to_hhmm` no `RoteiroEventoForm.__init__`).

### Trechos (Problemas 2 e 3)
- **Antes:** Bloco “4) Trechos” só era renderizado no servidor quando existia `context['trechos']` (após salvar e reabrir).
- **Depois:** 
  - Bloco “4) Trechos gerados” sempre presente.
  - Container vazio: `<div id="trechos-gerados-container">` com mensagem inicial: “Adicione ao menos um destino…”.
  - Todo o conteúdo dos trechos (cards por trecho + hidden `trecho_N_saida_dt` / `trecho_N_chegada_dt`) é preenchido por JavaScript, sem depender de submit.

Nenhuma alteração nos campos do formulário Django (form) além do que já existia; apenas o tipo do input de duração e a remoção da renderização servidor dos trechos.

---

## 2) O que foi alterado no JS

### Removido
- Máscara de duração que convertia dígitos (ex.: 330 → 03:30) no `id_duracao_hhmm`.
- Script que sincronizava inputs visíveis de cada trecho com os hidden (trechos passam a ser gerados só no JS).

### Adicionado / alterado
- **`getSedeNome()`:** Lê o texto da opção selecionada de `#id_origem_cidade`.
- **`getDestinosNomes()`:** Para cada `.destino-row`, lê o texto da opção selecionada do `.destino-cidade` e devolve um array de nomes na ordem.
- **`getDuracaoMinutes()`:** Lê `#id_duracao_hhmm` (valor HH:MM do `input type="time"`) e converte para minutos.
- **`getSaidaIdaDt()` / `getSaidaRetornoDt()`:** Montam um `Date` a partir dos campos de data e hora da ida e do retorno.
- **`dateTimeToStr(dt)` / `dateTimeToDisplay(dt)`:** Formatação para hidden (YYYY-MM-DDTHH:MM) e para exibição (dd/mm/yyyy HH:mm).
- **`renderTrechos()`:**
  1. Lê sede, destinos, duração, saída ida e saída retorno.
  2. Se não houver nenhum destino, mostra só a mensagem no container e retorna.
  3. Monta a lista de trechos: ida (sede → d1, d1 → d2, …) + retorno (último destino → sede).
  4. Calcula saída/chegada de cada trecho:
     - Ida: primeiro trecho começa na saída ida; cada trecho seguinte começa na chegada do anterior; chegada = saída + duração.
     - Retorno: saída = saída retorno; chegada = saída + duração.
  5. Gera o HTML dos cards (origem, destino, saída e chegada exibidos) e os hidden `trecho_N_saida_dt` e `trecho_N_chegada_dt` e preenche o `#trechos-gerados-container`.

### Quando `renderTrechos()` é chamado
- Na carga da página: `setTimeout(renderTrechos, 150)` para dar tempo de popular selects de cidade (incl. sede).
- Ao adicionar destino: no callback de `criarRowDestino` (e após carregar cidades da nova row, no `.then` de `loadCidadesForSelect`).
- Ao remover destino: no handler do botão “Remover”.
- Ao mudar UF ou cidade de qualquer destino: listeners em `.destino-estado` e `.destino-cidade`.
- Ao mudar sede: listener em `#id_origem_cidade`.
- Ao mudar duração, data/hora da ida ou data/hora do retorno: listeners em `id_duracao_hhmm`, `id_saida_data`, `id_saida_hora`, `id_retorno_data`, `id_retorno_hora`.
- Após carregar cidades (sede ou destinos): no `.then` de `loadCidadesForSelect` para que os nomes dos selects estejam disponíveis ao montar os trechos.

Assim, os trechos são regenerados e recalculados na hora, sem precisar salvar.

---

## 3) Como os trechos passam a ser gerados imediatamente

- A estrutura de trechos é definida só por **sede** (nome da cidade de origem) e **lista de destinos** (nomes na ordem das rows).
- Regras:
  - 1 destino: trecho 1 ida (sede → d1), trecho 2 retorno (d1 → sede).
  - 2 destinos: ida (sede → d1), (d1 → d2), retorno (d2 → sede).
  - N destinos: N trechos de ida + 1 de retorno.
- Sempre que a lista de destinos muda (add/remove linha ou mudança de cidade em qualquer row), o JS chama `renderTrechos()`, que:
  - Lê de novo sede e destinos a partir do DOM.
  - Reconstrói a lista de trechos (origem/destino por trecho).
  - Recalcula saídas/chegadas com a duração e as datas/horas atuais da ida e do retorno.
  - Substitui o conteúdo de `#trechos-gerados-container` (cards + hidden para o submit).

O usuário vê e pode conferir os trechos antes de salvar; ao submeter o formulário, os hidden já vêm preenchidos com os valores calculados.

---

## 4) Como o cálculo automático funciona

- **Duração:** Um único valor HH:MM (por trecho), usado em todos os trechos (ida e retorno).
- **Ida:**  
  - Trecho 1: saída = “Saída ida (data + hora)”, chegada = saída + duração.  
  - Trecho k (k > 1): saída = chegada do trecho k−1, chegada = saída + duração.
- **Retorno:** Um único trecho: saída = “Saída retorno (data + hora)”, chegada = saída + duração.
- Exemplo (como no enunciado):  
  Sede Curitiba, destinos Tibagi e Ponta Grossa, duração 03:30, saída ida 13/03/2026 14:00, saída retorno 16/03/2026 08:00:
  - Trecho 1: Curitiba → Tibagi: saída 14:00, chegada 17:30.
  - Trecho 2: Tibagi → Ponta Grossa: saída 17:30, chegada 21:00.
  - Trecho 3 (retorno): Ponta Grossa → Curitiba: saída 08:00, chegada 11:30.

O JS usa os valores atuais dos campos (duração, saída ida, saída retorno) e atualiza a cada mudança nesses campos ou na lista de destinos.

---

## 5) Como testar manualmente

1. **Duração como hora**
   - Abrir cadastro ou edição de roteiro.
   - Verificar que o campo “Duração (HH:MM)” é um seletor de hora (relógio) igual a “Saída ida — hora” e “Saída retorno — hora”.
   - Na edição de um roteiro com duração salva (ex.: 01:05), conferir que o valor aparece em HH:MM.

2. **Trechos gerados na hora**
   - Com evento que tenha pelo menos um destino na Etapa 1, abrir “Cadastrar roteiro” (sede e destinos já preenchidos).
   - Verificar que, logo ao carregar (ou após ~150 ms), a seção “4) Trechos gerados” mostra os trechos (ex.: Ida 1, Retorno) sem clicar em Salvar.
   - Clicar em “Adicionar destino”, escolher UF e cidade: deve aparecer mais um trecho de ida e o retorno deve passar a ser “último destino → sede”.
   - Remover um destino: a lista de trechos deve atualizar na hora (menos um trecho de ida, retorno ajustado).

3. **Cálculo automático**
   - Preencher duração (ex.: 03:30), “Saída ida — data” e “Saída ida — hora” (ex.: 13/03/2026 14:00).
   - Verificar que o primeiro trecho de ida mostra saída 14:00 e chegada 17:30.
   - Com dois destinos, verificar que o segundo trecho de ida começa em 17:30 e a chegada é 21:00.
   - Preencher “Saída retorno — data” e “hora” (ex.: 16/03/2026 08:00): o trecho de retorno deve mostrar chegada 11:30.
   - Alterar duração ou horários e conferir que os trechos recalculam na hora.

4. **Persistência**
   - Salvar o roteiro e reabrir a edição: duração em HH:MM, destinos e trechos (com horários) devem reaparecer corretamente; os trechos exibidos devem bater com o que foi calculado/salvo.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Duração = campo de hora (type="time"), mesmo padrão visual/funcional dos campos de hora | OK |
| Sem máscara por dígitos (ex.: 330 → 03:30); digitação normal em HH:MM | OK |
| Edição exibe duração em HH:MM corretamente | OK |
| Ao adicionar destino, trechos atualizam imediatamente no frontend | OK |
| Ao remover destino, trechos atualizam imediatamente | OK |
| Trechos gerados a partir de sede + destinos (ida + retorno) | OK |
| Cálculo: cada perna usa a duração; ida encadeada; retorno = saída retorno + duração | OK |
| Ao alterar duração / saída ida / saída retorno, trechos recalculam na hora | OK |
| Backend persiste roteiro e trechos; ao reabrir edição, tudo correto | OK |
| Testes: duração HH:MM na edição, container de trechos, múltiplos trechos, cálculo ida/retorno, persistência | OK |

---

## Arquivos alterados

- **`templates/eventos/guiado/roteiro_form.html`**
  - Duração: `input type="text"` → `input type="time"`, removida máscara.
  - Bloco 4: substituído bloco servidor de trechos por `#trechos-gerados-container` + mensagem inicial.
  - JS: removida máscara da duração; adicionadas `getSedeNome`, `getDestinosNomes`, `getDuracaoMinutes`, `getSaidaIdaDt`, `getSaidaRetornoDt`, helpers de formatação e `renderTrechos()`; chamadas a `renderTrechos()` em todos os pontos listados acima; listeners de duração passam a chamar `renderTrechos()` em vez de só atualizar chegada ida/retorno.
- **`eventos/tests/test_eventos.py`**
  - `test_edicao_mostra_duracao_em_hhmm`: garantia de que o campo duração tem `id="id_duracao_hhmm"` e `type="time"`.
  - Novos: `test_trechos_gerados_container_presente`, `test_calculo_automatico_ida_persistido`, `test_calculo_automatico_retorno_persistido` (persistência da diferença saída→chegada = duração).

Backend (views, forms, models) permanece como já estava: formulário continua recebendo `duracao_hhmm` em HH:MM e convertendo para minutos; trechos continuam sendo salvos via `trecho_N_saida_dt` e `trecho_N_chegada_dt` enviados pelo formulário (preenchidos pelo JS).
