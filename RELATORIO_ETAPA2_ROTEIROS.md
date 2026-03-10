# Relatório — Etapa 2: Roteiros do evento (Evento guiado)

Implementação da Etapa 2 do fluxo guiado: cadastro de um ou mais roteiros vinculados ao evento, com status RASCUNHO/FINALIZADO.

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/models.py` | Novo model `RoteiroEvento` com todos os campos; `save()` calcula chegada_dt/retorno_chegada_dt, normaliza observacoes em maiúsculo e define status (FINALIZADO se `esta_completo()`, senão RASCUNHO). |
| `eventos/migrations/0002_roteiro_evento.py` | Migração que cria a tabela de roteiros. |
| `eventos/forms.py` | Novo `RoteiroEventoForm` (campos da etapa 2; chegada_dt e retorno_chegada_dt só no model/template). Validação: cidade no estado (origem e destino); retorno preenchido só com saída+duração juntos. |
| `eventos/views.py` | `_evento_etapa2_ok()`, `_get_evento_etapa2()`, `_setup_roteiro_querysets()`, `guiado_etapa_2_lista`, `guiado_etapa_2_cadastrar`, `guiado_etapa_2_editar`, `guiado_etapa_2_excluir`. Painel atualizado para usar etapa2_ok e não marcar Etapa 2 como “Em breve”. |
| `eventos/urls.py` | Rotas etapa-2: lista, cadastrar, editar, excluir. |
| `templates/eventos/guiado/etapa_2_lista.html` | **Novo:** lista de roteiros (tabela origem→destino, saída→chegada, retorno, status, Editar/Excluir); botões “Cadastrar roteiro”, “Voltar para o painel”, “Próxima etapa”. |
| `templates/eventos/guiado/roteiro_form.html` | **Novo:** formulário de roteiro (origem/destino com estado→cidade dependente), ida (saída, duração, chegada calculada), retorno opcional, observações; JS para carregar cidades, exibir chegada em tempo real e maiúsculas em observações. |
| `templates/eventos/guiado/painel.html` | Botão “Próxima etapa” passa a apontar para Etapa 2 (roteiros); adicionado link “Etapa 3 (Em breve)”. |
| `eventos/tests/test_eventos.py` | Nova classe `EventoEtapa2RoteirosTest` com 9 testes. |

---

## 2) Model criado

**RoteiroEvento** (app `eventos`):

| Campo | Tipo | Observação |
|-------|------|------------|
| evento | FK(Evento, CASCADE) | related_name='roteiros' |
| origem_estado | FK(Estado, SET_NULL, null, blank) | related_name='+' |
| origem_cidade | FK(Cidade, SET_NULL, null, blank) | related_name='+' |
| destino_estado | FK(Estado, SET_NULL, null, blank) | related_name='+' |
| destino_cidade | FK(Cidade, SET_NULL, null, blank) | related_name='+' |
| saida_dt | DateTimeField(null, blank) | Data/hora saída |
| duracao_min | PositiveIntegerField(null, blank) | Minutos |
| chegada_dt | DateTimeField(null, blank) | Calculado no `save()` |
| retorno_saida_dt | DateTimeField(null, blank) | Opcional |
| retorno_duracao_min | PositiveIntegerField(null, blank) | Opcional |
| retorno_chegada_dt | DateTimeField(null, blank) | Calculado no `save()` |
| observacoes | TextField(blank, default='') | Salvo em MAIÚSCULO no `save()` |
| status | CharField(choices=RASCUNHO/FINALIZADO) | Definido no `save()` |
| created_at, updated_at | DateTimeField | auto_now_add / auto_now |

**Método `esta_completo()`:** retorna True quando estão preenchidos: evento, origem_estado, origem_cidade, destino_estado, destino_cidade, saida_dt, duracao_min e chegada_dt (retorno opcional).

---

## 3) Critérios de completude

- **FINALIZADO:** `esta_completo()` True: evento + origem (estado + cidade) + destino (estado + cidade) + saida_dt + duracao_min + chegada_dt (calculado no `save()`).
- **RASCUNHO:** qualquer outro caso.
- Retorno (retorno_saida_dt, retorno_duracao_min, retorno_chegada_dt) é opcional; se preenchido parcialmente, o form exige “saída e duração do retorno juntos”.

---

## 4) Cálculo de chegada

- **Backend (model `save()`):**  
  - `chegada_dt = saida_dt + timedelta(minutes=duracao_min)` quando `saida_dt` e `duracao_min` existem; senão `chegada_dt = None`.  
  - `retorno_chegada_dt = retorno_saida_dt + timedelta(minutes=retorno_duracao_min)` quando ambos existem; senão `retorno_chegada_dt = None`.
- **Frontend (template):** JS lê `saida_dt` e `duracao_min` (e os de retorno), calcula a chegada e exibe nos campos somente leitura “Chegada (calculada)” e “Retorno — chegada (calculada)” em tempo real.

---

## 5) Lista e formulário

**Lista (Etapa 2):**
- Cabeçalho: “Etapa 2 — Roteiros do evento”; botão “Cadastrar roteiro” e “Voltar para o painel”.
- Tabela: colunas Origem→Destino, Saída→Chegada, Retorno, Status (badge Rascunho/Finalizado), Ações (Editar, Excluir).
- Ordenação: RASCUNHO primeiro (mais recentes), depois FINALIZADO (mais recentes).
- Se não houver roteiros: mensagem e botão “Cadastrar roteiro”.
- Rodapé: “Voltar para o painel” e “Próxima etapa”.

**Formulário (cadastrar/editar):**
- Origem: estado + cidade (cidades dependentes do estado via API).
- Destino: estado + cidade (mesma API).
- Ida: saida_dt (datetime-local), duracao_min (minutos), chegada (somente leitura, calculada).
- Retorno (opcional): retorno_saida_dt, retorno_duracao_min, retorno chegada (somente leitura).
- Observações: salvas em maiúsculas (backend + JS no input).
- Ao cadastrar: origem padrão = evento.cidade_base (e estado da cidade base).

---

## 6) Como testar manualmente

1. **Acesso à Etapa 2**  
   - Painel do evento → “Próxima etapa (Etapa 2 — Roteiros)” → lista de roteiros.

2. **Cadastrar roteiro**  
   - “Cadastrar roteiro” → preencher origem (estado + cidade; se evento tiver cidade base, origem já vem preenchida), destino (estado + cidade), saída, duração → conferir “Chegada (calculada)” no formulário e após salvar na lista.

3. **Status**  
   - Salvar só origem/destino sem datas → roteiro deve ficar RASCUNHO.  
   - Preencher origem, destino, saída e duração → salvar → roteiro deve ficar FINALIZADO e painel deve mostrar Etapa 2 como OK.

4. **Validação**  
   - Escolher estado A e cidade de outro estado → deve dar erro de “cidade deve pertencer ao estado”.

5. **Retorno**  
   - Preencher só “Retorno — saída” ou só “Retorno — duração” → deve dar erro para preencher os dois juntos ou deixar em branco.

6. **Editar / Excluir**  
   - Na lista, Editar um roteiro e salvar; Excluir e confirmar → roteiro some da lista.

7. **Painel**  
   - Com pelo menos um roteiro FINALIZADO, o painel deve mostrar Etapa 2 com badge OK.

---

## 7) Checklist de aceite

| Critério | Status |
|----------|--------|
| Model RoteiroEvento com todos os campos e regras (observacoes maiúsculo, cidade no estado, chegada/retorno calculados) | OK |
| Método `esta_completo()` e status automático (FINALIZADO/RASCUNHO) no `save()` | OK |
| Rotas GET etapa-2, GET+POST cadastrar/editar, POST excluir; roteiro sempre do evento da URL | OK |
| Lista com origem→destino, saída→chegada, retorno, status; RASCUNHO primeiro, depois FINALIZADO | OK |
| Formulário com origem/destino dependentes (API), chegada/retorno calculados (somente leitura), observações em maiúsculas | OK |
| Origem padrão = evento.cidade_base ao cadastrar | OK |
| Painel: Etapa 2 OK se existir roteiro FINALIZADO; “Próxima etapa” leva à Etapa 2 | OK |
| Testes: lista exige login, criar roteiro, origem padrão, cidade no estado, cálculo chegada, incompleto→RASCUNHO, completo→FINALIZADO, excluir, painel Etapa 2 OK | OK |

**Não implementado nesta entrega:** ofícios, termos, justificativas, pacote final.

---

*Relatório referente à Etapa 2 (Roteiros) do evento guiado.*
