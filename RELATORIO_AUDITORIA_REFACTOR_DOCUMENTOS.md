# RELATORIO_AUDITORIA_REFACTOR_DOCUMENTOS.md

> **Arquivo gerado para auditar o estado real da refatoração "documentos independentes"**
> Gerado em: 18/03/2026
> Propósito: análise arquitetural crítica — pode ser colado integralmente no ChatGPT para revisão independente.

---

## 1. Resumo executivo

O sistema sofreu uma reestruturação significativa em relação ao estado inicial (`first commit` de 2024), migrando de uma arquitetura puramente centrada em eventos para um modelo híbrido. Contudo, **essa mudança foi incremental e parcial, não uma reescrita arquitetural limpa**.

Do ponto de vista técnico:

- O app `documentos` foi **esvaziado completamente** (models.py com 1 linha, views.py com 5 linhas, urls.py sem rotas). Toda a lógica foi movida para o app `eventos`.
- O app `eventos` cresceu para absorver: Ofício (com wizard 4 etapas), Roteiro (avulso e vinculado), DocumentoAvulso (tipo: termo, justificativa, PT, OS, outro), além do próprio Evento.
- O `Oficio` e o `RoteiroEvento` podem existir sem vínculo com Evento (FK `null=True`).
- No entanto, `EventoFundamentacao` (Plano de Trabalho / Ordem de Serviço) ainda usa `OneToOneField(Evento, CASCADE)` obrigatório.
- `TermoAutorizacao`, `Justificativa`, `PlanoTrabalho` e `OrdemServico` não têm models próprios no sentido das entidades requiridas — são implementados como `DocumentoAvulso` (tipo genérico) ou campos dentro do `Oficio`/`EventoFundamentacao`.

**Conclusão preliminar**: a arquitetura foi **parcialmente alterada**. Ofício e Roteiro ganharam independência real. PT e OS ainda exigem Evento. O sistema ainda não é document-centric no sentido estrito solicitado. A transição ocorreu mas ficou incompleta em pontos críticos do domínio.

---

## 2. Base de comparação utilizada

| Dado | Valor |
|------|-------|
| Branch atual | `refactor/arquitetura-documentos-independentes` |
| Commit HEAD | `3af9ddf` — _chore: checkpoint antes da reestruturacao completa para documentos independentes_ |
| Branch base remota | `origin/main` |
| Merge-base calculado | `b6d903ece3412432a4df12d1da891380884cc3f3` |
| Merge-base | commit `b6d903e` — _docs: adiciona livro de funcoes e regras de negocio de oficios_ |
| Commits à frente do merge-base | `1` (só o checkpoint com `db.sqlite3.bak`) |
| Diff entre `origin/main` (009785b local) e HEAD | **247 arquivos, +44.372 / -3.641 linhas** |

**Observação crítica**: O diff relevante para análise é entre `origin/main` (ref local `009785b`) e o HEAD atual. O "checkpoint antes da reestruturação" foi o único commit do branch, adicionando apenas `db.sqlite3.bak`. Ou seja: **toda a refatoração analisada já existia na base antes desse branch ser criado** — ela foi consolidada gradualmente em commits anteriores à ramificação. O branch atual não introduziu código novo além do backup do banco.

---

## 3. Inventário de arquivos alterados

### 3.1 Criados (principais)

**App `eventos` — novo app criado do zero:**
- `eventos/__init__.py`, `eventos/admin.py`, `eventos/apps.py`
- `eventos/models.py` (1.228 linhas)
- `eventos/views.py` (4.996 linhas)
- `eventos/views_global.py` (1.050 linhas)
- `eventos/forms.py` (1.039 linhas)
- `eventos/urls.py` (110 linhas)
- `eventos/utils.py` (108 linhas)
- `eventos/migrations/` — 30 migrations (0001 a 0030)

**Serviços do app `eventos`:**
- `eventos/services/__init__.py`
- `eventos/services/corredores_pr.py` (518 linhas)
- `eventos/services/diarias.py` (309 linhas)
- `eventos/services/documentos/__init__.py` (64 linhas)
- `eventos/services/documentos/backends.py` (220 linhas)
- `eventos/services/documentos/context.py` (701 linhas)
- `eventos/services/documentos/filenames.py` (36 linhas)
- `eventos/services/documentos/justificativa.py` (55 linhas)
- `eventos/services/documentos/oficio.py` (163 linhas)
- `eventos/services/documentos/ordem_servico.py` (86 linhas)
- `eventos/services/documentos/plano_trabalho.py` (94 linhas)
- `eventos/services/documentos/renderer.py` (405 linhas)
- `eventos/services/documentos/termo_autorizacao.py` (390 linhas)
- `eventos/services/documentos/types.py` (112 linhas)
- `eventos/services/documentos/validators.py` (260 linhas)
- `eventos/services/estimativa_local.py` (650 linhas)
- `eventos/services/justificativa.py` (53 linhas)
- `eventos/services/oficio_schema.py` (58 linhas)
- `eventos/services/plano_trabalho_domain.py` (158 linhas)
- `eventos/services/routing_provider.py` (224 linhas)

**Templates criados (app eventos):**
- `templates/eventos/global/documentos_hub.html` (179 linhas)
- `templates/eventos/global/oficios_lista.html` (153 linhas)
- `templates/eventos/global/roteiros_lista.html` (143 linhas)
- `templates/eventos/global/roteiro_avulso_form.html` (213 linhas)
- `templates/eventos/global/documento_avulso_form.html` (96 linhas)
- `templates/eventos/global/documento_derivado_lista.html` (128 linhas)
- `templates/eventos/global/justificativas_lista.html` (116 linhas)
- `templates/eventos/global/termos_lista.html` (102 linhas)
- `templates/eventos/global/simulacao_diarias.html` (223 linhas)
- `templates/eventos/oficio/wizard_step1.html` (630 linhas)
- `templates/eventos/oficio/wizard_step2.html` (1.132 linhas)
- `templates/eventos/oficio/wizard_step3.html` (1.329 linhas)
- `templates/eventos/oficio/wizard_step4.html` (262 linhas)
- `templates/eventos/oficio/justificativa.html` (170 linhas)
- `templates/eventos/oficio/documentos.html` (162 linhas)
- `templates/eventos/oficio/_wizard_header.html` (18 linhas)
- `templates/eventos/oficio/_wizard_stepper.html` (12 linhas)
- `templates/eventos/guiado/etapa_1.html` a `etapa_6.html`
- `templates/eventos/guiado/painel.html`, `roteiro_form.html` (566 linhas)
- Templates para modelos_justificativa, modelos_motivo, tipos_demanda

**Testes:**
- `eventos/tests/test_eventos.py` (7.073 linhas)
- `eventos/tests/test_diarias.py` (136 linhas)
- `eventos/tests/test_global_views.py` (204 linhas)
- `eventos/tests/test_plano_trabalho.py` (158 linhas)
- `cadastros/tests/test_cadastros.py` (1.525 linhas)

**Scripts:**
- `scripts/analisar_estimativa_pr.py` (321 linhas)
- `scripts/benchmark_estimativa_pr_relatorio.py` (503 linhas)
- `scripts/validar_estimativa_pr_cega.py` (501 linhas)

**Relatórios (docs — 60+ arquivos .md):**
- Todos os `RELATORIO_*.md` na raiz do projeto

### 3.2 Alterados (principais)

- `config/urls.py` — adicionado `path('eventos/', include('eventos.urls'))`; `documentos/` foi removido
- `core/navigation.py` — reescrita da sidebar (295 linhas de delta)
- `core/views/dashboard.py` — ajustes (16 linhas de delta)
- `static/css/style.css` — 618 linhas adicionadas/alteradas
- `cadastros/views/hubs.py` — 78 linhas alteradas
- `templates/base.html` — 2 linhas
- `templates/core/dashboard.html` — 14 linhas

### 3.3 Removidos (principais)

**App `documentos` — esvaziado, não excluído:**
- `documentos/admin.py` — removido conteúdo (14 linhas removidas)
- `documentos/migrations/0001_initial.py` — 268 linhas removidas (toda a estrutura antiga)
- `documentos/models.py` — de 377 linhas para 1 linha (`from django.db import models`)
- `documentos/views.py` — de 655 linhas para 5 linhas (stub vazio)
- `documentos/urls.py` — de 52 rotas para 0 rotas (apenas esqueleto)

**Templates do app `documentos` — todos removidos:**
- `templates/documentos/oficios/step1.html` a `step4.html`, `lista.html`, `justificativa.html`, `_stepper.html`
- `templates/documentos/eventos/`, `roteiros/`, `termos/`, `justificativas/`, `ordens/`, `planos/`, `modelos_*`
- `templates/documentos/hub.html`, `templates/documentos/lista.html`

---

## 4. Alterações por camada

### 4.1 Models

**Models relevantes em `eventos/models.py`:**

| Model | Linhas aprox. | Evento FK | Natureza |
|-------|---------------|-----------|----------|
| `TipoDemandaEvento` | 15-36 | — | Cadastro auxiliar; sem vínculo com Evento |
| `Evento` | 38-158 | — | Entidade principal do módulo de evento |
| `EventoParticipante` | 157-180 | **OBRIGATÓRIO** (`CASCADE`) | Filho de Evento; faz sentido |
| `SolicitantePlanoTrabalho` | 181-207 | — | Cadastro auxiliar |
| `CoordenadorOperacional` | 208-228 | — | Cadastro auxiliar |
| `EventoFundamentacao` | 223-335 | **OBRIGATÓRIO** (`OneToOne CASCADE`) | **Problema: PT/OS acoplado ao Evento** |
| `EfetivoPlanoTrabalho` | 336-380 | **OBRIGATÓRIO** (via Evento) | Filho de Evento |
| `EventoTermoParticipante` | 381-460 | **OBRIGATÓRIO** (`CASCADE`) | Termo por participante de evento |
| `EventoFinalizacao` | 460-510 | **OBRIGATÓRIO** (`OneToOne CASCADE`) | Filho de Evento |
| `DocumentoAvulso` | 511-618 | **OPCIONAL** (`SET_NULL, null=True`) | Documento sem dependência de Evento ✓ |
| `ModeloMotivoViagem` | 619-680 | — | Cadastro auxiliar |
| `ModeloJustificativa` | 681-718 | — | Cadastro auxiliar |
| `Oficio` | 719-1008 | **OPCIONAL** (`CASCADE, null=True`) | **Principal mudança arquitetural** ✓ |
| `OficioTrecho` | 1009-1100 | — | Filho de Oficio; independente ✓ |
| `EventoDestino` | 1127-1152 | **OBRIGATÓRIO** (`CASCADE`) | Filho de Evento; faz sentido |
| `RoteiroEventoDestino` | 1153-1180 | — | Filho de RoteiroEvento |
| `RoteiroEventoTrecho` | 1181-1257 | — | Filho de RoteiroEvento |
| `RoteiroEvento` | 1259-1228 | **OPCIONAL** (`CASCADE, null=True`) | **Mudança arquitetural** ✓ |

**Campos críticos do `Oficio`:**
```python
evento = models.ForeignKey(Evento, ..., null=True, blank=True)  # OPCIONAL ✓
tipo_origem = CharField(choices=['AVULSO', 'EVENTO'])            # distingue contexto ✓
roteiro_evento = FK(RoteiroEvento, null=True, blank=True)        # opcional ✓
viajantes = ManyToManyField('cadastros.Viajante')                # sem tabela intermediária própria
```

**Ausências críticas vs especificação:**
- Não existe model `OficioViajante` como tabela intermediária real com `ordem` e snapshot
- Não existe model `TermoAutorizacao` próprio
- Não existe model `Justificativa` próprio (é campo texto no Oficio + DocumentoAvulso genérico)
- Não existe model `PlanoTrabalho` próprio
- Não existe model `OrdemServico` próprio
- `EventoFundamentacao` é o único portador de PT/OS e exige Evento obrigatoriamente

### 4.2 Migrations

30 migrations em `eventos/`, todas aplicadas (`[X]`):

| Migration | O que muda |
|-----------|------------|
| 0001 | Criação de Evento, EventoParticipante, EventoDestino |
| 0002 | Adição de RoteiroEvento (com evento obrigatório) |
| 0003 | TipoDemandaEvento, destinos do roteiro |
| 0004 | Popula tipos de demanda padrão |
| 0005 | RoteiroEventoDestino |
| 0006 | RoteiroEventoTrecho |
| 0007 | Distância e duração nos trechos do roteiro |
| 0008 | Tempo cru adicional nos trechos |
| 0009 | Composição da viagem: veículo, motorista, participantes |
| **0010** | **Cria model Oficio com `evento = FK(null=True, blank=True)` ← INDEPENDENTE DESDE O INÍCIO** |
| 0011 | Campos legado do ofício (placa, modelo, combustível etc.) |
| 0012 | ModeloMotivoViagem, data de criação, número/ano automático |
| 0013 | Normalização de protocolos existentes |
| 0014 | Remove OficioCounter, adiciona numeração automática |
| 0015 | `porte_transporte_armas` no Oficio |
| 0016 | `estado_sede`, `cidade_sede`, motorista no Oficio |
| 0017 | `quantidade_diarias`, `roteiro_evento` (FK opcional) no Oficio |
| 0018 | `ModeloJustificativa`, `justificativa_texto`, `justificativa_modelo` |
| 0019 | `EventoFundamentacao` (PT/OS com `OneToOne(Evento, CASCADE)`) |
| 0020 | `tipo_documento` em EventoFundamentacao |
| 0021 | `EventoTermoParticipante` (termos por participante, evento obrigatório) |
| 0022 | `EventoFinalizacao` |
| 0023 | `modalidade` no EventoTermoParticipante |
| 0024 | PT: solicitante, coordenador, efetivo |
| **0025** | **RoteiroEvento: `evento` vira `null=True`; campo `tipo` (AVULSO/EVENTO) ← ROTEIRO INDEPENDENTE** |
| 0026 | Ajuste de roteiro avulso autogenerado |
| **0027** | **Oficio: campo `tipo_origem` (AVULSO/EVENTO)** |
| 0028 | Campos de retorno (direção de volta) no Oficio |
| 0029 | `gerar_termo_preenchido` no Oficio |
| 0030 | Altera `roteiro_modo` no Oficio |

**Estado das migrations:**
- `python manage.py check`: 0 issues
- `python manage.py makemigrations --check`: `No changes detected`
- Cadeia coerente e sem quebras

**Ponto crítico na migration 0019**: `EventoFundamentacao` foi criado com `OneToOneField(Evento, CASCADE)` obrigatório. Nunca foi alterado para `null=True`. Não há migration que torne PT/OS independentes.

### 4.3 URLs

**Estrutura atual de rotas:**

```
/ (root)                    — core (dashboard)
/cadastros/                 — app cadastros (viajantes, veículos, cargos, etc.)
/eventos/                   — app eventos (TUDO: ofícios, roteiros, eventos, docs)
  oficio/novo/              — criação de ofício (avulso OU com evento_id)
  oficio/<pk>/step1/        — wizard step 1
  oficio/<pk>/step2/        — wizard step 2
  oficio/<pk>/step3/        — wizard step 3
  oficio/<pk>/step4/        — wizard step 4
  oficio/<pk>/justificativa/
  oficio/<pk>/documentos/
  oficio/<pk>/excluir/
  oficios/                  — lista global de ofícios (todos, avulsos e vinculados)
  roteiros/                 — lista global de roteiros
  roteiros/avulso/novo/     — cadastro de roteiro avulso
  roteiros/avulso/<pk>/editar/
  documentos/               — hub central de documentos
  documentos/planos-trabalho/ — lista de PT derivados de ofícios/eventos
  documentos/ordens-servico/  — lista de OS derivados de ofícios/eventos
  documentos/justificativas/  — lista de justificativas
  documentos/termos/          — lista de termos de autorização
  documentos/avulsos/novo/    — documento avulso genérico
  simulacao-diarias/
  <pk>/guiado/etapa-1/      — fluxo guiado evento
  <pk>/guiado/etapa-2/      — roteiros do evento
  <pk>/guiado/etapa-5/      — ofícios do evento (chama oficio_novo via redirect)
  ...
```

**Problemas nas rotas:**
- **A raiz** NÃO é `/documentos/` como especificado — permanece no dash sob `/`
- **Ofícios** estão em `/eventos/oficio/...`, não em `/documentos/oficios/...`
- **Roteiros** estão em `/eventos/roteiros/...`, não em `/documentos/roteiros/...`
- **Hub** está em `/eventos/documentos/`, não em `/documentos/`
- O namespace `eventos:` é usado para TUDO, incluindo entidades que deveriam ser independentes de evento
- Não existe `app_name = 'documentos'` com rotas reais

**Positivo:**
- `/eventos/oficio/novo/?evento_id=X` — suporta criação com ou sem evento
- `/eventos/roteiros/avulso/novo/` — roteiro sem evento
- Sem rotas duplicadas para a mesma entidade (ofício tem um único wizard)

### 4.4 Views

**Organização:**
- `eventos/views.py` (4.996 linhas) — wizard do ofício, fluxo guiado de eventos, modelos de motivo/justificativa, roteiros
- `eventos/views_global.py` (1.050 linhas) — lista global de ofícios, roteiros, hub, PT/OS derivados, simulação de diárias

**`oficio_novo` (L1798)**:
```python
def oficio_novo(request):
    evento_id_raw = request.GET.get('evento_id')
    evento = None
    if evento_id_raw:
        evento = Evento.objects.get(pk=int(evento_id_raw))
    if evento:
        oficio = Oficio.objects.create(evento=evento, tipo_origem=Oficio.ORIGEM_EVENTO)
    else:
        oficio = Oficio.objects.create(evento=None, tipo_origem=Oficio.ORIGEM_AVULSO)
    return redirect('eventos:oficio-step1', pk=oficio.pk)
```
→ **Ofício pode ser criado sem evento**. ✓

**`guiado_etapa_3_criar_oficio` (L1271)**:
```python
def guiado_etapa_3_criar_oficio(request, evento_id):
    # Delega para a criação global
    novo_url = f"{reverse('eventos:oficio-novo')}?evento_id={evento.pk}"
    return redirect(novo_url)
```
→ **O fluxo guiado delega para o cadastro real do ofício** ✓. Não existe CRUD paralelo para ofício dentro do evento.

**`oficio_step1`, `oficio_step2`, `oficio_step3`, `oficio_step4`**: views únicas para todas as situações (avulso e vinculado a evento). Sem duplicação. ✓

**Problemas nas views:**
- `_oficio_redirect_pos_exclusao` retorna para `eventos:guiado-etapa-5` quando ofício tem evento_id, não para lista de ofícios — acoplamento de navegação residual.
- `oficio_global_lista` e `planos_trabalho_global` filtram por `evento_id` mas não por ofício avulso separadamente de forma explícita (UI).
- `planos_trabalho_global` e `ordens_servico_global` listam documentos derivados de ofícios — mas o PT/OS real (EventoFundamentacao) ainda exige evento obrigatoriamente.

**`roteiro_avulso_cadastrar` (L4727)**: view específica para roteiro sem evento. Usa o mesmo form `RoteiroEventoForm` mas com `tipo=TIPO_AVULSO`. **Dois formulários diferentes para o mesmo model** — apesar de usarem o mesmo form class, o template é diferente (`roteiro_avulso_form.html` vs `guiado/roteiro_form.html` de 566 linhas).

### 4.5 Forms

**Forms em `eventos/forms.py` (1.039 linhas):**

| Form | Modelo | Campo evento |
|------|--------|-------------|
| `EventoForm` | Evento | — (é o form do próprio Evento) |
| `EventoEtapa1Form` | Evento | — |
| `EventoFundamentacaoForm` | EventoFundamentacao | via instância já vinculada |
| `EventoFinalizacaoForm` | EventoFinalizacao | via instância |
| `DocumentoAvulsoForm` | DocumentoAvulso | `evento` (campo opcional) |
| `TipoDemandaEventoForm` | TipoDemandaEvento | — |
| `ModeloMotivoViagemForm` | ModeloMotivoViagem | — |
| `ModeloJustificativaForm` | ModeloJustificativa | — |
| `OficioJustificativaForm` | — (Form puro) | — |
| `RoteiroEventoForm` | RoteiroEvento | `evento` (campo disponível) |
| `OficioStep1Form` | — (Form puro) | sem campo evento |
| `OficioStep2Form` | — (Form puro) | sem campo evento |

**Positivo:** `OficioStep1Form` e `OficioStep2Form` são forms puros sem campo `evento` — o vínculo com evento é feito na view, não forçado pelo form. ✓

**Problema:** `EventoFundamentacaoForm` não tem um campo para criar PT/OS sem estar atrelado a um evento (a instância da EventoFundamentacao já vem com `evento` preenchido).

### 4.6 Templates

**Wizard do ofício (templates criados):**
- `_wizard_header.html` — cabeçalho com título, botões de ação e stepper
- `_wizard_stepper.html` — stepper de navegação pelo topo
- `wizard_step1.html` (630 linhas) — dados + viajantes
- `wizard_step2.html` (1.132 linhas) — veículo + motorista
- `wizard_step3.html` (1.329 linhas) — roteiro + trechos + diárias
- `wizard_step4.html` (262 linhas) — resumo + finalização

**Verificação de rodapé:**
- Nenhum dos templates `wizard_step*.html` contém `btn-prev`, `btn-next`, `Próximo`, `Anterior`, ou `Voltar` como botões de rodapé de navegação
- A navegação é inteiramente pelo stepper no topo
- ✓ Rodapé de navegação removido

**Botão "Cadastrar novo viajante" no Step 1:**
```html
<a href="{{ cadastrar_viajante_url }}" class="btn btn-outline-secondary btn-sm" data-autosave-link="1">
    Cadastrar novo viajante
</a>
```
URL gerada: `cadastros:viajante-cadastrar?next=<url_step1_atual>` ✓

**Botão "Cadastrar novo veículo" no Step 2:**
URL gerada: `cadastros:veiculo-cadastrar?next=<url_step2_atual>` ✓

**Suporte ao parâmetro `next` nos cadastros:**
- `cadastros/views/viajantes.py` — `_next_url_safe()` lê `?next=` e redireciona após salvar ✓
- `cadastros/views/veiculos.py` — `_next_url_safe()` lê `?next=` e redireciona após salvar ✓
- Após cadastrar viajante/veículo, o usuário é devolvido ao passo do wizard de origem ✓

**Observação**: não há parâmetros `context_source` ou `preselected_event_id` além do `?next=` simples. O padrão de contexto especificado na arquitetura-alvo não foi implementado completamente.

### 4.7 Services / Helpers / Utilitários

**`eventos/services/documentos/`** — serviços de geração de documentos Word (DOCX):
- `context.py` (701 linhas) — constrói contexto para todos os templates de documentos
- `renderer.py` (405 linhas) — renderiza DOCX usando `python-docx`
- `backends.py` (220 linhas)
- `oficio.py` (163 linhas) — geração do ofício
- `termo_autorizacao.py` (390 linhas) — termo de autorização
- `plano_trabalho.py` (94 linhas) — plano de trabalho
- `ordem_servico.py` (86 linhas) — ordem de serviço
- `justificativa.py` (55 linhas) — justificativa
- `validators.py` (260 linhas) — validações antes de gerar

**`eventos/services/estimativa_local.py`** (650 linhas) — estimativa de distância sem API externa, usando dados de coordenadas das cidades.

**`eventos/services/diarias.py`** (309 linhas) — cálculo de diárias baseado no roteiro.

**`eventos/services/routing_provider.py`** (224 linhas) — provedor de cálculo de rotas.

**`core/navigation.py`** — reescrito para refletir nova estrutura. Sidebar com: Central de documentos → Eventos → Roteiros → Simulação de diárias → Documentos (submenu) → Viajantes → Veículos → Configurações.

---

## 5. Impacto arquitetural real

### O sistema continua event-centric?

**Parcialmente sim.** Para PT/OS (EventoFundamentacao com OneToOne obrigatório para Evento), para EventoTermoParticipante (termos vinculados a evento), para o fluxo guiado em geral — sim, o Evento ainda é entidade pai obrigatória.

### O sistema ficou document-centric?

**Parcialmente.** Para Ofício e Roteiro, sim. A criação independente é real e funcional. Para os demais documentos (PT, OS, Termo real), não. A "lista global" de PT/OS apenas re-lista ofícios existentes pelo status do documento neles gerado — não são entidades criáveis independentemente.

### Evento deixou de ser pai obrigatório?

- **Para Ofício**: SIM. FK `null=True`. ✓
- **Para Roteiro**: SIM. FK `null=True` desde migration 0025. ✓
- **Para DocumentoAvulso**: SIM. FK `null=True`. ✓
- **Para EventoFundamentacao (PT/OS)**: NÃO. OneToOne obrigatório. ✗
- **Para EventoTermoParticipante**: NÃO. FK obrigatória. ✗

### Fluxo guiado virou só camada de navegação/contexto?

**Parcialmente.** O fluxo guiado de ofício (`guiado_etapa_3_criar_oficio`) delega corretamente para `oficio_novo` (o cadastro real). Porém, o fluxo guiado de roteiros (`guiado_etapa_2_cadastrar/editar`) tem suas próprias views separadas das views de roteiro avulso — são o mesmo form class mas caminhos distintos.

### Houve desacoplamento estrutural?

Sim, parcialmente. A mudança de Ofício (migration 0010, criado com `evento null=True`) e Roteiro (migration 0025, tornando `evento null=True`) são desacoplamentos estruturais reais na camada de banco.

---

## 6. Verificação entidade por entidade

### 6.1 Ofício

| Aspecto | Antes (origin/main ~009785b) | Agora (HEAD) |
|---------|------------------------------|--------------|
| Model | Em `documentos/models.py` (removido completamente) | `eventos/models.py` — `Oficio` |
| FK Evento | Não existia (era outro modelo) | `null=True, blank=True` — OPCIONAL ✓ |
| Wizard | Existia em `templates/documentos/oficios/` | `templates/eventos/oficio/wizard_step*.html` |
| Independência real | Não verificável no estado anterior (tudo foi removido) | **SIM** — pode criar sem evento ✓ |
| Dependências obrigatórias | — | Nenhuma FK obrigatória para entidades maiores |

**Situação atual**: `Oficio` é uma entidade independente. Pode existir sem evento. Tem campo `tipo_origem` para distinguir contexto. O wizard é o único cadastro.

### 6.2 Termo

| Aspecto | Estado atual |
|---------|--------------|
| Model próprio | Não. Existe como `DocumentoAvulso(tipo=TERMO_AUTORIZACAO)` ou `EventoTermoParticipante` |
| Independência real | **PARCIAL** — como DocumentoAvulso sim; como EventoTermoParticipante não |
| Rota independente | `eventos:documentos-termos` — lista de termos globais (derivados de ofícios) |
| Criação sem evento | Como DocumentoAvulso: SIM. Como EventoTermoParticipante: NÃO |

### 6.3 Justificativa

| Aspecto | Estado atual |
|---------|--------------|
| Model próprio | Não. É campo `justificativa_texto` no `Oficio` ou `DocumentoAvulso(tipo=JUSTIFICATIVA)` |
| Independência real | **PARCIAL** — campo no Oficio não depende de evento; como DocumentoAvulso sim |
| Rota independente | `eventos:documentos-justificativas` — lista global |
| Criação sem evento | Campo no Oficio: sim; DocumentoAvulso: sim |

### 6.4 Plano de Trabalho

| Aspecto | Estado atual |
|---------|--------------|
| Model próprio | Não. É `EventoFundamentacao` (OneToOne com Evento) |
| Independência real | **NÃO** — exige Evento obrigatoriamente |
| Rota independente | `eventos:documentos-planos-trabalho` — lista derivada de ofícios/eventos |
| Criação sem evento | **IMPOSSÍVEL** com a modelagem atual |

### 6.5 Ordem de Serviço

| Aspecto | Estado atual |
|---------|--------------|
| Model próprio | Não. É `EventoFundamentacao` (campo `tipo_documento='OS'`) |
| Independência real | **NÃO** — exige Evento obrigatoriamente |
| Rota independente | `eventos:documentos-ordens-servico` — lista derivada |
| Criação sem evento | **IMPOSSÍVEL** com a modelagem atual |

### 6.6 Roteiro

| Aspecto | Estado atual |
|---------|--------------|
| Model próprio | Sim — `RoteiroEvento` em `eventos/models.py` |
| FK Evento | `null=True, blank=True` desde migration 0025 ✓ |
| Campo `tipo` | `AVULSO` ou `EVENTO` — distingue contexto ✓ |
| Views independentes | `roteiro_avulso_cadastrar`, `roteiro_avulso_editar` ✓ |
| Views no fluxo guiado | `guiado_etapa_2_cadastrar/editar` (views distintas, mesmo form) |
| Lista global | `eventos:roteiros-global` — avulsos e vinculados ✓ |
| Duplicidade | PARCIAL — dois caminhos distintos para o mesmo form |

### 6.7 Evento

| Aspecto | Estado atual |
|---------|--------------|
| É pai obrigatório? | Para Ofício e Roteiro: NÃO ✓. Para PT/OS: SIM ✗ |
| É agrupador opcional? | Para Ofício e Roteiro: SIM ✓. Para PT/OS: NÃO ✗ |
| Tem fluxo guiado? | SIM — fluxo de 6 etapas |
| Entidades-filho obrigatórias | EventoFundamentacao, EventoFinalizacao (1:1 CASCADE) |

---

## 7. Verificação do princípio de cadastro único

### Existe cadastro único de ofício?

**SIM.** O wizard em `/eventos/oficio/novo/` é o único ponto de criação. O fluxo guiado de evento delega para ele via `guiado_etapa_3_criar_oficio → redirect(oficio_novo?evento_id=X)`. Não existe uma rota de criação de ofício específica do fluxo de evento. ✓

### Existe cadastro único de roteiro?

**PARCIAL.** Tecnicamente usam o mesmo model (`RoteiroEvento`) e o mesmo form class (`RoteiroEventoForm`). Mas os templates são diferentes: `guiado/roteiro_form.html` (566 linhas) para roteiros de eventos e `global/roteiro_avulso_form.html` (213 linhas) para roteiros avulsos. São experiências diferentes para a mesma entidade.

### Existe cadastro único de viajante/veículo?

**SIM.** Os botões "Cadastrar novo viajante" e "Cadastrar novo veículo" no wizard do ofício apontam para os cadastros reais em `cadastros:viajante-cadastrar` e `cadastros:veiculo-cadastrar`. Suportam `?next=<url_retorno>` para devolver ao wizard após salvar. ✓

### O fluxo guiado reaproveita ou duplica?

- **Para ofício**: reaproveita ✓
- **Para roteiro**: parcialmente reaproveita (mesmo form, template diferente) ⚠
- **Para PT/OS**: cria dentro do contexto de evento, não há cadastro independente ✗
- **Para termos por participante**: cria dentro de evento ✗

### Existe tela paralela para a mesma entidade?

O cadastro de ofício não tem tela paralela. O cadastro de roteiro tem dois templates diferentes. Não há CRUD paralelo no sentido de duas rotas separadas que fazem a mesma coisa com a mesma entidade para o mesmo contexto — mas há divergência de experiência para roteiros.

### `context_source`/`return_to`/`preselected_event_id` foram implementados?

**PARCIALMENTE.** O padrão de contexto implementado é apenas `?next=<url>` nos cadastros de viajante/veículo. O padrão completo especificado (`return_to`, `context_source`, `preselected_event_id`, `preselected_roteiro_id`) **não foi implementado**. A criação de ofício a partir do fluxo guiado passa `?evento_id=X` mas não devolve ao ponto do fluxo guiado após salvar — redireciona para o Step 1 do wizard, de onde o usuário precisa navegar manualmente de volta.

---

## 8. Verificação do wizard do ofício

### Step 1 — Dados e viajantes

- **Número automático**: SIM — `Oficio.get_next_available_numero()` com retry para concorrência ✓
- **Data automática**: SIM — `data_criacao = timezone.localdate()` se não informada ✓
- **Protocolo com máscara**: SIM — normalização e formatação implementadas ✓
- **Motivo e modelo de motivo**: SIM — `ModeloMotivoViagem` com dropdown e API de texto ✓
- **Custeio**: SIM — tipos com nome de instituição condicional ✓
- **Viajantes**: SIM — autocomplete real, seleção múltipla, chips visuais ✓
- **Botão novo viajante → cadastro real → retorno**: SIM ✓
- **Autosave**: SIM — `_autosave_oficio_step1` com JSON response específico ✓
- **Status RASCUNHO preservado**: SIM — `_save_oficio_preserving_status` ✓
- **Evento como campo do step 1?**: NÃO — evento é passado na criação (não editável no wizard)
- **Seleção de evento no step 1**: NÃO IMPLEMENTADO — a spec pede "sem evento / usar existente / criar novo evento" como seleção no wizard, mas isso não existe

### Step 2 — Transporte

- **Busca de viatura**: SIM — autocomplete com API ✓
- **Preenchimento automático ao escolher viatura**: SIM ✓
- **Botão nova viatura → cadastro real → retorno**: SIM ✓
- **Motorista**: SIM — autocomplete de viajantes como motorista ✓
- **Regra de carona**: SIM — campo `motorista_carona` com campos condicionais ✓
- **Persistência**: SIM ✓

### Step 3 — Roteiro e diárias

- **Seleção entre roteiro existente / novo / sem roteiro**: SIM — `roteiro_modo` (EVENTO_EXISTENTE / ROTEIRO_PROPRIO) ✓
- **Estados e municípios reais**: SIM — FK para `Estado` e `Cidade` ✓
- **Trechos reais**: SIM — `OficioTrecho` com origem, destino, saída, chegada, distância, duração ✓
- **Estimativa de km/tempo sem API externa**: SIM — `estimativa_local.py` ✓
- **Diárias calculadas**: SIM — `oficio_step3_calcular_diarias` ✓
- **Retorno real**: SIM — campos de retorno no Oficio ✓
- **Persistência e reabertura fiel**: SIM — `_get_oficio_step3_saved_state` ✓
- **Criar roteiro reutilizável**: SIM — `_salvar_roteiro_reutilizavel_oficio` ✓

### Step 4 — Resumo / Finalização

- **Resumo real**: SIM — dados de step1/2/3 consolidados ✓
- **Status de justificativa**: SIM — `_build_oficio_justificativa_info` ✓
- **Finalização com validação**: SIM — `_validate_oficio_for_finalize` ✓
- **Bloqueio quando incompleto**: SIM ✓

### Justificativa

- **Modelos reais**: SIM — `ModeloJustificativa` com CRUD ✓
- **Aplicar modelo**: SIM — API de texto e aplicação no formulário ✓
- **Salvar texto**: SIM — `_autosave_oficio_justificativa` ✓
- **Vínculo real com ofício**: SIM — `Oficio.justificativa_texto` + `justificativa_modelo` FK ✓
- **Depende de evento?**: NÃO — a justificativa do ofício é independente ✓

### Documentos do ofício

- **Tela real de documentos**: SIM — `oficio_documentos` view + template ✓
- **Status dos documentos**: SIM — `_build_oficio_document_cards` ✓
- **Download DOCX/PDF**: SIM — via `oficio_documento_download` ✓
- **Erro 500 para tipo inválido?**: NÃO verificado diretamente; `_build_oficio_document_download_context` tem verificação de tipo

---

## 9. Evidências concretas de desacoplamento ou acoplamento

### Desacoplamento confirmado por código

1. **`eventos/models.py L746`**: `Oficio.evento = models.ForeignKey(Evento, ..., null=True, blank=True)` — FK nulável desde migration 0010
2. **`eventos/models.py L1278`**: `RoteiroEvento.evento = models.ForeignKey(Evento, ..., null=True, blank=True)` — FK nulável desde migration 0025
3. **`eventos/views.py L1798-1828`**: `oficio_novo()` cria `Oficio` com `evento=None` quando não há `evento_id` na querystring
4. **`eventos/views.py L1271-1286`**: `guiado_etapa_3_criar_oficio()` redireciona para `oficio_novo` — não cria ofício independentemente, delega para o cadastro real
5. **`eventos/views.py L4727`**: `roteiro_avulso_cadastrar()` cria roteiro com `tipo=TIPO_AVULSO` sem exigir `evento_id`
6. **`cadastros/views/viajantes.py L22-38`**: `_next_url_safe()` implementa retorno ao wizard após cadastrar viajante
7. **`cadastros/views/veiculos.py L17-35`**: `_next_url_safe()` implementa retorno ao wizard após cadastrar veículo
8. **`eventos/models.py L551`**: `DocumentoAvulso.evento = FK(null=True, blank=True)` — documento avulso pode existir sem evento
9. **`eventos/models.py L905`**: `Oficio.tipo_origem = CharField(choices=['AVULSO', 'EVENTO'])` — campo semântico para distinguir contexto

### Acoplamento residual confirmado por código

1. **`eventos/models.py L236-242`**: `EventoFundamentacao.evento = models.OneToOneField(Evento, on_delete=CASCADE)` sem `null=True` — PT/OS exige evento obrigatoriamente
2. **`eventos/models.py L398-403`**: `EventoTermoParticipante.evento = models.ForeignKey(Evento, on_delete=CASCADE)` sem `null=True` — termos por participante exigem evento
3. **`eventos/models.py L159-162`**: `EventoParticipante.evento = models.ForeignKey(Evento, on_delete=CASCADE)` — participantes exigem evento
4. **`eventos/views.py L1831-1835`**: `_oficio_redirect_pos_exclusao()` redireciona para `guiado-etapa-5` do evento se ofício tiver `evento_id` — acoplamento de navegação
5. **`eventos/models.py L1329-1334`** (RoteiroEvento.esta_completo): `if self.tipo == self.TIPO_EVENTO and not self.evento_id: return False` — roteiro do tipo EVENTO não pode ser finalizado sem evento vinculado — acoplamento conceitual residual
6. **`eventos/views_global.py L884-910`**: `planos_trabalho_global()` e `ordens_servico_global()` são listas derivadas de ofícios, não cadastros próprios. Não há rota para criar PT/OS independente.
7. **`config/urls.py`**: não existe `path('documentos/', include('documentos.urls'))` com rotas reais — o app `documentos` está vazio
8. **`eventos/views_global.py L629`**: `documentos_hub()` em `/eventos/documentos/` — a "central de documentos" está dentro do namespace de eventos, não tem path próprio independente

---

## 10. Pontos que ainda estão errados

### Falhas arquiteturais críticas

1. **PT/OS amarrados ao Evento**: `EventoFundamentacao` usa `OneToOneField(Evento, CASCADE)` — impossível criar PT ou OS sem evento no banco atual. Precisaria de migration para `null=True` + nova tela de criação independente.

2. **TermoAutorizacao sem model próprio**: Existe como `DocumentoAvulso(tipo=TERMO_AUTORIZACAO)` ou como `EventoTermoParticipante`. O segundo exige evento obrigatório. O primeiro é genérico demais para comportar as regras específicas de termo.

3. **Justificativa sem model próprio**: É campo de texto no Ofício ou DocumentoAvulso genérico. Não tem entidade própria com regras de negócio independentes.

4. **OficioViajante ausente como tabela intermediária real**: O Ofício usa `viajantes = ManyToManyField('cadastros.Viajante')` que cria a tabela `eventos_oficio_viajantes` implicitamente. Não há campo `ordem` nem snapshot de nome/cargo na tabela intermediária — se o viajante for editado, o ofício perderá os dados históricos.

5. **Rotas não seguem a especificação**: `/documentos/oficios/`, `/documentos/roteiros/`, `/documentos/eventos/` são as rotas desejadas. O que existe é `/eventos/oficio/...`, `/eventos/roteiros/...`, `/eventos/documentos/...`.

### Duplicidades residuais

6. **Dois templates para criação de roteiro**: `guiado/roteiro_form.html` (566 linhas) vs `global/roteiro_avulso_form.html` (213 linhas) — o mesmo form class (`RoteiroEventoForm`) com duas experiências distintas. Conceitualmente é duplicidade.

7. **Planos de trabalho "globais" são listas derivadas**: As views `planos_trabalho_global` e `ordens_servico_global` listam ofícios pelo tipo de documento gerado — não são módulos de cadastro de PT/OS independentes.

### Problemas de navegação/UX

8. **Retorno ao fluxo guiado após criar ofício**: Após criar ofício pelo fluxo guiado de evento, o usuário vai para o Step 1 do wizard. Para voltar ao painel do evento, precisa navegar manualmente. O parâmetro `return_to` não está implementado nesse ponto.

9. **Seleção de evento como contexto no wizard**: A spec pede que no wizard do ofício seja possível "sem evento / usar evento existente / criar novo evento" como seleção. Hoje o evento é passado na criação via `?evento_id=X` ou não passado — não há seleção interativa dentro do wizard.

### Problemas de modelagem

10. **`RoteiroEvento.esta_completo()` rejeita roteiro TIPO_EVENTO sem evento_id**: Acoplamento semântico. Um roteiro criado como "vinculado a evento" que perdeu o vínculo ficará sempre como RASCUNHO.

11. **`Oficio.tipo_origem` defaulta para EVENTO**: Na migration 0027, o campo `tipo_origem` foi adicionado com `default='EVENTO'`. Todos os ofícios antigos ficaram com `tipo_origem='EVENTO'` mesmo sem ter `evento_id` — inconsistência nos dados históricos.

---

## 11. O que foi realmente concluído

1. ✅ Model `Oficio` com FK opcional para Evento (`null=True, blank=True`)
2. ✅ Campo `tipo_origem` no Oficio (AVULSO / EVENTO)
3. ✅ `oficio_novo` view suporta criação com ou sem evento
4. ✅ Wizard de ofício (4 etapas + justificativa + documentos) funcional
5. ✅ Model `RoteiroEvento` com FK opcional para Evento (desde migration 0025)
6. ✅ Campo `tipo` no RoteiroEvento (AVULSO / EVENTO)
7. ✅ Views `roteiro_avulso_cadastrar` e `roteiro_avulso_editar` para roteiros independentes
8. ✅ Model `DocumentoAvulso` com FKs opcionais para Evento, Roteiro, PT, Oficio
9. ✅ Hub de documentos em `/eventos/documentos/`
10. ✅ Lista global de ofícios em `/eventos/oficios/` (avulsos e vinculados)
11. ✅ Lista global de roteiros em `/eventos/roteiros/`
12. ✅ `guiado_etapa_3_criar_oficio` delega para `oficio_novo` (sem CRUD paralelo)
13. ✅ Botão "Cadastrar novo viajante" aponta para cadastro real com `?next=` ✓
14. ✅ Botão "Cadastrar novo veículo" aponta para cadastro real com `?next=` ✓
15. ✅ Navegação do wizard pelo stepper no topo (sem botões de rodapé)
16. ✅ `ModeloMotivoViagem` e `ModeloJustificativa` com CRUD completo
17. ✅ Step 3: trechos reais, estimativa local de km/tempo, diárias calculadas
18. ✅ Migrations sem erros (`check`: 0 issues; `makemigrations --check`: no changes)
19. ✅ App `documentos` esvaziado (sem conflito com novo `eventos`)
20. ✅ App legado separado em `_legacy/`

---

## 12. O que ficou parcial ou provisório

1. ⚠ **PT/OS** — existem como `EventoFundamentacao` (evento obrigatório); as "listas globais" são derivadas e não módulos de criação independente
2. ⚠ **TermoAutorizacao** — sem model próprio; é `DocumentoAvulso(tipo=TERMO)` ou `EventoTermoParticipante` (evento obrigatório)
3. ⚠ **Justificativa** — sem model próprio; é campo texto no Oficio ou `DocumentoAvulso(tipo=JUSTIFICATIVA)`
4. ⚠ **OficioViajante** — sem tabela intermediária própria; usa M2M implícita sem ordenação ou snapshot
5. ⚠ **Template de roteiro duplicado** — dois templates distintos para o mesmo form class (guiado vs avulso)
6. ⚠ **Padrão `return_to`/`context_source`** — apenas `?next=` implementado; sem `return_to`, `context_source`, `preselected_event_id`
7. ⚠ **Seleção de evento no wizard do ofício** — não é possível escolher/trocar evento dentro do wizard; apenas passado na criação
8. ⚠ **Rotas divergem da especificação** — `/eventos/...` em vez de `/documentos/...`
9. ⚠ **`tipo_origem` default EVENTO** — dados históricos com inconsistência
10. ⚠ **`oficio_redirect_pos_exclusao`** — volta para evento quando ofício foi criado com evento_id (não volta para lista de ofícios)

---

## 13. Próximas correções recomendadas

### Críticas

1. **Desacoplar PT/OS de Evento**: Criar model `PlanoTrabalho` e `OrdemServico` próprios (ou tornar `EventoFundamentacao.evento` opcional com `null=True`, blank=True`), adicionar rotas de criação independente e migrar os dados existentes.

2. **Criar TermoAutorizacao como entidade própria** (ou consolidar `DocumentoAvulso(tipo=TERMO)` como o único caminho e eliminar `EventoTermoParticipante` como dependência de evento — tornar eventos opcional nele também).

3. **Migration para corrigir `tipo_origem` retroativo**: Executar `UPDATE oficio SET tipo_origem='AVULSO' WHERE evento_id IS NULL` via `migrations.RunSQL`.

### Altas

4. **Adicionar `OficioViajante` como tabela intermediária com `ordem`**: Substituir `viajantes = ManyToManyField` por `through='OficioViajante'` com campos `ordem`, `nome_snapshot`, `cargo_snapshot`.

5. **Unificar template de roteiro**: Usar um único template para roteiro avulso e roteiro de evento, com contexto passado pela view.

6. **Implementar `return_to` no wizard do ofício**: Ao abrir wizard a partir do fluxo guiado, guardar `return_to` e redirecionar após finalizar cada step.

7. **Corrigir `oficio_redirect_pos_exclusao`**: Redirecionar sempre para lista de ofícios, não para painel do evento.

### Médias

8. **Reorganizar rotas para `/documentos/...`**: Mover URLs do ofício, roteiro e hub para o app `documentos` com namespace `documentos:`, mantendo os models em `eventos`.

9. **Implementar seleção de evento no wizard**: No Step 1 do ofício, adicionar campo de seleção de evento (sem evento / usar existente / criar novo).

10. **Corrigir `RoteiroEvento.esta_completo()`**: Remover verificação `if self.tipo == TIPO_EVENTO and not self.evento_id: return False` ou torná-la menos restritiva.

### Baixas

11. **Renomear app `eventos`**: Considerar renomear para `documentos` ou `core_doc` para refletir a nova responsabilidade que não é mais centrada em eventos.

12. **Completar padrão de contexto**: Adicionar `context_source` e `preselected_event_id` como parâmetros de navegação global.

---

## 14. Veredito final

### Classificação: ARQUITETURA PARCIALMENTE ALTERADA

**Justificativa técnica:**

A refatoração introduziu mudanças estruturais reais e funcionais na camada de banco (migrations 0010, 0025, 0027) que desacoplam `Oficio` e `RoteiroEvento` de `Evento`. O wizard do ofício é funcional, opera como cadastro único, suporta criação sem evento e o fluxo guiado o reutiliza corretamente.

Porém, três problemas impedem classificar como "ARQUITETURA REALMENTE ALTERADA":

1. **`EventoFundamentacao` (PT/OS) continua com `OneToOneField(Evento)` obrigatório** — as entidades PT e OS ainda não existem sem evento no banco. A spec pede que PT e OS sejam entidades independentes. Isso não foi feito.

2. **`TermoAutorizacao`, `Justificativa`, `PlanoTrabalho` e `OrdemServico` não têm models próprios** — são implementados como `DocumentoAvulso` (tipo genérico) ou campos dentro de Oficio/EventoFundamentacao. A spec pede entidades de domínio próprias.

3. **As rotas continuam em `/eventos/...`** — não foi criada a estrutura `/documentos/...`. O namespace `eventos` hospeda entidades que deveriam ser "document-centric" sem o prefixo de eventos.

O sistema saiu de 100% event-centric para ~60% document-centric. A mudança foi real e não cosmética para Ofício e Roteiro. Para o restante do domínio documental, permanece fundamentalmente incompleta.

---

*Fim do relatório. Gerado via inspeção de código, git diff, leitura de models.py (1.228 linhas), views.py (4.996 linhas), views_global.py (1.050 linhas), urls.py (110 linhas), 30 migrations e templates principais.*
