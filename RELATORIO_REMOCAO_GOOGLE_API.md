# Relatório — Remoção completa da Google Routes API / Google Maps API

## 1) Arquivos alterados / removidos

| Ação | Arquivo |
|------|---------|
| **Alterado** | `config/settings.py` — Removidos `GOOGLE_MAPS_API_KEY` e comentário sobre Google Routes; aviso de `.env` passou a citar `POSTGRES_*`. |
| **Alterado** | `.env.example` — Removidas a variável `GOOGLE_MAPS_API_KEY` e o comentário sobre Google Routes API. |
| **Alterado** | `README.md` — Removido o bloco "Opcional — Google Routes API" (instruções de chave e uso do botão). |
| **Alterado** | `eventos/services/__init__.py` — Docstring atualizada: "estimativa local" em vez de "Google Routes". |
| **Removido** | `eventos/services/google_routes.py` — Arquivo excluído (serviço completo da Google). |
| **Alterado** | `eventos/tests/test_eventos.py` — Removida a classe `GoogleRoutesServiceTest` (4 testes que usavam `google_routes` e mocks de `requests.post`). |
| **Alterado** | `RELATORIO_ENV_SETTINGS.md` — Exemplos e validação no shell passaram a usar `POSTGRES_DB` em vez de `GOOGLE_MAPS_API_KEY`. |
| **Alterado** | `RELATORIO_TRECHOS_GOOGLE_ROUTES_KM.md` — Incluído aviso de **OBSOLETO** no topo, com referência à estimativa local. |
| **Alterado** | `RELATORIO_ESTIMATIVA_LOCAL_KM.md` — Texto atualizado: `google_routes.py` removido; nenhuma dependência Google no projeto. |

**Não alterados (e por quê):**

- **`eventos/views.py`** — Já utilizava apenas `estimativa_local`; não havia imports nem uso de Google.
- **`eventos/urls.py`** — A rota `trechos/<int:pk>/calcular-km/` foi mantida: é o endpoint de **estimativa local** (mesma URL, backend sem Google).
- **`templates/eventos/guiado/roteiro_form.html`** — Botão "Estimar km/tempo" e variáveis `urlTrechoCalcularKmBase` / `csrfTokenCalcularKm` continuam sendo usados para esse endpoint local; não há referência a Google.
- **`eventos/migrations/0007_trecho_distancia_duracao_rota.py`** — Migration histórica; não foi editada (boas práticas Django). O estado atual do model está em `eventos/models.py` (help_text já em "ESTIMATIVA_LOCAL").

---

## 2) O que foi removido do settings / .env.example / README

- **settings.py:** Variável `GOOGLE_MAPS_API_KEY` e a linha que a lia de `os.getenv(...)`; comentário "Google Routes API (cálculo de km nos trechos dos roteiros)". No aviso de `.env` inexistente, o exemplo passou de "GOOGLE_MAPS_API_KEY" para "POSTGRES_*".
- **.env.example:** Linha `GOOGLE_MAPS_API_KEY=SUA_CHAVE_AQUI` e o comentário "Google Routes API — chave para cálculo de distância/duração nos trechos dos roteiros (opcional)".
- **README.md:** Parágrafo "Opcional — Google Routes API (cálculo de km nos trechos dos roteiros)" e a instrução para definir `GOOGLE_MAPS_API_KEY` no `.env` e usar o botão "Calcular km".

---

## 3) Rotas removidas

**Nenhuma rota foi removida.** A URL `trechos/<int:pk>/calcular-km/` permanece e é usada pelo fluxo de **estimativa local** (view `trecho_calcular_km` chama `estimar_distancia_duracao`). O nome da rota continua `trecho-calcular-km`.

---

## 4) Views / services removidos

- **Removido:** `eventos/services/google_routes.py` (arquivo inteiro), incluindo:
  - `calcular_rota_entre_cidades`
  - `minutos_para_hhmm` (a versão usada hoje é a de `estimativa_local`)
  - `ROTA_FONTE_GOOGLE`, constantes de URL/timeout e toda a lógica de chamada à API Google.

**Mantida:** View `trecho_calcular_km` em `eventos/views.py` — agora depende apenas de `estimar_distancia_duracao` (estimativa local).

---

## 5) Testes removidos / ajustados

- **Removida** a classe **`GoogleRoutesServiceTest`** em `eventos/tests/test_eventos.py`, com os 4 testes:
  - `test_minutos_para_hhmm` (google_routes)
  - `test_calcular_rota_converte_resposta_corretamente` (mock `requests.post`)
  - `test_calcular_rota_sem_chave_retorna_erro`
  - `test_calcular_rota_api_erro_nao_quebra`

**Mantidos:** `EstimativaLocalServiceTest` (incluindo `test_minutos_para_hhmm` via `estimativa_local`) e `TrechoCalcularKmEndpointTest` (endpoint com estimativa local e persistência). A suíte de eventos continua passando sem a integração Google.

---

## 6) Campos do model mantidos para uso futuro (e por quê)

No model **`RoteiroEventoTrecho`** os campos abaixo foram **mantidos** e já são usados pela estimativa local:

| Campo | Uso atual / futuro |
|-------|---------------------|
| `distancia_km` | Preenchido pela estimativa local; exibido no card do trecho. |
| `duracao_estimada_min` | Preenchido pela estimativa local; exibido no card. |
| `rota_fonte` | Recebe `ESTIMATIVA_LOCAL`; pode ser usado para MANUAL ou outras fontes no futuro. Sem constantes ou choices Google. |
| `rota_calculada_em` | Data/hora do último cálculo (local); útil para auditoria. |

Nenhum valor default, enum ou help_text faz referência à Google; os textos atuais falam em "Estimar km/tempo" e "estimativa local".

---

## 7) Confirmação: nenhuma dependência ativa da Google API

- Não existe mais `GOOGLE_MAPS_API_KEY` em settings, `.env.example` ou README.
- Não existe mais o arquivo `eventos/services/google_routes.py` nem imports dele em views, URLs ou testes.
- O endpoint `trechos/<pk>/calcular-km/` é exclusivamente de estimativa local (coordenadas + haversine).
- O botão na UI é "Estimar km/tempo" e chama esse endpoint; não há botão, JS ou mensagem de erro referindo Google, chave ou API externa.
- Nenhum teste chama ou mocka a Google; a suíte não depende de Google.

**Única menção restante:** o arquivo de migration **`eventos/migrations/0007_trecho_distancia_duracao_rota.py`** contém, no histórico, um `help_text` com a palavra "GOOGLE". Esse arquivo não foi alterado por ser migration já aplicada; o estado atual do model está correto em `eventos/models.py` e não referencia Google.

O sistema funciona normalmente sem qualquer dependência da Google API.
