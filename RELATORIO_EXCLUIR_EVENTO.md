# Relatório: Exclusão de evento no módulo Eventos

## 1) Arquivos alterados

| Arquivo | Alteração |
|--------|-----------|
| `eventos/views.py` | Import de `messages` e `require_http_methods`; nova view `evento_excluir` (POST only); remoção do import local de `messages` em `tipos_demanda_excluir`. |
| `eventos/urls.py` | Nova rota `path('<int:pk>/excluir/', login_required(views.evento_excluir), name='excluir')`. |
| `templates/eventos/evento_lista.html` | Botão "Excluir" por linha: form POST para `eventos:excluir` com `onsubmit="return confirm('Excluir este evento?');"`. |
| `templates/eventos/evento_detalhe.html` | Botão "Excluir evento": form POST para `eventos:excluir` com confirmação JS. |
| `eventos/tests/test_eventos.py` | Nova classe `EventoExcluirTest` com 5 testes (login, sem vínculos, com roteiros bloqueado, redirect sucesso, GET retorna 405). |

---

## 2) Rota criada

- **URL:** `POST /eventos/<pk>/excluir/`
- **Name:** `eventos:excluir`
- **View:** `evento_excluir(request, pk)`
- **Decoradores:** `@login_required`, `@require_http_methods(['POST'])` — exclusão só por POST; GET retorna 405.

---

## 3) Regra de exclusão adotada

- **Permitir exclusão** quando o evento **não** tiver **roteiros** (`RoteiroEvento`) vinculados.
  - Nesse caso o evento é excluído com `evento.delete()`. O Django remove em cascata os `EventoDestino` e limpa a tabela M2M de `tipos_demanda` (ver item 4).
- **Bloquear exclusão** quando o evento tiver **ao menos um roteiro** (`evento.roteiros.exists()`).
  - Não chama `delete()`; redireciona para a lista com mensagem de erro: *"Este evento não pode ser excluído porque já possui dados vinculados (roteiros)."*

Roteiros foram escolhidos como vínculo impeditivo por representarem dados da Etapa 2 (trabalho já realizado). Tipos de demanda e destinos são dados da própria definição do evento (Etapa 1) e são tratados em cascata.

---

## 4) Bloqueio x cascata para vínculos internos

- **Bloqueio:** exclusão é **bloqueada** apenas quando existem **roteiros** (`RoteiroEvento`) vinculados ao evento.
- **Cascata (segura nesta fase):**
  - **EventoDestino:** `on_delete=models.CASCADE` no FK para `Evento`. Ao excluir o evento, os destinos do evento são excluídos pelo Django.
  - **RoteiroEvento:** `on_delete=models.CASCADE` no FK para `Evento`. Se não houvesse regra de negócio, o Django excluiria os roteiros ao excluir o evento; a regra de negócio **impede** a exclusão do evento quando existe ao menos um roteiro, então a cascata de roteiros não é executada na prática.
  - **Tipos de demanda (M2M):** não há FK de `Evento` em `TipoDemandaEvento`; a tabela intermediária do M2M é limpa ao excluir o evento. Nenhum `TipoDemandaEvento` é apagado.

Resumo: para eventos **sem roteiros**, a exclusão é permitida e os únicos dados removidos em cascata são os **destinos do evento** (e o próprio evento); tipos de demanda continuam no sistema. Para eventos **com roteiros**, a exclusão é bloqueada e nada é apagado.

---

## 5) Como testar manualmente

1. **Exclusão permitida (sem roteiros)**  
   - Criar um evento pelo fluxo guiado (Etapa 1 com tipos e destinos); não criar roteiros.  
   - Na **lista de eventos**, clicar em "Excluir" na linha do evento; confirmar no diálogo.  
   - Deve redirecionar para a lista e exibir mensagem de sucesso; o evento some.  
   - Repetir criando um evento, abrindo o **detalhe** e clicando em "Excluir evento"; confirmar. Mesmo resultado.

2. **Exclusão bloqueada (com roteiros)**  
   - Criar um evento e, no fluxo guiado, adicionar ao menos um roteiro na Etapa 2.  
   - Na lista ou no detalhe, clicar em "Excluir" / "Excluir evento" e confirmar.  
   - Deve permanecer na lista (ou voltar para ela) com mensagem de erro informando que o evento não pode ser excluído por possuir dados vinculados (roteiros). O evento continua na lista.

3. **Segurança**  
   - Sem estar logado, acessar diretamente `POST /eventos/<id>/excluir/` (ex.: via ferramenta de requisições). Deve redirecionar para login.  
   - Acessar `GET /eventos/<id>/excluir/`: deve retornar 405 (Method Not Allowed).

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Rota POST `/eventos/<pk>/excluir/` criada | OK |
| Exclusão somente por POST (GET retorna 405) | OK |
| Login obrigatório para excluir | OK |
| Evento sem vínculos impeditivos (sem roteiros) pode ser excluído | OK |
| Evento com roteiros não pode ser excluído; mensagem clara | OK |
| Após exclusão bem-sucedida: redirect para lista + mensagem de sucesso | OK |
| Botão "Excluir" na lista (por linha) | OK |
| Botão "Excluir evento" no detalhe | OK |
| Confirmação antes de excluir (JS) | OK |
| Testes: login, sem vínculos, com roteiros, redirect, GET 405 | OK |
