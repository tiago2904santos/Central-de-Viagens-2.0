# Relatório: Etapa 3 e composição da viagem no projeto legado

**Objetivo:** Mapear no projeto antigo (legado) tudo que corresponde à etapa de composição da viagem (participantes, veículo, motorista) e aos fluxos relacionados, para basear a implementação no projeto novo no comportamento real do sistema antigo.

**Data:** 2025-03-09  
**Escopo:** `legacy/viagens/` (projeto antigo como referência).

---

## 1. Conclusão principal: onde está a “composição” no legado

No **projeto legado**:

- **Etapa 3 do EVENTO** não é “composição da viagem”.
- **Etapa 3 do evento** = **Hub de Ofícios do evento** (listar ofícios, criar novo ofício no contexto do evento, editar, central de documentos).
- A **composição (viajantes, veículo, motorista)** existe apenas no **wizard do OFÍCIO**, nas etapas **1 e 2 do ofício** (dados gerais + transporte).

Ou seja: no legado **não há** uma “Etapa 3 — Composição da viagem” no nível do evento. Há “Etapa 3 — Ofícios do evento”; a composição é **por ofício**, dentro do fluxo de criar/editar cada ofício.

---

## 2. Etapa 3 do evento no legado (hub de ofícios)

### 2.1 O que é

- **Rota:** `eventos/<evento_id>/guiado/etapa-3/`
- **View:** `evento_guiado_etapa3` em `legacy/viagens/views/_shared.py` (linha ~4846)
- **Template:** `viagens/evento_guiado_etapa3.html`
- **Descrição (docstring):** “Etapa 3: hub de ofícios do evento — lista, criar novo (wizard com contexto evento), editar, central de documentos.”

### 2.2 Comportamento

- **GET:** Carrega o evento com `prefetch_related("oficios__trechos")`, lista `evento.oficios.order_by("id")`.
- **Tela:**
  - Título: “Ofícios do evento (Etapa 3)”
  - Botão: “Criar Ofício neste Evento” → `formulario?evento_id={{ evento.id }}` (inicia wizard do ofício com evento na sessão).
  - Tabela de ofícios: número/ano, protocolo, destino (tipo_destino), status (Rascunho/Finalizado), ações (Editar, Central de Documentos).
  - Links: “Voltar ao painel”, “Ir para Pacote do Evento”.
- **Status no painel:** Etapa 3 do evento fica **OK** quando `evento.oficios.exists()` (serviço `evento_guiado.py`: `etapa3_ok = evento.oficios.exists()`).

### 2.3 Entidades envolvidas (evento, etapa 3)

- **Evento:** modelo `Evento` (titulo, tipo_demanda, cidade_base, data_inicio, data_fim, tem_convite_ou_oficio_evento). **Não** possui campos de viajantes, veículo ou motorista no nível do evento.
- **Oficio:** modelo `Oficio` com FK `evento` (opcional). Um evento tem N ofícios (`evento.oficios`).

Nenhuma tela de “composição da viagem” (participantes, veículo, motorista) é exibida na Etapa 3 do evento.

---

## 3. Onde está a composição: wizard do Ofício (steps 1 e 2)

A composição (viajantes, veículo, motorista) no legado é feita **por ofício**, no wizard de criação/edição do ofício.

### 3.1 Step 1 do ofício — Dados gerais e viajantes

- **Rota criação:** `oficios/novo/` → view `formulario`
- **Rota edição:** `oficios/<oficio_id>/editar/etapa-1/` → view `oficio_edit_step1`

**Campos / sessão:**

- Numeração: ofício (número/ano), protocolo.
- Motivo, custeio (UNIDADE, OUTRA_INSTITUICAO, ONUS_LIMITADOS), nome_instituicao_custeio.
- **Viajantes:** `viajantes_ids` (lista de IDs), formulário `ServidoresSelectForm` (multiselect de viajantes).

**Regras:**

- **Obrigatório:** “Selecione ao menos um viajante.” (`_validate_edit_wizard_data`: `if not viajantes_ids: erros["viajantes"] = "Selecione ao menos um viajante."`).
- Dados aplicados ao ofício via `_apply_step1_to_oficio(oficio, payload)`:
  - `oficio.viajantes.set(viajantes)` a partir de `viajantes_ids`; se vazio, `oficio.viajantes.clear()`.

**Modelo Oficio (participantes):**

- `viajantes` = `ManyToManyField(Viajante, related_name="oficios", blank=True)`.

---

### 3.2 Step 2 do ofício — Transporte (veículo e motorista)

- **Rota criação:** `oficios/etapa-2/` → view `oficio_step2`
- **Rota edição:** `oficios/<oficio_id>/editar/etapa-2/` → view `oficio_edit_step2`
- **Template:** `viagens/oficio_step2.html` — título “Etapa 2 - Transporte”, subtítulo “Informe veiculo e motorista. O motorista pode ser um viajante.”

**Campos (veículo):**

- **placa** (texto; ao sair do campo busca veículo cadastrado por placa).
- **modelo** (texto, pode vir do cadastro do veículo).
- **combustivel** (select ou texto, opções do sistema).
- **tipo_viatura** (Caracterizada / Descaracterizada).

**Campos (motorista):**

- **motorista:** select de viajantes (`MotoristaSelectForm`) — pode ser um dos viajantes já escolhidos no step 1.
- **motorista_nome:** texto livre para “motorista nome manual” (ex.: motorista de outro ofício).
- **Motorista “carona”** (não é um dos viajantes do ofício):
  - `motorista_oficio_numero`, `motorista_oficio_ano`, `motorista_protocolo`.
  - Exibidos em bloco condicional `carona-fields` quando motorista é carona.

**Regras de validação (edit flow, `_validate_edit_wizard_data`):**

- Veículo: “Preencha placa, modelo e combustivel.” (`if not placa_val or not modelo_val or not combustivel_val: erros["veiculo"] = ...`).
- Viajantes: “Selecione ao menos um viajante.” (step 1).
- Se motorista carona: exige número e ano do ofício do motorista e protocolo.

**Persistência (`_apply_step2_to_oficio`):**

- **Veículo:** se placa existe e há `Veiculo` com essa placa, usa FK `oficio.veiculo`; senão `veiculo = None`. Sempre preenche também `placa`, `modelo`, `combustivel` (texto) e `tipo_viatura` no ofício.
- **Motorista:**  
  - Se há `motorista_id` (viajante): `motorista_viajante` = esse Viajante, `motorista` = nome, `motorista_carona = False`.  
  - Se motorista não está em `viajantes_ids`: `motorista_carona = True`; preenche `motorista_oficio`, `motorista_oficio_numero`, `motorista_oficio_ano`, `motorista_protocolo`, `carona_oficio_referencia` (FK para outro ofício se aplicável).

**Modelo Oficio (veículo e motorista):**

- `veiculo` = `ForeignKey(Veiculo, null=True, blank=True, related_name="oficios")`
- `placa`, `modelo`, `combustivel` = CharField (redundantes com cadastro do veículo, mas preenchidos)
- `tipo_viatura` = CharField (choices Caracterizada/Descaracterizada)
- `motorista` = CharField (nome)
- `motorista_viajante` = `ForeignKey(Viajante, null=True, blank=True, related_name="oficios_motorista")`
- `motorista_oficio`, `motorista_oficio_numero`, `motorista_oficio_ano`, `motorista_protocolo`
- `motorista_carona` = BooleanField
- `carona_oficio_referencia` = `ForeignKey("self", null=True, blank=True, ...)`

---

## 4. Resumo das entidades do legado que participam da “composição”

- **Evento:** não possui campos de composição; etapa 3 = hub de ofícios.
- **Oficio:**
  - Participantes: `viajantes` (M2M com Viajante).
  - Veículo: `veiculo` (FK), `placa`, `modelo`, `combustivel`, `tipo_viatura`.
  - Motorista: `motorista` (nome), `motorista_viajante` (FK), `motorista_oficio*`, `motorista_protocolo`, `motorista_carona`, `carona_oficio_referencia`.
- **Viajante:** cadastro de servidores; usados em `oficio.viajantes` e opcionalmente em `oficio.motorista_viajante`.
- **Veiculo:** cadastro de veículos; `oficio.veiculo` pode apontar para um; placa usada para busca no step 2.

---

## 5. Campos obrigatórios (composição no ofício)

- **Step 1:** pelo menos um viajante selecionado; protocolo.
- **Step 2:** placa, modelo e combustível (do veículo); se motorista for “carona”, número/ano do ofício do motorista e protocolo.

Motorista pode ser opcional em alguns fluxos (nome manual vazio), mas o step 2 sempre exige veículo (placa, modelo, combustivel).

---

## 6. Regras de negócio relevantes

- Viajantes: ao menos um por ofício.
- Veículo: placa, modelo e combustível obrigatórios; pode buscar veículo por placa e preencher modelo/combustível/tipo_viatura.
- Motorista: pode ser um dos viajantes do ofício ou “carona” (outro ofício + protocolo); se carona, exige ofício do motorista e protocolo.
- Numeração do ofício: reservada/atribuída no step 1; evento pode ser passado via `evento_id` na sessão ao criar ofício a partir da Etapa 3 do evento.

---

## 7. Vínculos com outras etapas e documentos

- **Evento → Ofícios:** um evento tem N ofícios; Etapa 3 do evento lista esses ofícios e permite criar novo com `evento_id` na sessão.
- **Ofício → Evento:** FK opcional; quando criado a partir do evento, trechos do step 3 do ofício podem ser “seedados” a partir dos roteiros do evento (`_seed_trechos_from_evento_roteiros`).
- **Termos:** por (ofício, viajante); usam viajantes e dados do ofício (incl. motorista/veículo para texto).
- **PT/OS:** vinculados ao ofício; etapa 4 do evento exige PT ou OS quando não tem convite/ofício.
- **Justificativa:** por ofício (prazo < 10 dias); desbloqueia finalização do ofício.
- **Documentos/central:** ofício gera ofício DOCX/PDF, justificativa, plano, ordem, termos; tudo atrelado ao ofício, não ao evento diretamente.

Não há “composição centralizada no evento” que alimente termos ou documentos; cada ofício carrega sua própria composição.

---

## 8. Fluxo principal do usuário (composição no legado)

1. **Pelo evento:** Evento → Etapa 2 (Roteiro) → Etapa 3 (Ofícios) → “Criar Ofício neste Evento” → wizard do ofício.
2. **Wizard do ofício:**  
   - Step 1: numeração, protocolo, motivo, custeio, **seleção de viajantes** (obrigatório ≥ 1).  
   - Step 2: **placa, modelo, combustível, tipo viatura**, **motorista** (viajante ou carona com ofício/protocolo).  
   - Step 3: trechos (roteiro).  
   - Step 4: resumo / finalização.
3. Edição: mesmo fluxo por etapas; `oficio_edit_step1`, `oficio_edit_step2`, etc.

Ou seja: o usuário nunca preenche “composição da viagem” em uma tela do **evento**; preenche na criação/edição de **cada ofício**.

---

## 9. Casos especiais

- **Motorista carona:** motorista não é um dos viajantes do ofício; preenche ofício e protocolo do motorista; pode ter `carona_oficio_referencia` (FK para outro ofício).
- **Veículo não cadastrado:** ofício pode ter apenas placa/modelo/combustivel em texto, com `veiculo` FK null.
- **Criação a partir do evento:** `evento_id` na sessão; step 3 do ofício pode pré-preencher trechos a partir dos roteiros do evento.
- **Validação ao salvar (edit):** `_validate_edit_wizard_data` exige protocolo, viajantes, placa/modelo/combustivel, trechos e retorno; se motorista carona, ofício e protocolo do motorista.

---

## 10. O que precisa existir no projeto novo para ficar equivalente ao legado

### 10.1 Fiel ao legado (equivalência)

- **Etapa 3 do evento** = “Ofícios do evento” (hub): listar ofícios do evento, criar novo com contexto do evento, editar, central de documentos. Status “OK” quando existir ao menos um ofício vinculado ao evento.
- **Composição (viajantes, veículo, motorista)** somente no **módulo Ofício** (quando existir), em duas etapas:
  - Etapa 1 do ofício: numeração, protocolo, motivo, custeio, **viajantes** (obrigatório ≥ 1).
  - Etapa 2 do ofício: **veículo** (placa, modelo, combustível, tipo_viatura), **motorista** (viajante do ofício ou carona com ofício/protocolo).
- Modelo **Oficio** (ou equivalente) com: `viajantes` (M2M), `veiculo` (FK), `placa`, `modelo`, `combustivel`, `motorista`, `motorista_viajante`, campos de motorista carona e `carona_oficio_referencia`.
- **Evento** sem campos de composição; composição sempre associada ao ofício.

### 10.2 Se o projeto novo quiser “Etapa 3 — Composição da viagem” no nível do evento

Isso **não** existe no legado. Seria uma decisão de desenho diferente:

- **Opção A:** Manter Etapa 3 do evento = Ofícios (como no legado) e tratar composição apenas dentro do fluxo do ofício quando o módulo ofício for implementado.
- **Opção B:** Introduzir uma “Etapa 3 — Composição da viagem” no **evento** (viajantes, veículo, motorista no nível do evento), sabendo que no legado essa informação só existe por ofício. Nesse caso:
  - Ou a composição do evento serve como “default” ao criar ofícios (pré-preenchimento).
  - Ou o evento passa a ter uma composição “global” além dos ofícios (duplicação de conceito em relação ao legado).

Recomendação: para **equivalência funcional** com o legado, manter Etapa 3 do evento = Ofícios e implementar composição (viajantes, veículo, motorista) no wizard do ofício (steps 1 e 2). Qualquer “composição no evento” deve ser documentada explicitamente como extensão em relação ao legado.

---

## 11. Arquivos do legado consultados

| Arquivo | Uso |
|--------|-----|
| `legacy/viagens/urls.py` | Rotas evento guiado etapa 3, ofício step 2/3, edit step 2/3 |
| `legacy/viagens/views/_shared.py` | `evento_guiado_etapa3`, `oficio_step2`, `oficio_edit_step3`, `_apply_step1_to_oficio`, `_apply_step2_to_oficio`, `_validate_edit_wizard_data`, contexto step 2 |
| `legacy/viagens/models.py` | `Evento`, `Oficio` (viajantes, veiculo, motorista*, carona) |
| `legacy/viagens/forms.py` | Formulários do ofício (ServidoresSelectForm, MotoristaSelectForm, etc.) |
| `legacy/viagens/templates/viagens/evento_guiado_etapa3.html` | Tela Etapa 3 do evento (lista de ofícios) |
| `legacy/viagens/templates/viagens/oficio_step2.html` | Tela Transporte do ofício (veículo + motorista) |
| `legacy/viagens/services/evento_guiado.py` | Progresso do painel; etapa3_ok = evento.oficios.exists() |

---

**Fim do relatório.** Nenhuma alteração foi feita no código; apenas análise e documentação do comportamento do projeto legado para embasar decisões de implementação no projeto novo.
