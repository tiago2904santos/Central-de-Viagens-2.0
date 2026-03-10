# Relatório — Correções nos Roteiros do Evento (Etapa 2)

Referência de comportamento: **projeto legacy** (RELATORIO_ESPECIFICACAO_LEGACY.md, RELATORIO_ETAPA2_ROTEIROS.md).  
Foco em funcionalidade: sede, destinos, duração em HH:MM, horários (ida/retorno), trechos gerados.

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/utils.py` | **Novo.** Helpers `hhmm_to_minutes()` e `minutes_to_hhmm()` para conversão HH:MM ↔ minutos. |
| `eventos/forms.py` | Campo `duracao_hhmm` (CharField) no formulário; removido `retorno_duracao_min` dos fields; `duracao_min` em HiddenInput; em `clean()` conversão de `duracao_hhmm` para `duracao_min`; em `__init__` preenchimento de `duracao_hhmm.initial` a partir de `instance.duracao_min` na edição. |
| `eventos/models.py` | Em `RoteiroEvento.save()`: retorno usa a mesma duração da ida (`duracao_min`) para calcular `retorno_chegada_dt` (antes usava `retorno_duracao_min`). |
| `eventos/views.py` | `_trechos_roteiro()` passa a retornar para cada trecho: `de`, `para`, `saida_str`, `chegada_str`, `tipo` ('ida' ou 'retorno'); horários calculados com `duracao_min` e `saida_dt`/`retorno_saida_dt`. |
| `templates/eventos/guiado/roteiro_form.html` | Duração em HH:MM (input único); removido campo retorno duração; labels "Data/hora saída ida", "Chegada ida (calculada)", "Data/hora saída retorno", "Chegada retorno (calculada)"; tabela de trechos com colunas Trecho, De, Para, Saída, Chegada; JS passa a usar `duracao_hhmm` e `hhmmToMinutes()` para calcular as duas chegadas em tempo real. |
| `eventos/tests/test_eventos.py` | POST dos testes de roteiro passam a usar `duracao_hhmm` (ex.: `'02:00'`, `'01:30'`) e não enviam mais `retorno_duracao_min`; novos testes: `test_duracao_hhmm_converte_para_minutos`, `test_edicao_mostra_duracao_em_hhmm`, `test_chegada_retorno_calculada`, `test_trechos_multiplos_destinos`, `test_edicao_nao_sobrescreve_sede_com_config`. |

---

## 2) Prefill da sede

- **Cadastro novo:** continua usando `ConfiguracaoSistema.cidade_sede_padrao`. A view `guiado_etapa_2_cadastrar` monta `initial['origem_estado']` e `initial['origem_cidade']` a partir de `config.cidade_sede_padrao` quando existir. O formulário abre com UF (Sede) e Cidade (Sede) já preenchidos.
- **Edição:** o formulário é instanciado com `instance=roteiro`. A sede exibida é a salva no roteiro (`origem_estado`/`origem_cidade`); a configuração atual **não** sobrescreve.
- Testes: `test_cadastro_roteiro_herda_sede_da_configuracao`, `test_origem_padrao_vem_da_configuracao_sede`, `test_edicao_nao_sobrescreve_sede_com_config`.

---

## 3) HH:MM ↔ minutos

- **Formulário:** o usuário informa a duração em **HH:MM** (ex.: 03:30, 01:05) no campo `duracao_hhmm`. O valor é convertido em minutos no backend e salvo em `RoteiroEvento.duracao_min`.
- **Helpers em `eventos/utils.py`:**
  - `hhmm_to_minutes(value)`: string "HH:MM" → int minutos (ex.: "03:30" → 210). Valida formato e faixa (MM 00–59).
  - `minutes_to_hhmm(minutes)`: int minutos → string "HH:MM" (ex.: 65 → "01:05").
- **Validação:** `RoteiroEventoForm.clean_duracao_hhmm()` valida o formato; `clean()` chama `hhmm_to_minutes(duracao_hhmm)` e preenche `cleaned_data['duracao_min']`.
- **Edição:** em `__init__`, se há `instance` com `duracao_min`, define `self.fields['duracao_hhmm'].initial = minutes_to_hhmm(instance.duracao_min)` para exibir HH:MM ao reabrir o formulário.
- Testes: `test_duracao_hhmm_converte_para_minutos`, `test_edicao_mostra_duracao_em_hhmm`.

---

## 4) Horários (ida e retorno)

- **Uma única duração:** o mesmo valor em HH:MM (e em minutos no banco) é usado para a ida e para o retorno. O campo "Retorno — duração" foi removido do formulário.
- **Ida:** Data/hora saída ida (`saida_dt`) + Duração (HH:MM) → Chegada ida (calculada), preenchida no `save()` do model e exibida em tempo real no frontend.
- **Retorno:** Data/hora saída retorno (`retorno_saida_dt`) + mesma duração → Chegada retorno (calculada), também no `save()` e no JS.
- **Model:** em `RoteiroEvento.save()`: `chegada_dt = saida_dt + timedelta(minutes=duracao_min)`; `retorno_chegada_dt = retorno_saida_dt + timedelta(minutes=duracao_min)` (quando há `retorno_saida_dt`).
- **Frontend:** JS lê `id_duracao_hhmm`, converte com `hhmmToMinutes()`, e atualiza os campos somente leitura "Chegada ida (calculada)" e "Chegada retorno (calculada)" ao alterar saída ou duração.
- Testes: `test_calculo_chegada_ao_salvar`, `test_chegada_retorno_calculada`.

---

## 5) Trechos gerados

- **Fonte:** `_trechos_roteiro(roteiro)` em `eventos/views.py`.
- **Entrada:** sede (origem), destinos do roteiro (ordem), `duracao_min`, `saida_dt`, `retorno_saida_dt`.
- **Saída:** lista de dicionários com `de`, `para`, `saida_str`, `chegada_str`, `tipo` ('ida' ou 'retorno').
- **Regras:**
  1. **Ida:** Trecho 1: sede → primeiro destino (saída = `saida_dt`, chegada = saída + duração). Trechos seguintes: destino N → destino N+1 (saída = chegada do trecho anterior, chegada = saída + duração).
  2. **Retorno:** Último destino → sede (saída = `retorno_saida_dt`, chegada = saída + `duracao_min`). Só é incluído se existir pelo menos um destino e `retorno_saida_dt`; se o último destino for igual à sede, o trecho de retorno não é gerado.
- **Template:** tabela com colunas Trecho, De, Para, Saída, Chegada; linha de retorno com rótulo "Retorno".
- Teste: `test_trechos_multiplos_destinos` (ida + retorno com horários).

---

## 6) Uso do legacy como referência

- **RELATORIO_ETAPA2_ROTEIROS.md:** origem/destino, ida (saída, duração, chegada calculada), retorno opcional (saída, duração, chegada calculada), lista de roteiros com origem→destino e saída→chegada.
- **RELATORIO_ESPECIFICACAO_LEGACY.md:** Roteiro com estado_sede, cidade_sede; TrechoRoteiro com saida/chegada data e hora, tempo_viagem_minutos.
- Ajustes feitos para aproximar do legacy:
  - Sede pré-preenchida pela configuração no cadastro novo.
  - Duração em formato legível (HH:MM) no formulário, com conversão interna em minutos.
  - Uma duração única para ida e retorno (como “tempo por trecho” no legacy).
  - Bloco de horários com saída ida, chegada ida (calculada), saída retorno, chegada retorno (calculada).
  - Trechos gerados com sede → destinos (ida) e último destino → sede (retorno), com saída/chegada por trecho.

---

## 7) Como testar manualmente

1. **Sede**
   - Em Configurações, defina a cidade sede padrão.
   - Crie um evento e vá à Etapa 2 → Cadastrar roteiro: UF (Sede) e Cidade (Sede) devem vir preenchidos.
   - Altere a sede, salve, edite o roteiro: deve aparecer a sede salva, não a da configuração atual.

2. **Duração HH:MM**
   - No formulário de roteiro, informe duração "03:30" ou "01:05".
   - Salve e edite novamente: o campo deve mostrar "03:30" ou "01:05".
   - Valide com valor inválido (ex.: "3:70"): deve exibir erro de formato.

3. **Horários**
   - Preencha Data/hora saída ida e Duração (HH:MM): "Chegada ida (calculada)" deve atualizar em tempo real.
   - Preencha Data/hora saída retorno: "Chegada retorno (calculada)" deve usar a mesma duração e atualizar em tempo real.
   - Salve e confira na lista/detalhe que as datas de chegada estão corretas.

4. **Trechos**
   - Roteiro com sede, um ou mais destinos, saída ida e (opcional) saída retorno preenchidas.
   - Abra a edição: a seção "Trechos gerados" deve listar ida (sede → destino 1 → …) e retorno (último destino → sede), com colunas Saída e Chegada preenchidas.

---

## 8) Checklist de aceite

| Critério | Status |
|----------|--------|
| Cadastro novo herda sede das Configurações | OK |
| Edição mostra sede salva no roteiro (não sobrescreve com config) | OK |
| Duração em HH:MM no formulário; conversão e persistência em minutos | OK |
| Edição exibe duração no formato HH:MM | OK |
| Chegada ida = saída ida + duração (backend e frontend) | OK |
| Chegada retorno = saída retorno + mesma duração | OK |
| Uma duração única para ida e retorno; campo retorno duração removido | OK |
| Trechos gerados com de/para e saída/chegada por segmento; ida + retorno | OK |
| Testes: sede, HH:MM, edição HH:MM, chegada ida/retorno, trechos, edição não sobrescreve sede | OK |

---

*Relatório referente às correções nos roteiros do evento (Etapa 2), alinhadas ao comportamento do projeto legacy.*
