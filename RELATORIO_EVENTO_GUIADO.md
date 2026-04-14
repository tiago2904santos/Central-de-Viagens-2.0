# Relatório — Evento guiado (primeira entrega)

Implementação do fluxo principal: entrada do fluxo guiado, Etapa 1 do evento e painel de progresso/pendências.

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `config/urls.py` | Inclusão de `path('eventos/', include('eventos.urls'))`. |
| `eventos/forms.py` | Novo `EventoEtapa1Form` (campos da Etapa 1, sem `status`). |
| `eventos/views.py` | Funções `_evento_etapa1_completa`, `guiado_novo`, `guiado_etapa_1`, `guiado_painel` e helper `_setup_etapa1_querysets`. |
| `eventos/urls.py` | Rotas `guiado/novo/`, `<pk>/guiado/etapa-1/`, `<pk>/guiado/painel/`. |
| `templates/eventos/evento_lista.html` | Botão "Novo (fluxo guiado)" no header; botão "Abrir fluxo guiado" por linha. |
| `templates/eventos/evento_detalhe.html` | Botão "Abrir fluxo guiado". |
| `core/navigation.py` | Eventos habilitado com `url_name='eventos:lista'`. |
| `eventos/tests/test_eventos.py` | Classe `EventoGuiadoTest` com 6 testes. |

### Novos arquivos

| Arquivo | Descrição |
|---------|-----------|
| `templates/eventos/guiado/etapa_1.html` | Formulário da Etapa 1 (título, tipo, descrição, datas, estado/cidade principal, cidade base, convite/ofício) e botões Salvar / Salvar e continuar. |
| `templates/eventos/guiado/painel.html` | Painel com resumo do evento, status e cards das 6 etapas (1 OK/Pendente, 2–6 Em breve). |

---

## 2) Rotas criadas

| Rota | Nome | Comportamento |
|------|------|----------------|
| `GET /eventos/guiado/novo/` | `eventos:guiado-novo` | Exige login. Cria evento em RASCUNHO (título provisório, tipo OUTRO, data_inicio/data_fim = hoje, cidade_base da configuração se houver) e redireciona para `/eventos/<id>/guiado/etapa-1/`. |
| `GET` / `POST /eventos/<id>/guiado/etapa-1/` | `eventos:guiado-etapa-1` | Exige login. Exibe e processa formulário da Etapa 1. Salvar: persiste; se dados mínimos completos, status → EM_ANDAMENTO; permanece na etapa 1. Salvar e continuar: persiste e redireciona para o painel. |
| `GET /eventos/<id>/guiado/etapa-1/` | `eventos:guiado-etapa-1` | Exige login. Abre a etapa inicial do fluxo guiado com os dados do evento e o acesso às próximas etapas. |

---

## 3) Como ficou a Etapa 1

- **Campos:** título, tipo_demanda, descricao, data_inicio, data_fim, estado_principal, cidade_principal, cidade_base, tem_convite_ou_oficio_evento.
- **Comportamento:** estado_principal carrega cidades em `cidade_principal` via API existente (`cadastros:api-cidades-por-estado`). Cidade base vem preenchida da configuração ao criar pelo fluxo guiado e pode ser alterada.
- **Validação:** data_fim ≥ data_inicio; cidade_principal deve pertencer ao estado_principal; cidade_base válida (choices ativos).
- **Botões:** Salvar (fica na etapa 1); Salvar e continuar (vai ao painel); Cancelar (volta ao painel).
- **Dados mínimos para EM_ANDAMENTO:** título (não vazio), tipo_demanda, data_inicio, data_fim e data_fim ≥ data_inicio.

---

## 4) Como ficou o painel

- **Cabeçalho:** título da página "Painel do evento"; links "Ver detalhe" e "Lista de eventos".
- **Resumo:** card com título do evento, tipo, período, local (cidade/estado) e badge de status.
- **Etapas:** 6 cards em grid:
  - Etapa 1 — Evento: OK (verde) se dados mínimos preenchidos, senão Pendente (amarelo).
  - Etapas 2–6 (Roteiros, Ofícios, Fundamentação/PT-OS, Termos, Finalização): "Em breve".
- **Ações:** "Voltar para Etapa 1" (primary); "Próxima etapa" (leva à página "Em breve").

---

## 5) Como testar manualmente

1. **Entrada do fluxo**
   - Sem login: acessar `/eventos/guiado/novo/` → redirecionamento para login.
   - Com login: acessar "Eventos" no menu → "Novo (fluxo guiado)" → deve criar um evento e abrir a Etapa 1.

2. **Etapa 1**
   - Preencher título, tipo, datas (data_fim ≥ data_inicio). Opcional: estado/cidade principal (se escolher estado, cidade deve ser do mesmo estado), cidade base (pode vir da configuração), convite/ofício.
   - "Salvar": permanece na etapa 1; com dados mínimos o status do evento passa a "Em andamento".
   - "Salvar e continuar": salva e vai ao painel.
   - Testar cidade principal de outro estado → deve exibir erro de validação.

3. **Painel**
   - Acessar por "Abrir fluxo guiado" na lista ou no detalhe do evento, ou após "Salvar e continuar".
   - Verificar resumo, status e cards (Etapa 1 OK ou Pendente; 2–6 Em breve).
   - "Voltar para Etapa 1" → formulário da etapa 1.
   - "Próxima etapa" → página "Em breve".

4. **Integração**
   - Na lista de eventos: "Novo (fluxo guiado)" e por linha "Abrir fluxo guiado".
   - No detalhe do evento: "Abrir fluxo guiado" → painel.

---

## 6) Checklist de aceite

| Critério | Status |
|----------|--------|
| Model Evento com os campos solicitados (titulo, tipo_demanda, descricao, data_inicio, data_fim, estado_principal, cidade_principal, cidade_base, tem_convite_ou_oficio_evento, status, created_at, updated_at) | OK |
| tipo_demanda: PCPR_NA_COMUNIDADE, OPERACAO_POLICIAL, PARANA_EM_ACAO, OUTRO | OK |
| status: RASCUNHO, EM_ANDAMENTO, FINALIZADO, ARQUIVADO | OK |
| cidade_base padrão da ConfiguracaoSistema quando existir | OK |
| Validação data_fim ≥ data_inicio e cidade_principal no estado_principal | OK |
| GET /eventos/guiado/novo/ exige login e redireciona para etapa-1 | OK |
| GET+POST /eventos/<id>/guiado/etapa-1/ com Salvar e Salvar e continuar | OK |
| Salvar atualiza etapa e, se mínimos completos, status EM_ANDAMENTO | OK |
| Salvar e continuar redireciona para o painel | OK |
| GET /eventos/<id>/guiado/painel/ com resumo, status e etapas 1–6 | OK |
| Etapa 1 = OK quando dados mínimos preenchidos; 2–6 Em breve | OK |
| Botão "Voltar para Etapa 1" e "Próxima etapa" (Em breve) | OK |
| Lista e detalhe do evento com "Abrir fluxo guiado" / "Novo (fluxo guiado)" | OK |
| Menu Eventos habilitado | OK |
| Testes: guiado novo (login + redirect), etapa 1 salva, cidade inválida, painel autenticado, etapa 1 OK no painel | OK |

**Não implementado nesta entrega (conforme escopo):** roteiros, ofícios, termos, justificativas, pacote final.

---

*Relatório referente à primeira entrega do fluxo Evento guiado.*
