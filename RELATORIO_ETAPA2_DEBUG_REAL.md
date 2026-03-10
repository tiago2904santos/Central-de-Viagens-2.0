# Relatório — Etapa 2 (Roteiros) — Debug real e correções

## 1) Causa real do bug

Três causas foram identificadas e corrigidas:

### A) Listener faltando no novo destino
Ao clicar em **"Adicionar destino"**, a nova linha era criada com listener apenas em **estado** e no botão **Remover**. O **select de cidade** da nova linha **não** tinha `change` ligado a `renderTrechos()`. Assim, ao escolher a cidade no novo destino, os trechos não eram recalculados e o novo trecho não aparecia com origem/destino corretos (ou continuava com "—").

### B) Trechos “fantasmas” para destino vazio
`getDestinosNomes()` considerava **todas** as linhas de destino e devolvia `'—'` quando a cidade não estava selecionada. Com isso, ao adicionar uma linha nova (ainda sem cidade), eram gerados trechos com origem/destino "—" (ex.: "Londrina → —" e "— → Sede"). O usuário via um trecho “incompleto” e confuso em vez de ver o novo trecho só quando o destino estivesse preenchido.

### C) Listeners duplicados a cada render
`attachTrechosListeners(containerTrechos)` era chamado **dentro** de `renderTrechos()` sempre que o HTML dos trechos era substituído. Cada nova renderização **acumulava** novos listeners no container (change, input, click). Com o tempo isso podia gerar comportamento estranho ou múltiplas execuções.

---

## 2) O que foi alterado no JS

- **`getDestinosNomes()`**  
  Só inclui no array destinos cujo select de cidade tem **valor selecionado** (`cidadeSel.value`). Linhas sem cidade escolhida são ignoradas. Assim, o número de trechos = número de destinos válidos + 1 (retorno), sem trechos "—".

- **`criarRowDestino()`**  
  Adicionado `cidadeSelect.addEventListener('change', ...)` que chama `renderTrechos()` quando o usuário seleciona a cidade na nova linha. O novo trecho passa a aparecer assim que o destino fica completo.

- **Listeners dos trechos**  
  `attachTrechosListeners(containerTrechos)` foi **removido** de dentro de `renderTrechos()`. Os listeners (change, input, click) passam a ser ligados **uma única vez** ao `#trechos-gerados-container` no carregamento da página. Como os eventos são tratados por **delegação** no container, continuam valendo para qualquer trecho gerado depois (incluindo o novo trecho ao adicionar destino), sem acumular listeners.

---

## 3) O que foi alterado no template

- Nenhuma alteração de **markup** (HTML) dos blocos de trecho. Os cards continuam com os mesmos inputs visíveis (date/time) e hidden.
- A única alteração no template foi no **script**: as mudanças descritas no item 2 (comportamento de `getDestinosNomes`, listener no novo destino, e chamada única de `attachTrechosListeners`).

---

## 4) Hidden inputs — fonte principal ou não

- **Fonte principal de envio** para o backend continuam sendo os **hidden** `trecho_N_saida_dt` e `trecho_N_chegada_dt` (o backend lê esses nomes no POST).
- Os inputs **visíveis** (date/time) são a **fonte de edição** para o usuário. A função `syncTrechoHidden(card)` é chamada em `change` e `input` (por delegação no container) e copia `data + hora` dos campos visíveis para os hidden. Assim, ao submeter, os hidden já estão preenchidos.
- Nada foi “removido” como fonte; a organização é: usuário edita os visíveis → JS mantém os hidden em sync → submit envia os hidden. O backend não foi alterado.

---

## 5) Como o novo trecho passa a nascer utilizável

1. Usuário clica em **"Adicionar destino"** → surge uma nova linha (UF + Cidade + Remover).
2. Usuário escolhe **UF** → o select de cidades é carregado (já existia).
3. Usuário escolhe **Cidade** → o novo listener dispara `renderTrechos()`.
4. `getDestinosNomes()` passa a incluir essa cidade → a lista de trechos é recalculada: N idas + 1 retorno, com o novo trecho (ex.: “Ida 3” e “Retorno” atualizado).
5. O HTML dos trechos é substituído; cada card (incluindo o novo) tem os **quatro inputs visíveis** (saída data/hora, chegada data/hora) gerados pelo mesmo `renderTrechos()`.
6. Os listeners do container (já ligados uma vez) tratam `change`/`input` em qualquer card, então o novo trecho já pode ser preenchido e os hidden são atualizados.
7. Não é necessário salvar para o novo trecho aparecer nem para poder preencher data/hora.

---

## 6) Como reproduzir e confirmar a correção

1. **Cadastro novo**  
   - Evento com Etapa 1 preenchida (pelo menos um destino).  
   - Ir para Etapa 2 → Cadastrar roteiro.  
   - Verificar: sede da configuração; destinos do evento; trechos já listados (ida(s) + retorno) com inputs de data/hora utilizáveis.

2. **Adicionar destino**  
   - Clicar em **"Adicionar destino"**.  
   - Selecionar UF e depois Cidade na nova linha.  
   - Verificar: surge imediatamente um novo trecho (ex.: “Ida 3”) e o retorno atualizado, **com os quatro campos visíveis** (saída data/hora, chegada data/hora) preenchíveis, sem salvar.

3. **Preencher e salvar**  
   - Preencher data/hora em um ou mais trechos (incluindo o recém-adicionado).  
   - Salvar.  
   - Reabrir o roteiro (edição).  
   - Verificar: mesmos trechos e horários persistidos.

4. **Remover destino**  
   - Na edição, remover um destino (deixando pelo menos um).  
   - Verificar: a lista de trechos é recalculada na hora (menos uma ida, retorno atualizado), sem salvar.

5. **Testes automatizados**  
   - `python manage.py test eventos.tests.test_eventos.EventoEtapa2RoteirosTest`  
   - Inclui o novo teste `test_script_renderiza_inputs_visiveis_por_trecho`, que garante que o script gera no HTML os inputs visíveis (type="date", type="time", _saida_date, _chegada_date, etc.).

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Cadastro novo abre com sede da configuração | OK |
| Cadastro novo abre com destinos do evento | OK |
| Trechos iniciais já renderizados e utilizáveis (sem salvar) | OK |
| Adicionar destino → selecionar cidade → novo trecho aparece na hora | OK |
| Novo trecho com 4 campos visíveis (saída data/hora, chegada data/hora) | OK |
| Preencher trecho (incluindo novo) sem salvar | OK |
| Remover destino recalcula trechos na hora | OK |
| Salvar persiste todos os trechos e horários | OK |
| Reabrir edição mantém trechos e horários | OK |
| Sem trechos “fantasma” (—) | OK |
| Mesmo template/comportamento em cadastro e edição | OK |
| Duração (HH:MM) sugere chegada; chegada editável manualmente | OK (já existia) |
| Testes Etapa 2 passando (incl. inputs visíveis) | OK |

---

## Arquivos alterados

- `templates/eventos/guiado/roteiro_form.html`: ajustes em JS (`getDestinosNomes`, `criarRowDestino`, chamada única de `attachTrechosListeners`).
- `eventos/tests/test_eventos.py`: novo teste `test_script_renderiza_inputs_visiveis_por_trecho`.

Nenhuma alteração em views ou modelos; apenas template e teste.
