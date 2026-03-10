# Relatório: Etapa 3 do evento como Ofícios do evento (fiel ao legado)

**Data:** 2025-03-10  
**Objetivo:** Corrigir o rumo da implementação da Etapa 3 do evento com base na análise do legado: Etapa 3 = hub de Ofícios do evento (não composição da viagem). Composição (viajantes, veículo, motorista) fica no wizard do Ofício, a ser implementado depois.

---

## 1. Arquivos alterados / criados

| Arquivo | Alteração |
|--------|------------|
| `eventos/models.py` | Adicionado modelo **Oficio** (evento FK, numero, ano, protocolo, status, created_at, updated_at). Mantidos no Evento os campos veiculo, motorista, observacoes_operacionais e o modelo EventoParticipante (não usados na Etapa 3; reservados para uso futuro se necessário). |
| `eventos/migrations/0010_oficio_model.py` | Nova migração criando a tabela Oficio. |
| `eventos/views.py` | `_evento_etapa3_ok`: passa a usar `evento.oficios.exists()`. `guiado_painel`: Etapa 3 renomeada para "Ofícios do evento"; query do evento sem prefetch de veiculo/motorista/participantes. `guiado_etapa_3`: substituída por hub (listagem de ofícios, sem formulário de composição). Novas views: `guiado_etapa_3_criar_oficio`, `oficio_editar` (placeholder), `oficio_documentos` (placeholder). Removido uso de EventoEtapa3Form. |
| `eventos/urls.py` | Comentário "Etapa 3: Composição" trocado por "Ofícios do evento". Novas rotas: `guiado-etapa-3-criar-oficio`, `oficio-editar`, `oficio-documentos`. |
| `eventos/forms.py` | EventoEtapa3Form mantido no arquivo (não usado na Etapa 3; pode ser reutilizado no wizard do ofício depois). |
| `eventos/admin.py` | Registrado **Oficio** no admin. |
| `templates/eventos/guiado/etapa_3.html` | Substituído por tela de hub: título "Ofícios do evento (Etapa 3)", tabela de ofícios (número/ano, protocolo, status, ações Editar / Central de Documentos), botão "Criar Ofício neste Evento", links Voltar ao painel e Excluir evento. |
| `templates/eventos/guiado/painel.html` | Texto do botão inferior: "Etapa 3 — Composição da viagem" → "Etapa 3 — Ofícios do evento". |
| `templates/eventos/oficio/editar_placeholder.html` | **Novo.** Placeholder da edição do ofício (mensagem "wizard em breve", links para etapa 3 e painel). |
| `templates/eventos/oficio/documentos_placeholder.html` | **Novo.** Placeholder da central de documentos do ofício. |
| `eventos/tests/test_eventos.py` | PainelBlocosClicaveisTest: assertiva do bloco 3 atualizada para "Ofícios do evento". Classe **EventoEtapa3ComposicaoTest** substituída por **EventoEtapa3OficiosTest** (login, listar ofícios, botão criar, etapa3 OK com ofício, etapa3 pendente sem ofício, criar ofício preserva vínculo). Import de `Oficio` adicionado. |

---

## 2. Blocos do painel clicáveis

- **Comportamento:** No painel do evento, cada card de etapa implementada (1, 2 e 3) é um link (`<a href="{{ e.url }}">`) que leva à rota correspondente.
- **Etapas 1 e 2:** `guiado-etapa-1` (pk do evento), `guiado-etapa-2` (evento_id).
- **Etapa 3:** `guiado-etapa-3` (evento_id) → tela "Ofícios do evento".
- **Etapas 4, 5 e 6:** Continuam como "Em breve", sem URL (`e.url` é `None`), apenas `<div>` com badge.
- **Acessibilidade:** Links com `aria-label="Ir para Etapa N — Nome"`. Classe `card-clickable` e hover mantidos.

---

## 3. Como a Etapa 3 foi implementada

- **Nome:** "Ofícios do evento" (conforme legado).
- **Rota:** `GET /eventos/<evento_id>/guiado/etapa-3/` → view `guiado_etapa_3`.
- **Conteúdo:** Lista de ofícios do evento (`evento.oficios.order_by('id')`). Tabela com colunas: Número/Ano, Protocolo, Status (Rascunho/Finalizado), Ações (Editar, Central de Documentos). Se não houver ofícios, card com texto "Nenhum ofício vinculado..." e botão "Criar Ofício neste Evento". Dois botões de ação no rodapé: "Criar Ofício neste Evento" e "Voltar ao painel".
- **Criar ofício:** Link/botão "Criar Ofício neste Evento" aponta para `guiado-etapa-3-criar-oficio` (GET ou POST). A view cria um `Oficio(evento=evento, status=RASCUNHO)` e redireciona de volta para a lista da Etapa 3, com mensagem de sucesso.
- **Editar ofício:** Link "Editar" → `eventos:oficio-editar` (pk do ofício). Template placeholder informa que o wizard de edição será implementado em breve.
- **Central de Documentos:** Link "Central de Documentos" → `eventos:oficio-documentos` (pk do ofício). Template placeholder informa que a central será implementada em breve.

---

## 4. Vínculo evento → ofícios (modelagem)

- **Modelo Oficio** (em `eventos/models.py`):
  - `evento` = `ForeignKey(Evento, null=True, blank=True, related_name='oficios')`
  - `numero`, `ano` (opcionais, para numeração futura)
  - `protocolo` (CharField, blank)
  - `status` (RASCUNHO / FINALIZADO)
  - `created_at`, `updated_at`
- **Relação:** Um evento tem N ofícios (`evento.oficios`). Um ofício pertence a um evento (ou nenhum, se `evento` for null).
- **Status da Etapa 3 no painel:** `etapa3_ok = evento.oficios.exists()` (True se existir ao menos um ofício vinculado).

---

## 5. Regra do status OK / Pendente da Etapa 3

- **OK:** quando existe ao menos um ofício vinculado ao evento (`evento.oficios.exists()` retorna True).
- **Pendente:** quando não existe nenhum ofício (`evento.oficios.count() == 0`).
- Implementação: função `_evento_etapa3_ok(evento)` em `eventos/views.py` retorna `evento.oficios.exists()`.

---

## 6. O que foi deixado para o módulo Ofício

- **Composição da viagem no nível do evento:** Não implementada. Não há tela de seleção global de viajantes, veículo ou motorista no evento.
- **Campos no modelo Evento** (veiculo, motorista, observacoes_operacionais) e o modelo **EventoParticipante** permanecem no banco; não são usados na Etapa 3 atual. Podem ser removidos em limpeza futura ou reaproveitados como default ao criar ofício.
- **Wizard do Ofício (futuro):**
  - **Step 1:** numeração, protocolo, motivo, custeio, viajantes (obrigatório ≥ 1).
  - **Step 2:** veículo (placa, modelo, combustível, tipo_viatura), motorista (viajante ou carona com ofício/protocolo).
- **Central de Documentos do ofício:** Geração/download de ofício, justificativa, plano/ordem, termos — placeholder pronto, implementação futura.
- **Edição do ofício:** Tela real de edição (wizard steps) a ser implementada; hoje só placeholder.

---

## 7. Como testar manualmente

1. **Login:** Acessar o sistema com usuário autenticado.
2. **Criar ou abrir um evento:** Ir em Eventos e criar um evento ou abrir um existente; acessar "Fluxo guiado" / painel do evento.
3. **Painel — blocos clicáveis:** Clicar no card "Etapa 1 — Evento": deve abrir a etapa 1. Voltar ao painel. Clicar no card "Etapa 2 — Roteiros": deve abrir a etapa 2. Voltar. Clicar no card "Etapa 3 — Ofícios do evento": deve abrir a tela de ofícios.
4. **Etapa 3 — lista vazia:** Sem ofícios, deve aparecer "Nenhum ofício vinculado..." e o botão "Criar Ofício neste Evento". Status da Etapa 3 no painel deve ser "Pendente".
5. **Criar ofício:** Na Etapa 3, clicar em "Criar Ofício neste Evento". Deve voltar à mesma tela com mensagem de sucesso e uma linha na tabela (número "—", status Rascunho, ações Editar e Central de Documentos).
6. **Painel — Etapa 3 OK:** Voltar ao painel. O card da Etapa 3 deve estar com badge "OK".
7. **Editar / Documentos:** Na lista de ofícios, clicar em "Editar" ou "Central de Documentos". Devem abrir as telas placeholder com links de volta para Ofícios do evento e Painel.

---

## 8. Checklist de aceite

| Item | Status |
|------|--------|
| Blocos das etapas 1, 2 e 3 clicáveis no painel | OK |
| Etapa 3 do evento = "Ofícios do evento" | OK |
| Etapa 3 lista ofícios do evento | OK |
| Etapa 3 permite criar novo ofício no contexto do evento | OK |
| Etapa 3 fica OK quando existir ao menos um ofício vinculado | OK |
| Etapa 3 fica Pendente quando não existir ofício | OK |
| Não existe composição global da viagem no evento nesta etapa | OK |
| Botão "Criar Ofício neste Evento" visível e funcional | OK |
| Links Editar e Central de Documentos (placeholders) presentes | OK |
| Fluxo de criação de ofício preserva vínculo com o evento | OK |

---

**Fim do relatório.**
