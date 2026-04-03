(function() {
  var MODE_META = {
    RAPIDO: {
      label: 'Termo simples',
      template: 'termo_autorizacao.docx'
    },
    AUTOMATICO_COM_VIATURA: {
      label: 'Automatico com viatura',
      template: 'termo_autorizacao_automatico.docx'
    },
    AUTOMATICO_SEM_VIATURA: {
      label: 'Automatico sem viatura',
      template: 'termo_autorizacao_automatico_sem_viatura.docx'
    }
  };

  function parseJsonScript(id, fallback) {
    var element = document.getElementById(id);
    if (!element) {
      return fallback;
    }
    try {
      return JSON.parse(element.textContent || '');
    } catch (error) {
      return fallback;
    }
  }

  function setText(selector, value) {
    var element = document.querySelector(selector);
    if (element) {
      element.textContent = value || '-';
    }
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function parseDateDisplay(value) {
    var raw = String(value || '').trim();
    if (!raw) {
      return '';
    }
    var parts = raw.split('-');
    if (parts.length !== 3) {
      return raw;
    }
    return [parts[2], parts[1], parts[0]].join('/');
  }

  function buildPeriodoDisplay(dataInicio, dataFim, fallback) {
    if (!dataInicio) {
      return fallback || '-';
    }
    var inicio = parseDateDisplay(dataInicio);
    var fim = parseDateDisplay(dataFim);
    if (fim && fim !== inicio) {
      return inicio + ' a ' + fim;
    }
    return inicio;
  }

  function normalizeDestinationLabel(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function uniqueDestinations(items) {
    var seen = new Set();
    return (items || []).reduce(function(acc, item) {
      var normalized = normalizeDestinationLabel(item && item.label ? item.label : item);
      if (!normalized) {
        return acc;
      }
      var key = normalized.toLowerCase();
      if (seen.has(key)) {
        return acc;
      }
      seen.add(key);
      acc.push({ label: normalized });
      return acc;
    }, []);
  }

  function parseDestinationText(value) {
    return uniqueDestinations(
      String(value || '')
        .split(/,|\n|;/)
        .map(function(item) { return item.trim(); })
        .filter(Boolean)
    );
  }

  function inferMode(travelersCount, hasVehicle) {
    if (travelersCount > 0 && hasVehicle) {
      return 'AUTOMATICO_COM_VIATURA';
    }
    if (travelersCount > 0) {
      return 'AUTOMATICO_SEM_VIATURA';
    }
    return 'RAPIDO';
  }

  function initTermsForm() {
    var form = document.getElementById('termo-form');
    if (!form) {
      return;
    }

    var readOnly = form.getAttribute('data-read-only-context') === 'true';
    var previewUrl = form.getAttribute('data-preview-url') || '';
    var oficiosPorEventoUrl = form.getAttribute('data-oficios-por-evento-url') || '';
    var cidadesApiBase = form.getAttribute('data-cidades-api-url') || '';
    var eventoSelect = document.getElementById('id_evento');
    var oficiosSelect = document.getElementById('id_oficios');
    var oficiosSelectionList = document.querySelector('[data-oficios-selection-list]');
    var oficiosEmptyText = document.querySelector('[data-oficios-empty-text]');
    var destinoInput = document.getElementById('id_destino');
    var dataEventoInput = document.getElementById('id_data_evento');
    var dataEventoFimInput = document.getElementById('id_data_evento_fim');
    var dataUnicaCheckbox = document.getElementById('id_data_evento_unica');
    var hiddenTravelersInput = document.querySelector('input[name="viajantes_ids"]');
    var hiddenVehicleInput = document.querySelector('input[name="veiculo_id"]');
    var destinosContainer = document.getElementById('destinos-container');
    var destinoRowTemplate = document.getElementById('destino-row-tpl');
    var addDestinoBtn = document.getElementById('btn-add-destino');
    var viajantesWrapper = document.getElementById('viajantes-autocomplete-wrapper');
    var viajantesChipList = document.getElementById('viajantes-chip-list');
    var viajantesChipCount = document.getElementById('viajantes-chip-count');
    var viajantesChipEmpty = document.getElementById('viajantes-chip-empty');
    var veiculoWrapper = document.getElementById('termo-veiculo-autocomplete-wrapper');
    var veiculoChipContainer = document.getElementById('termo-veiculo-chip');
    var veiculoCount = document.getElementById('termo-veiculo-count');
    var veiculoEmpty = document.getElementById('termo-veiculo-empty');
    var viajantesInput = document.getElementById('viajantes-autocomplete-input');
    var viajantesResults = document.getElementById('viajantes-autocomplete-results');
    var veiculoInput = document.getElementById('termo-veiculo-input');
    var veiculoResults = document.getElementById('termo-veiculo-results');
    var allOficiosOptions = [];
    var travelerSelected = new Map();
    var selectedVehicle = parseJsonScript('termo-selected-veiculo', null);
    var travelerSuggestionItems = [];
    var travelerActiveIndex = -1;
    var travelerFetchSequence = 0;
    var travelerDebounceTimer = null;
    var vehicleSuggestionItems = [];
    var vehicleActiveIndex = -1;
    var vehicleFetchSequence = 0;
    var vehicleDebounceTimer = null;
    var latestPreview = parseJsonScript('termo-preview-payload', {
      evento: null,
      oficios: [],
      destinos: [],
      destino: '',
      periodo_display: '-',
      total_viaturas: 0,
      veiculos: []
    });

    if (oficiosSelect) {
      allOficiosOptions = Array.from(oficiosSelect.options).map(function(opt) {
        return { value: opt.value, text: opt.textContent };
      });
    }

    parseJsonScript('termo-selected-viajantes', []).forEach(function(item) {
      if (item && item.id) {
        travelerSelected.set(String(item.id), item);
      }
    });

    function selectedOficios() {
      if (!oficiosSelect) {
        return [];
      }
      return Array.prototype.slice.call(oficiosSelect.options)
        .filter(function(option) { return option.selected; })
        .map(function(option) {
          return {
            id: option.value,
            label: option.textContent
          };
        });
    }

    function selectedOptionValues(select) {
      if (!select) {
        return [];
      }
      return Array.prototype.slice.call(select.options)
        .filter(function(option) { return option.selected; })
        .map(function(option) { return option.value; });
    }

    function toggleDataFim() {
      if (!dataUnicaCheckbox || !dataEventoFimInput) return;
      if (dataUnicaCheckbox.checked) {
        if (dataEventoInput) dataEventoFimInput.value = dataEventoInput.value;
        dataEventoFimInput.readOnly = true;
        dataEventoFimInput.setAttribute('aria-disabled', 'true');
        dataEventoFimInput.classList.add('bg-light');
      } else {
        dataEventoFimInput.readOnly = false;
        dataEventoFimInput.removeAttribute('aria-disabled');
        dataEventoFimInput.classList.remove('bg-light');
      }
    }

    async function filterOficiosByEvento(eventoId) {
      if (!oficiosSelect) return;
      if (!eventoId) {
        oficiosSelect.innerHTML = '';
        allOficiosOptions.forEach(function(opt) {
          var o = document.createElement('option');
          o.value = opt.value;
          o.textContent = opt.text;
          oficiosSelect.appendChild(o);
        });
        renderOficiosSelection();
        return;
      }
      if (!oficiosPorEventoUrl) return;
      try {
        var resp = await fetch(oficiosPorEventoUrl + '?evento_id=' + encodeURIComponent(eventoId), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) return;
        var data = await resp.json();
        oficiosSelect.innerHTML = '';
        (data.oficios || []).forEach(function(oficio) {
          var o = document.createElement('option');
          o.value = String(oficio.id);
          o.textContent = oficio.label;
          oficiosSelect.appendChild(o);
        });
        Array.from(oficiosSelect.options).forEach(function(opt) { opt.selected = true; });
        renderOficiosSelection();
      } catch (e) { /* silent */ }
    }

    function syncHiddenTravelers() {
      if (hiddenTravelersInput) {
        hiddenTravelersInput.value = Array.from(travelerSelected.keys()).join(',');
      }
    }

    function syncHiddenVehicle() {
      if (hiddenVehicleInput) {
        hiddenVehicleInput.value = selectedVehicle && selectedVehicle.id ? String(selectedVehicle.id) : '';
      }
    }

    async function mountCidadeOptionsForRow(cidadeSelect, estadoId, selectedCidadeId) {
      cidadeSelect.innerHTML = '<option value="">Selecione...</option>';
      if (!estadoId || !cidadesApiBase) return;
      try {
        var resp = await fetch(cidadesApiBase.replace('/0/', '/' + estadoId + '/'), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) return;
        var cities = await resp.json();
        cities.forEach(function(city) {
          var opt = document.createElement('option');
          opt.value = city.id;
          opt.textContent = city.nome;
          if (String(city.id) === String(selectedCidadeId || '')) opt.selected = true;
          cidadeSelect.appendChild(opt);
        });
      } catch (e) { /* silent */ }
    }

    function collectDestinos() {
      if (!destinosContainer || !destinoInput) return;
      var rows = Array.from(destinosContainer.querySelectorAll('.pt-dest-row'));
      var parts = [];
      rows.forEach(function(row) {
        var eSel = row.querySelector('.destino-estado');
        var cSel = row.querySelector('.destino-cidade');
        if (!eSel || !cSel || !eSel.value || !cSel.value) return;
        var eText = eSel.options[eSel.selectedIndex] ? eSel.options[eSel.selectedIndex].textContent : '';
        var cText = cSel.options[cSel.selectedIndex] ? cSel.options[cSel.selectedIndex].textContent : '';
        var sigla = /\(([^)]+)\)\s*$/.exec(eText);
        if (cText) parts.push(sigla ? cText + '/' + sigla[1] : cText);
      });
      destinoInput.value = parts.join(', ');
      var countBadges = document.querySelectorAll('[data-count-badge-destinos]');
      countBadges.forEach(function(b) { b.textContent = String(parts.length); });
      renderSummary();
    }

    async function addDestinoRow(dest) {
      if (!destinosContainer || !destinoRowTemplate) return;
      var d = dest || {};
      var clone = destinoRowTemplate.content.cloneNode(true);
      destinosContainer.appendChild(clone);
      var addedRow = destinosContainer.lastElementChild;
      if (!addedRow) return;
      var estadoSel = addedRow.querySelector('.destino-estado');
      var cidadeSel = addedRow.querySelector('.destino-cidade');
      if (estadoSel && d.estado_id) {
        estadoSel.value = String(d.estado_id);
        if (estadoSel.value && d.cidade_id) {
          await mountCidadeOptionsForRow(cidadeSel, estadoSel.value, d.cidade_id);
        }
      }
    }

    function bootstrapDestinos() {
      addDestinoRow({});
    }

    if (destinosContainer) {
      destinosContainer.addEventListener('change', async function(ev) {
        var row = ev.target.closest('.pt-dest-row');
        if (!row) return;
        if (ev.target.classList.contains('destino-estado')) {
          var cidadeSel = row.querySelector('.destino-cidade');
          await mountCidadeOptionsForRow(cidadeSel, ev.target.value, '');
        }
        collectDestinos();
      });
      destinosContainer.addEventListener('click', function(ev) {
        var btn = ev.target.closest('.btn-rem-destino');
        if (!btn) return;
        if (destinosContainer.querySelectorAll('.pt-dest-row').length <= 1) return;
        btn.closest('.pt-dest-row').remove();
        collectDestinos();
      });
    }
    if (addDestinoBtn) {
      addDestinoBtn.addEventListener('click', async function() {
        await addDestinoRow({});
        collectDestinos();
      });
    }

    function renderTravelerChips() {
      if (!viajantesChipList) return;
      Array.from(viajantesChipList.querySelectorAll('.oficio-selection-chip')).forEach(function(el) { el.remove(); });
      if (viajantesChipEmpty) viajantesChipEmpty.style.display = travelerSelected.size ? 'none' : '';
      travelerSelected.forEach(function(item, id) {
        var chip = document.createElement('div');
        chip.className = 'oficio-glance-chip oficio-selection-chip';
        chip.setAttribute('data-viajante-chip', id);
        var nomeEl = document.createElement('span');
        nomeEl.className = 'oficio-glance-chip-nome';
        nomeEl.textContent = item.nome || item.label || 'Servidor';
        chip.appendChild(nomeEl);
        var unidade = item.lotacao || item.unidade_lotacao || item.unidade_lotacao_nome;
        if (unidade) {
          var subEl = document.createElement('span');
          subEl.className = 'oficio-glance-chip-sub';
          subEl.textContent = typeof unidade === 'string' ? unidade : (unidade.nome || '');
          chip.appendChild(subEl);
        }
        if (!readOnly) {
          var removeBtn = document.createElement('button');
          removeBtn.type = 'button';
          removeBtn.className = 'oficio-selection-chip-remove';
          removeBtn.setAttribute('aria-label', 'Remover viajante');
          removeBtn.innerHTML = '&times;';
          (function(capturedId) {
            removeBtn.addEventListener('click', function() {
              travelerSelected.delete(capturedId);
              syncHiddenTravelers();
              renderTravelerChips();
              renderSummary();
            });
          }(id));
          chip.appendChild(removeBtn);
        }
        if (viajantesChipEmpty && viajantesChipEmpty.parentNode === viajantesChipList) {
          viajantesChipList.insertBefore(chip, viajantesChipEmpty);
        } else {
          viajantesChipList.appendChild(chip);
        }
      });
      if (viajantesChipCount) viajantesChipCount.textContent = String(travelerSelected.size);
    }

    function renderOficiosSelection() {
      if (!oficiosSelectionList || !oficiosEmptyText) {
        return;
      }
      oficiosSelectionList.innerHTML = '';
      var selected = selectedOficios();
      if (!selected.length) {
        oficiosEmptyText.classList.remove('d-none');
        return;
      }
      oficiosEmptyText.classList.add('d-none');

      selected.forEach(function(item) {
        var chip = document.createElement('span');
        chip.className = 'termo-selection-chip';

        var label = document.createElement('span');
        label.textContent = item.label || 'Oficio';
        chip.appendChild(label);

        if (!readOnly) {
          var removeButton = document.createElement('button');
          removeButton.type = 'button';
          removeButton.className = 'btn btn-sm border-0 bg-transparent text-danger p-0';
          removeButton.innerHTML = '&times;';
          removeButton.addEventListener('click', function() {
            Array.prototype.slice.call(oficiosSelect.options).forEach(function(option) {
              if (String(option.value) === String(item.id)) {
                option.selected = false;
              }
            });
            renderOficiosSelection();
            fetchPreview();
          });
          chip.appendChild(removeButton);
        }

        oficiosSelectionList.appendChild(chip);
      });

      var oficiosCount = document.querySelector('[data-count-badge-oficios]');
      if (oficiosCount) {
        oficiosCount.textContent = String(selected.length);
      }
    }

    function renderVehicleChip() {
      if (!veiculoChipContainer) return;
      Array.from(veiculoChipContainer.querySelectorAll('.oficio-selection-chip')).forEach(function(el) { el.remove(); });
      var hasVehicle = selectedVehicle && selectedVehicle.id;
      if (veiculoEmpty) veiculoEmpty.style.display = hasVehicle ? 'none' : '';
      if (veiculoCount) veiculoCount.textContent = hasVehicle ? '1' : '0';
      if (hasVehicle) {
        var chip = document.createElement('div');
        chip.className = 'oficio-glance-chip oficio-selection-chip';
        var nomeEl = document.createElement('span');
        nomeEl.className = 'oficio-glance-chip-nome';
        nomeEl.textContent = selectedVehicle.label || selectedVehicle.placa_formatada || selectedVehicle.modelo || 'Viatura';
        chip.appendChild(nomeEl);
        if (selectedVehicle.combustivel) {
          var subEl = document.createElement('span');
          subEl.className = 'oficio-glance-chip-sub';
          subEl.textContent = [selectedVehicle.combustivel, selectedVehicle.tipo_viatura_label].filter(Boolean).join(' • ');
          chip.appendChild(subEl);
        }
        if (!readOnly) {
          var removeBtn = document.createElement('button');
          removeBtn.type = 'button';
          removeBtn.className = 'oficio-selection-chip-remove';
          removeBtn.setAttribute('aria-label', 'Remover viatura');
          removeBtn.innerHTML = '&times;';
          removeBtn.addEventListener('click', function() {
            selectedVehicle = null;
            syncHiddenVehicle();
            renderVehicleChip();
            renderSummary();
          });
          chip.appendChild(removeBtn);
        }
        if (veiculoEmpty && veiculoEmpty.parentNode === veiculoChipContainer) {
          veiculoChipContainer.insertBefore(chip, veiculoEmpty);
        } else {
          veiculoChipContainer.appendChild(chip);
        }
      }
    }

    function renderSummary() {
      var travelerItems = Array.from(travelerSelected.values());
      var selectedOficiosList = selectedOficios();
      var modeKey = inferMode(travelerItems.length, Boolean(selectedVehicle && selectedVehicle.id));
      var modeMeta = MODE_META[modeKey];
      var estimatedTerms = travelerItems.length > 0 ? travelerItems.length : 1;
      var eventLabel = eventoSelect && eventoSelect.value
        ? eventoSelect.options[eventoSelect.selectedIndex].textContent.trim()
        : (latestPreview.evento && latestPreview.evento.label) || '-';
      var dataInicio = dataEventoInput ? dataEventoInput.value : '';
      var dataFim = (dataUnicaCheckbox && dataUnicaCheckbox.checked)
        ? dataInicio
        : (dataEventoFimInput ? dataEventoFimInput.value : '');
      var periodDisplay = buildPeriodoDisplay(dataInicio, dataFim, latestPreview.periodo_display);
      var destinosDisplay = (destinoInput && destinoInput.value) ? destinoInput.value : '-';

      setText('[data-compact-periodo]', periodDisplay || '-');
      setText('[data-compact-destinos]', destinosDisplay);
      setText('[data-compact-servidores]', String(travelerItems.length));
      setText('[data-compact-viaturas]', String(selectedVehicle && selectedVehicle.id ? 1 : (latestPreview.total_viaturas || 0)));
      setText('[data-inference-modelo]', modeMeta.label);
      setText('[data-inference-template]', modeMeta.template);
      setText('[data-inference-estimativa]', String(estimatedTerms));
      setText('[data-summary-template]', modeMeta.template);
      setText('[data-summary-periodo]', periodDisplay || '-');
      setText('[data-summary-estimativa]', String(estimatedTerms));
      setText('[data-summary-total-viajantes]', String(travelerItems.length));
      setText('[data-summary-evento]', eventLabel || '-');
      setText('[data-summary-evento-compact]', eventLabel || '-');
      setText('[data-summary-oficios]', selectedOficiosList.length ? String(selectedOficiosList.length) + ' selecionado(s)' : '-');
      setText('[data-summary-destinos]', destinosDisplay);
      setText('[data-summary-servidores]', String(travelerItems.length));
      setText('[data-summary-veiculo]', selectedVehicle && selectedVehicle.id ? (selectedVehicle.label || selectedVehicle.modelo || '-') : '-');
    }

    function clearTravelerSuggestions() {
      travelerSuggestionItems = [];
      travelerActiveIndex = -1;
      if (!viajantesResults) {
        return;
      }
      viajantesResults.innerHTML = '';
      viajantesResults.classList.add('d-none');
    }

    function setActiveTravelerSuggestion(index) {
      travelerActiveIndex = index;
      Array.prototype.forEach.call(
        viajantesResults ? viajantesResults.querySelectorAll('[data-suggestion-index]') : [],
        function(button, buttonIndex) {
          button.classList.toggle('active', buttonIndex === travelerActiveIndex);
        }
      );
    }

    function addSelectedTraveler(item) {
      if (!item || !item.id) {
        return;
      }
      var id = String(item.id);
      if (travelerSelected.has(id)) {
        clearTravelerSuggestions();
        if (viajantesInput) {
          viajantesInput.value = '';
          viajantesInput.focus();
        }
        return;
      }
      travelerSelected.set(id, item);
      syncHiddenTravelers();
      renderTravelerChips();
      renderSummary();
      clearTravelerSuggestions();
      if (viajantesInput) {
        viajantesInput.value = '';
        viajantesInput.focus();
      }
    }

    function renderTravelerSuggestions() {
      if (!viajantesResults) {
        return;
      }
      viajantesResults.innerHTML = '';
      if (!travelerSuggestionItems.length) {
        var emptyState = document.createElement('div');
        emptyState.className = 'list-group-item text-muted small';
        emptyState.textContent = 'Nenhum viajante encontrado.';
        viajantesResults.appendChild(emptyState);
        viajantesResults.classList.remove('d-none');
        return;
      }

      travelerSuggestionItems.forEach(function(item, index) {
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
        lotacaoRow.textContent = String(item.lotacao || '').trim() || 'Lotação não informada';
        button.appendChild(lotacaoRow);
        button.addEventListener('click', function() {
          addSelectedTraveler(item);
        });
        viajantesResults.appendChild(button);
      });
      viajantesResults.classList.remove('d-none');
      setActiveTravelerSuggestion(0);
    }

    async function searchTravelerSuggestions(term) {
      var searchUrl = viajantesWrapper ? viajantesWrapper.getAttribute('data-search-url') || '' : '';
      if (!searchUrl) {
        clearTravelerSuggestions();
        return;
      }
      var texto = String(term || '').trim();
      if (texto.length < 2) {
        clearTravelerSuggestions();
        return;
      }
      var sequence = ++travelerFetchSequence;
      try {
        var url = new URL(searchUrl, window.location.origin);
        url.searchParams.set('q', texto);
        var response = await fetch(url.toString(), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok || sequence !== travelerFetchSequence) {
          return;
        }
        var payload = await response.json();
        travelerSuggestionItems = (payload.results || []).filter(function(item) {
          return item && item.id && !travelerSelected.has(String(item.id));
        });
        renderTravelerSuggestions();
      } catch (error) {
        if (sequence === travelerFetchSequence) {
          clearTravelerSuggestions();
        }
      }
    }

    function debounceTravelerSearch() {
      window.clearTimeout(travelerDebounceTimer);
      travelerDebounceTimer = window.setTimeout(function() {
        searchTravelerSuggestions(viajantesInput ? viajantesInput.value : '');
      }, 180);
    }

    function clearVehicleSuggestions() {
      vehicleSuggestionItems = [];
      vehicleActiveIndex = -1;
      if (!veiculoResults) {
        return;
      }
      veiculoResults.innerHTML = '';
      veiculoResults.classList.add('d-none');
    }

    function setActiveVehicleSuggestion(index) {
      vehicleActiveIndex = index;
      Array.prototype.forEach.call(
        veiculoResults ? veiculoResults.querySelectorAll('[data-vehicle-suggestion]') : [],
        function(button, buttonIndex) {
          button.classList.toggle('active', buttonIndex === vehicleActiveIndex);
        }
      );
    }

    function applySelectedVehicle(item) {
      if (!item || !item.id) {
        return;
      }
      selectedVehicle = item;
      syncHiddenVehicle();
      renderVehicleChip();
      renderSummary();
      clearVehicleSuggestions();
      if (veiculoInput) {
        veiculoInput.value = '';
        veiculoInput.focus();
      }
    }

    function renderVehicleSuggestions() {
      if (!veiculoResults) {
        return;
      }
      veiculoResults.innerHTML = '';
      if (!vehicleSuggestionItems.length) {
        var emptyState = document.createElement('div');
        emptyState.className = 'list-group-item text-muted small';
        emptyState.textContent = 'Nenhuma viatura encontrada.';
        veiculoResults.appendChild(emptyState);
        veiculoResults.classList.remove('d-none');
        return;
      }
      vehicleSuggestionItems.forEach(function(item, index) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'list-group-item list-group-item-action oficio-viajante-result-item';
        button.setAttribute('data-vehicle-suggestion', String(index));

        var topRow = document.createElement('span');
        topRow.className = 'oficio-viajante-result-top';
        topRow.textContent = item.label || [item.placa_formatada || item.placa || '', item.modelo || 'Viatura'].filter(Boolean).join(' • ');
        button.appendChild(topRow);

        var bottomRow = document.createElement('span');
        bottomRow.className = 'oficio-viajante-result-bottom';
        bottomRow.textContent = [item.combustivel || '', item.tipo_viatura_label || ''].filter(Boolean).join(' • ') || 'Dados complementares não informados';
        button.appendChild(bottomRow);

        button.addEventListener('click', function() {
          applySelectedVehicle(item);
        });
        veiculoResults.appendChild(button);
      });
      veiculoResults.classList.remove('d-none');
      setActiveVehicleSuggestion(0);
    }

    async function searchVehicleSuggestions(term) {
      var searchUrl = veiculoWrapper ? veiculoWrapper.getAttribute('data-search-url') || '' : '';
      if (!searchUrl) {
        clearVehicleSuggestions();
        return;
      }
      var texto = String(term || '').trim();
      if (texto.length < 2) {
        clearVehicleSuggestions();
        return;
      }
      var sequence = ++vehicleFetchSequence;
      try {
        var url = new URL(searchUrl, window.location.origin);
        url.searchParams.set('q', texto);
        var response = await fetch(url.toString(), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok || sequence !== vehicleFetchSequence) {
          return;
        }
        var payload = await response.json();
        var currentVehicleId = selectedVehicle && selectedVehicle.id ? String(selectedVehicle.id) : '';
        vehicleSuggestionItems = (payload.results || []).filter(function(item) {
          return item && item.id && String(item.id) !== currentVehicleId;
        });
        renderVehicleSuggestions();
      } catch (error) {
        if (sequence === vehicleFetchSequence) {
          clearVehicleSuggestions();
        }
      }
    }

    function debounceVehicleSearch() {
      window.clearTimeout(vehicleDebounceTimer);
      vehicleDebounceTimer = window.setTimeout(function() {
        searchVehicleSuggestions(veiculoInput ? veiculoInput.value : '');
      }, 180);
    }

    function applyPreview(payload) {
      latestPreview = payload || latestPreview;
      var hasContext = Boolean(
        latestPreview.evento || (latestPreview.oficios && latestPreview.oficios.length)
      );

      if (hasContext) {
        if (dataEventoInput && latestPreview.data_evento) {
          dataEventoInput.value = latestPreview.data_evento;
        }
        if (dataEventoFimInput && latestPreview.data_evento_fim) {
          dataEventoFimInput.value = latestPreview.data_evento_fim;
        }
        toggleDataFim();
        var hasFilledRows = destinosContainer && Array.from(
          destinosContainer.querySelectorAll('.pt-dest-row')
        ).some(function(row) {
          var es = row.querySelector('.destino-estado');
          var cs = row.querySelector('.destino-cidade');
          return es && cs && es.value && cs.value;
        });
        if (!hasFilledRows && destinoInput) {
          var destinoText = latestPreview.destino ||
            (latestPreview.destinos || []).map(function(d) {
              return d.label || String(d);
            }).join(', ');
          if (destinoText) destinoInput.value = destinoText;
        }
      }

      if (!readOnly) {
        travelerSelected.clear();
        (latestPreview.viajantes || []).forEach(function(item) {
          travelerSelected.set(String(item.id), item);
        });
        if (latestPreview.veiculo_inferido && latestPreview.veiculo_inferido.id) {
          selectedVehicle = latestPreview.veiculo_inferido;
        } else if (!(latestPreview.total_viaturas > 1 && selectedVehicle && selectedVehicle.id)) {
          selectedVehicle = null;
        }
        syncHiddenTravelers();
        syncHiddenVehicle();
      }

      renderTravelerChips();
      renderVehicleChip();
      renderOficiosSelection();
      renderSummary();
    }

    async function fetchPreview() {
      if (readOnly || !previewUrl) {
        renderSummary();
        return;
      }
      var params = new URLSearchParams();
      if (eventoSelect && eventoSelect.value) {
        params.set('evento', eventoSelect.value);
      }
      selectedOptionValues(oficiosSelect).forEach(function(value) {
        params.append('oficios', value);
      });
      try {
        var response = await fetch(previewUrl + '?' + params.toString(), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok) {
          return;
        }
        applyPreview(await response.json());
      } catch (error) {
        renderSummary();
      }
    }

    if (viajantesInput && !readOnly) {
      viajantesInput.addEventListener('input', debounceTravelerSearch);
      viajantesInput.addEventListener('focus', function() {
        if ((viajantesInput.value || '').trim().length >= 2) {
          debounceTravelerSearch();
        }
      });
      viajantesInput.addEventListener('keydown', function(event) {
        if (!travelerSuggestionItems.length) {
          return;
        }
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          setActiveTravelerSuggestion(Math.min(travelerSuggestionItems.length - 1, travelerActiveIndex + 1));
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          setActiveTravelerSuggestion(Math.max(0, travelerActiveIndex - 1));
          return;
        }
        if (event.key === 'Enter' || event.key === 'Tab') {
          if (travelerActiveIndex >= 0 && travelerSuggestionItems[travelerActiveIndex]) {
            event.preventDefault();
            addSelectedTraveler(travelerSuggestionItems[travelerActiveIndex]);
          }
          return;
        }
        if (event.key === 'Escape') {
          clearTravelerSuggestions();
        }
      });
    }

    if (veiculoInput && !readOnly) {
      veiculoInput.addEventListener('input', debounceVehicleSearch);
      veiculoInput.addEventListener('focus', function() {
        if ((veiculoInput.value || '').trim().length >= 2) {
          debounceVehicleSearch();
        }
      });
      veiculoInput.addEventListener('keydown', function(event) {
        if (!vehicleSuggestionItems.length) {
          return;
        }
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          setActiveVehicleSuggestion(Math.min(vehicleSuggestionItems.length - 1, vehicleActiveIndex + 1));
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          setActiveVehicleSuggestion(Math.max(0, vehicleActiveIndex - 1));
          return;
        }
        if (event.key === 'Enter' || event.key === 'Tab') {
          if (vehicleActiveIndex >= 0 && vehicleSuggestionItems[vehicleActiveIndex]) {
            event.preventDefault();
            applySelectedVehicle(vehicleSuggestionItems[vehicleActiveIndex]);
          }
          return;
        }
        if (event.key === 'Escape') {
          clearVehicleSuggestions();
        }
      });
    }

    document.addEventListener('click', function(event) {
      if (viajantesWrapper && !viajantesWrapper.contains(event.target)) {
        clearTravelerSuggestions();
      }
      if (veiculoWrapper && !veiculoWrapper.contains(event.target)) {
        clearVehicleSuggestions();
      }
    });

    if (eventoSelect && !readOnly) {
      eventoSelect.addEventListener('change', async function() {
        await filterOficiosByEvento(eventoSelect.value);
        fetchPreview();
      });
    }

    if (oficiosSelect && !readOnly) {
      oficiosSelect.addEventListener('change', fetchPreview);
    }

    if (oficiosSelect && !readOnly) {
      oficiosSelect.addEventListener('mousedown', function(event) {
        var option = event.target;
        if (!option || option.tagName !== 'OPTION') {
          return;
        }
        event.preventDefault();
        option.selected = !option.selected;
        renderOficiosSelection();
        fetchPreview();
      });
    }

    if (dataUnicaCheckbox) {
      dataUnicaCheckbox.addEventListener('change', function() {
        toggleDataFim();
        renderSummary();
      });
    }

    if (dataEventoInput) {
      dataEventoInput.addEventListener('change', function() {
        toggleDataFim();
        renderSummary();
      });
    }

    if (dataEventoFimInput) {
      dataEventoFimInput.addEventListener('change', renderSummary);
    }

    syncHiddenTravelers();
    syncHiddenVehicle();
    toggleDataFim();
    bootstrapDestinos();
    renderTravelerChips();
    renderVehicleChip();
    renderOficiosSelection();
    renderSummary();
    fetchPreview();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTermsForm);
  } else {
    initTermsForm();
  }
})();
