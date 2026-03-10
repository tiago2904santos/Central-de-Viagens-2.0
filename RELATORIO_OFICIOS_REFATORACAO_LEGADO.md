# Relatório: Limpeza e refeitura do módulo de Ofícios (baseado no legado)

**Data:** 2025-03-10  
**Objetivo:** Limpar a implementação anterior e recriar a Etapa 3 (Ofícios do evento) e o wizard do ofício com campos e regras do projeto legado, sem Central de Documentos nesta entrega.

---

## 1. Arquivos alterados / criados

| Arquivo | Alteração |
|--------|------------|
| **eventos/models.py** | Modelo **Oficio** expandido com todos os campos do legado: vínculos (evento, viajantes M2M, veiculo, motorista_viajante, carona_oficio_referencia); dados gerais (numero, ano, protocolo, motivo, custeio_tipo, nome_instituicao_custeio, tipo_destino); transporte (placa, modelo, combustivel, tipo_viatura); motorista (motorista, motorista_carona, motorista_oficio, motorista_oficio_numero, motorista_oficio_ano, motorista_protocolo). Choices: CUSTEIO_CHOICES, TIPO_DESTINO_CHOICES, TIPO_VIATURA_CHOICES. |
| **eventos/migrations/0011_oficio_campos_legado.py** | Migração que adiciona os novos campos ao Oficio. |
| **eventos/forms.py** | **OficioStep1Form**: numero, ano, protocolo, motivo, custeio_tipo, nome_instituicao_custeio, viajantes (M2M); validação: ao menos 1 viajante. **OficioStep2Form**: placa, modelo, combustivel, tipo_viatura, motorista_viajante, motorista_nome, motorista_carona, motorista_oficio_numero/ano, motorista_protocolo; validação: placa/modelo/combustivel obrigatórios; se carona, ofício número/ano e protocolo obrigatórios. |
| **eventos/views.py** | **Limpeza:** Removida view `oficio_documentos`. `guiado_etapa_3` docstring atualizada (sem central de documentos). **Alterações:** `guiado_etapa_3_criar_oficio` passa a redirecionar para `oficio-step1` (wizard) em vez de voltar à lista. `oficio_editar` passa a redirecionar para `oficio-step1`. **Novas views:** `_get_oficio_for_wizard`, `oficio_step1` (GET/POST Step 1), `oficio_step2` (GET/POST Step 2), `oficio_step3` (placeholder trechos), `oficio_step4` (resumo + botão finalizar). |
| **eventos/urls.py** | Removida rota `oficio-documentos`. Adicionadas: `oficio-step1`, `oficio-step2`, `oficio-step3`, `oficio-step4`. Comentário "Wizard do Ofício (Steps 1–4)". |
| **templates/eventos/guiado/etapa_3.html** | **Limpeza:** Removido botão/link "Central de Documentos". Adicionada coluna "Destino / Tipo" (tipo_destino). Ações: apenas "Editar" (link para wizard). Texto de apoio atualizado. |
| **templates/eventos/oficio/_wizard_stepper.html** | **Novo.** Barra de navegação entre steps 1–4. |
| **templates/eventos/oficio/wizard_step1.html** | **Novo.** Formulário Step 1: número, ano, protocolo, motivo, custeio, nome instituição, viajantes (checkboxes). Botões Salvar e Salvar e avançar (Step 2). |
| **templates/eventos/oficio/wizard_step2.html** | **Novo.** Formulário Step 2: placa, modelo, combustível, tipo viatura, motorista (viajante ou nome manual), motorista carona e campos (número/ano ofício, protocolo). Botões Salvar e Salvar e avançar (Step 3). |
| **templates/eventos/oficio/wizard_step3.html** | **Novo.** Placeholder: mensagem de que trechos serão integrados com roteiros do evento em breve. Botão Avançar (Step 4). |
| **templates/eventos/oficio/wizard_step4.html** | **Novo.** Resumo do ofício (número, protocolo, motivo, custeio, viajantes, placa/modelo, combustível, motorista, status). Botões: Finalizar ofício, Voltar para Ofícios do evento, Voltar (Step 3). |
| **eventos/tests/test_eventos.py** | Removida asserção que continha `oficio-documentos`. Ajuste em `test_criar_oficio_preserva_vinculo_com_evento`: redirecionamento esperado para step1. **Nova classe OficioWizardTest:** step1 exige ao menos 1 viajante; step1 salva viajantes; step2 exige placa/modelo/combustível; step2 motorista carona exige ofício/protocolo; editar redireciona para step1; step4 finalizar marca status FINALIZADO. |

---

## 2. O que foi limpo da implementação anterior

- **Central de Documentos:** Removido link e botão da lista da Etapa 3. Removidas rota `oficio-documentos` e view `oficio_documentos`. Não há tela de central de documentos nesta entrega.
- **Etapa 3:** Mantida como "Ofícios do evento" (hub/lista). Removida qualquer referência a "composição da viagem" na tela; lista apenas ofícios com coluna Destino/Tipo e ação Editar.
- **Placeholder de edição:** A ação "Editar" passou a levar ao Step 1 do wizard (não mais à página placeholder). O arquivo `editar_placeholder.html` permanece no projeto mas não é mais usado (oficio_editar redireciona).
- **Criação de ofício:** Fluxo alterado de "criar rascunho e voltar à lista" para "criar rascunho e abrir Step 1 do wizard".

---

## 3. Como a Etapa 3 foi refeita

- **Rota:** `GET /eventos/<evento_id>/guiado/etapa-3/` (inalterada).
- **Conteúdo:** Lista de ofícios do evento em tabela com colunas: Número/Ano, Protocolo, **Destino/Tipo** (tipo_destino), Status, Ações (apenas **Editar**). Botão principal "Criar Ofício neste Evento" (leva a criar rascunho e abrir Step 1). Links: Voltar ao painel, Excluir evento. Sem botão ou link para Central de Documentos.
- **Status da etapa no painel:** `etapa3_ok = evento.oficios.exists()` (OK quando existe ao menos um ofício).

---

## 4. Como a lista de ofícios foi implementada

- A listagem usa `evento.oficios.order_by('id')`.
- Cada linha exibe: `numero_formatado`, `protocolo`, `get_tipo_destino_display` (ou tipo_destino), badge de status (Rascunho/Finalizado), link "Editar" para `eventos:oficio-editar` (que redireciona para Step 1).
- Mensagem quando não há ofícios: "Nenhum ofício vinculado...". Botão "Criar Ofício neste Evento" em dois pontos (topo e rodapé).

---

## 5. Como o wizard/cadastro do ofício foi implementado

- **Step 1 (Dados e viajantes):** Rota `oficio/<pk>/step1/`. Formulário com numero, ano, protocolo, motivo, custeio_tipo, nome_instituicao_custeio, viajantes (checkboxes; queryset = viajantes finalizados). Regra: pelo menos 1 viajante. Salvar persiste no Oficio e em `oficio.viajantes.set()`. "Salvar e avançar" redireciona para Step 2.
- **Step 2 (Transporte):** Rota `oficio/<pk>/step2/`. Campos: placa, modelo, combustivel, tipo_viatura, motorista_viajante (select), motorista_nome, motorista_carona (checkbox), motorista_oficio_numero, motorista_oficio_ano, motorista_protocolo. Regras: placa, modelo e combustível obrigatórios; se motorista_carona, número e ano do ofício do motorista e protocolo obrigatórios. Persistência em campos do Oficio; motorista_oficio preenchido como "N/AAAA" quando há número e ano. "Salvar e avançar" redireciona para Step 3.
- **Step 3 (Trechos):** Placeholder. Mensagem de que a integração com roteiros do evento será feita em breve. Botão "Avançar (Step 4)".
- **Step 4 (Resumo):** Resumo em dl (número, protocolo, motivo, custeio, viajantes, placa/modelo, combustível, motorista, status). Botão "Finalizar ofício" (define status FINALIZADO). Botão "Voltar para Ofícios do evento" (quando ofício tem evento). Botão "Voltar (Step 3)".

Navegação entre steps: incluindo `_wizard_stepper.html` em cada step com links para step1/2/3/4.

---

## 6. Campos do legado reproduzidos

| Legado | Projeto novo (Oficio) |
|--------|------------------------|
| evento (FK) | evento (FK) |
| viajantes (M2M) | viajantes (M2M Viajante) |
| veiculo (FK) | veiculo (FK Veiculo) |
| motorista_viajante (FK) | motorista_viajante (FK Viajante) |
| carona_oficio_referencia (FK self) | carona_oficio_referencia (FK self) |
| numero, ano, protocolo | numero, ano, protocolo |
| motivo | motivo |
| custeio_tipo, nome_instituicao_custeio | custeio_tipo, nome_instituicao_custeio |
| tipo_destino | tipo_destino (choices INTERIOR/CAPITAL/BRASILIA) |
| placa, modelo, combustivel, tipo_viatura | placa, modelo, combustivel, tipo_viatura |
| motorista (nome) | motorista |
| motorista_carona | motorista_carona |
| motorista_oficio, motorista_oficio_numero, motorista_oficio_ano, motorista_protocolo | idem |
| status (RASCUNHO/FINALIZADO) | status (STATUS_RASCUNHO/STATUS_FINALIZADO) |

---

## 7. Regras do legado aplicadas

1. **Etapa 3 do evento:** OK quando existe ao menos um ofício vinculado ao evento (`evento.oficios.exists()`).
2. **Step 1:** Obrigatório pelo menos 1 viajante; validação no form e persistência em `oficio.viajantes.set()`.
3. **Step 2:** Placa, modelo e combustível obrigatórios (validação no form).
4. **Motorista:** Pode ser um viajante (motorista_viajante) ou nome manual (motorista); motorista carona (motorista_carona=True) exige número e ano do ofício do motorista e protocolo (validação no form).
5. **Criação a partir do evento:** "Criar Ofício neste Evento" cria Oficio com evento preenchido e redireciona para Step 1, mantendo vínculo com o evento.
6. **Status:** Rascunho por padrão; Step 4 permite "Finalizar ofício" (status FINALIZADO).

---

## 8. O que ficou fora do escopo (explicitamente)

- **Central de Documentos:** Não implementada. Sem link, rota ou tela nesta entrega.
- **Geração de PDF/DOCX do ofício:** Não implementada.
- **Pacote do evento / compilação de documentos:** Não implementada.
- **Step 3 (Trechos):** Apenas placeholder; integração com roteiros do evento para preencher/editar trechos do ofício fica para implementação futura.
- **Excluir ofício:** Não adicionado na lista da Etapa 3 (apenas Editar); pode ser incluído depois com confirmação.

---

## 9. Como testar manualmente

1. Login e acessar um evento; abrir o painel do evento (fluxo guiado).
2. **Painel:** Clicar no bloco "Etapa 3 — Ofícios do evento". Deve abrir a lista de ofícios. Sem ofícios: mensagem e botão "Criar Ofício neste Evento".
3. **Criar ofício:** Clicar em "Criar Ofício neste Evento". Deve criar um ofício e abrir o Step 1 do wizard.
4. **Step 1:** Preencher número, ano, protocolo, motivo, escolher custeio, selecionar ao menos um viajante. "Salvar e avançar" deve ir para Step 2.
5. **Step 2:** Preencher placa, modelo, combustível. Escolher motorista (viajante ou nome manual) ou marcar motorista carona e preencher número/ano do ofício e protocolo. "Salvar e avançar" deve ir para Step 3.
6. **Step 3:** Clicar em "Avançar (Step 4)".
7. **Step 4:** Ver resumo. Clicar em "Finalizar ofício". Depois "Voltar para Ofícios do evento". Na lista, o ofício deve aparecer com status Finalizado e tipo_destino (se preenchido).
8. **Editar:** Na lista, clicar em "Editar" em um ofício. Deve abrir o Step 1 com dados já salvos. Alterar e salvar; reabrir e conferir persistência.

---

## 10. Checklist de aceite

| Item | Status |
|------|--------|
| Etapa 3 do evento = "Ofícios do evento" | OK |
| Etapa 3 lista ofícios do evento | OK |
| Bloco da Etapa 3 no painel clicável | OK |
| Botão "Criar Ofício neste Evento" existe e funciona | OK |
| Cadastro/wizard do ofício existe e funciona | OK |
| Step 1 tem viajantes (obrigatório ≥ 1) | OK |
| Step 2 tem transporte e motorista | OK |
| Regras principais do legado aplicadas | OK |
| Central de Documentos não existe nesta entrega | OK |
| Lista com coluna Destino/Tipo | OK |
| Step 4 permite finalizar ofício | OK |
| Testes Painel + Etapa 3 + Wizard passando | OK |

---

**Fim do relatório.**
