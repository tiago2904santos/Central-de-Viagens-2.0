(function () {
  'use strict';
  var form = document.getElementById('oficio-step3-form');
  if (!form || form.dataset.ready === '1') return;
  form.dataset.ready = '1';
  function $(id) { return document.getElementById(id); }
  var initialState = JSON.parse($('step3-state-data').textContent || '{}');
  var routes = JSON.parse($('step3-routes-data').textContent || '[]');
  var rawInitialDiarias = JSON.parse($('step3-diarias-data').textContent || 'null');
  var initialDiarias = rawInitialDiarias && typeof rawInitialDiarias === 'object' ? rawInitialDiarias : null;
  var routeMap = {};
  routes.forEach(function(item) { routeMap[String(item.id)] = item; });
  var apiCidades = form.dataset.apiCidadesUrl || '';
  var apiDiarias = form.dataset.apiDiariasUrl || '';
  var csrf = (form.querySelector('input[name="csrfmiddlewaretoken"]') || {}).value || '';
  var urlTrechosEstimar = form.dataset.urlTrechosEstimar || '';
  var urlCalcularRotaPreview = form.dataset.apiCalcularRotaPreviewUrl || '';
  var autosaveIdInput = $('id_autosave_obj_id');
  var autosaveStatus = $('roteiro-autosave-status');
  function readJsonResponse(resp) {
    var contentType = (resp.headers && resp.headers.get('content-type')) || '';
    if (contentType.indexOf('application/json') !== -1) {
      return resp.json().then(function(data) { return { ok: resp.ok, data: data }; });
    }
    return resp.text().then(function() {
      return {
        ok: false,
        data: {
          ok: false,
          error: resp.status === 401
            ? 'Sessao expirada. Faca login novamente para continuar.'
            : 'O servidor retornou uma resposta invalida para a calculadora.'
        }
      };
    });
  }
  var autosave = window.OficioWizard ? window.OficioWizard.createAutosave({
    form: form,
    statusElement: autosaveStatus,
    captureSubmit: false,
    onSuccess: function(data) {
      if (!data || !data.id) return;
      if (autosaveIdInput) autosaveIdInput.value = String(data.id);
      if (data.edit_url) {
        form.setAttribute('action', data.edit_url);
        if (window.location.pathname !== data.edit_url) {
          window.history.replaceState({}, '', data.edit_url);
        }
      }
    }
  }) : null;
  var destinoEstadoDefaultId = form.dataset.destinoEstadoDefaultId || '';
  var applyingState = false;
  var diariasTimer = null;
  var diariasInFlight = false;
  var diariasNeedsRerun = false;
  var routeSearchTimer = null;
  var loopRenderTimer = null;
  var autoEstimarTimer = null;
  var citiesCache = {};
  var lastTrechosSignature = null;
  var TRECHOS_EMPTY_HTML = '<div class="roteiro-editor__empty"><p class="roteiro-editor__empty-title">Trechos ainda não disponíveis</p><p class="roteiro-editor__empty-text">Selecione a sede e ao menos um destino para editar os trechos.</p></div>';
  function refreshSelectPickers(root) {
    if (window.OficioWizard && typeof window.OficioWizard.refreshSelectPickers === 'function') {
      window.OficioWizard.refreshSelectPickers(root || form);
    }
  }
  function scheduleAutosave() {
    if (autosave) autosave.schedule();
  }
  function notifyRouteStateChanged() {
    try {
      window.dispatchEvent(new CustomEvent('roteiros:route-state-changed'));
    } catch (e) {
      /* ignore */
    }
  }
  function cidadesUrl(estadoId) { return apiCidades.replace(/\/0\/?$/, '/' + estadoId + '/'); }
  function pad(v) { return v < 10 ? '0' + v : String(v); }
  function hhmm(min) { min = parseInt(min || 0, 10) || 0; if (!min) return '-'; return pad(Math.floor(min / 60)) + ':' + pad(min % 60); }
  function formatDurationInput(min) { min = parseInt(min || 0, 10); if (Number.isNaN(min) || min <= 0) return ''; return pad(Math.floor(min / 60)) + ':' + pad(min % 60); }
  function normalizeDurationInput(value) {
    var raw = String(value || '').trim(); if (!raw) return '';
    if (raw.indexOf(':') !== -1) {
      var parts = raw.split(':');
      var hours = (parts[0] || '').replace(/\D/g, '').slice(0, 2);
      var minutes = parts.slice(1).join('').replace(/\D/g, '').slice(0, 2);
      if (!hours && !minutes) return '';
      return minutes ? (hours + ':' + minutes) : (hours + ':');
    }
    var digits = raw.replace(/\D/g, '').slice(0, 4); if (!digits) return '';
    if (digits.length <= 2) return digits;
    if (digits.length === 3) return digits.slice(0, 2) + ':' + digits.slice(2);
    return digits.slice(0, 2) + ':' + digits.slice(2, 4);
  }
  function parseDurationInput(value) {
    var text = String(value || '').trim(); if (!text) return null;
    var norm = text.indexOf(':') !== -1 ? text : normalizeDurationInput(text);
    var parts = norm.split(':'); if (parts.length !== 2) return null;
    var hours = parseInt(parts[0], 10); var minutes = parseInt(parts[1], 10);
    if (Number.isNaN(hours) || Number.isNaN(minutes) || minutes < 0 || minutes > 59) return null;
    return (hours * 60) + minutes;
  }
  function parseMinutesValue(value) {
    if (value == null || String(value).trim() === '') return null;
    var parsed = parseInt(value, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  function normalizeLocationLabel(value) {
    return String(value || '').trim().toUpperCase();
  }
  function isLoopModeActive(state) {
    if (state && state.bate_volta_diario && state.bate_volta_diario.ativo) return true;
    return !!($('id_bate_volta_diario_ativo') && $('id_bate_volta_diario_ativo').checked);
  }
  function toggleBateVoltaPanel() {
    var active = isLoopModeActive();
    var panel = $('bate-volta-panel');
    var status = $('bate-volta-status-text');
    var chip = $('bate-volta-status-chip');
    if (panel) {
      panel.classList.toggle('is-muted', !active);
    }
    if (chip) {
      chip.textContent = active ? 'Ativo' : 'Inativo';
      chip.classList.toggle('is-on', active);
    }
    if (status) {
      status.textContent = active
        ? 'Modo ativo. O editor abaixo passa a refletir o loop diário gerado.'
        : 'Modo inativo.';
    }
  }
  function syncBateVoltaDurationInputs() {
    var idaHidden = $('id_bate_volta_ida_tempo_min');
    var idaText = $('id_bate_volta_ida_tempo_hhmm');
    var voltaHidden = $('id_bate_volta_volta_tempo_min');
    var voltaText = $('id_bate_volta_volta_tempo_hhmm');
    if (idaText && idaHidden && document.activeElement !== idaText) {
      idaText.value = formatDurationInput(parseMinutesValue(idaHidden.value));
    }
    if (voltaText && voltaHidden && document.activeElement !== voltaText) {
      voltaText.value = formatDurationInput(parseMinutesValue(voltaHidden.value));
    }
  }
  function stateHasReturnToSede(state) {
    var sedeId = String((state && state.sede_cidade_id) || ($('id_origem_cidade') || {}).value || '');
    var sedeNome = normalizeLocationLabel(selectedText($('id_origem_cidade')));
    return ((state && state.trechos) || []).some(function(trecho) {
      var destinoId = String(trecho.destino_cidade_id || '');
      var destinoNome = normalizeLocationLabel(trecho.destino_nome || '');
      return (sedeId && destinoId && sedeId === destinoId) || (sedeNome && destinoNome && sedeNome === destinoNome);
    });
  }
  function shouldUseExactTrechos(state) {
    return isLoopModeActive(state) || stateHasReturnToSede(state);
  }
  function formatDateInputValue(dateObj) {
    return dateObj.getFullYear() + '-' + pad(dateObj.getMonth() + 1) + '-' + pad(dateObj.getDate());
  }
  function addMinutes(dateValue, timeValue, totalMinutes) {
    var start = new Date(dateValue + 'T' + timeValue);
    if (Number.isNaN(start.getTime())) return null;
    var end = new Date(start.getTime() + (totalMinutes * 60000));
    return {
      data: formatDateInputValue(end),
      hora: pad(end.getHours()) + ':' + pad(end.getMinutes())
    };
  }
  /** chegada = saída + tempo_viagem + tempo_adicional (cruza meia-noite conforme Date). */
  function calcularChegada(saidaData, saidaHora, tempoViagemMin, tempoAdicionalMin) {
    var cru = parseInt(tempoViagemMin || 0, 10) || 0;
    var add = parseInt(tempoAdicionalMin || 0, 10);
    if (Number.isNaN(add) || add < 0) add = 0;
    var total = cru + add;
    if (!saidaData || !saidaHora || total <= 0) return null;
    return addMinutes(saidaData, saidaHora, total);
  }
  function buildLoopTrechosFromInputs() {
    if (!isLoopModeActive()) return [];
    var destinosValidos = getDestinos().filter(function(destino) { return destino.estado_id && destino.cidade_id; });
    if (!destinosValidos.length) return [];
    var destino = destinosValidos[0];
    var dataInicio = $('id_bate_volta_data_inicio').value || '';
    var dataFim = $('id_bate_volta_data_fim').value || '';
    var idaHora = $('id_bate_volta_ida_saida_hora').value || '';
    var voltaHora = $('id_bate_volta_volta_saida_hora').value || '';
    var idaMin = parseMinutesValue($('id_bate_volta_ida_tempo_min').value);
    var voltaMin = parseMinutesValue($('id_bate_volta_volta_tempo_min').value);
    var sedeEstadoId = $('id_origem_estado').value || '';
    var sedeCidadeId = $('id_origem_cidade').value || '';
    var sedeNome = selectedText($('id_origem_cidade'));
    if (!dataInicio || !dataFim || !idaHora || !voltaHora || !idaMin || !voltaMin || !sedeEstadoId || !sedeCidadeId || !sedeNome) {
      return [];
    }
    var current = new Date(dataInicio + 'T00:00');
    var end = new Date(dataFim + 'T00:00');
    if (Number.isNaN(current.getTime()) || Number.isNaN(end.getTime()) || current.getTime() > end.getTime()) {
      return [];
    }
    var trechos = [];
    var ordem = 0;
    while (current.getTime() <= end.getTime()) {
      var dataBase = formatDateInputValue(current);
      var idaChegada = addMinutes(dataBase, idaHora, idaMin);
      var voltaChegada = addMinutes(dataBase, voltaHora, voltaMin);
      if (!idaChegada || !voltaChegada) return [];
      trechos.push({
        ordem: ordem++,
        origem_nome: sedeNome,
        destino_nome: destino.cidade_nome || '',
        origem_estado_id: sedeEstadoId,
        origem_cidade_id: sedeCidadeId,
        destino_estado_id: destino.estado_id,
        destino_cidade_id: destino.cidade_id,
        saida_data: dataBase,
        saida_hora: idaHora,
        chegada_data: idaChegada.data,
        chegada_hora: idaChegada.hora,
        distancia_km: '',
        tempo_cru_estimado_min: String(idaMin),
        tempo_adicional_min: '0',
        duracao_estimada_min: String(idaMin),
        rota_fonte: ''
      });
      trechos.push({
        ordem: ordem++,
        origem_nome: destino.cidade_nome || '',
        destino_nome: sedeNome,
        origem_estado_id: destino.estado_id,
        origem_cidade_id: destino.cidade_id,
        destino_estado_id: sedeEstadoId,
        destino_cidade_id: sedeCidadeId,
        saida_data: dataBase,
        saida_hora: voltaHora,
        chegada_data: voltaChegada.data,
        chegada_hora: voltaChegada.hora,
        distancia_km: '',
        tempo_cru_estimado_min: String(voltaMin),
        tempo_adicional_min: '0',
        duracao_estimada_min: String(voltaMin),
        rota_fonte: ''
      });
      current.setDate(current.getDate() + 1);
    }
    return trechos;
  }
  function syncRetornoFromLoopTrechos(trechos, fallbackRetorno) {
    var last = trechos && trechos.length ? trechos[trechos.length - 1] : null;
    if (!last && !fallbackRetorno) return;
    last = last || fallbackRetorno || {};
    $('id_retorno_saida_cidade').value = last.origem_nome || (fallbackRetorno && fallbackRetorno.saida_cidade) || '';
    $('id_retorno_chegada_cidade').value = last.destino_nome || (fallbackRetorno && fallbackRetorno.chegada_cidade) || '';
    $('id_retorno_saida_data').value = last.saida_data || (fallbackRetorno && fallbackRetorno.saida_data) || '';
    $('id_retorno_saida_hora').value = last.saida_hora || (fallbackRetorno && fallbackRetorno.saida_hora) || '';
    $('id_retorno_chegada_data').value = last.chegada_data || (fallbackRetorno && fallbackRetorno.chegada_data) || '';
    $('id_retorno_chegada_hora').value = last.chegada_hora || (fallbackRetorno && fallbackRetorno.chegada_hora) || '';
    $('id_retorno_tempo_cru_estimado_min').value = last.tempo_cru_estimado_min || '';
    $('id_retorno_tempo_adicional_min').value = last.tempo_adicional_min || '0';
    $('id_retorno_duracao_estimada_min').value = last.duracao_estimada_min || '';
  }
  function splitLoopTrechosAndRetorno(trechos) {
    // No bate-volta diario, o ultimo deslocamento gerado representa o retorno final.
    // Ele alimenta o bloco proprio de Retorno e nao deve renderizar como trecho comum.
    var items = Array.isArray(trechos) ? trechos.slice() : [];
    if (!items.length) return { trechos: [], retorno: null };
    return { trechos: items.slice(0, -1), retorno: items[items.length - 1] };
  }
  function computeTrechosSignature(seedState) {
    var destinos = getDestinos().map(function(destino) {
      return [destino.estado_id || '', destino.cidade_id || ''].join(':');
    }).join('|');
    if (isLoopModeActive(seedState)) {
      return [
        'loop',
        $('id_origem_estado').value || '',
        $('id_origem_cidade').value || '',
        destinos,
        $('id_bate_volta_data_inicio').value || '',
        $('id_bate_volta_data_fim').value || '',
        $('id_bate_volta_ida_saida_hora').value || '',
        $('id_bate_volta_ida_tempo_min').value || '',
        $('id_bate_volta_volta_saida_hora').value || '',
        $('id_bate_volta_volta_tempo_min').value || ''
      ].join('::');
    }
    return [
      'normal',
      $('id_origem_estado').value || '',
      $('id_origem_cidade').value || '',
      destinos
    ].join('::');
  }
  function scheduleLoopTrechosRender(options) {
    clearTimeout(loopRenderTimer);
    loopRenderTimer = setTimeout(function() {
      renderTrechos(captureCurrentState(), options || { preferSeed: true, force: true });
      scheduleRealtimeDiarias();
    }, 160);
  }
  function selectedText(el) { return el && el.selectedIndex >= 0 && el.options[el.selectedIndex] ? String(el.options[el.selectedIndex].text || '').trim() : ''; }
  function esc(value) { return String(value || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function makeStableKey(prefix) {
    if (window.crypto && window.crypto.randomUUID) return prefix + '-' + window.crypto.randomUUID();
    return prefix + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  }
  function loadCities(select, estadoId, selectedId) {
    if (!estadoId) { select.innerHTML = '<option value="">---------</option>'; select.disabled = true; refreshSelectPickers(select); return Promise.resolve(); }
    function applyCities(cidades) {
      select.innerHTML = '<option value="">---------</option>';
      cidades.forEach(function(cidade) {
        var opt = document.createElement('option');
        opt.value = cidade.id;
        opt.textContent = cidade.nome;
        if (String(cidade.id) === String(selectedId || '')) opt.selected = true;
        select.appendChild(opt);
      });
      select.disabled = false;
      refreshSelectPickers(select);
    }
    if (citiesCache[String(estadoId)]) {
      applyCities(citiesCache[String(estadoId)]);
      return Promise.resolve();
    }
    select.disabled = true;
    return fetch(cidadesUrl(estadoId)).then(function(r) { return r.json(); }).then(function(data) {
      var cidades = Array.isArray(data) ? data : (data.cidades || []);
      citiesCache[String(estadoId)] = cidades;
      applyCities(cidades);
    }).catch(function() { select.disabled = false; refreshSelectPickers(select); });
  }
  function currentTrechosMap() {
    // Preserva campos manuais usando a chave estavel do trecho; a ordem visual pode mudar.
    var map = {};
    $('trechos-gerados-container').querySelectorAll('.card[data-key]').forEach(function(card) {
      var o = card.dataset.ordem;
      map[card.dataset.key] = { id: card.dataset.trechoId || '', ordem: parseInt(o, 10) || 0, origem_nome: card.dataset.origemNome || '', destino_nome: card.dataset.destinoNome || '',
        origem_estado_id: card.dataset.origemEstadoId || '', origem_cidade_id: card.dataset.origemCidadeId || '',
        destino_estado_id: card.dataset.destinoEstadoId || '', destino_cidade_id: card.dataset.destinoCidadeId || '',
        saida_data: (card.querySelector('[name="trecho_' + o + '_saida_data"]') || {}).value || '',
        saida_hora: (card.querySelector('[name="trecho_' + o + '_saida_hora"]') || {}).value || '',
        chegada_data: (card.querySelector('[name="trecho_' + o + '_chegada_data"]') || {}).value || '',
        chegada_hora: (card.querySelector('[name="trecho_' + o + '_chegada_hora"]') || {}).value || '',
        distancia_km: (card.querySelector('[name="trecho_' + o + '_distancia_km"]') || {}).value || '',
        tempo_cru_estimado_min: (card.querySelector('[name="trecho_' + o + '_tempo_cru_estimado_min"]') || {}).value || '',
        tempo_adicional_min: (card.querySelector('[name="trecho_' + o + '_tempo_adicional_min"]') || {}).value || '0',
        duracao_estimada_min: (card.querySelector('[name="trecho_' + o + '_duracao_estimada_min"]') || {}).value || '',
        rota_fonte: (card.querySelector('[name="trecho_' + o + '_rota_fonte"]') || {}).value || '' };
    }); return map;
  }
  function stateTrechosMap(state) {
    // Compatibilidade: dados antigos podem chegar indexados por id/cidade,
    // mas a chave estavel continua tendo prioridade quando existir.
    var map = {};
    ((state && state.trechos) || []).forEach(function(t) {
      var keys = [
        t.key,
        t.destino_key,
        t.id,
        t.destino_cidade_id,
        String(t.origem_cidade_id || '') + '->' + String(t.destino_cidade_id || '')
      ];
      keys.forEach(function(key) { if (key != null && String(key) !== '') map[String(key)] = t; });
    });
    return map;
  }
  function recalcCard(card, suggestArrival) {
    var o = card.dataset.ordem;
    var cruInput = card.querySelector('[name="trecho_' + o + '_tempo_cru_estimado_min"]');
    var tvInput = card.querySelector('.trecho-tempo-viagem-hhmm');
    var addInput = card.querySelector('[name="trecho_' + o + '_tempo_adicional_min"]');
    var durInput = card.querySelector('[name="trecho_' + o + '_duracao_estimada_min"]');
    if (tvInput) { var norm = normalizeDurationInput(tvInput.value); if (document.activeElement !== tvInput) tvInput.value = norm; var parsed = parseDurationInput(norm); if (cruInput) cruInput.value = parsed != null ? String(parsed) : ''; }
    var cru = parseInt((cruInput || {}).value || 0, 10) || 0;
    var add = parseInt((addInput || {}).value || 0, 10); if (Number.isNaN(add) || add < 0) add = 0; if (addInput) addInput.value = String(add);
    var total = cru + add;
    card.dataset.tempoCruMin = cru ? String(cru) : ''; card.dataset.tempoTotalMin = total ? String(total) : '';
    if (durInput) durInput.value = total ? String(total) : '';
    if (tvInput && document.activeElement !== tvInput) tvInput.value = formatDurationInput(cru);
    var totEl = card.querySelector('.trecho-tempo-total');     if (totEl) totEl.value = total ? hhmm(total) : '';
    var sdEl = card.querySelector('[name="trecho_' + o + '_saida_data"]');
    var shEl = card.querySelector('[name="trecho_' + o + '_saida_hora"]');
    var cdEl = card.querySelector('[name="trecho_' + o + '_chegada_data"]');
    var chEl = card.querySelector('[name="trecho_' + o + '_chegada_hora"]');
    if (suggestArrival && sdEl && shEl && cdEl && chEl) {
      if (!sdEl.value || !shEl.value) {
        cdEl.value = '';
        chEl.value = '';
      } else if (total > 0) {
        var cheg = calcularChegada(sdEl.value, shEl.value, cru, add);
        if (cheg) {
          cdEl.value = cheg.data;
          chEl.value = cheg.hora;
        }
      } else {
        cdEl.value = '';
        chEl.value = '';
      }
    }
  }
  function recalcRetorno(suggestArrival) {
    var cruI = $('id_retorno_tempo_cru_estimado_min'); var tvI = $('id_retorno_tempo_viagem_hhmm');
    var addI = $('id_retorno_tempo_adicional_min'); var durI = $('id_retorno_duracao_estimada_min');
    if (tvI) { var n2 = normalizeDurationInput(tvI.value); if (document.activeElement !== tvI) tvI.value = n2; var p2 = parseDurationInput(n2); if (cruI) cruI.value = p2 != null ? String(p2) : ''; }
    if (cruI && String(cruI.value || '').trim() === '') {
      var sd = $('id_retorno_saida_data').value || ''; var sh = $('id_retorno_saida_hora').value || '';
      var cd = $('id_retorno_chegada_data').value || ''; var ch = $('id_retorno_chegada_hora').value || '';
      if (sd && sh && cd && ch) { var sD = new Date(sd+'T'+sh); var eD = new Date(cd+'T'+ch); if (!Number.isNaN(sD.getTime()) && !Number.isNaN(eD.getTime()) && eD >= sD) { var dc = Math.round((eD - sD) / 60000); if (cruI) cruI.value = dc > 0 ? String(dc) : ''; } }
    }
    var cru2 = parseInt((cruI || {}).value || 0, 10) || 0;
    var add2 = parseInt((addI || {}).value || 0, 10); if (Number.isNaN(add2) || add2 < 0) add2 = 0; if (addI) addI.value = String(add2);
    var tot2 = cru2 + add2; if (durI) durI.value = tot2 ? String(tot2) : '';
    if (tvI && document.activeElement !== tvI) tvI.value = formatDurationInput(cru2);
    if ($('id_retorno_tempo_total')) $('id_retorno_tempo_total').value = tot2 ? hhmm(tot2) : '';
    if (suggestArrival && $('id_retorno_saida_data') && $('id_retorno_saida_hora') && $('id_retorno_chegada_data') && $('id_retorno_chegada_hora')) {
      var rsd = $('id_retorno_saida_data').value;
      var rsh = $('id_retorno_saida_hora').value;
      if (!rsd || !rsh || tot2 <= 0) {
        $('id_retorno_chegada_data').value = '';
        $('id_retorno_chegada_hora').value = '';
      } else {
        var rCheg = calcularChegada(rsd, rsh, cru2, add2);
        if (rCheg) {
          $('id_retorno_chegada_data').value = rCheg.data;
          $('id_retorno_chegada_hora').value = rCheg.hora;
        }
      }
    }
  }
  function canCalculateRoutePreview() {
    var sedeCidade = ($('id_origem_cidade') || {}).value || '';
    var destinos = getDestinos().filter(function(d) { return d && d.cidade_id; });
    return !!(sedeCidade && destinos.length);
  }
  function buildRoutePreviewPayload() {
    var origemCidadeId = parseInt((($('id_origem_cidade') || {}).value || ''), 10);
    if (!origemCidadeId) return null;
    var destinos = getDestinos()
      .filter(function(d) { return d && d.cidade_id; })
      .map(function(d, idx) {
        return {
          uuid: String(d.key || ('tmp-' + (idx + 1))),
          cidade_id: parseInt(d.cidade_id, 10),
        };
      });
    if (!destinos.length) return null;
    var retornoCard = $('retorno-card');
    var retornoCidadeId = retornoCard ? parseInt(retornoCard.dataset.destinoCidadeId || '', 10) : NaN;
    var incluirRetorno = !!(retornoCard && retornoCard.dataset.origemCidadeId && retornoCard.dataset.destinoCidadeId);
    return {
      origem_cidade_id: origemCidadeId,
      destinos: destinos,
      retorno_cidade_id: Number.isNaN(retornoCidadeId) ? null : retornoCidadeId,
      incluir_retorno: incluirRetorno,
      modo: isLoopModeActive() ? 'bate_volta' : 'normal',
    };
  }
  function applyRoutePreviewResult(result, options) {
    var opts = options || {};
    var overwriteAdditional = !!opts.overwriteAdditional;
    var legs = (result && result.legs) || [];
    legs.forEach(function(leg) {
      if (leg.kind === 'retorno') {
        if ($('id_retorno_distancia_km') && leg.distance_km != null) $('id_retorno_distancia_km').value = String(leg.distance_km);
        if ($('id_retorno_tempo_cru_estimado_min') && leg.travel_minutes != null) $('id_retorno_tempo_cru_estimado_min').value = String(leg.travel_minutes);
        if ($('id_retorno_rota_fonte') && leg.provider) $('id_retorno_rota_fonte').value = leg.provider;
        if ($('id_retorno_duracao_estimada_min') && leg.total_minutes != null) $('id_retorno_duracao_estimada_min').value = String(leg.total_minutes);
        var addRet = $('id_retorno_tempo_adicional_min');
        if (addRet && leg.additional_minutes != null && (overwriteAdditional || String(addRet.value || '').trim() === '' || addRet.dataset.manual !== '1')) {
          addRet.value = String(leg.additional_minutes);
          if (overwriteAdditional) addRet.dataset.manual = '0';
        }
        recalcRetorno(true);
        return;
      }
      var card = $('trechos-gerados-container').querySelector('.card[data-key="' + String(leg.uuid || '') + '"]');
      if (!card) {
        card = Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]')).find(function(c) {
          return String(c.dataset.origemCidadeId || '') === String(leg.from_cidade_id || '') &&
            String(c.dataset.destinoCidadeId || '') === String(leg.to_cidade_id || '');
        });
      }
      if (!card) return;
      var ord = card.dataset.ordem;
      var distInp = card.querySelector('[name="trecho_' + ord + '_distancia_km"]');
      var cruInp = card.querySelector('[name="trecho_' + ord + '_tempo_cru_estimado_min"]');
      var fonteInp = card.querySelector('[name="trecho_' + ord + '_rota_fonte"]');
      var durInp = card.querySelector('[name="trecho_' + ord + '_duracao_estimada_min"]');
      var addInp = card.querySelector('[name="trecho_' + ord + '_tempo_adicional_min"]');
      if (distInp && leg.distance_km != null) distInp.value = String(leg.distance_km);
      if (cruInp && leg.travel_minutes != null) cruInp.value = String(leg.travel_minutes);
      if (fonteInp && leg.provider) fonteInp.value = leg.provider;
      if (durInp && leg.total_minutes != null) durInp.value = String(leg.total_minutes);
      if (addInp && leg.additional_minutes != null && (overwriteAdditional || String(addInp.value || '').trim() === '' || addInp.dataset.manual !== '1')) {
        addInp.value = String(leg.additional_minutes);
        if (overwriteAdditional) addInp.dataset.manual = '0';
      }
      recalcCard(card, true);
    });
    chainSuggestedDepartures();
    chainRetornoSaidaFromLastTrecho();
    updateResumo();
    scheduleRealtimeDiarias();
    scheduleAutosave();
    notifyRouteStateChanged();
  }
  function chainSuggestedDepartures() {
    if (isLoopModeActive()) return;
    var cards = Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]'));
    for (var i = 1; i < cards.length; i++) {
      var prev = cards[i - 1];
      var cur = cards[i];
      var po = prev.dataset.ordem;
      var co = cur.dataset.ordem;
      var pcd = prev.querySelector('[name="trecho_' + po + '_chegada_data"]');
      var pch = prev.querySelector('[name="trecho_' + po + '_chegada_hora"]');
      var csd = cur.querySelector('[name="trecho_' + co + '_saida_data"]');
      var csh = cur.querySelector('[name="trecho_' + co + '_saida_hora"]');
      if (!pcd || !pch || !csd || !csh) continue;
      if (!(pcd.value && pch.value)) continue;
      if (csd.value || csh.value) continue;
      csd.value = pcd.value;
      csh.value = pch.value;
      recalcCard(cur, true);
    }
  }
  /** Se o bloco Retorno existe e saída ainda vazia, usa chegada do último trecho IDA (fluxo multi-destino). */
  function chainRetornoSaidaFromLastTrecho() {
    if (isLoopModeActive()) return;
    var cards = Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]'));
    if (!cards.length) return;
    var last = cards[cards.length - 1];
    var o = last.dataset.ordem;
    var pcd = last.querySelector('[name="trecho_' + o + '_chegada_data"]');
    var pch = last.querySelector('[name="trecho_' + o + '_chegada_hora"]');
    var rsd = $('id_retorno_saida_data');
    var rsh = $('id_retorno_saida_hora');
    if (!pcd || !pch || !rsd || !rsh) return;
    if (!(pcd.value && pch.value)) return;
    if (rsd.value || rsh.value) return;
    rsd.value = pcd.value;
    rsh.value = pch.value;
    recalcRetorno(true);
  }
  function applyEstimarPayloadToRetorno(data) {
    if ($('id_retorno_distancia_km') && data.distancia_km != null) $('id_retorno_distancia_km').value = String(data.distancia_km);
    if ($('id_retorno_tempo_cru_estimado_min') && data.tempo_cru_estimado_min != null) {
      $('id_retorno_tempo_cru_estimado_min').value = String(data.tempo_cru_estimado_min);
    }
    if ($('id_retorno_duracao_estimada_min') && data.duracao_estimada_min != null) {
      $('id_retorno_duracao_estimada_min').value = String(data.duracao_estimada_min);
    }
    if ($('id_retorno_rota_fonte') && data.rota_fonte) $('id_retorno_rota_fonte').value = data.rota_fonte;
    var addI = $('id_retorno_tempo_adicional_min');
    if (addI && data.tempo_adicional_sugerido_min != null && String(addI.value || '').trim() === '') {
      addI.value = String(data.tempo_adicional_sugerido_min);
    }
    recalcRetorno(true);
  }
  function applyEstimarPayloadToTrechoCard(card, data) {
    var ord = card.dataset.ordem;
    var distInp = card.querySelector('[name="trecho_' + ord + '_distancia_km"]');
    if (distInp && data.distancia_km != null) distInp.value = String(data.distancia_km);
    var cruInp = card.querySelector('[name="trecho_' + ord + '_tempo_cru_estimado_min"]');
    if (cruInp && data.tempo_cru_estimado_min != null) cruInp.value = String(data.tempo_cru_estimado_min);
    var fonteInp = card.querySelector('[name="trecho_' + ord + '_rota_fonte"]');
    if (fonteInp && data.rota_fonte) fonteInp.value = data.rota_fonte;
    var durInp = card.querySelector('[name="trecho_' + ord + '_duracao_estimada_min"]');
    if (durInp && data.duracao_estimada_min != null) durInp.value = String(data.duracao_estimada_min);
    var addInp = card.querySelector('[name="trecho_' + ord + '_tempo_adicional_min"]');
    if (addInp && data.tempo_adicional_sugerido_min != null && String(addInp.value || '').trim() === '') {
      addInp.value = String(data.tempo_adicional_sugerido_min);
    }
    recalcCard(card, true);
  }
  function scheduleAutoEstimarTrechos() {
    clearTimeout(autoEstimarTimer);
    autoEstimarTimer = setTimeout(runAutoEstimarTrechos, 450);
  }
  function runAutoEstimarTrechos() {
    if (!urlTrechosEstimar || applyingState || isLoopModeActive()) return;
    var cards = Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]'));
    var pending = cards.filter(function(card) {
      var distInp = card.querySelector('[name^="trecho_"][name$="_distancia_km"]');
      var cruInp = card.querySelector('[name^="trecho_"][name$="_tempo_cru_estimado_min"]');
      if (distInp && String(distInp.value || '').trim() !== '') return false;
      if (cruInp && String(cruInp.value || '').trim() !== '') return false;
      var ocid = card.dataset.origemCidadeId;
      var dcid = card.dataset.destinoCidadeId;
      return !!(ocid && dcid);
    });
    pending.reduce(function(seq, card) {
      return seq.then(function() {
        var ocid = card.dataset.origemCidadeId;
        var dcid = card.dataset.destinoCidadeId;
        return fetch(urlTrechosEstimar, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
            'X-Requested-With': 'XMLHttpRequest'
          },
          credentials: 'same-origin',
          body: JSON.stringify({ origem_cidade_id: parseInt(ocid, 10), destino_cidade_id: parseInt(dcid, 10) })
        }).then(readJsonResponse).then(function(result) {
          var data = result && result.data;
          if (!data || !data.ok) return;
          applyEstimarPayloadToTrechoCard(card, data);
          chainSuggestedDepartures();
          chainRetornoSaidaFromLastTrecho();
          updateResumo();
          scheduleRealtimeDiarias();
          scheduleAutosave();
        });
      });
    }, Promise.resolve());
  }
  function buildTrechoCard(trecho, value) {
    var o = trecho.ordem; var dist = value.distancia_km || ''; var cru = value.tempo_cru_estimado_min || '';
    var add = (value.tempo_adicional_min != null && value.tempo_adicional_min !== '') ? value.tempo_adicional_min : 0;
    var fonte = value.rota_fonte || '';
    var trechoId = value.id || trecho.id || '';
    return '<div class="card roteiro-editor__trecho-card oficio-step3-trecho-card" data-key="'+esc(trecho.key)+'" data-trecho-id="'+esc(trechoId)+'" data-ordem="'+o+'" data-origem-nome="'+esc(trecho.origem_nome)+'" data-destino-nome="'+esc(trecho.destino_nome)+'" data-origem-estado-id="'+esc(trecho.origem_estado_id)+'" data-origem-cidade-id="'+esc(trecho.origem_cidade_id)+'" data-destino-estado-id="'+esc(trecho.destino_estado_id)+'" data-destino-cidade-id="'+esc(trecho.destino_cidade_id)+'">' +
      '<div class="card-header py-3"><span class="fw-semibold">Trecho '+(o+1)+' â€” '+esc(trecho.origem_nome)+' â†’ '+esc(trecho.destino_nome)+'</span></div>' +
      '<div class="card-body">' +
        '<input type="hidden" name="trecho_'+o+'_origem_nome" value="'+esc(trecho.origem_nome)+'">' +
        '<input type="hidden" name="trecho_'+o+'_id" value="'+esc(trechoId)+'">' +
        '<input type="hidden" name="trecho_'+o+'_destino_nome" value="'+esc(trecho.destino_nome)+'">' +
        '<input type="hidden" name="trecho_'+o+'_origem_estado_id" value="'+esc(trecho.origem_estado_id)+'">' +
        '<input type="hidden" name="trecho_'+o+'_origem_cidade_id" value="'+esc(trecho.origem_cidade_id)+'">' +
        '<input type="hidden" name="trecho_'+o+'_destino_estado_id" value="'+esc(trecho.destino_estado_id)+'">' +
        '<input type="hidden" name="trecho_'+o+'_destino_cidade_id" value="'+esc(trecho.destino_cidade_id)+'">' +
        '<div class="row g-3">' +
          '<div class="col-md-6"><div class="roteiro-editor__subpanel h-100"><div class="roteiro-editor__subpanel-title">Saída</div><div class="row g-2">' +
            '<div class="col-12"><label class="roteiro-editor__field-label">Cidade</label><input type="text" class="form-control" value="'+esc(trecho.origem_nome)+'" readonly></div>' +
            '<div class="col-md-6"><label class="roteiro-editor__field-label">Data</label><input type="date" class="form-control" name="trecho_'+o+'_saida_data" value="'+esc(value.saida_data||'')+'" ></div>' +
            '<div class="col-md-6"><label class="roteiro-editor__field-label">Hora</label><input type="time" class="form-control" name="trecho_'+o+'_saida_hora" value="'+esc(value.saida_hora||'')+'" ></div>' +
          '</div></div></div>' +
          '<div class="col-md-6"><div class="roteiro-editor__subpanel h-100"><div class="roteiro-editor__subpanel-title">Chegada</div><div class="row g-2">' +
            '<div class="col-12"><label class="roteiro-editor__field-label">Cidade</label><input type="text" class="form-control" value="'+esc(trecho.destino_nome)+'" readonly></div>' +
            '<div class="col-md-6"><label class="roteiro-editor__field-label">Data</label><input type="date" class="form-control" name="trecho_'+o+'_chegada_data" value="'+esc(value.chegada_data||'')+'" ></div>' +
            '<div class="col-md-6"><label class="roteiro-editor__field-label">Hora</label><input type="time" class="form-control" name="trecho_'+o+'_chegada_hora" value="'+esc(value.chegada_hora||'')+'" ></div>' +
          '</div></div></div>' +
          '<div class="col-12"><div class="roteiro-editor__grid oficio-step3-time-calc-grid align-items-end">' +
            '<div class="field-span-4"><label class="roteiro-editor__field-label">Tempo de viagem</label><input type="text" class="form-control trecho-tempo-viagem-hhmm" value="'+esc(formatDurationInput(cru))+'" placeholder="00:00" inputmode="numeric" maxlength="5" autocomplete="off"><input type="hidden" name="trecho_'+o+'_tempo_cru_estimado_min" value="'+esc(cru)+'" ></div>' +
            '<div class="field-span-4"><label class="roteiro-editor__field-label">Tempo adicional</label><input type="number" min="0" step="15" class="form-control" name="trecho_'+o+'_tempo_adicional_min" value="'+esc(add)+'" ></div>' +
            '<div class="field-span-4"><label class="roteiro-editor__field-label">Tempo total</label><input type="text" class="form-control trecho-tempo-total" value="" readonly></div>' +
          '</div></div>' +
          '<div class="col-12"><div class="roteiro-editor__helper text-danger d-none trecho-erro"></div></div>' +
        '</div>' +
        '<input type="hidden" name="trecho_'+o+'_distancia_km" value="'+esc(dist)+'">' +
        '<input type="hidden" name="trecho_'+o+'_duracao_estimada_min" value="'+esc(value.duracao_estimada_min||'')+'">' +
        '<input type="hidden" name="trecho_'+o+'_rota_fonte" value="'+esc(fonte)+'">' +
        '<div class="mt-3">' +
          '<button type="button" class="btn btn-outline-primary btn-sm btn-calcular-km roteiro-editor__btn-pill">Estimar km/tempo</button>' +
        '</div>' +
      '</div></div>';
  }
  function getDestinoRows() { return Array.from($('destinos-container').querySelectorAll('.destino-row')); }
  function reindexDestinoRows() { getDestinoRows().forEach(function(row, idx) { row.dataset.index = String(idx); var es = row.querySelector('.destino-estado'); var ci = row.querySelector('.destino-cidade'); if (es) es.name = 'destino_estado_'+idx; if (ci) ci.name = 'destino_cidade_'+idx; }); }
  function refreshDestinoButtons() { var rows = getDestinoRows(); rows.forEach(function(row) { var btn = row.querySelector('.btn-remover-destino'); if (btn) btn.disabled = rows.length <= 1; }); }
  function estadoOptionsMarkup(selectedId) { var se = $('id_origem_estado'); return (se ? Array.from(se.options) : []).map(function(opt) { var v = String(opt.value||''); if (!v) return '<option value="">---------</option>'; var sel = String(selectedId||'')=== v?' selected':''; return '<option value="'+esc(v)+'"'+sel+'>'+esc(String(opt.textContent||'').trim())+'</option>'; }).join(''); }
  function bindDestinoDragAndDrop(row) {
    row.addEventListener('dragstart', function(e) { row.classList.add('is-dragging'); e.dataTransfer.effectAllowed='move'; e.dataTransfer.setData('text/plain', row.dataset.index||'0'); });
    row.addEventListener('dragend', function() { row.classList.remove('is-dragging'); getDestinoRows().forEach(function(r) { r.classList.remove('is-drop-target'); }); });
    row.addEventListener('dragover', function(e) { e.preventDefault(); if (!row.classList.contains('is-dragging')) row.classList.add('is-drop-target'); });
    row.addEventListener('dragleave', function() { row.classList.remove('is-drop-target'); });
    row.addEventListener('drop', function(e) {
      e.preventDefault(); var fi = parseInt(e.dataTransfer.getData('text/plain')||'-1',10); var rows = getDestinoRows(); var dr = rows[fi];
      if (!dr || dr === row) { row.classList.remove('is-drop-target'); return; }
      var c = $('destinos-container'); var all = getDestinoRows(); var ti = all.indexOf(row); var di = all.indexOf(dr);
      if (di < ti) c.insertBefore(dr, row.nextSibling); else c.insertBefore(dr, row);
      row.classList.remove('is-drop-target'); reindexDestinoRows(); renderTrechos(captureCurrentState(), { force: true }); scheduleRealtimeDiarias(); scheduleAutosave();
      if (window.RoteirosMap && typeof window.RoteirosMap.onDestinosReordered === 'function') {
        window.RoteirosMap.onDestinosReordered();
      }
    });
  }
  function addDestinoRow(destino) {
    var idx = getDestinoRows().length; var row = document.createElement('div');
    row.className = 'destino-row roteiro-editor__destination-card'; row.draggable = true; row.dataset.index = String(idx);
    // A identidade do destino precisa sobreviver a reorder/remocao para nao zerar trechos preenchidos.
    row.dataset.key = (destino && (destino.key || destino.destino_key || destino.id)) ? String(destino.key || destino.destino_key || destino.id) : makeStableKey('destino');
    var selE = destino && destino.estado_id ? destino.estado_id : (destinoEstadoDefaultId || '');
    row.innerHTML = '<div class="roteiro-editor__drag-col"><button type="button" class="roteiro-editor__drag-handle destino-drag-handle" aria-label="Arrastar para reordenar">&#8942;</button></div>' +
      '<div class="roteiro-editor__destination-fields"><div><label class="roteiro-editor__field-label"></label><select name="destino_estado_'+idx+'" class="destino-estado form-select" data-oficio-picker-search="always" data-oficio-picker-search-placeholder="Filtrar UF...">'+estadoOptionsMarkup(selE)+'</select></div>' +
      '<div><label class="roteiro-editor__field-label"></label><select name="destino_cidade_'+idx+'" class="destino-cidade form-select" data-oficio-picker-search="always" data-oficio-picker-search-placeholder="Filtrar cidade..."><option value="">Município</option></select></div></div>' +
      '<div class="roteiro-editor__remove-col"><button type="button" class="btn-remover-destino roteiro-editor__icon-btn" title="Remover destino" aria-label="Remover destino">&times;</button></div>';
    $('destinos-container').appendChild(row); refreshSelectPickers(row);
    var cs = row.querySelector('.destino-cidade');
    var p = selE ? loadCities(cs, selE, (destino && destino.cidade_id) ? destino.cidade_id : null) : Promise.resolve();
    bindDestinoDragAndDrop(row); reindexDestinoRows(); refreshDestinoButtons(); return p;
  }
  function renderDestinos(destinos) {
    $('destinos-container').innerHTML = '';
    var items = Array.isArray(destinos) && destinos.length ? destinos : [{ estado_id: destinoEstadoDefaultId || null, cidade_id: null }];
    var p = Promise.resolve(); items.forEach(function(d) { p = p.then(function() { return addDestinoRow(d || { estado_id: null, cidade_id: null }); }); }); return p;
  }
  function getDestinos() { return getDestinoRows().map(function(row) { var es = row.querySelector('.destino-estado'); var ci = row.querySelector('.destino-cidade'); return { key: row.dataset.key || '', estado_id: es ? es.value||null : null, cidade_id: ci ? ci.value||null : null, cidade_nome: selectedText(ci) }; }); }
  function updateRetornoCities() {
    var cards = Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]'));
    var sede = selectedText($('id_origem_cidade'));
    var sedeId = ($('id_origem_cidade') || {}).value || '';
    var ultima = cards.length ? (cards[cards.length-1].dataset.destinoNome||'') : '';
    var lastDestId = cards.length ? (cards[cards.length-1].dataset.destinoCidadeId||'') : '';
    if ($('id_retorno_saida_cidade')) $('id_retorno_saida_cidade').value = ultima;
    if ($('id_retorno_chegada_cidade')) $('id_retorno_chegada_cidade').value = sede;
    var rc = $('retorno-card');
    if (rc) {
      rc.dataset.origemCidadeId = lastDestId || '';
      rc.dataset.destinoCidadeId = sedeId || '';
    }
  }
  function renderTrechos(seedState, options) {
    // Re-renderizar trechos nao pode sobrescrever data/hora/tempo manual com vazio/default.
    // Por isso os valores atuais da tela sao combinados com o seed antes de montar os cards.
    var opts = options || {};
    var preferSeed = !!opts.preferSeed;
    var force = !!opts.force;
    toggleBateVoltaPanel();
    syncBateVoltaDurationInputs();
    var signature = computeTrechosSignature(seedState);
    if (!force && !preferSeed && signature === lastTrechosSignature) {
      updateResumo();
      return;
    }

    if (shouldUseExactTrechos(seedState)) {
      var explicitTrechos = isLoopModeActive(seedState) ? buildLoopTrechosFromInputs() : [];
      var loopRetorno = null;
      if (isLoopModeActive(seedState) && explicitTrechos.length) {
        var splitLoop = splitLoopTrechosAndRetorno(explicitTrechos);
        explicitTrechos = splitLoop.trechos;
        loopRetorno = splitLoop.retorno;
      }
      if (!explicitTrechos.length) {
        explicitTrechos = ((seedState && seedState.trechos) || []).map(function(trecho, idx) {
          var copy = Object.assign({}, trecho);
          copy.ordem = idx;
          return copy;
        });
      }
      if (!explicitTrechos.length) {
        $('trechos-gerados-container').innerHTML = TRECHOS_EMPTY_HTML;
        updateRetornoCities();
        recalcRetorno(false);
        updateResumo();
        lastTrechosSignature = signature;
        return;
      }
      $('trechos-gerados-container').innerHTML = explicitTrechos.map(function(trecho, idx) {
        return buildTrechoCard(
          {
            ordem: idx,
            key: String(trecho.key || trecho.destino_key || trecho.id || ('explicit-' + idx + '-' + String(trecho.origem_cidade_id || '') + '->' + String(trecho.destino_cidade_id || ''))),
            id: trecho.id || '',
            origem_estado_id: trecho.origem_estado_id,
            origem_cidade_id: trecho.origem_cidade_id,
            destino_estado_id: trecho.destino_estado_id,
            destino_cidade_id: trecho.destino_cidade_id,
            origem_nome: trecho.origem_nome || '',
            destino_nome: trecho.destino_nome || ''
          },
          Object.assign({}, trecho, { ordem: idx })
        );
      }).join('');
      $('trechos-gerados-container').querySelectorAll('.card[data-key]').forEach(function(card) { recalcCard(card, false); });
      chainSuggestedDepartures();
      if (isLoopModeActive(seedState)) {
        syncRetornoFromLoopTrechos(loopRetorno ? [loopRetorno] : [], seedState && seedState.retorno);
      } else {
        updateRetornoCities();
      }
      chainRetornoSaidaFromLastTrecho();
      recalcRetorno(false);
      updateResumo();
      scheduleAutoEstimarTrechos();
      lastTrechosSignature = signature;
      notifyRouteStateChanged();
      return;
    }

    var sedeEid = $('id_origem_estado').value || null;
    var sedeCid = $('id_origem_cidade').value || null;
    var sedeNome = selectedText($('id_origem_cidade'));
    var destinos = getDestinos().filter(function(d) { return d.estado_id && d.cidade_id; });
    if (!sedeEid || !sedeCid || !destinos.length) {
      $('trechos-gerados-container').innerHTML = TRECHOS_EMPTY_HTML;
      updateRetornoCities();
      recalcRetorno(false);
      updateResumo();
      lastTrechosSignature = signature;
      return;
    }
    var cm = currentTrechosMap();
    var sm = stateTrechosMap(seedState || {});
    var trechos = [];
    var oeId = sedeEid;
    var ocId = sedeCid;
    var oNome = sedeNome;
    destinos.forEach(function(d, idx) {
      var key = String(d.key || d.cidade_id || (String(ocId || '') + '->' + String(d.cidade_id || '')));
      trechos.push({
        ordem: idx,
        key: key,
        origem_estado_id: oeId,
        origem_cidade_id: ocId,
        destino_estado_id: d.estado_id,
        destino_cidade_id: d.cidade_id,
        origem_nome: oNome,
        destino_nome: d.cidade_nome || ''
      });
      oeId = d.estado_id;
      ocId = d.cidade_id;
      oNome = d.cidade_nome || '';
    });
    $('trechos-gerados-container').innerHTML = trechos.map(function(t) {
      var cv = cm[t.key] || {};
      var sv = sm[t.key] || sm[String(t.destino_cidade_id || '')] || {};
      return buildTrechoCard(t, preferSeed ? Object.assign({}, cv, sv) : Object.assign({}, sv, cv));
    }).join('');
    $('trechos-gerados-container').querySelectorAll('.card[data-key]').forEach(function(c) { recalcCard(c, false); });
    chainSuggestedDepartures();
    updateRetornoCities();
    chainRetornoSaidaFromLastTrecho();
    recalcRetorno(false);
    updateResumo();
    scheduleAutoEstimarTrechos();
    lastTrechosSignature = signature;
    notifyRouteStateChanged();
  }
  function updateResumo() {
    var cards = Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]'));
    var totMin = 0; var totKm = 0;
    cards.forEach(function(c) { totMin += parseInt(c.dataset.tempoTotalMin||0,10)||0; var de = c.querySelector('[name$="_distancia_km"]'); if (de && de.value) { var v = parseFloat(de.value); if (!Number.isNaN(v)) totKm += v; } });
    form.dataset.resumoTrechos = String(cards.length);
    form.dataset.resumoKm = cards.length ? totKm.toFixed(2).replace('.',',')+' km' : '-';
    form.dataset.resumoTempo = cards.length ? hhmm(totMin) : '-';
  }
  function getSelectedRouteInput() {
    return form.querySelector('[data-route-selected-input]');
  }
  function getSelectedRouteId() {
    var input = getSelectedRouteInput();
    return input ? String(input.value || '') : '';
  }
  function setSelectedRouteId(value) {
    var input = getSelectedRouteInput();
    if (!input) return;
    input.value = value ? String(value) : '';
  }
  function captureCurrentState() {
    return {
      roteiro_modo: $('id_roteiro_modo_evento').checked ? 'EVENTO_EXISTENTE' : 'ROTEIRO_PROPRIO',
      roteiro_id: $('id_roteiro_modo_evento').checked ? (getSelectedRouteId() || null) : null,
      sede_estado_id: $('id_origem_estado').value||null, sede_cidade_id: $('id_origem_cidade').value||null,
      destinos_atuais: getDestinos().map(function(d) { return { key: d.key, estado_id: d.estado_id, cidade_id: d.cidade_id }; }),
      bate_volta_diario: {
        ativo: !!($('id_bate_volta_diario_ativo') && $('id_bate_volta_diario_ativo').checked),
        data_inicio: ($('id_bate_volta_data_inicio') || {}).value || '',
        data_fim: ($('id_bate_volta_data_fim') || {}).value || '',
        ida_saida_hora: ($('id_bate_volta_ida_saida_hora') || {}).value || '',
        ida_tempo_min: ($('id_bate_volta_ida_tempo_min') || {}).value || '',
        volta_saida_hora: ($('id_bate_volta_volta_saida_hora') || {}).value || '',
        volta_tempo_min: ($('id_bate_volta_volta_tempo_min') || {}).value || ''
      },
      trechos: Array.from($('trechos-gerados-container').querySelectorAll('.card[data-key]')).map(function(c) {
        var o = parseInt(c.dataset.ordem||'0',10)||0;
        return { id: c.dataset.trechoId||'', key: c.dataset.key||'', ordem: o, origem_nome: c.dataset.origemNome||'', destino_nome: c.dataset.destinoNome||'',
          origem_estado_id: c.dataset.origemEstadoId||null, origem_cidade_id: c.dataset.origemCidadeId||null,
          destino_estado_id: c.dataset.destinoEstadoId||null, destino_cidade_id: c.dataset.destinoCidadeId||null,
          saida_data: (c.querySelector('[name="trecho_'+o+'_saida_data"]')||{}).value||'',
          saida_hora: (c.querySelector('[name="trecho_'+o+'_saida_hora"]')||{}).value||'',
          chegada_data: (c.querySelector('[name="trecho_'+o+'_chegada_data"]')||{}).value||'',
          chegada_hora: (c.querySelector('[name="trecho_'+o+'_chegada_hora"]')||{}).value||'',
          distancia_km: (c.querySelector('[name="trecho_'+o+'_distancia_km"]')||{}).value||'',
          tempo_cru_estimado_min: (c.querySelector('[name="trecho_'+o+'_tempo_cru_estimado_min"]')||{}).value||'',
          tempo_adicional_min: (c.querySelector('[name="trecho_'+o+'_tempo_adicional_min"]')||{}).value||'0',
          duracao_estimada_min: (c.querySelector('[name="trecho_'+o+'_duracao_estimada_min"]')||{}).value||'',
          rota_fonte: (c.querySelector('[name="trecho_'+o+'_rota_fonte"]')||{}).value||'' };
      }),
      retorno: { saida_cidade: $('id_retorno_saida_cidade').value||'', chegada_cidade: $('id_retorno_chegada_cidade').value||'',
        saida_data: $('id_retorno_saida_data').value||'', saida_hora: $('id_retorno_saida_hora').value||'',
        chegada_data: $('id_retorno_chegada_data').value||'', chegada_hora: $('id_retorno_chegada_hora').value||'',
        distancia_km: $('id_retorno_distancia_km').value||'', tempo_cru_estimado_min: $('id_retorno_tempo_cru_estimado_min').value||'',
        tempo_adicional_min: $('id_retorno_tempo_adicional_min').value||'0', duracao_estimada_min: $('id_retorno_duracao_estimada_min').value||'', rota_fonte: $('id_retorno_rota_fonte').value||'' }
    };
  }
  function setDiariasStatus(state, text) {
    var status = $('diarias-status'); if (!status) return;
    status.dataset.state = state || 'pending';
    status.textContent = text || 'Aguardando dados para cálculo.';
  }
  function applyDiarias(result) {
    var totais = result && result.totais ? result.totais : null;
    var errEl = $('diarias-error');
    if (errEl) {
      errEl.textContent = '';
      errEl.classList.add('d-none');
    }
    $('diarias-tipo').textContent = result && result.tipo_destino ? result.tipo_destino : '-';
    $('diarias-qtd').textContent = totais && totais.total_diarias ? totais.total_diarias : '-';
    $('diarias-valor').textContent = totais && totais.total_valor ? totais.total_valor : '-';
    $('diarias-extenso').textContent = totais && totais.valor_extenso ? totais.valor_extenso : 'Não informado';
    $('id_tipo_destino').value = result && result.tipo_destino ? result.tipo_destino : '';
    $('id_quantidade_diarias').value = totais && totais.total_diarias ? totais.total_diarias : '';
    $('id_valor_diarias').value = totais && totais.total_valor ? totais.total_valor : '';
    $('id_valor_diarias_extenso').value = totais && totais.valor_extenso ? totais.valor_extenso : '';
  }
  function clearDiariasAsPending() {
    var errEl = $('diarias-error');
    if (errEl) {
      errEl.textContent = '';
      errEl.classList.add('d-none');
    }
    applyDiarias(null);
    setDiariasStatus('pending', 'Aguardando dados para cálculo.');
  }
  function markDiariasStale() {
    setDiariasStatus('stale', 'Cálculo desatualizado.');
  }
  function hasCompleteDataForDiarias(state) {
    if (!state || !state.sede_estado_id || !state.sede_cidade_id) return false;
    if (!Array.isArray(state.trechos) || !state.trechos.length) return false;
    for (var i = 0; i < state.trechos.length; i++) {
      var t = state.trechos[i] || {};
      if (!t.origem_estado_id || !t.origem_cidade_id || !t.destino_estado_id || !t.destino_cidade_id) return false;
      if (!t.saida_data || !t.saida_hora || !t.chegada_data || !t.chegada_hora) return false;
    }
    var ret = state.retorno || {};
    return !!(ret.saida_data && ret.saida_hora && ret.chegada_data && ret.chegada_hora);
  }
  function scheduleRealtimeDiarias() {
    markDiariasStale();
    var state = captureCurrentState();
    if (!hasCompleteDataForDiarias(state)) {
      clearTimeout(diariasTimer);
      clearDiariasAsPending();
      return;
    }
    clearTimeout(diariasTimer);
    diariasTimer = setTimeout(function() { calculateDiarias(); }, 700);
  }
  function collectDiariasFormData() {
    var fd = new FormData(form);
    fd.set('sede_estado', $('id_origem_estado').value || '');
    fd.set('sede_cidade', $('id_origem_cidade').value || '');
    return fd;
  }
  function calculateDiarias() {
    if (!apiDiarias) return Promise.resolve();
    if (diariasInFlight) { diariasNeedsRerun = true; return Promise.resolve(); }
    diariasInFlight = true;
    var errPre = $('diarias-error');
    if (errPre) {
      errPre.textContent = '';
      errPre.classList.add('d-none');
    }
    setDiariasStatus('pending', 'Calculando diárias...');
    return fetch(apiDiarias, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrf,
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'same-origin',
      body: collectDiariasFormData()
    }).then(readJsonResponse)
      .then(function(result) {
        if (!result.ok || !result.data || !result.data.ok) {
          var errs = (result.data && result.data.errors) || [];
          throw new Error(errs.join('\n') || ((result.data && result.data.error) || 'Erro ao calcular as diárias.'));
        }
        applyDiarias(result.data);
        setDiariasStatus('updated', 'Cálculo atualizado (1 servidor).');
      }).catch(function(err) {
        var msg = String((err && err.message) ? err.message : '').trim();
        if (!msg || msg === '.') {
          msg = 'Erro ao calcular as diárias.';
        }
        var errBox = $('diarias-error');
        if (errBox) {
          errBox.textContent = msg;
          errBox.classList.remove('d-none');
        }
        setDiariasStatus('error', 'Falha no cálculo.');
      }).finally(function() {
        diariasInFlight = false;
        if (diariasNeedsRerun) {
          diariasNeedsRerun = false;
          scheduleRealtimeDiarias();
        }
      });
  }
  function applyState(state) {
    var cur = Object.assign({}, state || {}); applyingState = true;
    var curRouteId = cur.roteiro_id || '';
    if (cur.roteiro_modo === 'EVENTO_EXISTENTE' && curRouteId) { $('id_roteiro_modo_evento').checked=true; $('id_roteiro_modo_proprio').checked=false; setSelectedRouteId(curRouteId); }
    else { $('id_roteiro_modo_evento').checked=false; $('id_roteiro_modo_proprio').checked=true; setSelectedRouteId(''); }
    setModeUi();
    $('id_origem_estado').value = cur.sede_estado_id || '';
    return loadCities($('id_origem_cidade'), cur.sede_estado_id, cur.sede_cidade_id)
      .then(function() { refreshSelectPickers($('id_origem_estado')); return renderDestinos(cur.destinos_atuais); })
      .then(function() {
        var loop = cur.bate_volta_diario || {};
        if ($('id_bate_volta_diario_ativo')) $('id_bate_volta_diario_ativo').checked = !!loop.ativo;
        if ($('id_bate_volta_data_inicio')) $('id_bate_volta_data_inicio').value = loop.data_inicio || '';
        if ($('id_bate_volta_data_fim')) $('id_bate_volta_data_fim').value = loop.data_fim || '';
        if ($('id_bate_volta_ida_saida_hora')) $('id_bate_volta_ida_saida_hora').value = loop.ida_saida_hora || '';
        if ($('id_bate_volta_ida_tempo_min')) $('id_bate_volta_ida_tempo_min').value = loop.ida_tempo_min != null ? loop.ida_tempo_min : '';
        if ($('id_bate_volta_volta_saida_hora')) $('id_bate_volta_volta_saida_hora').value = loop.volta_saida_hora || '';
        if ($('id_bate_volta_volta_tempo_min')) $('id_bate_volta_volta_tempo_min').value = loop.volta_tempo_min != null ? loop.volta_tempo_min : '';
        syncBateVoltaDurationInputs();
        toggleBateVoltaPanel();
        renderTrechos(cur, { preferSeed: true });
        var ret = cur.retorno || {};
        $('id_retorno_saida_data').value = ret.saida_data||''; $('id_retorno_saida_hora').value = ret.saida_hora||'';
        $('id_retorno_chegada_data').value = ret.chegada_data||''; $('id_retorno_chegada_hora').value = ret.chegada_hora||'';
        $('id_retorno_distancia_km').value = ret.distancia_km||'';
        $('id_retorno_tempo_cru_estimado_min').value = ret.tempo_cru_estimado_min != null ? ret.tempo_cru_estimado_min : '';
        $('id_retorno_tempo_adicional_min').value = ret.tempo_adicional_min != null ? ret.tempo_adicional_min : 0;
        $('id_retorno_duracao_estimada_min').value = ret.duracao_estimada_min||''; $('id_retorno_rota_fonte').value = ret.rota_fonte||'';
        if ($('id_retorno_saida_cidade') && !$('id_retorno_saida_cidade').value && ret.saida_cidade) $('id_retorno_saida_cidade').value = ret.saida_cidade;
        if ($('id_retorno_chegada_cidade') && !$('id_retorno_chegada_cidade').value && ret.chegada_cidade) $('id_retorno_chegada_cidade').value = ret.chegada_cidade;
        recalcRetorno(false); updateResumo(); applyingState = false; scheduleRealtimeDiarias();
      });
  }
  function dtBr(d,h) { if (!d&&!h) return ''; var p=d?d.split('-'):null; return (p?p[2]+'/'+p[1]+'/'+p[0]:'')+(h?' '+h:''); }
  function routePeriodSummary(route) {
    var trechos=(route&&route.state&&route.state.trechos)||[]; var ret=(route&&route.state&&route.state.retorno)||{};
    if (!trechos.length) return 'Sem período informado';
    var ini=dtBr(trechos[0].saida_data||'',trechos[0].saida_hora||''); var ult=trechos[trechos.length-1]||{};
    var fim=dtBr(ret.chegada_data||ult.chegada_data||'',ret.chegada_hora||ult.chegada_hora||'');
    return ini&&fim ? ini+' até '+fim : (ini||fim||'Sem período informado');
  }
  function routeDestinationsSummary(route) {
    var trechos=(route&&route.state&&route.state.trechos)||[]; var names=[];
    trechos.forEach(function(t) { var n=String(t.destino_nome||'').trim(); if (n&&names.indexOf(n)===-1) names.push(n); });
    if (!names.length) return 'Sem destinos';
    return names.slice(0,3).join(' â€¢ ')+(names.length>3?' +'+(names.length-3):'');
  }
  function normalizeRouteSearch(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }
  function routeSearchText(route) {
    return [
      route && route.label,
      route && route.resumo,
      route && route.tipo_label,
      routeDestinationsSummary(route),
      routePeriodSummary(route)
    ].join(' ');
  }
  function renderRouteList(filterText) {
    var target = $('roteiro-lista'); if (!target) return;
    var selId = getSelectedRouteId(); var term = normalizeRouteSearch(filterText);
    var filtered = routes.filter(function(r) { if (!term) return true; return normalizeRouteSearch(routeSearchText(r)).indexOf(term)!==-1; });
    if (!filtered.length) { target.innerHTML = '<div class="oficio-step3-route-empty">Nenhum roteiro encontrado para a busca.</div>'; return; }
    target.innerHTML = filtered.map(function(r) {
      var rid=String(r.id); var ac=rid===selId?' is-active':'';
      return '<button type="button" class="oficio-step3-route-item'+ac+'" data-route-id="'+esc(rid)+'">' +
        '<span class="route-title">'+esc(r.label||'Roteiro #'+rid)+'</span>' +
        '<span class="route-destinos">'+esc(routeDestinationsSummary(r))+'</span>' +
        '<span class="route-periodo">'+esc(routePeriodSummary(r))+'</span></button>';
    }).join('');
  }
  function routeResumo() {
    var r = routeMap[String(getSelectedRouteId() || '')];
    $('roteiro-selector-resumo').textContent = r ? ((r.tipo_label ? r.tipo_label+' â€” ' : '')+r.resumo) : '';
    renderRouteList($('id_roteiro_busca') ? $('id_roteiro_busca').value : '');
  }
  function setModeUi() {
    var em = $('id_roteiro_modo_evento').checked;
    var panel = $('roteiro-selector-wrapper');
    var routeInput = getSelectedRouteInput();
    if (panel) {
      panel.classList.toggle('d-none', !em);
      panel.hidden = !em;
    }
    if (routeInput) routeInput.disabled = !em || !routes.length;
    if ($('id_roteiro_busca')) {
      $('id_roteiro_busca').disabled = !em || !routes.length;
      if (!em) $('id_roteiro_busca').value = '';
    }
    if (!em) setSelectedRouteId('');
    routeResumo();
  }
  $('destinos-container').addEventListener('change', function(e) {
    if (applyingState) return; var row = e.target.closest('.destino-row'); if (!row) return;
    if (e.target.classList.contains('destino-estado')) { var cs = row.querySelector('.destino-cidade'); loadCities(cs, e.target.value||'', null).then(function() { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); }); }
    else { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); }
  });
  $('destinos-container').addEventListener('click', function(e) {
    var btn = e.target.closest('.btn-remover-destino'); if (!btn) return;
    var rows = getDestinoRows(); if (rows.length <= 1) return;
    btn.closest('.destino-row').remove(); reindexDestinoRows(); refreshDestinoButtons(); renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave();
  });
  $('btn-adicionar-destino').addEventListener('click', function() { addDestinoRow({ estado_id: destinoEstadoDefaultId||null, cidade_id: null }).then(function() { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); }); });
  $('id_origem_estado').addEventListener('change', function() { if (applyingState) return; loadCities($('id_origem_cidade'), $('id_origem_estado').value, null).then(function() { renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); }); });
  $('id_origem_cidade').addEventListener('change', function() { if (applyingState) return; renderTrechos(captureCurrentState()); scheduleRealtimeDiarias(); scheduleAutosave(); });
  $('trechos-gerados-container').addEventListener('click', function (e) {
    var btn = e.target.closest('.btn-calcular-km');
    if (!btn || applyingState) return;
    e.preventDefault();
    var card = btn.closest('.card[data-key]');
    if (!card) return;
    var ord = card.dataset.ordem;
    var ocid = card.dataset.origemCidadeId;
    var dcid = card.dataset.destinoCidadeId;
    var err = card.querySelector('.trecho-erro');
    if (err) { err.classList.add('d-none'); err.textContent = ''; }
    if (!urlTrechosEstimar || !ocid || !dcid) {
      if (err) { err.textContent = 'Defina origem e destino do trecho para estimar.'; err.classList.remove('d-none'); }
      return;
    }
    btn.disabled = true;
    fetch(urlTrechosEstimar, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
        'X-Requested-With': 'XMLHttpRequest'
      },
      credentials: 'same-origin',
      body: JSON.stringify({ origem_cidade_id: parseInt(ocid, 10), destino_cidade_id: parseInt(dcid, 10) })
    }).then(readJsonResponse).then(function (result) {
      var data = result && result.data;
      btn.disabled = false;
      if (!data || !data.ok) {
        if (err) { err.textContent = (data && data.erro) ? data.erro : 'Não foi possível estimar.'; err.classList.remove('d-none'); }
        return;
      }
      applyEstimarPayloadToTrechoCard(card, data);
      chainSuggestedDepartures();
      chainRetornoSaidaFromLastTrecho();
      updateResumo();
      scheduleRealtimeDiarias();
      scheduleAutosave();
    }).catch(function () {
      btn.disabled = false;
      if (err) { err.textContent = 'Falha na requisição.'; err.classList.remove('d-none'); }
    });
  });
  var btnRetornoEstimar = $('btn-retorno-estimar');
  if (btnRetornoEstimar) {
    btnRetornoEstimar.addEventListener('click', function() {
      if (applyingState) return;
      var rc = $('retorno-card');
      var err = $('retorno-erro');
      var ocid = rc ? rc.dataset.origemCidadeId : '';
      var dcid = rc ? rc.dataset.destinoCidadeId : '';
      if (err) { err.classList.add('d-none'); err.textContent = ''; }
      if (!urlTrechosEstimar || !ocid || !dcid) {
        if (err) {
          err.textContent = 'Defina trechos e sede para estimar o retorno.';
          err.classList.remove('d-none');
        }
        return;
      }
      btnRetornoEstimar.disabled = true;
      fetch(urlTrechosEstimar, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
          'X-Requested-With': 'XMLHttpRequest'
        },
        credentials: 'same-origin',
        body: JSON.stringify({ origem_cidade_id: parseInt(ocid, 10), destino_cidade_id: parseInt(dcid, 10) })
      }).then(readJsonResponse).then(function(result) {
        btnRetornoEstimar.disabled = false;
        var data = result && result.data;
        if (!data || !data.ok) {
          if (err) {
            err.textContent = (data && data.erro) ? data.erro : 'Não foi possível estimar.';
            err.classList.remove('d-none');
          }
          return;
        }
        applyEstimarPayloadToRetorno(data);
        scheduleRealtimeDiarias();
        scheduleAutosave();
      }).catch(function() {
        btnRetornoEstimar.disabled = false;
        if (err) {
          err.textContent = 'Falha na requisição.';
          err.classList.remove('d-none');
        }
      });
    });
  }
  $('trechos-gerados-container').addEventListener('input', function(e) {
    var c = e.target.closest('.card[data-key]'); if (!c || applyingState) return;
    var n = e.target.name||'';
    if (n.indexOf('_saida_')!==-1||n.indexOf('_tempo_adicional_min')!==-1||n.indexOf('_tempo_cru_estimado_min')!==-1||e.target.classList.contains('trecho-tempo-viagem-hhmm')) {
      if (n.indexOf('_tempo_adicional_min') !== -1) e.target.dataset.manual = '1';
      recalcCard(c, true);
      chainSuggestedDepartures();
      chainRetornoSaidaFromLastTrecho();
    }
    updateResumo(); scheduleRealtimeDiarias(); scheduleAutosave();
  });
  $('trechos-gerados-container').addEventListener('change', function(e) {
    var c = e.target.closest('.card[data-key]'); if (!c || applyingState) return;
    var n = e.target.name||'';
    if (n.indexOf('_saida_')!==-1||n.indexOf('_tempo_adicional_min')!==-1||n.indexOf('_tempo_cru_estimado_min')!==-1||e.target.classList.contains('trecho-tempo-viagem-hhmm')) {
      if (n.indexOf('_tempo_adicional_min') !== -1) e.target.dataset.manual = '1';
      recalcCard(c, true);
      chainSuggestedDepartures();
      chainRetornoSaidaFromLastTrecho();
    }
    updateResumo(); scheduleRealtimeDiarias(); scheduleAutosave();
  });
  ['id_retorno_saida_data','id_retorno_saida_hora','id_retorno_chegada_data','id_retorno_chegada_hora','id_retorno_tempo_viagem_hhmm','id_retorno_tempo_adicional_min'].forEach(function(id) {
    $(id).addEventListener('input', function() { if (applyingState) return; if (id === 'id_retorno_tempo_adicional_min') this.dataset.manual = '1'; recalcRetorno(id.indexOf('saida_')!==-1||id.indexOf('tempo_')!==-1); scheduleRealtimeDiarias(); scheduleAutosave(); notifyRouteStateChanged(); });
    $(id).addEventListener('change', function() { if (applyingState) return; recalcRetorno(true); scheduleRealtimeDiarias(); scheduleAutosave(); });
  });
  if ($('id_roteiro_busca')) {
    $('id_roteiro_busca').addEventListener('input', function() {
      clearTimeout(routeSearchTimer);
      routeSearchTimer = setTimeout(function() {
        renderRouteList($('id_roteiro_busca').value || '');
      }, 120);
    });
  }
  ['id_bate_volta_diario_ativo','id_bate_volta_data_inicio','id_bate_volta_data_fim','id_bate_volta_ida_saida_hora','id_bate_volta_volta_saida_hora'].forEach(function(id) {
    var field = $(id);
    if (!field) return;
    field.addEventListener('change', function() {
      if (applyingState) return;
      toggleBateVoltaPanel();
      scheduleLoopTrechosRender({ preferSeed: false, force: true });
      scheduleAutosave();
    });
  });
  [
    { text: 'id_bate_volta_ida_tempo_hhmm', hidden: 'id_bate_volta_ida_tempo_min' },
    { text: 'id_bate_volta_volta_tempo_hhmm', hidden: 'id_bate_volta_volta_tempo_min' }
  ].forEach(function(pair) {
    var textInput = $(pair.text);
    var hiddenInput = $(pair.hidden);
    if (!textInput || !hiddenInput) return;
    textInput.addEventListener('input', function() {
      if (applyingState) return;
      var normalized = normalizeDurationInput(this.value);
      var parsed = parseDurationInput(normalized);
      hiddenInput.value = parsed != null ? String(parsed) : '';
      if (normalized !== this.value) this.value = normalized;
      scheduleLoopTrechosRender({ preferSeed: false, force: true });
      scheduleAutosave();
    });
    textInput.addEventListener('blur', function() {
      syncBateVoltaDurationInputs();
    });
  });
  if ($('roteiro-lista')) {
    $('roteiro-lista').addEventListener('click', function(e) {
      var btn = e.target.closest('[data-route-id]'); if (!btn) return;
      var rid = btn.getAttribute('data-route-id')||''; if (!rid) return;
      setSelectedRouteId(rid);
      routeResumo();
      var r = routeMap[String(rid)];
      if (r && r.state && $('id_roteiro_modo_evento').checked) applyState(r.state);
      else scheduleRealtimeDiarias();
      scheduleAutosave();
    });
  }
  if ($('id_roteiro_modo_evento')) {
    $('id_roteiro_modo_evento').addEventListener('change', function() {
      setModeUi();
      if ($('id_roteiro_modo_evento').checked && getSelectedRouteId()) { var r = routeMap[String(getSelectedRouteId())]; if (r && r.state) applyState(r.state); }
      else { scheduleRealtimeDiarias(); }
      scheduleAutosave();
    });
  }
  if ($('id_roteiro_modo_proprio')) {
    $('id_roteiro_modo_proprio').addEventListener('change', function() { setModeUi(); scheduleRealtimeDiarias(); scheduleAutosave(); });
  }
  setModeUi();
  toggleBateVoltaPanel();
  syncBateVoltaDurationInputs();
  applyState(initialState).then(function() {
    if (initialDiarias) {
      applyDiarias(initialDiarias);
      setDiariasStatus('updated', 'Cálculo carregado (1 servidor).');
    } else {
      scheduleRealtimeDiarias();
    }
    notifyRouteStateChanged();
  });
  window.RoteirosStep3 = {
    canCalculateRoutePreview: canCalculateRoutePreview,
    buildRoutePreviewPayload: buildRoutePreviewPayload,
    applyRoutePreviewResult: applyRoutePreviewResult,
    getPreviewEndpointUrl: function() { return urlCalcularRotaPreview; },
  };
})();
