# Relatório: Roteiros do evento — prefill e estrutura (sede + N destinos)

## 1) Arquivos alterados

| Arquivo | Alteração |
|--------|-----------|
| `eventos/models.py` | Novo model `RoteiroEventoDestino` (roteiro FK, estado, cidade, ordem). `RoteiroEvento`: removidos `destino_estado` e `destino_cidade`; `origem_*` tratados como sede; `esta_completo()` passa a exigir `self.destinos.exists()` e `if not self.pk: return False`; `__str__` usa lista de destinos. |
| `eventos/migrations/0005_roteiro_destinos.py` | Cria `RoteiroEventoDestino`, migra dados de `destino_*` para uma linha por roteiro, remove os dois FKs de `RoteiroEvento`. |
| `eventos/forms.py` | `RoteiroEventoForm`: removidos `destino_estado` e `destino_cidade`; mantidos sede (origem), saida_dt, duracao_min, retorno, observacoes. Validação de cidade/estado só para origem. |
| `eventos/views.py` | `_get_evento_etapa2`: prefetch de `destinos`. `_setup_roteiro_querysets`: apenas sede (origem). Novas funções `_destinos_roteiro_para_template`, `_trechos_roteiro`. Cadastrar: sede inicial de `ConfiguracaoSistema.cidade_sede_padrao`; `destinos_atuais` de `evento.destinos`; POST parseia `destino_estado_N`/`destino_cidade_N`, valida, salva roteiro, recria `RoteiroEventoDestino`, chama `roteiro.save()`. Editar: `destinos_atuais` de `roteiro.destinos`; mesmo fluxo de POST; contexto `trechos` para a lista. Lista: prefetch de `destinos` e exibição por roteiro. |
| `templates/eventos/guiado/roteiro_form.html` | Seção 1) Sede (UF + Cidade). 2) Destinos do roteiro (linhas dinâmicas com destino_estado_N, destino_cidade_N, adicionar/remover). 3) Duração e horários (duracao_min, ida, retorno). Trechos gerados (lista de/para quando há dados). JS: carregar cidades por estado, add/remove destinos, cálculo de chegada. |
| `templates/eventos/guiado/etapa_2_lista.html` | Coluna origem → destinos passa a usar `r.destinos` em vez de `destino_cidade`/`destino_estado`. |
| `eventos/tests/test_eventos.py` | Uso de `RoteiroEventoDestino`; testes de roteiro passam a enviar `destino_estado_0`/`destino_cidade_0`; criação de roteiro em testes com `RoteiroEventoDestino.objects.create`; novos testes: prefill sede da config, prefill destinos do evento, edição mostra dados do roteiro, form abre sem sede/destinos, múltiplos destinos. |

---

## 2) Prefill de sede

- **Fonte:** `ConfiguracaoSistema.get_singleton().cidade_sede_padrao`.
- **Quando:** Somente ao abrir **Cadastrar roteiro** (GET). Não na edição.
- **Como:** Se existir `cidade_sede_padrao`, o form recebe `initial['origem_estado']` e `initial['origem_cidade']` (estado da cidade sede). O usuário pode alterar.
- **Sem sede na config:** `initial` fica vazio; o formulário abre normalmente.

---

## 3) Prefill de destinos

- **Fonte:** Destinos do evento (Etapa 1), ou seja, `evento.destinos` (`EventoDestino`), ordenados por `ordem`.
- **Quando:** Somente ao abrir **Cadastrar roteiro** (GET). Na **edição** usam-se os destinos já salvos do roteiro (`roteiro.destinos`), não os do evento.
- **Como:** A view monta `destinos_atuais` (lista de dicts com `estado_id`, `cidade_id`, `cidade`, `estado`) a partir de `evento.destinos` (cadastro) ou `roteiro.destinos` (edição). O template renderiza uma linha por item (estado/cidade) com `destino_estado_N` e `destino_cidade_N`. Se o evento não tiver destinos, é enviado um único item vazio para sempre haver ao menos uma linha.
- **Liberdade:** O usuário pode editar, remover e adicionar destinos; o backend valida “pelo menos um destino” e “cidade do estado”.

---

## 4) Diferença entre criar novo e editar

| | Cadastro novo | Edição |
|--|----------------|--------|
| **Sede** | Preenchida por `ConfiguracaoSistema.cidade_sede_padrao` (se houver). | Valores já salvos do roteiro. |
| **Destinos** | Preenchidos pelos destinos do evento (Etapa 1). | Destinos já salvos do roteiro (`RoteiroEventoDestino`). Não são sobrescritos pelos destinos atuais do evento. |
| **Persistência** | POST: salva roteiro, apaga e recria `RoteiroEventoDestino` a partir do POST. | Idem: roteiro atualizado e destinos substituídos pelos do formulário. |

---

## 5) Como testar manualmente

1. **Configuração**
   - Em Configurações, definir “Cidade sede padrão” (ex.: Curitiba/PR).

2. **Evento com destinos**
   - Criar/editar um evento na Etapa 1 com pelo menos um destino (ex.: Curitiba e Londrina).

3. **Cadastrar roteiro**
   - Evento → Etapa 2 → Cadastrar roteiro.
   - Verificar: UF e Cidade da sede = sede padrão; linhas de destino = destinos do evento.
   - Alterar sede, destinos, duração, ida/retorno; salvar.
   - Conferir na lista da Etapa 2: sede → destinos e dados corretos.

4. **Editar roteiro**
   - Editar o roteiro criado.
   - Verificar: sede e destinos são os **do roteiro**, não os atuais do evento.
   - Alterar e salvar; reabrir e conferir persistência.

5. **Trechos**
   - Em um roteiro editado com sede e pelo menos um destino, a seção “Trechos gerados” deve mostrar: sede → 1º destino → … → último destino → sede.

6. **Sem sede / sem destinos**
   - Evento sem destinos na Etapa 1: cadastro de roteiro deve abrir com uma linha de destino vazia.
   - Configuração sem cidade sede: cadastro de roteiro deve abrir com sede em branco.

---

## 6) Checklist de aceite

| Item | Status |
|------|--------|
| Sede pré-preenchida da ConfiguracaoSistema no cadastro novo | OK |
| Destinos pré-preenchidos do evento (Etapa 1) no cadastro novo | OK |
| Edição usa dados salvos do roteiro (não do evento) | OK |
| Formulário abre sem quebrar quando não há sede ou destinos | OK |
| Múltiplos destinos do evento aparecem no novo roteiro | OK |
| Estrutura: Sede + 1..N destinos + duração + ida/retorno | OK |
| Trechos gerados (sede→d1→…→dN→sede) na tela de edição | OK |
| Validação: pelo menos um destino; cidade do estado | OK |
| Testes: prefill sede, prefill destinos, edição, sem quebrar, múltiplos destinos | OK |
