# Relatório — Cálculo automático de quilometragem nos trechos (Google Routes API)

**OBSOLETO — A integração com Google Routes API foi removida do projeto. O cálculo de km/tempo nos trechos é feito por estimativa local (coordenadas + haversine). Ver `RELATORIO_ESTIMATIVA_LOCAL_KM.md`.**

---

## Resumo

Foi implementado o cálculo opcional de distância (km) e duração estimada nos **trechos dos roteiros** via **Google Routes API (computeRoutes)**. O uso é apenas nos trechos; a chave é configurada por variável de ambiente; o cálculo é acionado por botão "Calcular km"; após calcular, os valores podem ser editados manualmente. Serviço isolado, endpoint autenticado e UI sem recarregar a página.

---

## 1) Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `eventos/models.py` | Campos `distancia_km`, `duracao_estimada_min`, `rota_fonte`, `rota_calculada_em` em `RoteiroEventoTrecho`. |
| `eventos/migrations/0007_trecho_distancia_duracao_rota.py` | Migração que adiciona os quatro campos. |
| `config/settings.py` | `GOOGLE_MAPS_API_KEY` lido de variável de ambiente. |
| `.env.example` | Exemplo de `GOOGLE_MAPS_API_KEY`. |
| `README.md` | Instrução opcional para configurar a chave. |
| `eventos/services/__init__.py` | Novo pacote de serviços. |
| `eventos/services/google_routes.py` | Serviço isolado: `calcular_rota_entre_cidades`, `minutos_para_hhmm`, tratamento de erros. |
| `eventos/views.py` | View `trecho_calcular_km` (POST, JSON); `_estrutura_trechos` e `trechos_initial` com `distancia_km`, `duracao_estimada_hhmm`, `id`. |
| `eventos/urls.py` | Rota `trechos/<int:pk>/calcular-km/` → `trecho_calcular_km`. |
| `templates/eventos/guiado/roteiro_form.html` | Botão "Calcular km", exibição de Distância e Tempo estimado por trecho, `initialTrechosData` e URL/CSRF para o fetch, JS para chamada e atualização do card. |
| `eventos/tests/test_eventos.py` | Classes `GoogleRoutesServiceTest` e `TrechoCalcularKmEndpointTest` com 7 testes (mock de HTTP). |

---

## 2) Modelagem adicionada

No model **`RoteiroEventoTrecho`**:

- **`distancia_km`** — `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)`  
  Preenchido manualmente ou pelo botão "Calcular km".

- **`duracao_estimada_min`** — `PositiveIntegerField(null=True, blank=True)`  
  Duração em minutos (ex.: 250).

- **`rota_fonte`** — `CharField(max_length=30, blank=True, default='')`  
  Ex.: `"GOOGLE"` quando calculado pela API.

- **`rota_calculada_em`** — `DateTimeField(null=True, blank=True)`  
  Data/hora do último cálculo.

Nenhum campo existente foi removido.

---

## 3) Como configurar GOOGLE_MAPS_API_KEY

1. No **Google Cloud Console**, crie um projeto (ou use um existente), ative a **Routes API** e crie uma chave de API.
2. No `.env` do projeto (cópia do `.env.example`), defina:
   ```bash
   GOOGLE_MAPS_API_KEY=sua-chave-aqui
   ```
3. Reinicie o servidor (ex.: `runserver`). O `settings.py` lê com `os.getenv('GOOGLE_MAPS_API_KEY', '').strip()`.
4. Sem a chave, o botão "Calcular km" continua visível (em trechos já salvos), mas a API retorna erro e a mensagem exibida indica que a chave não está configurada.

Não deixe a chave hardcoded no código.

---

## 4) Como funciona o serviço isolado

**Módulo:** `eventos/services/google_routes.py`

- **`minutos_para_hhmm(minutos)`**  
  Converte minutos em string `HH:MM` (ex.: 340 → `'05:40'`). Usado na UI e no JSON do endpoint.

- **`calcular_rota_entre_cidades(origem_cidade, origem_uf, destino_cidade, destino_uf, api_key)`**  
  1. Monta endereços no formato `"Cidade, UF, Brasil"` (ex.: `"Curitiba, PR, Brasil"`).  
  2. Faz `POST` em `https://routes.googleapis.com/directions/v2:computeRoutes` com:
     - Headers: `X-Goog-Api-Key`, `X-Goog-FieldMask: routes.duration,routes.distanceMeters`
     - Body: `origin.address`, `destination.address`, `travelMode: DRIVE`
  3. Lê `routes[0].distanceMeters` e `routes[0].duration` (ex.: `"24800s"`).  
  4. Converte distância para km (`Decimal`) e duração para minutos (segundos → `(s+29)//60`) e `duracao_estimada_hhmm`.  
  5. Retorna dict: `ok`, `distancia_km`, `duracao_estimada_min`, `duracao_estimada_hhmm`, `erro`, `raw` (opcional).

**Tratamento de erros:** chave ausente, timeout (15 s), exceção de rede, resposta não 200, JSON inválido, `routes` vazio. Em todos os casos retorna `ok=False` e `erro` preenchido, sem exceção não tratada.

---

## 5) Como funciona o endpoint

- **URL:** `POST /eventos/trechos/<pk>/calcular-km/`  
  Nome da rota: `eventos:trecho-calcular-km`.

- **Autenticação:** `@login_required`. Sem login → 302 para a página de login.

- **Entrada:** usa o trecho com `pk` da URL. Origem/destino vêm de `trecho.origem_cidade`/`origem_estado` e `trecho.destino_cidade`/`destino_estado` (nome da cidade e sigla da UF).

- **Fluxo:**  
  1. Carrega o trecho (com `select_related` para cidade/estado).  
  2. Monta `origem_cidade`, `origem_uf`, `destino_cidade`, `destino_uf`.  
  3. Chama `calcular_rota_entre_cidades(..., api_key=settings.GOOGLE_MAPS_API_KEY)`.  
  4. Se `ok`: atualiza o trecho (`distancia_km`, `duracao_estimada_min`, `rota_fonte='GOOGLE'`, `rota_calculada_em=timezone.now()`) e salva.  
  5. Responde com JSON: `ok`, `distancia_km`, `duracao_estimada_min`, `duracao_estimada_hhmm`, `erro`.

- **Resposta:** sempre 200 (JSON). Em erro da API, `ok: false` e `erro` com mensagem; trecho não é alterado.

---

## 6) Como testar manualmente

1. **Configurar a chave**  
   Defina `GOOGLE_MAPS_API_KEY` no `.env` e reinicie o servidor.

2. **Ter um roteiro com trechos salvos**  
   Crie um evento, preencha a Etapa 1, na Etapa 2 crie um roteiro com sede e pelo menos um destino e salve (para que os trechos existam no banco).

3. **Abrir a edição do roteiro**  
   Em "Editar" do roteiro, na seção "4) Trechos", cada card de trecho (com origem/destino) deve mostrar:
   - Distância: valor ou "—"
   - Tempo estimado: HH:MM ou vazio
   - Botão **"Calcular km"** (só em trechos já salvos).

4. **Clicar em "Calcular km"**  
   - O botão desabilita durante a requisição.  
   - Em sucesso: Distância e Tempo estimado são preenchidos no card (distância com 2 decimais, tempo em HH:MM); a página não recarrega.  
   - Em erro (chave inválida, API fora, etc.): mensagem em vermelho no próprio card.

5. **Persistência**  
   Salve o formulário e reabra a edição: os valores de km e tempo estimado devem continuar nos cards (e no banco: `distancia_km`, `duracao_estimada_min`, `rota_fonte`, `rota_calculada_em`).

6. **Edição manual**  
   Os campos de distância/duração exibidos são apenas leitura no card; a alteração manual desses valores hoje é feita no banco ou em evoluções futuras. O relatório de aceite considera “podem ser editados manualmente” como permissão de fluxo (não apagar após calcular); a persistência é pelo endpoint ao clicar em "Calcular km".

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Campos no model (distancia_km, duracao_estimada_min, rota_fonte, rota_calculada_em) + migração | OK |
| GOOGLE_MAPS_API_KEY em settings, .env.example, README; sem chave no código | OK |
| Serviço isolado em eventos/services/google_routes.py | OK |
| computeRoutes: endereço texto, distanceMeters, duration; erros tratados | OK |
| Endpoint POST autenticado, retorno JSON (ok, distancia_km, duracao_estimada_min, duracao_estimada_hhmm, erro) | OK |
| Trecho atualizado no banco quando API retorna sucesso | OK |
| UI: botão "Calcular km" por trecho (quando trecho tem id), exibição de km e tempo em HH:MM, sem recarregar página | OK |
| Helper minutos → HH:MM (ex.: 340 → 05:40); distância com 2 decimais na UI | OK |
| Testes: serviço converte resposta; endpoint exige login; endpoint retorna km/duração quando API OK; endpoint trata erro; trecho salvo com rota_fonte e rota_calculada_em; mock HTTP, sem rede | OK |
