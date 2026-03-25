"""Helper: rewrites planos_trabalho_form.html with the Phase-2 functional upgrade."""
import pathlib, textwrap

ROOT = pathlib.Path(__file__).parent
DEST = ROOT / "templates/eventos/documentos/planos_trabalho_form.html"

CONTENT = r"""{% extends 'base.html' %}
{% load static %}

{% block title %}{% if object %}Editar{% else %}Novo{% endif %} Plano de Trabalho — Central de Viagens{% endblock %}
{% block page_title %}{% if object %}Editar{% else %}Novo{% endif %} Plano de Trabalho{% endblock %}

{% block extra_css %}
<style>
  /* ── Step transitions (fade-in on activate) ── */
  .pt-step { display: none; }
  .pt-step.is-active { display: block; animation: pt-step-in 0.18s ease both; }
  @keyframes pt-step-in { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }

  /* ── Dynamic summary bar ── */
  .pt-summary-bar {
    display: flex; flex-wrap: wrap; align-items: stretch;
    border: 1px solid #cde2f5; border-radius: 12px;
    background: linear-gradient(135deg,#f2f8ff 0%,#e8f2ff 100%);
    overflow: hidden; margin-bottom: 1.25rem;
  }
  .pt-summary-item {
    flex: 1 0 100px; display: flex; flex-direction: column; gap: .1rem;
    padding: .6rem .9rem; border-right: 1px solid #cde2f5;
  }
  .pt-summary-item:last-child { border-right: 0; }
  .pt-summary-label { color:#6b7f95; font-size:.61rem; font-weight:800; text-transform:uppercase; letter-spacing:.08em; }
  .pt-summary-value { color:#10324f; font-size:.88rem; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:140px; }
  .pt-summary-valor .pt-summary-value { color:#1a6d3a; font-weight:900; }
  @media(max-width:680px){
    .pt-summary-item { flex-basis:50%; border-bottom:1px solid #cde2f5; }
    .pt-summary-item:nth-child(even){ border-right:0; }
    .pt-summary-item:last-child{ border-bottom:0; }
  }

  /* ── Duration badge (step 2 header) ── */
  .pt-dur-badge {
    display:inline-flex; align-items:center; gap:4px;
    background:#e8f5ee; border:1px solid #b2d9c2; border-radius:8px;
    padding:.3rem .65rem; color:#1a6d3a; font-size:.82rem; font-weight:700;
    white-space:nowrap;
  }

  /* ── Diárias two-column calculator ── */
  .pt-diarias-shell { display:grid; grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr); gap:1.1rem; align-items:start; }
  @media(max-width:860px){ .pt-diarias-shell{ grid-template-columns:1fr; } }
  .pt-diarias-output {
    border:1px solid #cfe0f0; border-radius:14px;
    background:linear-gradient(150deg,#f8fbff 0%,#edf5fd 100%);
    box-shadow:0 16px 30px rgba(37,99,154,.14);
    padding:1.2rem; display:flex; flex-direction:column; gap:.9rem;
  }
  .pt-diarias-output.is-updated { animation: pt-diarias-pulse .55s ease; }
  @keyframes pt-diarias-pulse {
    0%  { box-shadow:0 16px 30px rgba(37,99,154,.14); }
    50% { box-shadow:0 8px 40px rgba(26,109,58,.35), 0 0 0 3px rgba(26,109,58,.15); }
    100%{ box-shadow:0 16px 30px rgba(37,99,154,.14); }
  }
  .pt-diarias-total-label { color:#5c7491; font-size:.68rem; letter-spacing:.09em; font-weight:800; text-transform:uppercase; }
  .pt-diarias-total-value { color:#143a63; font-size:2rem; line-height:1.04; font-weight:900; letter-spacing:-.01em; transition:color .4s ease; }
  .pt-diarias-total-value.is-flash { color:#1a6d3a; }
  .pt-diarias-auto-hint { font-size:.72rem; color:#4d8c5f; font-weight:700; display:none; }
  .pt-diarias-auto-hint.is-visible { display:block; }
  .pt-diarias-kpis { display:grid; gap:.45rem; }
  .pt-diarias-kpi { border:1px solid #d8e6f4; border-radius:10px; background:rgba(255,255,255,.85); padding:.55rem .65rem; }
  .pt-diarias-kpi strong { color:#153f67; font-size:.93rem; font-weight:820; display:block; }

  /* ── Coordinator principal concept ── */
  .pt-coord-badge-principal {
    display:inline-block; font-size:.57rem; font-weight:900; text-transform:uppercase; letter-spacing:.05em;
    color:#fff; background:#1a7a3f; border-radius:4px; padding:1px 5px; margin-left:4px; vertical-align:middle;
  }
  .pt-coord-make-principal {
    background:none; border:none; cursor:pointer;
    color:#9ab5cc; font-size:.8rem; padding:0 3px;
    transition:color .15s; line-height:1;
  }
  .pt-coord-make-principal:hover { color:#1a7a3f; }

  /* ── Coordinator search spinner ── */
  .pt-coord-search-state { display:none; align-items:center; gap:6px; font-size:.78rem; color:#4a90d9; padding:.35rem 0; }
  .pt-coord-search-state.is-visible { display:flex; }
  .pt-coord-spinner { width:14px; height:14px; border:2px solid #cde; border-top-color:#4a90d9; border-radius:50%; animation:pt-spin .7s linear infinite; flex-shrink:0; }
  @keyframes pt-spin { to{ transform:rotate(360deg); } }

  /* ── Chip add animation ── */
  @keyframes pt-chip-in { from{ opacity:0; transform:scale(.86); } to{ opacity:1; transform:scale(1); } }
  .pt-chip-anim { animation:pt-chip-in .18s ease both; }

  /* ── Activity grid ── */
  .pt-activity-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.55rem; }
  @media(max-width:640px){ .pt-activity-grid{ grid-template-columns:1fr; } }
  .pt-activity-item {
    border:1px solid #e5e7eb; border-radius:10px; padding:.6rem .7rem;
    background:#fff; cursor:pointer; transition:border-color .15s,background .15s;
  }
  .pt-activity-item:has(.form-check-input:checked){ border-color:#5b87b6; background:#f5faff; }
  .pt-activity-item .form-check{ margin:0; pointer-events:none; }
  .pt-activity-item .form-check-label{ color:#244665; font-size:.85rem; font-weight:600; pointer-events:none; }

  /* ── Review ── */
  .pt-review-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; }
  @media(max-width:760px){ .pt-review-grid{ grid-template-columns:1fr; } }
  .pt-review-list { display:grid; gap:0; }
  .pt-review-row { display:flex; justify-content:space-between; gap:.7rem; align-items:baseline; padding:.5rem 0; border-bottom:1px solid #edf2f7; font-size:.86rem; }
  .pt-review-row:last-child{ border-bottom:0; }
  .pt-review-label{ color:#6c8097; font-weight:700; flex-shrink:0; }
  .pt-review-value{ color:#163a5f; font-weight:700; text-align:right; }

  /* ── Destination row ── */
  .pt-dest-row{ border:1px solid #e6edf4; border-radius:10px; padding:.65rem; background:#fbfdff; }

  /* ── Step warning toast ── */
  #pt-step-warning{ transition:opacity .3s ease; }
</style>
{% endblock %}

{% block content %}
<div class="container-fluid pt-0 pb-4 oficio-wizard-page" data-glance-state="closed">
  <div class="oficio-wizard-shell">

    {# ──────────────────────── STICKY HEADER ──────────────────────── #}
    <div class="oficio-wizard-header" data-oficio-sticky-header>
      <div class="oficio-wizard-header-card">
        <div class="oficio-wizard-header-main">
          <div class="oficio-wizard-header-copy">
            <span class="oficio-wizard-eyebrow">Documento operacional</span>
            <h1>{% if object %}Editar{% else %}Novo{% endif %} Plano de Trabalho</h1>
            <p class="oficio-wizard-header-support">Fluxo guiado em 6 etapas — o sistema calcula e sugere automaticamente a partir do que você informa.</p>
          </div>
          <div class="oficio-wizard-header-badges">
            <div class="oficio-wizard-header-badge">
              <span>Número</span>
              <strong>{% if object %}{{ object.numero_formatado }}{% else %}{{ proximo_numero_pt }}{% endif %}</strong>
            </div>
            <div class="oficio-wizard-header-badge">
              <span>Data</span>
              <strong>{{ data_geracao_preview|date:'d/m/Y' }}</strong>
            </div>
          </div>
        </div>
        <div class="oficio-wizard-stepper-shell">
          <nav class="oficio-stepper" aria-label="Etapas" style="--oficio-step-count:6;">
            <button type="button" class="oficio-stepper-link is-active" data-step-target="0" aria-current="step">
              <span class="oficio-stepper-badge">1</span>
              <span class="oficio-stepper-copy">
                <span class="oficio-stepper-state">Etapa 1</span>
                <span class="oficio-stepper-label">Contexto</span>
              </span>
            </button>
            <button type="button" class="oficio-stepper-link" data-step-target="1">
              <span class="oficio-stepper-badge">2</span>
              <span class="oficio-stepper-copy">
                <span class="oficio-stepper-state">Etapa 2</span>
                <span class="oficio-stepper-label">Datas e Roteiro</span>
              </span>
            </button>
            <button type="button" class="oficio-stepper-link" data-step-target="2">
              <span class="oficio-stepper-badge">3</span>
              <span class="oficio-stepper-copy">
                <span class="oficio-stepper-state">Etapa 3</span>
                <span class="oficio-stepper-label">Equipe</span>
              </span>
            </button>
            <button type="button" class="oficio-stepper-link" data-step-target="3">
              <span class="oficio-stepper-badge">4</span>
              <span class="oficio-stepper-copy">
                <span class="oficio-stepper-state">Etapa 4</span>
                <span class="oficio-stepper-label">Atividades</span>
              </span>
            </button>
            <button type="button" class="oficio-stepper-link" data-step-target="4">
              <span class="oficio-stepper-badge">5</span>
              <span class="oficio-stepper-copy">
                <span class="oficio-stepper-state">Etapa 5</span>
                <span class="oficio-stepper-label">Diárias</span>
              </span>
            </button>
            <button type="button" class="oficio-stepper-link" data-step-target="5">
              <span class="oficio-stepper-badge">6</span>
              <span class="oficio-stepper-copy">
                <span class="oficio-stepper-state">Etapa 6</span>
                <span class="oficio-stepper-label">Revisão</span>
              </span>
            </button>
          </nav>
        </div>
      </div>
    </div>

    {# ── Validation alerts ── #}
    {% if form.errors or form.non_field_errors %}
    <div class="alert alert-danger mt-3 mb-0" role="alert">
      <strong>Existem campos inválidos.</strong>
      <ul class="mb-0 mt-2">
        {% for field in form %}{% for error in field.errors %}<li><strong>{{ field.label }}:</strong> {{ error }}</li>{% endfor %}{% endfor %}
        {% for error in form.non_field_errors %}<li>{{ error }}</li>{% endfor %}
      </ul>
    </div>
    {% endif %}

    {# ── Main panel ── #}
    <div class="card oficio-stage-panel" style="margin-top:1rem;">
      <div class="card-body">

        {# ══ RESUMO DINÂMICO — sempre visível ══ #}
        <div class="pt-summary-bar" id="pt-summary-bar" aria-label="Resumo do plano">
          <div class="pt-summary-item">
            <span class="pt-summary-label">Período</span>
            <span class="pt-summary-value" id="pts-periodo">—</span>
          </div>
          <div class="pt-summary-item">
            <span class="pt-summary-label">Duração</span>
            <span class="pt-summary-value" id="pts-dias">—</span>
          </div>
          <div class="pt-summary-item">
            <span class="pt-summary-label">Equipe</span>
            <span class="pt-summary-value" id="pts-equipe">—</span>
          </div>
          <div class="pt-summary-item">
            <span class="pt-summary-label">Coordenador</span>
            <span class="pt-summary-value" id="pts-coord">—</span>
          </div>
          <div class="pt-summary-item pt-summary-valor">
            <span class="pt-summary-label">Estimativa</span>
            <span class="pt-summary-value" id="pts-valor">—</span>
          </div>
        </div>

        <form method="post" novalidate id="pt-form">
          {% csrf_token %}
          <input type="hidden" name="return_to" value="{{ return_to }}">
          <input type="hidden" name="context_source" value="{{ context_source }}">
          <input type="hidden" name="preselected_event_id" value="{{ preselected_event_id }}">
          <input type="hidden" name="preselected_oficio_id" value="{{ preselected_oficio_id }}">
          <input type="hidden" name="data_criacao" value="{{ form.data_criacao.value|default:data_geracao_preview|date:'Y-m-d' }}">
          {{ form.destinos_payload }}
          {{ form.coordenadores_ids }}

          {# ════ ETAPA 1 — CONTEXTO ════ #}
          <div class="pt-step is-active" data-step-index="0">
            <div class="oficio-stage-intro">
              <span class="oficio-stage-kicker">Etapa 1</span>
              <h2 class="oficio-stage-title">Contexto</h2>
              <p class="oficio-stage-description">Defina os vínculos do documento e quem está solicitando.</p>
            </div>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Vínculos opcionais</h3>
                  <p class="oficio-stage-section-text">Associe a um evento, ofício ou roteiro para facilitar a rastreabilidade.</p>
                </div>
              </div>
              <div class="row g-3">
                <div class="col-md-4">
                  <label class="form-label" for="{{ form.evento.id_for_label }}">Evento</label>
                  {{ form.evento }}
                  {% if form.evento.errors %}<div class="invalid-feedback d-block">{{ form.evento.errors.0 }}</div>{% endif %}
                </div>
                <div class="col-md-4">
                  <label class="form-label" for="{{ form.oficio.id_for_label }}">Ofício principal</label>
                  {{ form.oficio }}
                  {% if form.oficio.errors %}<div class="invalid-feedback d-block">{{ form.oficio.errors.0 }}</div>{% endif %}
                </div>
                <div class="col-md-4">
                  <label class="form-label" for="{{ form.roteiro.id_for_label }}">Roteiro</label>
                  {{ form.roteiro }}
                  {% if form.roteiro.errors %}<div class="invalid-feedback d-block">{{ form.roteiro.errors.0 }}</div>{% endif %}
                </div>
                <div class="col-12">
                  <label class="form-label" for="{{ form.oficios_relacionados.id_for_label }}">Ofícios relacionados</label>
                  {{ form.oficios_relacionados }}
                  {% if form.oficios_relacionados.errors %}<div class="invalid-feedback d-block">{{ form.oficios_relacionados.errors.0 }}</div>{% endif %}
                </div>
              </div>
            </section>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Solicitante e horário</h3>
                  <p class="oficio-stage-section-text">Quem solicita o plano e o horário de atendimento previsto.</p>
                </div>
              </div>
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label" for="{{ form.solicitante_escolha.id_for_label }}">Solicitante</label>
                  {{ form.solicitante_escolha }}
                  <div id="col-solicitante-outros" class="mt-2">{{ form.solicitante_outros }}</div>
                  <div id="col-salvar-solicitante" class="form-check mt-2">
                    {{ form.salvar_solicitante_outros }}
                    <label class="form-check-label" for="{{ form.salvar_solicitante_outros.id_for_label }}">Salvar no gerenciador</label>
                  </div>
                </div>
                <div class="col-md-6">
                  <label class="form-label" for="{{ form.horario_atendimento_padrao.id_for_label }}">Horário de atendimento</label>
                  {{ form.horario_atendimento_padrao }}
                  <div id="col-horario-manual" class="mt-2">{{ form.horario_atendimento_manual }}</div>
                </div>
              </div>
            </section>
          </div>

          {# ════ ETAPA 2 — DATAS E ROTEIRO ════ #}
          <div class="pt-step" data-step-index="1">
            <div class="oficio-stage-intro">
              <span class="oficio-stage-kicker">Etapa 2</span>
              <h2 class="oficio-stage-title">Datas e Roteiro</h2>
              <p class="oficio-stage-description">Defina o período — a duração alimenta a calculadora de diárias automaticamente.</p>
            </div>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Período do deslocamento</h3>
                  <p class="oficio-stage-section-text">A quantidade de diárias será sugerida automaticamente a partir do período informado.</p>
                </div>
                <span id="pt-dur-badge" class="pt-dur-badge" style="display:none;"></span>
              </div>
              <div class="row g-3">
                <div class="col-md-3">
                  <label class="form-label d-block">Tipo</label>
                  <div class="border rounded-3 px-3 py-2 bg-white">
                    <div class="form-check mb-0">
                      {{ form.evento_data_unica }}
                      <label class="form-check-label" for="{{ form.evento_data_unica.id_for_label }}">Data única</label>
                    </div>
                  </div>
                </div>
                <div class="col-md-4">
                  <label class="form-label" for="{{ form.evento_data_inicio.id_for_label }}">Data de saída</label>
                  {{ form.evento_data_inicio }}
                  {% if form.evento_data_inicio.errors %}<div class="invalid-feedback d-block">{{ form.evento_data_inicio.errors.0 }}</div>{% endif %}
                </div>
                <div class="col-md-4" id="col-data-fim">
                  <label class="form-label" for="{{ form.evento_data_fim.id_for_label }}">Data de retorno</label>
                  {{ form.evento_data_fim }}
                  {% if form.evento_data_fim.errors %}<div class="invalid-feedback d-block">{{ form.evento_data_fim.errors.0 }}</div>{% endif %}
                </div>
              </div>
            </section>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Destinos</h3>
                  <p class="oficio-stage-section-text">Adicione um ou mais destinos (estado + cidade).</p>
                </div>
                <button type="button" class="btn btn-outline-primary btn-sm" id="btn-add-destino">+ Adicionar destino</button>
              </div>
              <div id="destinos-container" class="d-grid gap-2"></div>
              {% if form.destinos_payload.errors %}<div class="invalid-feedback d-block mt-1">{{ form.destinos_payload.errors.0 }}</div>{% endif %}
            </section>
          </div>

          {# ════ ETAPA 3 — EQUIPE ════ #}
          <div class="pt-step" data-step-index="2">
            <div class="oficio-stage-intro">
              <span class="oficio-stage-kicker">Etapa 3</span>
              <h2 class="oficio-stage-title">Equipe</h2>
              <p class="oficio-stage-description">Monte a composição — o total alimenta a calculadora de diárias.</p>
            </div>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Efetivo por cargo</h3>
                  <p class="oficio-stage-section-text">Adicione linhas de cargo + quantidade. Cargo sugerido: {{ pt_default_cargo_label }}.</p>
                </div>
                <button type="button" class="btn btn-outline-primary btn-sm" id="btn-add-efetivo">+ Adicionar cargo</button>
              </div>
              <div id="efetivo-rows">
                {{ efetivo_formset.management_form }}
                {% for row in efetivo_formset %}
                <div class="border rounded-3 p-3 mb-2 bg-white" data-ef-row>
                  {{ row.id }}
                  <div class="row g-3 align-items-end">
                    <div class="col-md-7">
                      <label class="form-label" for="{{ row.cargo.id_for_label }}">Cargo</label>
                      {{ row.cargo }}
                    </div>
                    <div class="col-md-3">
                      <label class="form-label" for="{{ row.quantidade.id_for_label }}">Qtd.</label>
                      {{ row.quantidade }}
                    </div>
                    <div class="col-md-2">
                      <div class="form-check mt-4">
                        {{ row.DELETE }}
                        <label class="form-check-label text-danger small" for="{{ row.DELETE.id_for_label }}">Remover</label>
                      </div>
                    </div>
                  </div>
                </div>
                {% endfor %}
              </div>
              <div class="row g-3 mt-1">
                <div class="col-md-4">
                  <label class="form-label" for="{{ form.quantidade_servidores.id_for_label }}">Total de servidores</label>
                  {{ form.quantidade_servidores }}
                  <div class="form-text">Atualizado automaticamente a partir das linhas acima.</div>
                </div>
              </div>
            </section>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Coordenadores operacionais</h3>
                  <p class="oficio-stage-section-text">O <strong>primeiro selecionado</strong> vira o coordenador principal. Você pode alterar clicando em ★.</p>
                </div>
                <a href="{{ pt_coordenador_operacional_create_url }}" class="btn btn-outline-secondary btn-sm" target="_blank" rel="noopener">Cadastrar novo</a>
              </div>

              <label class="form-label mb-1" for="coord-autocomplete-input">Buscar coordenador</label>
              <div class="position-relative" id="coord-autocomplete-wrapper" data-search-url="{{ buscar_coordenadores_url }}">
                <input type="text" id="coord-autocomplete-input" class="form-control" placeholder="Digite nome ou cargo…" autocomplete="off">
                <div id="coord-autocomplete-results" class="list-group position-absolute top-100 start-0 end-0 shadow-sm d-none" style="z-index:20;"></div>
              </div>
              <div class="pt-coord-search-state" id="coord-searching-state">
                <span class="pt-coord-spinner"></span>&nbsp;Buscando…
              </div>
              <div class="form-text mb-3">O primeiro selecionado torna-se o coordenador principal automaticamente.</div>

              <div class="oficio-selection-panel">
                <div class="oficio-selection-panel-head">
                  <span class="oficio-selection-panel-title">Coordenadores selecionados</span>
                  <span class="badge text-bg-secondary" id="coord-chip-count">0</span>
                </div>
                <div id="coord-chip-list" class="oficio-selection-chip-list">
                  <span class="oficio-glance-empty" id="coord-chip-empty">Nenhum coordenador selecionado.</span>
                </div>
              </div>
            </section>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Coordenação administrativa</h3>
                  <p class="oficio-stage-section-text">Servidor do banco de viajantes com papel administrativo.</p>
                </div>
              </div>
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label" for="{{ form.coordenador_administrativo.id_for_label }}">Coordenador administrativo</label>
                  {{ form.coordenador_administrativo }}
                  <div class="form-text">Origem: viajantes finalizados.</div>
                  {% if form.coordenador_administrativo.errors %}<div class="invalid-feedback d-block">{{ form.coordenador_administrativo.errors.0 }}</div>{% endif %}
                </div>
              </div>
            </section>
          </div>

          {# ════ ETAPA 4 — ATIVIDADES ════ #}
          <div class="pt-step" data-step-index="3">
            <div class="oficio-stage-intro">
              <span class="oficio-stage-kicker">Etapa 4</span>
              <h2 class="oficio-stage-title">Atividades</h2>
              <p class="oficio-stage-description">Selecione as atividades — metas e recursos são gerados automaticamente.</p>
            </div>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Atividades previstas</h3>
                  <p class="oficio-stage-section-text">Marque as atividades que serão realizadas neste plano.</p>
                </div>
              </div>
              <div class="pt-activity-grid">
                {% for atividade in plano_trabalho_atividades_catalogo %}
                <label class="pt-activity-item" for="pt-atividade-{{ atividade.codigo }}">
                  <div class="form-check">
                    <input class="form-check-input" type="checkbox" name="atividades_codigos" value="{{ atividade.codigo }}" id="pt-atividade-{{ atividade.codigo }}" {% if atividade.codigo in pt_selected_activity_codes %}checked{% endif %}>
                    <span class="form-check-label">{{ atividade.nome }}</span>
                  </div>
                </label>
                {% endfor %}
              </div>
            </section>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Metas e recursos</h3>
                  <p class="oficio-stage-section-text">Gerados automaticamente pelas atividades marcadas acima.</p>
                </div>
              </div>
              <div class="row g-3">
                <div class="col-md-6">
                  <label class="form-label" for="{{ form.metas_formatadas.id_for_label }}">Metas (auto)</label>
                  {{ form.metas_formatadas }}
                </div>
                <div class="col-md-6">
                  <label class="form-label" for="{{ form.recursos_texto.id_for_label }}">Recursos (auto)</label>
                  {{ form.recursos_texto }}
                </div>
              </div>
            </section>
          </div>

          {# ════ ETAPA 5 — DIÁRIAS ════ #}
          <div class="pt-step" data-step-index="4">
            <div class="oficio-stage-intro">
              <span class="oficio-stage-kicker">Etapa 5</span>
              <h2 class="oficio-stage-title">Diárias</h2>
              <p class="oficio-stage-description">Calculadora pré-alimentada com período e equipe — confirme ou ajuste.</p>
            </div>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div>
                  <h3 class="oficio-stage-section-title">Calculadora financeira</h3>
                  <p class="oficio-stage-section-text">Período e efetivo já informados — confirme os valores abaixo.</p>
                </div>
              </div>
              <div class="pt-diarias-shell">
                <div class="row g-3">
                  <div class="col-6">
                    <label class="form-label">Saída (espelho)</label>
                    <input type="text" id="pt-diarias-data-inicio" class="form-control" readonly tabindex="-1">
                  </div>
                  <div class="col-6">
                    <label class="form-label">Retorno (espelho)</label>
                    <input type="text" id="pt-diarias-data-fim" class="form-control" readonly tabindex="-1">
                  </div>
                  <div class="col-6">
                    <label class="form-label" for="{{ form.diarias_quantidade.id_for_label }}">Qtd. de diárias</label>
                    {{ form.diarias_quantidade }}
                    <div class="form-text text-success fw-semibold" id="pt-diarias-hint"></div>
                  </div>
                  <div class="col-6">
                    <label class="form-label" for="{{ form.diarias_valor_unitario.id_for_label }}">Valor / servidor / dia</label>
                    {{ form.diarias_valor_unitario }}
                  </div>
                  <div class="col-12">
                    <label class="form-label" for="{{ form.diarias_valor_total.id_for_label }}">Valor total oficial</label>
                    {{ form.diarias_valor_total }}
                  </div>
                  <div class="col-12">
                    <label class="form-label" for="{{ form.diarias_valor_extenso.id_for_label }}">Valor total por extenso</label>
                    {{ form.diarias_valor_extenso }}
                  </div>
                </div>
                <aside class="pt-diarias-output" id="pt-diarias-output-panel">
                  <div>
                    <div class="pt-diarias-total-label">Total estimado</div>
                    <div class="pt-diarias-total-value" id="pt-live-total">R$&nbsp;0,00</div>
                    <div class="pt-diarias-auto-hint" id="pt-diarias-auto-hint">↑ Estimativa calculada automaticamente</div>
                  </div>
                  <div class="pt-diarias-kpis">
                    <div class="pt-diarias-kpi">
                      <div class="form-text mb-0">Diárias</div>
                      <strong id="pt-live-diarias">0</strong>
                    </div>
                    <div class="pt-diarias-kpi">
                      <div class="form-text mb-0">Valor / dia</div>
                      <strong id="pt-live-unit">R$&nbsp;0,00</strong>
                    </div>
                    <div class="pt-diarias-kpi">
                      <div class="form-text mb-0">Efetivo</div>
                      <strong id="pt-live-efetivo">0</strong>
                    </div>
                    <div class="pt-diarias-kpi">
                      <div class="form-text mb-0">Período</div>
                      <strong id="pt-live-periodo">—</strong>
                    </div>
                  </div>
                </aside>
              </div>
            </section>
          </div>

          {# ════ ETAPA 6 — REVISÃO ════ #}
          <div class="pt-step" data-step-index="5">
            <div class="oficio-stage-intro">
              <span class="oficio-stage-kicker">Etapa 6</span>
              <h2 class="oficio-stage-title">Revisão final</h2>
              <p class="oficio-stage-description">Verifique tudo — o que está aqui é exatamente o que será salvo.</p>
            </div>

            <section class="oficio-stage-section">
              <div class="oficio-stage-section-head">
                <div><h3 class="oficio-stage-section-title">Resumo completo</h3></div>
              </div>
              <div class="pt-review-grid">
                <div class="card h-100">
                  <div class="card-body">
                    <p class="fw-bold text-uppercase mb-2" style="font-size:.7rem;letter-spacing:.08em;color:#6c8097;">Planejamento</p>
                    <div class="pt-review-list" id="pt-review-main"></div>
                  </div>
                </div>
                <div class="card h-100">
                  <div class="card-body">
                    <p class="fw-bold text-uppercase mb-2" style="font-size:.7rem;letter-spacing:.08em;color:#6c8097;">Financeiro</p>
                    <div class="pt-review-list" id="pt-review-finance"></div>
                  </div>
                </div>
              </div>
            </section>
          </div>

          {# ════ FOOTER NAV ════ #}
          <div class="oficio-wizard-footer-actions">
            <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;">
              <button type="button" class="btn btn-outline-secondary" id="pt-prev" disabled>← Voltar</button>
              <button type="button" class="btn btn-outline-primary" id="pt-next">Avançar →</button>
              <span class="badge text-bg-light text-muted" id="pt-progress-chip">1 / 6</span>
            </div>
            <div style="display:flex;gap:.5rem;flex-wrap:wrap;align-items:center;">
              <button class="btn btn-primary" type="submit">Salvar plano</button>
              {% if object %}
              <a class="btn btn-success" href="{% url 'eventos:documentos-planos-trabalho-download' object.pk 'docx' %}">DOCX</a>
              <a class="btn btn-outline-success" href="{% url 'eventos:documentos-planos-trabalho-download' object.pk 'pdf' %}">PDF</a>
              {% endif %}
              <a class="btn btn-outline-secondary" href="{{ return_to|default:'/eventos/documentos/planos-trabalho/' }}">Cancelar</a>
            </div>
          </div>

        </form>
      </div>
    </div>

  </div>
</div>

{{ selected_coordenadores_payload|json_script:"coordenadores-selected-data" }}
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/oficio_wizard.js' %}"></script>
<script>
(function () {
  'use strict';

  const form = document.getElementById('pt-form');
  if (!form) return;

  // ══════════════════════════════════════════════════════════
  //  CENTRAL STATE — single source of truth
  // ══════════════════════════════════════════════════════════
  const planoState = {
    datas:         { inicio: '', fim: '', dias: 0 },
    equipe:        { total: 0 },
    coordenadores: [],   // [{id, nome, cargo, isPrincipal}]
    roteiro:       [],   // [{estado_id, estado_sigla, cidade_id, cidade_nome}]
    diarias:       { qtd: 0, unitario: 0, total: 0 },
  };

  const _subs = [];
  function subscribe(fn) { _subs.push(fn); }
  function notify() { _subs.forEach((fn) => { try { fn(planoState); } catch (_) {} }); }

  // ══════════════════════════════════════════════════════════
  //  DOM REFS
  // ══════════════════════════════════════════════════════════
  const stepLinks   = Array.from(document.querySelectorAll('[data-step-target]'));
  const steps       = Array.from(document.querySelectorAll('.pt-step'));
  const prevBtn     = document.getElementById('pt-prev');
  const nextBtn     = document.getElementById('pt-next');
  const progressEl  = document.getElementById('pt-progress-chip');
  let   currentStep = 0;

  const eventSelect         = document.getElementById('{{ form.evento.id_for_label }}');
  const oficioSelect        = document.getElementById('{{ form.oficio.id_for_label }}');
  const oficiosSelect       = document.getElementById('{{ form.oficios_relacionados.id_for_label }}');
  const roteiroSelect       = document.getElementById('{{ form.roteiro.id_for_label }}');
  const solicitanteSelect   = document.getElementById('{{ form.solicitante_escolha.id_for_label }}');
  const solOutrosWrap       = document.getElementById('col-solicitante-outros');
  const salvarSolWrap       = document.getElementById('col-salvar-solicitante');
  const horarioPadrao       = document.getElementById('{{ form.horario_atendimento_padrao.id_for_label }}');
  const horarioManualWrap   = document.getElementById('col-horario-manual');
  const dataUnica           = document.getElementById('{{ form.evento_data_unica.id_for_label }}');
  const dataInicio          = document.getElementById('{{ form.evento_data_inicio.id_for_label }}');
  const dataFim             = document.getElementById('{{ form.evento_data_fim.id_for_label }}');
  const colDataFim          = document.getElementById('col-data-fim');
  const durBadge            = document.getElementById('pt-dur-badge');
  const coordAdmSelect      = document.getElementById('{{ form.coordenador_administrativo.id_for_label }}');
  const destinosContainer   = document.getElementById('destinos-container');
  const destinosPayload     = document.getElementById('{{ form.destinos_payload.id_for_label }}');
  const cidadesApiBase      = '{{ api_cidades_por_estado_url|escapejs }}';
  const totalFormsInput     = document.getElementById('id_efetivo-TOTAL_FORMS');
  const efetivoRows         = document.getElementById('efetivo-rows');
  const qtdServidores       = document.getElementById('{{ form.quantidade_servidores.id_for_label }}');
  const diariasQtd          = document.getElementById('{{ form.diarias_quantidade.id_for_label }}');
  const diariasUnit         = document.getElementById('{{ form.diarias_valor_unitario.id_for_label }}');
  const diariasTotal        = document.getElementById('{{ form.diarias_valor_total.id_for_label }}');
  const liveTotal           = document.getElementById('pt-live-total');
  const liveDiarias         = document.getElementById('pt-live-diarias');
  const liveUnit            = document.getElementById('pt-live-unit');
  const liveEfetivo         = document.getElementById('pt-live-efetivo');
  const livePeriodo         = document.getElementById('pt-live-periodo');
  const diariasInicioMirror = document.getElementById('pt-diarias-data-inicio');
  const diariasFimMirror    = document.getElementById('pt-diarias-data-fim');
  const diariasOutputPanel  = document.getElementById('pt-diarias-output-panel');
  const diariasAutoHint     = document.getElementById('pt-diarias-auto-hint');
  const diariasHintLabel    = document.getElementById('pt-diarias-hint');
  const reviewMain          = document.getElementById('pt-review-main');
  const reviewFinance       = document.getElementById('pt-review-finance');
  const stsPeriodo          = document.getElementById('pts-periodo');
  const stsDias             = document.getElementById('pts-dias');
  const stsEquipe           = document.getElementById('pts-equipe');
  const stsCoord            = document.getElementById('pts-coord');
  const stsValor            = document.getElementById('pts-valor');
  const coordWrapper        = document.getElementById('coord-autocomplete-wrapper');
  const coordInput          = document.getElementById('coord-autocomplete-input');
  const coordResults        = document.getElementById('coord-autocomplete-results');
  const coordChips          = document.getElementById('coord-chip-list');
  const coordCount          = document.getElementById('coord-chip-count');
  const coordEmpty          = document.getElementById('coord-chip-empty');
  const coordIdsInput       = document.getElementById('{{ form.coordenadores_ids.id_for_label }}');
  const coordSearchState    = document.getElementById('coord-searching-state');
  const buscarUrl           = coordWrapper ? coordWrapper.getAttribute('data-search-url') : '';
  let   coordDebounce       = null;

  // ══════════════════════════════════════════════════════════
  //  UTILITIES
  // ══════════════════════════════════════════════════════════
  function refreshPickers(root) {
    if (window.OficioWizard && typeof window.OficioWizard.refreshSelectPickers === 'function') {
      window.OficioWizard.refreshSelectPickers(root || form);
    }
  }
  function forceSearchable(sel, ph) {
    if (!sel) return;
    sel.setAttribute('data-oficio-picker-search', 'always');
    if (ph) sel.setAttribute('data-oficio-picker-search-placeholder', ph);
  }
  function parseCurrency(val) {
    const raw = String(val || '').trim();
    if (!raw) return 0;
    const n = parseFloat(raw.replace(/\./g, '').replace(',', '.').replace(/[^0-9.-]/g, ''));
    return Number.isFinite(n) ? n : 0;
  }
  function formatCurrency(val) {
    try { return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val || 0); }
    catch (_) { return 'R$ ' + (val || 0).toFixed(2); }
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    const parts = iso.split('-');
    if (parts.length < 3) return iso;
    return parts[2] + '/' + parts[1] + '/' + parts[0];
  }
  function selectedText(sel) {
    if (!sel || sel.selectedIndex < 0) return '—';
    const opt = sel.options[sel.selectedIndex];
    return opt ? String(opt.textContent || '').trim() : '—';
  }
  function showStepWarning(message) {
    let warn = document.getElementById('pt-step-warning');
    if (!warn) {
      warn = document.createElement('div');
      warn.id = 'pt-step-warning';
      warn.className = 'alert alert-warning py-2 px-3 mb-3';
      warn.setAttribute('role', 'alert');
      form.insertBefore(warn, form.firstChild);
    }
    warn.textContent = '\u26a0 ' + message;
    warn.style.display = '';
    clearTimeout(warn._t);
    warn._t = setTimeout(() => { if (warn) warn.style.display = 'none'; }, 5500);
  }

  // ══════════════════════════════════════════════════════════
  //  STEP NAVIGATION + PROGRESSIVE VALIDATION
  // ══════════════════════════════════════════════════════════
  const stepValidations = [
    null,   // 0→1: no block
    () => { // 1→2: warn if no dates
      if (!dataInicio || !dataInicio.value) {
        showStepWarning('Período sem data de saída — as diárias não serão calculadas automaticamente a partir das datas.');
      }
    },
    () => { // 2→3: warn if zero efetivo
      if (planoState.equipe.total < 1) {
        showStepWarning('Nenhum efetivo cadastrado. Você pode preencher e voltar antes de salvar.');
      }
    },
    null,
    null,
  ];

  function showStep(index) {
    const target = Math.max(0, Math.min(index, steps.length - 1));
    if (target > currentStep) {
      const validate = stepValidations[currentStep];
      if (typeof validate === 'function') validate();
    }
    currentStep = target;
    steps.forEach((s, i) => s.classList.toggle('is-active', i === currentStep));
    stepLinks.forEach((link, i) => {
      link.classList.toggle('is-active',    i === currentStep);
      link.classList.toggle('is-completed', i < currentStep);
      link.removeAttribute('aria-current');
      if (i === currentStep) link.setAttribute('aria-current', 'step');
    });
    if (progressEl) progressEl.textContent = (currentStep + 1) + ' / ' + steps.length;
    prevBtn.disabled = currentStep === 0;
    if (currentStep === steps.length - 2) {
      nextBtn.textContent = 'Ver revisão →';
    } else if (currentStep === steps.length - 1) {
      nextBtn.textContent = '\u2713 Pronto';
    } else {
      nextBtn.textContent = 'Avançar →';
    }
    if (currentStep === steps.length - 1) renderReview();
    if (currentStep === 4) syncDiariasMirrors();
    refreshPickers(steps[currentStep]);
  }

  stepLinks.forEach((link) => {
    link.addEventListener('click', () => {
      const t = parseInt(link.getAttribute('data-step-target') || '0', 10);
      if (!Number.isNaN(t)) showStep(t);
    });
  });
  prevBtn.addEventListener('click', () => showStep(currentStep - 1));
  nextBtn.addEventListener('click', () => showStep(Math.min(currentStep + 1, steps.length - 1)));

  // ══════════════════════════════════════════════════════════
  //  SUMMARY BAR SUBSCRIPTION
  // ══════════════════════════════════════════════════════════
  subscribe((state) => {
    const { datas, equipe, coordenadores, diarias } = state;
    if (stsPeriodo) {
      if (datas.inicio) {
        const periodoText = datas.fim && !(dataUnica && dataUnica.checked)
          ? fmtDate(datas.inicio) + ' \u2192 ' + fmtDate(datas.fim)
          : fmtDate(datas.inicio);
        stsPeriodo.textContent = periodoText;
      } else {
        stsPeriodo.textContent = '—';
      }
    }
    if (stsDias) stsDias.textContent = datas.dias ? datas.dias + ' dia' + (datas.dias !== 1 ? 's' : '') : '—';
    if (stsEquipe) stsEquipe.textContent = equipe.total > 0 ? equipe.total + ' servidor' + (equipe.total !== 1 ? 'es' : '') : '—';
    const principal = coordenadores.find((c) => c.isPrincipal);
    if (stsCoord) stsCoord.textContent = principal ? principal.nome : '—';
    if (stsValor) {
      const est = diarias.total || (diarias.qtd && diarias.unitario ? diarias.qtd * diarias.unitario : 0);
      stsValor.textContent = est ? formatCurrency(est) : '—';
    }
    // Duration badge on step 2
    if (durBadge) {
      if (datas.dias) {
        durBadge.textContent = '\uD83D\uDCC5 ' + datas.dias + ' dia' + (datas.dias !== 1 ? 's' : '');
        durBadge.style.display = '';
      } else {
        durBadge.style.display = 'none';
      }
    }
  });

  // ══════════════════════════════════════════════════════════
  //  PICKER HELPERS
  // ══════════════════════════════════════════════════════════
  forceSearchable(eventSelect,    'Filtrar evento...');
  forceSearchable(oficioSelect,   'Filtrar ofício...');
  forceSearchable(oficiosSelect,  'Filtrar ofícios...');
  forceSearchable(roteiroSelect,  'Filtrar roteiro...');
  forceSearchable(coordAdmSelect, 'Filtrar servidor...');

  // ══════════════════════════════════════════════════════════
  //  TOGGLE HELPERS
  // ══════════════════════════════════════════════════════════
  function toggleSolicitanteOutros() {
    if (!solicitanteSelect) return;
    const show = solicitanteSelect.value === '__OUTROS__';
    if (solOutrosWrap) solOutrosWrap.style.display = show ? '' : 'none';
    if (salvarSolWrap) salvarSolWrap.style.display = show ? '' : 'none';
  }
  function toggleHorarioManual() {
    if (!horarioPadrao || !horarioManualWrap) return;
    horarioManualWrap.style.display = horarioPadrao.value === '__OUTROS__' ? '' : 'none';
  }
  function toggleDataFim() {
    if (!dataUnica || !colDataFim) return;
    colDataFim.style.display = dataUnica.checked ? 'none' : '';
    if (dataUnica.checked && dataInicio && dataFim) dataFim.value = dataInicio.value;
  }

  // ══════════════════════════════════════════════════════════
  //  DATE → STATE
  // ══════════════════════════════════════════════════════════
  function parseDateRange() {
    const inicio = (dataInicio && dataInicio.value) || '';
    const fim    = (dataUnica && dataUnica.checked) ? inicio : ((dataFim && dataFim.value) || '');
    let dias = 0;
    if (inicio && fim) {
      const s = new Date(inicio + 'T00:00:00');
      const e = new Date(fim + 'T00:00:00');
      if (!isNaN(s) && !isNaN(e) && e >= s) dias = Math.floor((e - s) / 86400000) + 1;
    }
    planoState.datas = { inicio, fim, dias };
  }

  function onDatasChange() {
    toggleDataFim();
    parseDateRange();
    autoSuggestDiarias(false);
    notify();
  }

  // ══════════════════════════════════════════════════════════
  //  DIÁRIAS — AUTO-SUGGEST + COMPUTE
  // ══════════════════════════════════════════════════════════
  let _diariasAutoSet = false;

  function autoSuggestDiarias(fromStepEnter) {
    const dias = planoState.datas.dias;
    if (!dias || !diariasQtd) return;
    if (!diariasQtd.value || (fromStepEnter && !_diariasAutoSet)) {
      diariasQtd.value = String(dias);
      _diariasAutoSet = true;
      if (diariasHintLabel) diariasHintLabel.textContent = '\u2191 Sugerido automaticamente (' + dias + ' dias de período)';
      computeDiarias(true);
    }
  }

  function syncDiariasMirrors() {
    if (diariasInicioMirror) diariasInicioMirror.value = planoState.datas.inicio ? fmtDate(planoState.datas.inicio) : '—';
    if (diariasFimMirror)    diariasFimMirror.value    = planoState.datas.fim    ? fmtDate(planoState.datas.fim)    : '—';
  }

  function computeDiarias(animate) {
    syncDiariasMirrors();
    const totalOficial = parseCurrency(diariasTotal ? diariasTotal.value : '');
    const unitField    = parseCurrency(diariasUnit  ? diariasUnit.value  : '');
    const qtdRaw       = (() => {
      const raw = String((diariasQtd && diariasQtd.value) || '');
      const m   = raw.match(/[0-9]+([.,][0-9]+)?/);
      if (!m) return 0;
      const n = parseFloat(m[0].replace(',', '.'));
      return Number.isFinite(n) ? n : 0;
    })();
    const qtd     = qtdRaw || planoState.datas.dias || 0;
    const efetivo = parseInt((qtdServidores && qtdServidores.value) || '0', 10) || 0;
    let unit  = unitField;
    if (!unit && totalOficial && qtd) unit = totalOficial / qtd;
    let total = totalOficial;
    if (!total && unit && qtd) total = unit * qtd;

    planoState.diarias = { qtd, unitario: unit, total };

    if (liveTotal)   liveTotal.textContent   = formatCurrency(total);
    if (liveDiarias) liveDiarias.textContent = qtd + ' diária(s)';
    if (liveUnit)    liveUnit.textContent    = formatCurrency(unit);
    if (liveEfetivo) liveEfetivo.textContent = efetivo + ' servidor(es)';
    if (livePeriodo) livePeriodo.textContent = planoState.datas.dias ? planoState.datas.dias + ' dias' : '—';

    if (animate && diariasOutputPanel) {
      diariasOutputPanel.classList.remove('is-updated');
      void diariasOutputPanel.offsetWidth;
      diariasOutputPanel.classList.add('is-updated');
      if (diariasAutoHint) diariasAutoHint.classList.add('is-visible');
      if (liveTotal) {
        liveTotal.classList.remove('is-flash');
        void liveTotal.offsetWidth;
        liveTotal.classList.add('is-flash');
        setTimeout(() => liveTotal.classList.remove('is-flash'), 1200);
      }
      setTimeout(() => { if (diariasOutputPanel) diariasOutputPanel.classList.remove('is-updated'); }, 700);
    }
    notify();
  }

  // ══════════════════════════════════════════════════════════
  //  EVENT / OFICIO FILTER
  // ══════════════════════════════════════════════════════════
  function filterByEvent(sel) {
    if (!sel || !eventSelect) return;
    const eventId = String(eventSelect.value || '').trim();
    Array.from(sel.options).forEach((opt) => {
      if (!opt.value) { opt.hidden = false; return; }
      const optEvent = String(opt.dataset.eventId || '').trim();
      opt.hidden = !!eventId && !!optEvent && optEvent !== eventId;
    });
    refreshPickers(sel);
  }

  // ══════════════════════════════════════════════════════════
  //  DESTINOS
  // ══════════════════════════════════════════════════════════
  async function fetchCidades(estadoId) {
    if (!estadoId) return [];
    const url = cidadesApiBase.replace('/0/', '/' + estadoId + '/');
    const r = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
    return r.ok ? r.json() : [];
  }
  async function mountCidadeOptions(sel, estadoId, selId) {
    sel.innerHTML = '<option value="">Selecione...</option>';
    const list = await fetchCidades(estadoId);
    list.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.nome;
      if (String(selId || '') === String(c.id)) opt.selected = true;
      sel.appendChild(opt);
    });
    refreshPickers(sel);
  }
  async function addDestinoRow(dest) {
    const row = document.createElement('div');
    row.className = 'pt-dest-row';
    row.innerHTML =
      '<div class="row g-2 align-items-end">' +
        '<div class="col-md-5"><label class="form-label">Estado</label>' +
          '<select class="destino-estado form-select" data-oficio-picker-search="always" data-oficio-picker-search-placeholder="Filtrar UF...">' +
            '<option value="">Selecione...</option>' +
            '{% for estado in estados_choices %}<option value="{{ estado.pk }}">{{ estado.nome }} ({{ estado.sigla }})</option>{% endfor %}' +
          '</select></div>' +
        '<div class="col-md-5"><label class="form-label">Cidade</label>' +
          '<select class="destino-cidade form-select" data-oficio-picker-search="always" data-oficio-picker-search-placeholder="Filtrar cidade...">' +
            '<option value="">Selecione...</option>' +
          '</select></div>' +
        '<div class="col-md-2 d-flex align-items-end">' +
          '<button type="button" class="btn btn-outline-danger w-100 btn-rem-destino" title="Remover destino">\u00d7</button>' +
        '</div>' +
      '</div>';
    destinosContainer.appendChild(row);
    refreshPickers(row);
    const estadoSel = row.querySelector('.destino-estado');
    const cidadeSel = row.querySelector('.destino-cidade');
    estadoSel.value = String(dest.estado_id || '');
    if (estadoSel.value) await mountCidadeOptions(cidadeSel, estadoSel.value, dest.cidade_id || '');
    refreshPickers(row);
  }
  function collectDestinos() {
    const rows = Array.from(destinosContainer.querySelectorAll('.pt-dest-row'));
    const payload = [];
    rows.forEach((row) => {
      const eSel = row.querySelector('.destino-estado');
      const cSel = row.querySelector('.destino-cidade');
      if (!eSel || !cSel || !eSel.value || !cSel.value) return;
      const eText = eSel.options[eSel.selectedIndex] ? eSel.options[eSel.selectedIndex].textContent : '';
      const cText = cSel.options[cSel.selectedIndex] ? cSel.options[cSel.selectedIndex].textContent : '';
      const sigla = /\(([^)]+)\)\s*$/.exec(eText);
      payload.push({ estado_id: parseInt(eSel.value, 10), estado_sigla: sigla ? sigla[1] : '', cidade_id: parseInt(cSel.value, 10), cidade_nome: cText });
    });
    planoState.roteiro = payload;
    if (destinosPayload) destinosPayload.value = JSON.stringify(payload);
    notify();
  }
  async function bootstrapDestinos() {
    let initial = [];
    try { initial = JSON.parse((destinosPayload && destinosPayload.value) || '[]'); } catch (_) {}
    if (!Array.isArray(initial) || !initial.length) initial = [{ estado_id: '', cidade_id: '' }];
    for (const item of initial) await addDestinoRow(item || {});
    collectDestinos();
  }
  destinosContainer.addEventListener('change', async (ev) => {
    const row = ev.target.closest('.pt-dest-row');
    if (!row) return;
    if (ev.target.classList.contains('destino-estado')) {
      await mountCidadeOptions(row.querySelector('.destino-cidade'), ev.target.value, '');
    }
    collectDestinos();
  });
  destinosContainer.addEventListener('click', (ev) => {
    const btn = ev.target.closest('.btn-rem-destino');
    if (!btn) return;
    if (destinosContainer.querySelectorAll('.pt-dest-row').length <= 1) return;
    btn.closest('.pt-dest-row').remove();
    collectDestinos();
  });
  document.getElementById('btn-add-destino').addEventListener('click', async () => {
    await addDestinoRow({ estado_id: '', cidade_id: '' });
    collectDestinos();
  });

  // ══════════════════════════════════════════════════════════
  //  EFETIVO
  // ══════════════════════════════════════════════════════════
  function syncEfetivoTotal() {
    if (!qtdServidores) return;
    let total = 0;
    Array.from(efetivoRows.querySelectorAll('[data-ef-row]')).forEach((row) => {
      const qty = row.querySelector('input[name$="-quantidade"]');
      const del = row.querySelector('input[name$="-DELETE"]');
      if (!qty || (del && del.checked)) return;
      const v = parseInt(qty.value || '0', 10);
      if (!isNaN(v) && v > 0) total += v;
    });
    qtdServidores.value         = total > 0 ? String(total) : '';
    planoState.equipe.total     = total;
    computeDiarias(false);
    notify();
  }
  function reindexEfetivoRows() {
    Array.from(efetivoRows.querySelectorAll('[data-ef-row]')).forEach((row, idx) => {
      row.querySelectorAll('input, select, label').forEach((el) => {
        ['name', 'id', 'for'].forEach((attr) => {
          const cur = el.getAttribute(attr);
          if (!cur) return;
          el.setAttribute(attr, cur.replace(/efetivo-\d+-/g, 'efetivo-' + idx + '-'));
        });
      });
    });
    if (totalFormsInput) totalFormsInput.value = String(efetivoRows.querySelectorAll('[data-ef-row]').length);
    refreshPickers(efetivoRows);
  }
  function addEfetivoRow() {
    const rows = efetivoRows.querySelectorAll('[data-ef-row]');
    if (!rows.length) return;
    const clone = rows[rows.length - 1].cloneNode(true);
    clone.querySelectorAll('input, select').forEach((el) => {
      if (el.name && el.name.endsWith('-id'))     { el.value = '';     return; }
      if (el.name && el.name.endsWith('-DELETE')) { el.checked = false; return; }
      if (el.tagName === 'SELECT') { el.selectedIndex = 0; return; }
      if (el.type === 'number')   { el.value = '1'; return; }
      if (el.type !== 'hidden')   { el.value = ''; }
    });
    efetivoRows.appendChild(clone);
    reindexEfetivoRows();
    syncEfetivoTotal();
  }
  document.getElementById('btn-add-efetivo').addEventListener('click', addEfetivoRow);
  efetivoRows.addEventListener('change', syncEfetivoTotal);
  efetivoRows.addEventListener('input',  syncEfetivoTotal);

  // ══════════════════════════════════════════════════════════
  //  COORDENADORES (with PRINCIPAL concept)
  // ══════════════════════════════════════════════════════════
  function syncCoordIds() {
    if (coordIdsInput) coordIdsInput.value = planoState.coordenadores.map((c) => c.id).join(',');
    if (coordCount)   coordCount.textContent = String(planoState.coordenadores.length);
  }

  function renderCoordChips() {
    if (!coordChips) return;
    Array.from(coordChips.querySelectorAll('[data-coord-chip]')).forEach((c) => c.remove());
    if (planoState.coordenadores.length === 0) {
      if (coordEmpty) coordEmpty.style.display = '';
      syncCoordIds();
      notify();
      return;
    }
    if (coordEmpty) coordEmpty.style.display = 'none';
    planoState.coordenadores.forEach((item) => {
      const chip = document.createElement('div');
      chip.className = 'oficio-glance-chip oficio-selection-chip pt-chip-anim';
      chip.setAttribute('data-coord-chip', item.id);

      const nome = document.createElement('span');
      nome.className = 'oficio-glance-chip-nome';
      nome.textContent = item.nome;
      chip.appendChild(nome);

      if (item.isPrincipal) {
        const badge = document.createElement('span');
        badge.className = 'pt-coord-badge-principal';
        badge.textContent = 'Principal';
        chip.appendChild(badge);
      } else {
        const mkBtn = document.createElement('button');
        mkBtn.type = 'button';
        mkBtn.className = 'pt-coord-make-principal';
        mkBtn.title = 'Definir como coordenador principal';
        mkBtn.setAttribute('data-make-principal', item.id);
        mkBtn.textContent = '\u2605';
        chip.appendChild(mkBtn);
      }

      if (item.cargo) {
        const cargo = document.createElement('span');
        cargo.className = 'oficio-glance-chip-sub';
        cargo.textContent = item.cargo;
        chip.appendChild(cargo);
      }

      const rmBtn = document.createElement('button');
      rmBtn.type = 'button';
      rmBtn.className = 'oficio-selection-chip-remove';
      rmBtn.setAttribute('data-remove-coord', item.id);
      rmBtn.setAttribute('aria-label', 'Remover ' + item.nome);
      rmBtn.textContent = '\u00d7';
      chip.appendChild(rmBtn);

      coordChips.appendChild(chip);
    });
    syncCoordIds();
    notify();
  }

  function addCoordenador(id, item) {
    const strId = String(id);
    if (planoState.coordenadores.find((c) => c.id === strId)) return;
    const isPrincipal = planoState.coordenadores.length === 0;
    planoState.coordenadores.push({
      id:          strId,
      nome:        item.nome       || '',
      cargo:       item.cargo      || '',
      unidade:     item.unidade    || '',
      isPrincipal,
    });
    renderCoordChips();
  }
  function removeCoordenador(id) {
    const strId = String(id);
    const idx   = planoState.coordenadores.findIndex((c) => c.id === strId);
    if (idx === -1) return;
    const wasPrincipal = planoState.coordenadores[idx].isPrincipal;
    planoState.coordenadores.splice(idx, 1);
    if (wasPrincipal && planoState.coordenadores.length > 0) {
      planoState.coordenadores[0].isPrincipal = true;
    }
    renderCoordChips();
  }
  function setPrincipalCoordenador(id) {
    const strId = String(id);
    planoState.coordenadores.forEach((c) => { c.isPrincipal = c.id === strId; });
    renderCoordChips();
  }

  if (coordChips) {
    coordChips.addEventListener('click', (ev) => {
      const rmBtn = ev.target.closest('[data-remove-coord]');
      if (rmBtn) { removeCoordenador(rmBtn.getAttribute('data-remove-coord')); return; }
      const mkBtn = ev.target.closest('[data-make-principal]');
      if (mkBtn) setPrincipalCoordenador(mkBtn.getAttribute('data-make-principal'));
    });
  }

  // Pre-load existing coordinators from JSON payload
  (() => {
    const el = document.getElementById('coordenadores-selected-data');
    if (!el) return;
    try {
      const list = JSON.parse(el.textContent || '[]');
      list.forEach((item, idx) => {
        if (!item || !item.id) return;
        planoState.coordenadores.push({
          id:         String(item.id),
          nome:       item.nome  || '',
          cargo:      item.cargo || '',
          unidade:    item.unidade || '',
          isPrincipal: idx === 0,
        });
      });
      if (planoState.coordenadores.length) renderCoordChips();
    } catch (_) {}
  })();

  // Autocomplete
  if (coordInput) {
    coordInput.addEventListener('input', () => {
      clearTimeout(coordDebounce);
      const q = coordInput.value.trim();
      if (!q || !buscarUrl) {
        if (coordResults) coordResults.classList.add('d-none');
        return;
      }
      if (coordSearchState) coordSearchState.classList.add('is-visible');
      coordDebounce = setTimeout(async () => {
        try {
          const r = await fetch(buscarUrl + '?q=' + encodeURIComponent(q), {
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
          });
          if (coordSearchState) coordSearchState.classList.remove('is-visible');
          if (!r.ok) return;
          const data    = await r.json();
          const results = Array.isArray(data.results) ? data.results : [];
          coordResults.innerHTML = '';
          if (!results.length) { coordResults.classList.add('d-none'); return; }
          results.forEach((item) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'list-group-item list-group-item-action py-2 px-3';
            btn.innerHTML =
              '<strong class="d-block" style="font-size:.88rem">' + item.nome + '</strong>' +
              (item.cargo ? '<span class="text-muted" style="font-size:.78rem">' + item.cargo + (item.unidade ? ' \u2014 ' + item.unidade : '') + '</span>' : '');
            btn.addEventListener('click', () => {
              addCoordenador(item.id, item);
              coordInput.value = '';
              coordResults.classList.add('d-none');
            });
            coordResults.appendChild(btn);
          });
          coordResults.classList.remove('d-none');
        } catch (_) {
          if (coordSearchState) coordSearchState.classList.remove('is-visible');
        }
      }, 250);
    });
    coordInput.addEventListener('blur', () => {
      setTimeout(() => {
        if (coordSearchState) coordSearchState.classList.remove('is-visible');
        if (coordResults) coordResults.classList.add('d-none');
      }, 200);
    });
  }

  // ══════════════════════════════════════════════════════════
  //  REVIEW RENDER
  // ══════════════════════════════════════════════════════════
  function countAtividades() {
    return document.querySelectorAll('input[name="atividades_codigos"]:checked').length;
  }
  function renderReview() {
    if (!reviewMain || !reviewFinance) return;
    const s = planoState;
    const principal = s.coordenadores.find((c) => c.isPrincipal);
    function row(label, value) {
      return '<div class="pt-review-row"><span class="pt-review-label">' + label + '</span><span class="pt-review-value">' + (value || '—') + '</span></div>';
    }
    reviewMain.innerHTML = [
      row('Evento',          selectedText(eventSelect)),
      row('Ofício',          selectedText(oficioSelect)),
      row('Roteiro',         selectedText(roteiroSelect)),
      row('Solicitante',     selectedText(solicitanteSelect)),
      row('Saída',           s.datas.inicio ? fmtDate(s.datas.inicio) : '—'),
      row('Retorno',         s.datas.fim    ? fmtDate(s.datas.fim)    : '—'),
      row('Duração',         s.datas.dias   ? s.datas.dias + ' dia(s)' : '—'),
      row('Destinos',        s.roteiro.length ? s.roteiro.map((d) => d.cidade_nome || '?').join(', ') : '—'),
      row('Efetivo',         s.equipe.total > 0 ? String(s.equipe.total) : '—'),
      row('Coord. principal',principal ? principal.nome : '—'),
      row('Atividades',      String(countAtividades())),
    ].join('');
    const extEl = document.getElementById('{{ form.diarias_valor_extenso.id_for_label }}');
    reviewFinance.innerHTML = [
      row('Diárias',  (diariasQtd   && diariasQtd.value)   || '—'),
      row('Valor/dia',(diariasUnit  && diariasUnit.value)   || '—'),
      row('Total',    (diariasTotal && diariasTotal.value)  || '—'),
      row('Extenso',  extEl ? (extEl.value || '—') : '—'),
    ].join('');
  }

  // ══════════════════════════════════════════════════════════
  //  EVENT LISTENERS
  // ══════════════════════════════════════════════════════════
  if (eventSelect) {
    eventSelect.addEventListener('change', () => {
      filterByEvent(oficioSelect);
      filterByEvent(oficiosSelect);
      filterByEvent(roteiroSelect);
    });
    filterByEvent(oficioSelect);
    filterByEvent(oficiosSelect);
    filterByEvent(roteiroSelect);
  }
  if (solicitanteSelect) solicitanteSelect.addEventListener('change', toggleSolicitanteOutros);
  if (horarioPadrao)     horarioPadrao.addEventListener('change', toggleHorarioManual);
  if (dataUnica)         dataUnica.addEventListener('change', onDatasChange);
  if (dataInicio)        dataInicio.addEventListener('change', onDatasChange);
  if (dataFim)           dataFim.addEventListener('change', onDatasChange);
  [diariasQtd, diariasUnit, diariasTotal].forEach((el) => {
    if (!el) return;
    el.addEventListener('input',  () => { _diariasAutoSet = false; computeDiarias(false); });
    el.addEventListener('change', () => { _diariasAutoSet = false; computeDiarias(false); });
  });
  document.querySelectorAll('input[name="atividades_codigos"]').forEach((cb) => {
    cb.addEventListener('change', () => { if (currentStep === 5) renderReview(); });
  });
  form.addEventListener('submit', () => {
    collectDestinos();
    reindexEfetivoRows();
    syncEfetivoTotal();
  });

  // ══════════════════════════════════════════════════════════
  //  INIT
  // ══════════════════════════════════════════════════════════
  if (qtdServidores) qtdServidores.readOnly = true;
  toggleSolicitanteOutros();
  toggleHorarioManual();
  toggleDataFim();
  parseDateRange();
  bootstrapDestinos().then(() => {
    syncEfetivoTotal();
    computeDiarias(false);
    notify();
    refreshPickers(form);
  });
  showStep(0);

})();
</script>
{% endblock %}
"""

DEST.write_text(CONTENT, encoding="utf-8")
print(f"Written {DEST} — {len(CONTENT)} chars, {CONTENT.count(chr(10))} lines")
