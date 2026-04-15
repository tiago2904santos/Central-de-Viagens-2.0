(function() {
  var form = document.getElementById('ordem-servico-form');
  if (!form) {
    return;
  }

  var autosaveIdInput = document.getElementById('id_autosave_obj_id');
  var autosaveStatus = document.getElementById('ordem-servico-autosave-status');
  var dataUnicaInput = document.getElementById('id_data_unica');
  var dataDeslocamentoInput = document.getElementById('id_data_deslocamento');
  var dataFimInput = document.getElementById('id_data_deslocamento_fim');
  var eventoSelect = document.getElementById('id_evento');
  var oficioSelect = document.getElementById('id_oficio');
  var modeloMotivoSelect = document.getElementById('id_modelo_motivo');
  var motivoTextarea = document.getElementById('id_motivo_texto');
  var dataUnicaState = form.querySelector('[data-data-unica-state]');
  var dataUnicaPill = form.querySelector('[data-data-unica-pill]');
  var destinosInput = document.getElementById('id_destinos_payload');
  var destinosList = document.getElementById('destinos-container');
  var destinoTemplate = document.getElementById('ordem-servico-destino-row-template');
  var addDestinoBtn = document.getElementById('btn-adicionar-destino');
  var destinoEstadoDefaultId = destinosList ? destinosList.getAttribute('data-destino-estado-fixo-id') || '' : '';
  var destinoEstadoDefaultNome = destinosList ? destinosList.getAttribute('data-destino-estado-fixo-nome') || 'Paraná (PR)' : 'Paraná (PR)';
  var estadosDataEl = document.getElementById('ordem-servico-estados-data');
  var selectedDataElement = document.getElementById('viajantes-selected-data');
  var buscarViajantesWrapper = document.getElementById('viajantes-autocomplete-wrapper');
  var buscarViajantesInput = document.getElementById('viajantes-autocomplete-input');
  var buscarViajantesResults = document.getElementById('viajantes-autocomplete-results');
  var viajantesHiddenInputs = document.getElementById('viajantes-hidden-inputs');
  var viajantesChipList = document.getElementById('viajantes-chip-list');
  var viajantesChipCount = document.getElementById('viajantes-chip-count');
  var viajantesChipEmpty = document.getElementById('viajantes-chip-empty');
  var buscarViajantesUrl = buscarViajantesWrapper ? buscarViajantesWrapper.getAttribute('data-search-url') : '';
  var apiCidadesUrl = form.getAttribute('data-cidades-api-url') || '';
  var motivoApiBase = form.getAttribute('data-motivo-api-base') || '';
  var estadosChoices = [];
  var selectedMap = new Map();
  var suggestionItems = [];
  var activeSuggestionIndex = -1;
  var fetchSequence = 0;
  var searchDebounceTimer = null;
  var lastMotivoTemplate = '';

  var preview = {
    numero: document.getElementById('ordem-servico-preview-numero'),
    data: document.getElementById('ordem-servico-preview-data'),
    vinculo: document.getElementById('ordem-servico-preview-vinculo'),
    status: document.getElementById('ordem-servico-preview-status'),
  };

  function scheduleAutosave() {
    if (autosave) {
      autosave.schedule();
    }
    updateContextPreview();
  }

  function parseJsonElement(element, fallback) {
    if (!element) {
      return fallback;
    }
    try {
      return JSON.parse(element.textContent || '[]');
    } catch (error) {
      return fallback;
    }
  }

  function parseJsonValue(input, fallback) {
    if (!input) {
      return fallback;
    }
    try {
      var raw = String(input.value || '').trim();
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function joinPtBr(values) {
    var list = values.filter(Boolean);
    if (!list.length) {
      return '';
    }
    if (list.length === 1) {
      return list[0];
    }
    if (list.length === 2) {
      return list[0] + ' e ' + list[1];
    }
    return list.slice(0, -1).join(', ') + ' e ' + list[list.length - 1];
  }

  function setStatusLabel(node, enabled, onText, offText) {
    if (!node) {
      return;
    }
    node.textContent = enabled ? onText : offText;
  }

  function parseDateParts(raw) {
    if (!raw || raw.length !== 10) {
      return '';
    }
    var parts = raw.split('-');
    if (parts.length !== 3) {
      return '';
    }
    return parts[2] + '/' + parts[1] + '/' + parts[0];
  }

  function getSelectedOptionLabel(select) {
    if (!select || !select.selectedOptions || !select.selectedOptions.length) {
      return '';
    }
    return String(select.selectedOptions[0].textContent || '').trim();
  }

  function getDestinoRows() {
    if (!destinosList) {
      return [];
    }
    return Array.from(destinosList.querySelectorAll('.destino-row'));
  }

  function refreshDestinoButtons() {
    var rows = getDestinoRows();
    rows.forEach(function(row) {
      var btn = row.querySelector('.btn-remover-destino');
      if (btn) {
        btn.disabled = rows.length <= 1;
      }
    });
  }

  function reindexDestinoRows() {
    getDestinoRows().forEach(function(row, idx) {
      row.dataset.index = String(idx);
      var estado = row.querySelector('.destino-estado');
      var cidade = row.querySelector('.destino-cidade');
      var dragHandle = row.querySelector('.destino-drag-handle');
      if (estado) {
        estado.name = 'destino_estado_' + idx;
      }
      if (cidade) {
        cidade.name = 'destino_cidade_' + idx;
      }
      if (dragHandle) {
        dragHandle.setAttribute('aria-label', 'Arrastar destino ' + (idx + 1));
      }
    });
  }

  function isDataUnica() {
    return !!(dataUnicaInput && dataUnicaInput.checked);
  }

  function buildPeriodoLabel() {
    if (!dataDeslocamentoInput || !dataDeslocamentoInput.value) {
      return 'Período a definir';
    }
    var inicio = parseDateParts(dataDeslocamentoInput.value);
    if (!inicio) {
      return 'Período a definir';
    }
    var fim = dataFimInput && dataFimInput.value ? parseDateParts(dataFimInput.value) : '';
    if (isDataUnica()) {
      return inicio;
    }
    if (fim && fim !== inicio) {
      return inicio + ' a ' + fim;
    }
    return inicio;
  }

  function updateDataUnica() {
    if (!dataUnicaInput || !dataFimInput) {
      return;
    }

    var active = !!dataUnicaInput.checked;
    setStatusLabel(dataUnicaState, active, 'LIGADA', 'DESLIGADA');
    if (dataUnicaPill) {
      dataUnicaPill.classList.toggle('is-on', active);
      dataUnicaPill.classList.toggle('is-off', !active);
      dataUnicaPill.setAttribute('data-state', active ? 'on' : 'off');
    }

    dataFimInput.readOnly = active;
    dataFimInput.classList.toggle('is-locked', active);

    if (active && dataDeslocamentoInput) {
      dataFimInput.value = dataDeslocamentoInput.value;
    }

    updateContextPreview();
  }

  function renderAutosavePreview(payload) {
    if (!payload) {
      return;
    }
    if (payload.numero_formatado && preview.numero) {
      preview.numero.textContent = payload.numero_formatado;
    }
    if (payload.data_criacao_display && preview.data) {
      preview.data.textContent = payload.data_criacao_display;
    }
    if (payload.status_display && preview.status) {
      preview.status.textContent = payload.status_display;
    }
  }

  function getDestinosPayload() {
    var payload = [];
    if (!destinosList) {
      return payload;
    }

    destinosList.querySelectorAll('[data-destino-row]').forEach(function(row) {
      var estadoSelect = row.querySelector('.destino-estado');
      var cidadeSelect = row.querySelector('.destino-cidade');
      if (!estadoSelect || !cidadeSelect || !estadoSelect.value || !cidadeSelect.value) {
        return;
      }
      payload.push({
        estado_id: Number(estadoSelect.value),
        estado_sigla: estadoSelect.selectedOptions && estadoSelect.selectedOptions.length ? String(estadoSelect.selectedOptions[0].dataset.sigla || '').trim() : '',
        cidade_id: Number(cidadeSelect.value),
        cidade_nome: getSelectedOptionLabel(cidadeSelect),
      });
    });
    return payload;
  }

  function syncDestinosPayload() {
    var payload = getDestinosPayload();
    if (destinosInput) {
      destinosInput.value = JSON.stringify(payload);
    }
    return payload;
  }

  function buildEstadoOptions(selectedId) {
    var html = '<option value="">Selecione...</option>';
    estadosChoices.forEach(function(estado) {
      var selected = String(estado.id) === String(selectedId) ? ' selected' : '';
      html += '<option value="' + estado.id + '" data-sigla="' + String(estado.sigla || '').toUpperCase() + '"' + selected + '>' + estado.nome + ' (' + estado.sigla + ')</option>';
    });
    return html;
  }

  function buildCidadeUrl(estadoId) {
    return apiCidadesUrl.replace(/\/0\/?$/, '/' + String(estadoId) + '/');
  }

  function refreshPickers(root) {
    if (window.OficioWizard && typeof window.OficioWizard.refreshSelectPickers === 'function') {
      window.OficioWizard.refreshSelectPickers(root || form);
    }
  }

  function bindDestinoDragAndDrop(row) {
    if (!row) {
      return;
    }

    row.addEventListener('dragstart', function(event) {
      row.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', row.dataset.index || '0');
    });

    row.addEventListener('dragend', function() {
      row.classList.remove('is-dragging');
      getDestinoRows().forEach(function(item) {
        item.classList.remove('is-drop-target');
      });
    });

    row.addEventListener('dragover', function(event) {
      event.preventDefault();
      if (!row.classList.contains('is-dragging')) {
        row.classList.add('is-drop-target');
      }
    });

    row.addEventListener('dragleave', function() {
      row.classList.remove('is-drop-target');
    });

    row.addEventListener('drop', function(event) {
      event.preventDefault();
      var fromIndex = parseInt(event.dataTransfer.getData('text/plain') || '-1', 10);
      var rows = getDestinoRows();
      var dragged = rows[fromIndex];
      if (!dragged || dragged === row) {
        row.classList.remove('is-drop-target');
        return;
      }
      var container = destinosList;
      var allRows = getDestinoRows();
      var targetIndex = allRows.indexOf(row);
      var draggedIndex = allRows.indexOf(dragged);
      if (draggedIndex < targetIndex) {
        container.insertBefore(dragged, row.nextSibling);
      } else {
        container.insertBefore(dragged, row);
      }
      row.classList.remove('is-drop-target');
      reindexDestinoRows();
      refreshDestinoButtons();
      syncFromDestinos();
      scheduleAutosave();
    });
  }

  async function populateCities(selectCidade, estadoId, selectedCidadeId) {
    if (!selectCidade) {
      return;
    }

    selectCidade.innerHTML = '<option value="">Selecione...</option>';
    if (!estadoId) {
      selectCidade.disabled = true;
      refreshPickers(selectCidade);
      return;
    }

    selectCidade.disabled = true;
    try {
      var response = await fetch(buildCidadeUrl(estadoId), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!response.ok) {
        throw new Error('Falha ao carregar cidades');
      }
      var data = await response.json();
      var cidades = Array.isArray(data) ? data : (data.cidades || []);
      cidades.forEach(function(cidade) {
        var option = document.createElement('option');
        option.value = String(cidade.id);
        option.textContent = cidade.nome;
        if (selectedCidadeId && String(selectedCidadeId) === String(cidade.id)) {
          option.selected = true;
        }
        selectCidade.appendChild(option);
      });
    } catch (error) {
      selectCidade.innerHTML = '<option value="">Selecione...</option>';
    } finally {
      selectCidade.disabled = false;
      refreshPickers(selectCidade);
    }
  }

  function bindDestinoRow(row) {
    if (!row) {
      return;
    }

    var estadoSelect = row.querySelector('.destino-estado');
    var cidadeSelect = row.querySelector('.destino-cidade');

    if (estadoSelect && cidadeSelect) {
      if (estadoSelect.value) {
        populateCities(cidadeSelect, estadoSelect.value, cidadeSelect.getAttribute('data-cidade-id'));
      }

      estadoSelect.addEventListener('change', function() {
        cidadeSelect.removeAttribute('data-cidade-id');
        populateCities(cidadeSelect, estadoSelect.value, null).then(function() {
          syncDestinosPayload();
          scheduleAutosave();
        });
      });
    }

    if (cidadeSelect) {
      cidadeSelect.addEventListener('change', function() {
        syncDestinosPayload();
        scheduleAutosave();
      });
    }

    bindDestinoDragAndDrop(row);
  }

  async function addDestinoRow(initialData) {
    if (!destinoTemplate || !destinosList) {
      return;
    }

    var fragment = destinoTemplate.content.cloneNode(true);
    var row = fragment.querySelector('[data-destino-row]');
    var estadoSelect = row ? row.querySelector('.destino-estado') : null;
    var cidadeSelect = row ? row.querySelector('.destino-cidade') : null;

    if (!row || !estadoSelect || !cidadeSelect) {
      return;
    }

    row.draggable = true;
    var selectedEstadoId = initialData && initialData.estado_id ? initialData.estado_id : destinoEstadoDefaultId;
    estadoSelect.innerHTML = buildEstadoOptions(selectedEstadoId);
    estadoSelect.value = selectedEstadoId ? String(selectedEstadoId) : '';
    cidadeSelect.setAttribute('data-cidade-id', initialData && initialData.cidade_id ? String(initialData.cidade_id) : '');

    destinosList.appendChild(row);
    bindDestinoRow(row);
    await populateCities(cidadeSelect, estadoSelect.value, initialData ? initialData.cidade_id : null);
    refreshPickers(row);
    reindexDestinoRows();
    refreshDestinoButtons();
    syncDestinosPayload();
  }

  async function hydrateDestinos() {
    var payload = parseJsonValue(destinosInput, []);
    if (!Array.isArray(payload) || !payload.length) {
      await addDestinoRow({ estado_id: destinoEstadoDefaultId || null, cidade_id: null });
      return;
    }

    for (var i = 0; i < payload.length; i += 1) {
      await addDestinoRow(payload[i]);
    }
  }

  function clearSuggestions() {
    suggestionItems = [];
    activeSuggestionIndex = -1;
    if (!buscarViajantesResults) {
      return;
    }
    buscarViajantesResults.innerHTML = '';
    buscarViajantesResults.classList.add('d-none');
  }

  function setActiveSuggestion(nextIndex) {
    activeSuggestionIndex = nextIndex;
    if (!buscarViajantesResults) {
      return;
    }
    Array.prototype.forEach.call(buscarViajantesResults.querySelectorAll('[data-suggestion-index]'), function(button, index) {
      button.classList.toggle('active', index === activeSuggestionIndex);
    });
  }

  function renderSuggestions() {
    if (!buscarViajantesResults) {
      return;
    }

    buscarViajantesResults.innerHTML = '';
    if (!suggestionItems.length) {
      var emptyState = document.createElement('div');
      emptyState.className = 'list-group-item text-muted small';
      emptyState.textContent = 'Nenhum viajante encontrado.';
      buscarViajantesResults.appendChild(emptyState);
      buscarViajantesResults.classList.remove('d-none');
      return;
    }

    suggestionItems.forEach(function(item, index) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'list-group-item list-group-item-action oficio-viajante-result-item';
      button.setAttribute('data-suggestion-index', String(index));

      var topRow = document.createElement('span');
      topRow.className = 'oficio-viajante-result-top';
      var nome = String(item.nome || item.label || 'Viajante').trim();
      var rg = String(item.rg || '').trim();
      var cpf = String(item.cpf || '').trim();
      var cargo = String(item.cargo || '').trim();
      topRow.textContent = [nome, rg ? ('RG ' + rg) : '', cpf ? ('CPF ' + cpf) : '', cargo].filter(Boolean).join(' • ');
      button.appendChild(topRow);

      var lotacaoRow = document.createElement('span');
      lotacaoRow.className = 'oficio-viajante-result-bottom';
      lotacaoRow.textContent = String(item.lotacao || '').trim() || 'Lotacao nao informada';
      button.appendChild(lotacaoRow);

      buscarViajantesResults.appendChild(button);
    });

    buscarViajantesResults.classList.remove('d-none');
    setActiveSuggestion(0);
  }

  function renderHiddenInputs() {
    if (!viajantesHiddenInputs) {
      return;
    }
    viajantesHiddenInputs.innerHTML = '';
    selectedMap.forEach(function(item, id) {
      var input = document.createElement('input');
      input.type = 'hidden';
      input.name = 'viajantes';
      input.value = id;
      input.setAttribute('data-viajante-hidden', id);
      viajantesHiddenInputs.appendChild(input);
    });
  }

  function renderChips() {
    if (!viajantesChipList) {
      return;
    }

    viajantesChipList.innerHTML = '';
    if (!selectedMap.size) {
      var emptyState = document.createElement('span');
      emptyState.className = 'oficio-glance-empty';
      emptyState.id = 'viajantes-chip-empty';
      emptyState.textContent = 'Nenhum servidor selecionado.';
      viajantesChipList.appendChild(emptyState);
      viajantesChipEmpty = emptyState;
    } else {
      selectedMap.forEach(function(item, id) {
        var chip = document.createElement('div');
        chip.className = 'oficio-glance-chip oficio-selection-chip ordem-servico-selection-chip';
        chip.setAttribute('data-viajante-chip', id);

        var nomeEl = document.createElement('span');
        nomeEl.className = 'oficio-glance-chip-nome';
        nomeEl.textContent = item.nome || item.label || 'Viajante';
        chip.appendChild(nomeEl);

        var lotacao = String(item.lotacao || '').trim();
        if (lotacao) {
          var lotacaoEl = document.createElement('span');
          lotacaoEl.className = 'oficio-glance-chip-sub';
          lotacaoEl.textContent = lotacao;
          chip.appendChild(lotacaoEl);
        } else {
          var cargo = String(item.cargo || '').trim();
          if (cargo) {
            var cargoEl = document.createElement('span');
            cargoEl.className = 'oficio-glance-chip-sub';
            cargoEl.textContent = cargo;
            chip.appendChild(cargoEl);
          }
        }

        var removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'oficio-selection-chip-remove';
        removeButton.setAttribute('data-remove-viajante', id);
        removeButton.setAttribute('aria-label', 'Remover viajante ' + (item.nome || ''));
        removeButton.innerHTML = '&times;';
        removeButton.addEventListener('click', function() {
          removeSelectedViajante(id);
        });
        chip.appendChild(removeButton);
        viajantesChipList.appendChild(chip);
      });
    }

    if (viajantesChipCount) {
      viajantesChipCount.textContent = String(selectedMap.size);
    }

    if (viajantesChipEmpty) {
      viajantesChipEmpty.style.display = selectedMap.size ? 'none' : '';
    }
  }

  function updateContextPreview() {
    if (preview.data) {
      preview.data.textContent = buildPeriodoLabel();
    }
    if (preview.vinculo) {
      var vinculo = 'Cadastro avulso';
      if (oficioSelect && oficioSelect.value && oficioSelect.selectedOptions.length) {
        vinculo = 'Ofício ' + getSelectedOptionLabel(oficioSelect);
      } else if (eventoSelect && eventoSelect.value && eventoSelect.selectedOptions.length) {
        vinculo = 'Evento ' + getSelectedOptionLabel(eventoSelect);
      }
      preview.vinculo.textContent = vinculo;
    }
    if (preview.status) {
      var complete = isDocumentComplete();
      preview.status.textContent = complete ? 'Finalizado' : 'Rascunho';
      preview.status.classList.toggle('is-finalizado', complete);
      preview.status.classList.toggle('is-rascunho', !complete);
    }
  }

  function isDocumentComplete() {
    var destinos = syncDestinosPayload();
    var unique = isDataUnica();
    return !!(
      (dataDeslocamentoInput && dataDeslocamentoInput.value) &&
      (unique || (dataFimInput && dataFimInput.value)) &&
      (motivoTextarea && String(motivoTextarea.value || '').trim()) &&
      destinos.length &&
      selectedMap.size
    );
  }

  function addSelectedViajante(item) {
    if (!item || !item.id) {
      return;
    }
    var id = String(item.id);
    if (selectedMap.has(id)) {
      clearSuggestions();
      if (buscarViajantesInput) {
        buscarViajantesInput.value = '';
        buscarViajantesInput.focus();
      }
      return;
    }

    selectedMap.set(id, item);
    renderHiddenInputs();
    renderChips();
    clearSuggestions();
    if (buscarViajantesInput) {
      buscarViajantesInput.value = '';
      buscarViajantesInput.focus();
    }
    scheduleAutosave();
  }

  function removeSelectedViajante(id) {
    selectedMap.delete(String(id));
    renderHiddenInputs();
    renderChips();
    scheduleAutosave();
  }

  async function buscarSugestoes(term) {
    if (!buscarViajantesUrl) {
      clearSuggestions();
      return;
    }

    var texto = String(term || '').trim();
    if (texto.length < 2) {
      clearSuggestions();
      return;
    }

    var sequence = ++fetchSequence;
    try {
      var url = new URL(buscarViajantesUrl, window.location.origin);
      url.searchParams.set('q', texto);
      var response = await fetch(url.toString(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!response.ok || sequence !== fetchSequence) {
        return;
      }
      var payload = await response.json();
      suggestionItems = (payload.results || []).filter(function(item) {
        return item && item.id && !selectedMap.has(String(item.id));
      });
      renderSuggestions();
    } catch (error) {
      if (sequence === fetchSequence) {
        clearSuggestions();
      }
    }
  }

  function debounceBusca() {
    window.clearTimeout(searchDebounceTimer);
    searchDebounceTimer = window.setTimeout(function() {
      buscarSugestoes(buscarViajantesInput ? buscarViajantesInput.value : '');
    }, 180);
  }

  async function applyMotivoTemplate(force, options) {
    if (!modeloMotivoSelect || !modeloMotivoSelect.value || !motivoTextarea) {
      return;
    }

    var shouldAutosave = !options || options.autosave !== false;
    try {
      var url = String(motivoApiBase || '').replace(/\/0\/texto\/$/, '/' + String(modeloMotivoSelect.value) + '/texto/');
      var response = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      if (!response.ok) {
        return;
      }
      var data = await response.json();
      var texto = String((data && data.texto) || '').trim();
      if (!texto) {
        return;
      }
      if (force || !String(motivoTextarea.value || '').trim() || String(motivoTextarea.value || '').trim() === lastMotivoTemplate) {
        motivoTextarea.value = texto;
      }
      lastMotivoTemplate = texto;
      updateContextPreview();
      if (shouldAutosave) {
        scheduleAutosave();
      }
    } catch (error) {
      return;
    }
  }

  function syncFromSelection() {
    renderHiddenInputs();
    renderChips();
    updateContextPreview();
  }

  function syncFromDestinos() {
    syncDestinosPayload();
    updateContextPreview();
  }

  var autosave = window.OficioWizard ? window.OficioWizard.createAutosave({
    form: form,
    statusElement: autosaveStatus,
    onSuccess: function(data) {
      if (!data) {
        return;
      }
      if (autosaveIdInput && data.id) {
        autosaveIdInput.value = String(data.id);
      }
      if (data.edit_url) {
        form.setAttribute('action', data.edit_url);
        if (window.location.pathname !== data.edit_url) {
          window.history.replaceState({}, '', data.edit_url);
        }
      }
      renderAutosavePreview(data);
      updateContextPreview();
    }
  }) : null;

  parseJsonElement(selectedDataElement, []).forEach(function(item) {
    if (item && item.id) {
      selectedMap.set(String(item.id), item);
    }
  });

  estadosChoices = parseJsonElement(estadosDataEl, []);

  if (buscarViajantesInput) {
    buscarViajantesInput.addEventListener('input', function() {
      debounceBusca();
      scheduleAutosave();
    });
  }

  if (buscarViajantesInput) {
    buscarViajantesInput.addEventListener('keydown', function(event) {
      if (event.key === 'Escape') {
        clearSuggestions();
      }
    });
  }

  if (buscarViajantesResults) {
    buscarViajantesResults.addEventListener('click', function(event) {
      var suggestionButton = event.target.closest('[data-suggestion-index]');
      if (!suggestionButton) {
        return;
      }
      var index = Number(suggestionButton.getAttribute('data-suggestion-index'));
      if (!Number.isNaN(index) && suggestionItems[index]) {
        addSelectedViajante(suggestionItems[index]);
      }
    });
  }

  if (modeloMotivoSelect) {
    modeloMotivoSelect.addEventListener('change', function() {
      applyMotivoTemplate(true);
    });
  }

  if (motivoTextarea) {
    motivoTextarea.addEventListener('input', function() {
      updateContextPreview();
      scheduleAutosave();
    });
  }

  if (dataDeslocamentoInput) {
    dataDeslocamentoInput.addEventListener('change', function() {
      if (isDataUnica() && dataFimInput) {
        dataFimInput.value = dataDeslocamentoInput.value;
      }
      updateContextPreview();
      scheduleAutosave();
    });
  }

  if (dataFimInput) {
    dataFimInput.addEventListener('change', function() {
      updateContextPreview();
      scheduleAutosave();
    });
  }

  if (dataUnicaInput) {
    dataUnicaInput.addEventListener('change', function() {
      updateDataUnica();
      scheduleAutosave();
    });
  }

  if (eventoSelect) {
    eventoSelect.addEventListener('change', function() {
      updateContextPreview();
      scheduleAutosave();
    });
  }

  if (oficioSelect) {
    oficioSelect.addEventListener('change', function() {
      updateContextPreview();
      scheduleAutosave();
    });
  }

  if (addDestinoBtn) {
    addDestinoBtn.addEventListener('click', function() {
      addDestinoRow({ estado_id: destinoEstadoDefaultId || null, cidade_id: null }).then(function() {
        syncFromDestinos();
        scheduleAutosave();
      });
    });
  }

  destinosList && destinosList.addEventListener('change', function(event) {
    if (event.target && (event.target.classList.contains('destino-estado') || event.target.classList.contains('destino-cidade'))) {
      syncFromDestinos();
      scheduleAutosave();
    }
  });

  if (destinosList) {
    destinosList.addEventListener('click', function(event) {
      var removeButton = event.target.closest('.btn-remover-destino');
      if (!removeButton) {
        return;
      }
      var row = removeButton.closest('[data-destino-row]');
      if (!row) {
        return;
      }
      if (destinosList.querySelectorAll('[data-destino-row]').length <= 1) {
        return;
      }
      row.remove();
      reindexDestinoRows();
      refreshDestinoButtons();
      syncFromDestinos();
      scheduleAutosave();
    });
  }

  form.addEventListener('input', function(event) {
    if (event.target && event.target.type === 'hidden') {
      return;
    }
    if (!event.target || event.target === buscarViajantesInput) {
      return;
    }
    updateContextPreview();
  });

  form.addEventListener('change', function(event) {
    if (event.target && event.target.type === 'hidden') {
      return;
    }
    updateContextPreview();
  });

  updateDataUnica();
  hydrateDestinos().then(function() {
    syncFromSelection();
    syncFromDestinos();
    updateContextPreview();
    refreshPickers(form);
    if (modeloMotivoSelect && modeloMotivoSelect.value && motivoTextarea && !String(motivoTextarea.value || '').trim()) {
      applyMotivoTemplate(false, { autosave: false });
    }
  });
})();
