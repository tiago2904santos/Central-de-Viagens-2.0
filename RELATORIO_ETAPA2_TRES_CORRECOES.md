# Relatório — Três correções na Etapa 2 (Roteiros)

Correções implementadas: **Cidade (Sede)**, **Duração (HH:MM)** com máscara e **Trechos com horários próprios** (model e persistência).

---

## 1) Causa do bug da Cidade (Sede)

**Problema:** No cadastro novo de roteiro, mesmo com `ConfiguracaoSistema.cidade_sede_padrao` definida, a Cidade (Sede) não aparecia preenchida ou a opção correta não vinha selecionada.

**Causa:** Em `_setup_roteiro_querysets` o `estado_id` era definido só a partir de `request.POST` ou de `instance.origem_estado_id`. No **GET** do cadastro novo não há `instance` (roteiro ainda não existe) nem POST. O `initial` passado pela view (com estado e cidade da config) não era usado para montar o queryset de cidades. Com isso, `form.fields['origem_cidade'].queryset` ficava `Cidade.objects.none()` e o `<select>` de cidade era renderizado sem opções (ou sem a cidade da sede), e o JS ao carregar cidades por estado podia não manter a seleção.

**Correção:**
- Em `_setup_roteiro_querysets`: quando não for POST e não houver `instance.origem_estado_id`, usar `form.initial.get('origem_estado')` para definir `estado_id` e assim preencher `origem_cidade.queryset` com as cidades do estado da config.
- No template: usar `form.origem_cidade.value` (que reflete o `initial` no GET) para marcar a opção selecionada: `{% if form.origem_cidade.value == c.pk or form.instance.origem_cidade_id == c.pk %}selected{% endif %}`.

Com isso, no cadastro novo a UF e a Cidade (Sede) vêm da configuração e a cidade aparece selecionada; na edição continuam valendo os valores já salvos no roteiro.

---

## 2) Correção do campo Duração (HH:MM)

**Objetivo:** Alinhar a experiência ao campo de hora: máscara/normalização em HH:MM e comportamento previsível.

**Implementação:**
- **Frontend:** Foi adicionada máscara em JavaScript no `input` de duração:
  - Apenas dígitos são aceitos.
  - 2 dígitos → `00:MM` (ex.: 45 → 00:45).
  - 3 dígitos → `0H:MM` (ex.: 330 → 03:30).
  - 4 dígitos → `HH:MM` (ex.: 1234 → 12:34).
- **Backend:** Continua igual: validação e conversão com `hhmm_to_minutes()` / `minutes_to_hhmm()` em `eventos/utils.py`; o valor é salvo em `duracao_min` no modelo. Na edição, o valor é exibido em HH:MM.

A duração global (HH:MM) segue como apoio (ex.: preencher chegada quando houver só um trecho); cada trecho passou a ter **saída e chegada próprias** e pode ser editado independentemente.

---

## 3) Modelagem adotada para os trechos

Foi criado o model **`RoteiroEventoTrecho`** em `eventos/models.py`:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| roteiro | FK(RoteiroEvento, CASCADE) | related_name='trechos' |
| ordem | PositiveIntegerField | 0, 1, 2, ... |
| tipo | CharField | 'IDA' ou 'RETORNO' |
| origem_estado / origem_cidade | FK(Estado/Cidade, PROTECT) | Local de origem do trecho |
| destino_estado / destino_cidade | FK(Estado/Cidade, PROTECT) | Local de destino do trecho |
| saida_dt | DateTimeField (null, blank) | Saída do trecho |
| chegada_dt | DateTimeField (null, blank) | Chegada do trecho |

Migração: `eventos/migrations/0006_roteiro_evento_trecho.py`.

Cada deslocamento (sede→destino 1, destino 1→destino 2, …, último destino→sede) é um registro com horários próprios, refletindo o domínio real.

---

## 4) Como os trechos são gerados

- **Estrutura:** A partir da **sede** (origem do roteiro) e da **lista de destinos** (ordem) do roteiro:
  - **Ida:** trecho 0 = sede → destino 1, trecho 1 = destino 1 → destino 2, …
  - **Retorno:** último trecho = último destino → sede (tipo RETORNO).

- **Cadastro novo:** Após salvar roteiro e destinos, é chamada `_salvar_trechos_roteiro(roteiro, destinos_post, [])`, que cria um `RoteiroEventoTrecho` por perna (ida + retorno) com `saida_dt`/`chegada_dt` em branco. Em seguida o fluxo redireciona para a **edição** do roteiro para o usuário preencher os horários.

- **Edição:** A lista exibida vem de `_estrutura_trechos(roteiro)`: monta a mesma estrutura (sede + destinos do roteiro) e, para cada posição, preenche `saida_dt`/`chegada_dt` com os valores já salvos em `RoteiroEventoTrecho` (quando existirem). Assim, a tela mostra sempre a estrutura atual e os horários já gravados.

- **Ao salvar a edição:** São lidos do POST `trecho_0_saida_dt`, `trecho_0_chegada_dt`, …, `trecho_N_saida_dt`, `trecho_N_chegada_dt` (N = número de trechos da estrutura). Em seguida `_salvar_trechos_roteiro(roteiro, destinos_post, trechos_times)` substitui todos os trechos do roteiro pelos novos (estrutura + horários vindos do formulário).

---

## 5) Como a edição preserva os dados salvos

- **GET (abrir edição):** Os trechos exibidos vêm de `_estrutura_trechos(roteiro)`, que usa os **destinos já salvos** no roteiro e os **trechos já salvos** (`roteiro.trechos`). Para cada ordem, são usados os `saida_dt` e `chegada_dt` do banco. Não há regeneração automática que apague horários editados.

- **POST (salvar):** A estrutura de trechos é recalculada a partir da **lista de destinos enviada no POST** (que pode ter sido alterada). Os horários são os que o usuário preencheu no form (`trecho_N_saida_dt` / `trecho_N_chegada_dt`). Ou seja, o que está na tela é o que é salvo; não se sobrescreve com valores antigos nem se regenera estrutura “por cima” sem usar o que veio do formulário.

- **Sede na edição:** O formulário é instanciado com `instance=roteiro` e não recebe `initial` de configuração. Assim, UF e Cidade (Sede) exibidos são sempre os do roteiro, preservando o que já estava salvo.

---

## 6) Como testar manualmente

1. **Cidade (Sede)**  
   - Definir em Configurações a cidade sede padrão.  
   - Criar um evento, ir à Etapa 2 → Cadastrar roteiro.  
   - Verificar: UF (Sede) e Cidade (Sede) preenchidos e cidade selecionada.  
   - Alterar a sede, salvar, editar o roteiro: deve aparecer a sede que foi salva, não a da configuração.

2. **Duração (HH:MM)**  
   - No campo Duração, digitar apenas números: 45 → 00:45, 330 → 03:30, 1234 → 12:34.  
   - Salvar e reabrir: valor deve aparecer em HH:MM.

3. **Trechos com horários próprios**  
   - Cadastrar roteiro com sede e pelo menos um destino; salvar (redireciona para edição).  
   - Na edição, conferir blocos “Ida 1”, “Retorno” (e mais idas se houver mais destinos).  
   - Preencher em cada trecho: Saída (data/hora) e Chegada (data/hora). Salvar.  
   - Reabrir o roteiro: os horários devem permanecer.  
   - Alterar um horário, salvar de novo e reabrir: alteração deve estar persistida.

4. **Múltiplos destinos**  
   - Roteiro com 2 destinos: devem aparecer 2 trechos de ida e 1 de retorno.  
   - Cada um com origem/destino e campos de saída/chegada editáveis.

---

## 7) Checklist de aceite

| Critério | Status |
|----------|--------|
| Sede do novo roteiro vem das Configurações (UF + Cidade) | OK |
| Cidade (Sede) permanece selecionada ao abrir o cadastro | OK |
| Na edição, sede exibida é a salva no roteiro | OK |
| Duração em HH:MM com máscara (330→03:30, 45→00:45) | OK |
| Múltiplos destinos geram múltiplos trechos (ida + retorno) | OK |
| Cada trecho tem horários próprios editáveis (saída/chegada) | OK |
| Retorno é um trecho: último destino → sede | OK |
| Edição não sobrescreve trechos/horários sem uso do form | OK |
| Persistência dos trechos no banco (RoteiroEventoTrecho) | OK |
| Testes: sede, cidade selecionada, trechos, persistência | OK |

---

## Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/models.py` | Criação do model `RoteiroEventoTrecho`. |
| `eventos/migrations/0006_roteiro_evento_trecho.py` | Migração do novo model. |
| `eventos/views.py` | `_setup_roteiro_querysets`: uso de `form.initial` para estado no GET; `_estrutura_trechos`, `_salvar_trechos_roteiro`, `_parse_trechos_times_post`; cadastrar cria trechos e redireciona para editar; editar carrega/atualiza trechos e persiste horários do POST. |
| `templates/eventos/guiado/roteiro_form.html` | Select da sede: selected com `form.origem_cidade.value`; máscara HH:MM no campo duração; bloco 4: trechos com campos editáveis (data/hora saída e chegada por trecho) e script que preenche os hidden `trecho_N_saida_dt` / `trecho_N_chegada_dt`. |
| `eventos/tests/test_eventos.py` | Ajuste do teste de trechos para `tipo == 'RETORNO'`; novos testes `test_cidade_sede_selecionada_ao_abrir_cadastro` e `test_trechos_persistidos_ao_salvar_edicao`. |

---

*Relatório referente às três correções da Etapa 2 (Roteiros): Cidade Sede, Duração HH:MM e Trechos com horários próprios persistidos.*
