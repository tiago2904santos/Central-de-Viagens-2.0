# Relatório — Etapa 3 (Composição da viagem) e painel com blocos clicáveis

**Data:** 2026-03-10

---

## 1. Arquivos alterados / criados

### Criados
- `eventos/migrations/0009_etapa3_composicao_viagem.py` — migração: campos em Evento (veiculo, motorista, observacoes_operacionais) e modelo EventoParticipante.
- `templates/eventos/guiado/etapa_3.html` — tela da Etapa 3 (veículo, motorista, participantes, observações).
- `RELATORIO_ETAPA3_E_PAINEL_CLICAVEL.md` — este relatório.

### Alterados
- `eventos/models.py` — Campos em Evento: `veiculo` (FK Veiculo), `motorista` (FK Viajante), `observacoes_operacionais` (TextField). Novo modelo `EventoParticipante` (evento, viajante, ordem).
- `eventos/forms.py` — Novo `EventoEtapa3Form` (veiculo, motorista, viajantes_participantes, observacoes_operacionais); querysets só finalizados; validação: motorista entre participantes, ≥1 participante.
- `eventos/views.py` — `_evento_etapa3_ok(evento)`; `guiado_painel` com etapa 3 implementada, `etapas` com `url` por etapa e blocos clicáveis; nova view `guiado_etapa_3`.
- `eventos/urls.py` — Rota `guiado-etapa-3`: `<int:evento_id>/guiado/etapa-3/`.
- `templates/eventos/guiado/painel.html` — Blocos 1–3 com link quando `e.url`; etapas 4–6 “Em breve” sem link; botões inferiores: Etapa 1, Etapa 2, Etapa 3; CSS para `.card-clickable`.
- `eventos/tests/test_eventos.py` — Imports (Cargo, Viajante, Veiculo, etc.; EventoParticipante); `PainelBlocosClicaveisTest`; `EventoEtapa3ComposicaoTest`; ajuste em `test_painel_guiado_carrega_autenticado` (texto do botão).

---

## 2. Modelagem adotada

- **Evento (campos novos):**
  - `veiculo` — FK para `cadastros.Veiculo` (null/blank para migração; no formulário é obrigatório).
  - `motorista` — FK para `cadastros.Viajante` (obrigatório quando há veículo; deve ser um dos participantes).
  - `observacoes_operacionais` — TextField, opcional.

- **EventoParticipante (novo modelo):**
  - `evento` — FK Evento.
  - `viajante` — FK Viajante.
  - `ordem` — PositiveIntegerField (exibição).
  - UniqueConstraint (evento, viajante).

Participantes são acessados por `evento.participantes.order_by('ordem')` (queryset de `EventoParticipante`); viajantes por `[p.viajante for p in evento.participantes.all()]`.

---

## 3. Rotas adicionadas

| Método | Path | Nome | Descrição |
|--------|------|------|-----------|
| GET/POST | `/eventos/<evento_id>/guiado/etapa-3/` | `eventos:guiado-etapa-3` | Tela da Etapa 3 (composição da viagem). Exige login. |

---

## 4. Regras da composição (Etapa 3)

- Apenas **viajantes** e **veículos** com status **FINALIZADO** entram nos selects/checkboxes.
- **Veículo** obrigatório (nesta versão).
- **Motorista** obrigatório e deve ser um dos **viajantes participantes** selecionados.
- **Pelo menos 1 viajante** participante.
- Não é possível escolher o mesmo viajante mais de uma vez (lista de checkboxes, um por viajante).
- **Observações operacionais** opcionais.

---

## 5. Status Etapa 3 (OK / Pendente)

- **OK:** existe veículo (finalizado), existe motorista, motorista está entre os participantes e existe ao menos um participante.
- **Pendente:** caso contrário.

Implementado em `_evento_etapa3_ok(evento)` e usado no painel para o badge da Etapa 3.

---

## 6. Blocos do painel clicáveis

- Cada etapa na lista recebe um dicionário com `url` (reverse da rota) ou `url: None` (em breve).
- No template:
  - Se `e.url`: o bloco é um `<a href="{{ e.url }}">` envolvendo o card (classe `card-clickable`), com `aria-label` para acessibilidade.
  - Se não há `url`: bloco é um `<div class="card">` com badge “Em breve”, sem link.
- Estilos em `{% block extra_css %}`: hover e cursor para `.card-clickable`.

Etapas 1, 2 e 3 têm rota e ficam clicáveis; 4, 5 e 6 continuam “Em breve” e não clicáveis.

---

## 7. Como testar manualmente

1. **Login** e ir em Eventos.
2. Criar evento (fluxo guiado) e preencher Etapa 1 e salvar.
3. **Painel:** abrir o painel do evento.
   - Clicar no **bloco “Etapa 1 — Evento”** → deve abrir a Etapa 1.
   - Voltar ao painel; clicar no **bloco “Etapa 2 — Roteiros”** → deve abrir a lista da Etapa 2.
   - Voltar ao painel; clicar no **bloco “Etapa 3 — Composição da viagem”** → deve abrir a Etapa 3.
   - Etapas 4, 5 e 6 devem aparecer como “Em breve” e sem link.
4. **Etapa 3:**
   - Em Cadastros, ter ao menos 1 viajante e 1 veículo **finalizados**.
   - Na Etapa 3, escolher veículo, motorista (entre os viajantes listados) e marcar pelo menos um viajante participante.
   - Salvar → mensagem de sucesso; ao reabrir a Etapa 3, dados devem aparecer preenchidos.
   - “Salvar e voltar ao painel” → redireciona ao painel.
   - No painel, com composição mínima preenchida, a Etapa 3 deve aparecer com badge **OK**.
5. **Validação:** escolher motorista que não está nos participantes → deve dar erro de validação.
6. **Rascunho:** viajante/veículo em rascunho não deve aparecer nos selects/checkboxes da Etapa 3.

---

## 8. Checklist de aceite

| Item | Status |
|------|--------|
| Bloco Etapa 1 clicável | OK |
| Bloco Etapa 2 clicável | OK |
| Bloco Etapa 3 clicável | OK |
| Etapa 3 funcional (GET/POST) | OK |
| Etapa 3 salva veículo, motorista e participantes | OK |
| Apenas viajantes/veículos FINALIZADOS listados | OK |
| Viajante/veículo em rascunho não aparece | OK |
| Motorista obrigatório e entre participantes | OK |
| Painel reflete status OK da Etapa 3 quando completo | OK |
| Reabrir Etapa 3 mostra dados salvos | OK |
| Etapa 3 exige login | OK |
| Etapas 4–6 “Em breve” sem link | OK |
| Testes PainelBlocosClicaveisTest e EventoEtapa3ComposicaoTest | OK |
