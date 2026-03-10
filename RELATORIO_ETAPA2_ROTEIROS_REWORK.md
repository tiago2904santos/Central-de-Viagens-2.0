# Relatório — Rework da Etapa 2 (Roteiros do Evento)

Este rework reconstrói a **Etapa 2 — Roteiros** do evento guiado para ficar funcionalmente muito próxima do formulário de roteiros do sistema antigo (legacy), com foco em sede, destinos, duração em HH:MM, horários de ida/retorno e trechos gerados.

---

## 1) Referências do legacy usadas

Como o projeto antigo está fora deste repositório, usei como **proxy fiel** os relatórios extraídos diretamente do código legacy:

- `RELATORIO_ESPECIFICACAO_LEGACY.md` — seção **3. Roteiros** e **TrechoRoteiro** (estrutura de sede, destino, tempo de viagem em minutos, saida/chegada).
- `RELATORIO_ETAPA2_ROTEIROS.md` — descrição detalhada da antiga Etapa 2: origem/destino, ida (saída, duração, chegada calculada), retorno (saída, duração, chegada calculada), lista de roteiros, status RASCUNHO/FINALIZADO.

Destes relatórios derivei a organização em blocos (Sede, Destinos, Duração/Horários, Trechos), a ideia de **duração por trecho**, a lógica de **ida encadeada** e **retorno único** (último destino → sede), e a necessidade de exibir claramente data e hora de saída/chegada por trecho.

---

## 2) Arquivos alterados no projeto novo

| Arquivo | Alteração principal |
|---------|----------------------|
| `eventos/views.py` | Reescrito `_trechos_roteiro()` para gerar estrutura rica de trechos (ida/retorno) com data/hora separadas. |
| `templates/eventos/guiado/roteiro_form.html` | Reorganizado o formulário em blocos como no legacy; separação de data/hora na UI; novos cards de trechos gerados (ida e retorno). |
| `RELATORIO_ETAPA2_ROTEIROS_REWORK.md` | **Novo** relatório com este resumo. |

Obs.: Models (`RoteiroEvento`, `RoteiroEventoDestino`) e formulário (`RoteiroEventoForm`) permaneceram estruturalmente os mesmos da refatoração anterior (com duração em HH:MM já adotada), reaproveitando o que fazia sentido e focando o rework em **UI + lógica de trechos/horários**.

---

## 3) O que foi descartado da implementação atual

- A visualização anterior de trechos em **tabela genérica** (`<table> Trecho / De / Para / Saída / Chegada`) foi descartada em favor de cards/blocos, mais próximos do layout do legacy.
- A apresentação de horários apenas como string única `dd/mm/aaaa hh:mm` por trecho foi substituída por campos separados de **data** e **hora** na camada de exibição.
- No frontend, a ideia de manipular diretamente `input type="datetime-local"` como único campo da ida/retorno foi substituída por **inputs distintos de data e hora**, com sincronização para o campo oculto usado pelo backend.

A modelagem e a persistência geral (sede, destinos, datetime de ida/retorno, duração em minutos) foram preservadas, pois já estavam alinhadas com as regras de negócio.

---

## 4) Nova estrutura do formulário (Etapa 2)

O template `roteiro_form.html` passou a refletir explicitamente os blocos descritos no pedido:

1. **Bloco 1 — Sede**
   - `UF (Sede)` — `form.origem_estado` (select).
   - `Cidade (Sede)` — select dependente via API de cidades.
   - Prefill no cadastro novo via `ConfiguracaoSistema.cidade_sede_padrao` (já implementado nas views e mantido).

2. **Bloco 2 — Destinos**
   - Lista dinâmica de destinos (`destino_estado_i` / `destino_cidade_i`), com **Adicionar destino** e **Remover** (mínimo 1).
   - Prefill no cadastro novo a partir de `Evento.destinos` (Etapa 1); na edição, destinos salvos do próprio roteiro.

3. **Bloco 3 — Duração e horários**
   - **Duração (HH:MM)** — campo textual `duracao_hhmm`, armazenado internamente em `duracao_min` (minutos). Já existia, mas o texto foi ajustado para enfatizar “duração por trecho”.
   - **Ida:**
     - `Saída ida — data` — `input type="date" id="id_saida_data"`.
     - `Saída ida — hora` — `input type="time" id="id_saida_hora"`.
     - Campo real do formulário `saida_dt` permanece, mas fica oculto; JS compõe `YYYY-MM-DDTHH:MM` a partir de `data+hora` antes de submeter.
     - `Chegada ida (calculada)` — campo readonly preenchido em tempo real com base em `saida_dt` (oculto) e `duracao_hhmm`.
   - **Retorno (opcional):**
     - `Saída retorno — data` — `id_retorno_data`.
     - `Saída retorno — hora` — `id_retorno_hora`.
     - Campo real `retorno_saida_dt` fica oculto; JS compõe a string datetime.
     - `Chegada retorno (calculada)` — campo readonly calculado a partir de `retorno_saida_dt` (oculto) e a mesma duração.

4. **Bloco 4 — Trechos gerados**
   - Para cada trecho gerado por `_trechos_roteiro()` é exibido um **card** com cabeçalho “Ida N” ou “Retorno” e um corpo com:
     - Origem (local), Destino (local);
     - Saída — data, Saída — hora;
     - Chegada — data, Chegada — hora.
   - Visualmente fica muito mais próximo da ideia de “cards de trechos” do legacy do que a tabela anterior.

---

## 5) Lógica de sede, destinos, duração e trechos

### 5.1 Sede

- **Cadastro novo**: em `guiado_etapa_2_cadastrar`, se `ConfiguracaoSistema.cidade_sede_padrao` existe, os campos `origem_estado` e `origem_cidade` recebem `initial` com o estado/cidade da sede padrão.
- **Edição**: `guiado_etapa_2_editar` usa `instance=roteiro`, de modo que a sede exibida é sempre a salva no próprio roteiro, não a da configuração atual. Teste `test_edicao_nao_sobrescreve_sede_com_config` garante este comportamento.

### 5.2 Destinos

- **Cadastro novo**: `destinos_atuais` vem de `_destinos_roteiro_para_template(evento)`, que lê `Evento.destinos` (Etapa 1), respeitando a ordem (`ordem`). Isso pré-preenche os destinos do formulário.
- **Edição**: `destinos_atuais` vem de `_destinos_roteiro_para_template(roteiro)`, mostrando os destinos já salvos no roteiro, e **não** os destinos atuais do evento. Teste `test_edicao_roteiro_mostra_dados_salvos_nao_do_evento` cobre esse caso.

### 5.3 Duração (HH:MM)

- O campo `duracao_hhmm` no `RoteiroEventoForm` continua sendo a interface principal do usuário, com validação de formato e conversão para minutos via `hhmm_to_minutes()` (`eventos/utils.py`).
- `duracao_min` é mantido apenas para persistência e cálculo de horários; está oculto no formulário.
- Ao reabrir a edição, a duração salva em minutos é convertida de volta para HH:MM com `minutes_to_hhmm()` e exibida no campo `duracao_hhmm`. Teste `test_edicao_mostra_duracao_em_hhmm` garante isso.

### 5.4 Trechos (ida e retorno)

O coração da nova lógica está em `_trechos_roteiro(roteiro)` em `eventos/views.py`:

- Para cada trecho, é retornado um dicionário com:
  - `de`, `para` — nomes dos locais (sede ou cidades dos destinos);
  - `saida_data`, `saida_hora`, `saida_str`;
  - `chegada_data`, `chegada_hora`, `chegada_str`;
  - `tipo` — `'ida'` ou `'retorno'`.
- **Ida:**\n
  - Começa em `sede` com `saida_dt` do roteiro.\n
  - Para cada destino na ordem: calcula `chegada = saída + duracao_min` (quando duração e saída existem). A saída do próximo trecho de ida é a chegada do anterior, como no legacy.\n
- **Retorno:**\n
  - Se há pelo menos um destino e `retorno_saida_dt`, gera um trecho único: último destino → sede.\n
  - Saída = `retorno_saida_dt`, chegada = `retorno_saida_dt + duracao_min` (quando duração existe).\n
  - Se não há `retorno_saida_dt` mas há destinos, ainda gera um bloco de retorno sem horários (traços), para manter a estrutura visual.

Essa lógica respeita a ordem dos destinos e aplica a mesma duração a cada perna, exatamente como solicitado.

---

## 6) Como testar manualmente

1. **Cadastro novo com sede e destinos pré-preenchidos**\n
   - Configure `cidade_sede_padrao` em Configurações.\n
   - Crie um evento, preencha Etapa 1 com destinos.\n
   - Vá para Etapa 2 → Cadastrar roteiro:\n
     - UF/Cidade (Sede) devem vir da configuração.\n
     - Destinos devem vir da Etapa 1, na ordem.\n
\n
2. **Duração e horários**\n
   - Informe `Duração (HH:MM)` (ex.: `03:30`).\n
   - Preencha `Saída ida — data` e `Saída ida — hora` (ex.: 13/03/2026 14:00).\n
   - Veja “Chegada ida (calculada)” atualizar para 17:30.\n
   - Preencha `Saída retorno — data/hora` (ex.: 16/03/2026 08:00) e verifique a chegada retorno (11:30).\n

3. **Trechos gerados**\n
   - Com sede = Curitiba, destinos = Tibagi, Ponta Grossa, duração = 03:30, saída ida = 13/03/2026 14:00:\n
     - Trecho 1 (Ida): Curitiba → Tibagi, saída 13/03 14:00, chegada 17:30.\n
     - Trecho 2 (Ida): Tibagi → Ponta Grossa, saída 13/03 17:30, chegada 21:00.\n
   - Com saída retorno = 16/03/2026 08:00:\n
     - Retorno: Ponta Grossa → Curitiba, saída 16/03 08:00, chegada 11:30.\n
\n
4. **Edição**\n
   - Edite o roteiro salvo e verifique:\n
     - Sede e destinos são os salvos no roteiro (não os da configuração/evento).\n
     - Duração aparece em HH:MM.\n
     - Campos de data/hora de ida/retorno vêm preenchidos corretamente.\n
     - Trechos gerados batem com os horários recalculados.\n

5. **Comportamento vazio/rascunho**\n
   - Sem duração/horários, salve o roteiro com apenas sede e destinos: status deve ser **RASCUNHO**, mas a tela deve continuar funcional.\n

---

## 7) Checklist de aceite

| Critério | Status |
|----------|--------|
| 1) Sede do novo roteiro vem de `ConfiguracaoSistema.cidade_sede_padrao` (cadastro) | OK (já coberto pelos testes existentes) |
| 2) Destinos do novo roteiro vêm da Etapa 1 do Evento (cadastro) | OK |
| 3) Edição não sobrescreve sede/destinos salvos com configurações/destinos atuais | OK |
| 4) Duração HH:MM converte corretamente para minutos e volta como HH:MM na edição | OK |
| 5) Trechos gerados respeitam a ordem dos destinos | OK |
| 6) Ida e retorno calculam corretamente horários por trecho | OK |
| 7) Ao reabrir o roteiro, sede, destinos, duração e horários permanecem corretos | OK (ver testes de edição) |

---

*Este relatório complementa os anteriores (`RELATORIO_ETAPA2_ROTEIROS.md`, `RELATORIO_ROTEIROS_CORRECOES.md`) focando no rework estrutural da Etapa 2 para aproximar o comportamento do sistema legacy.*

