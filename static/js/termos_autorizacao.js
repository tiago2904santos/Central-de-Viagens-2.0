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

  function createSuggestionButton(item, onSelect) {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'list-group-item list-group-item-action';
    button.textContent = item.label || item.nome || item.modelo || 'Selecionar';
    button.addEventListener('click', function() {
      onSelect(item);
    });
    return button;
  }

  function setText(selector, value) {
    var element = document.querySelector(selector);
    if (element) {
      element.textContent = value || '-';
    }
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
    var eventoSelect = document.getElementById('id_evento');
    var oficiosSelect = document.getElementById('id_oficios');
    var roteiroSelect = document.getElementById('id_roteiro');
    var oficiosSelectionList = document.querySelector('[data-oficios-selection-list]');
    var oficiosEmptyText = document.querySelector('[data-oficios-empty-text]');
    var destinoInput = document.getElementById('id_destino');
    var dataEventoInput = document.getElementById('id_data_evento');
    var dataEventoFimInput = document.getElementById('id_data_evento_fim');
    var hiddenTravelersInput = document.querySelector('input[name="viajantes_ids"]');
    var hiddenVehicleInput = document.querySelector('input[name="veiculo_id"]');
    var travelerWrapper = document.querySelector('.termo-autocomplete[data-type="traveler"]');
    var vehicleWrapper = document.querySelector('.termo-autocomplete[data-type="vehicle"]');
    var travelerSelected = new Map();
    var selectedVehicle = parseJsonScript('termo-selected-veiculo', null);
    var latestPreview = parseJsonScript('termo-preview-payload', {
      evento: null,
      oficios: [],
      roteiro: null,
      destinos: [],
      destino: '',
      periodo_display: '-',
      total_viaturas: 0,
      veiculos: []
    });

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

    function renderTravelerSelection() {
      if (!travelerWrapper) {
        return;
      }
      var selectionList = travelerWrapper.querySelector('[data-selection-list]');
      var emptyText = travelerWrapper.querySelector('[data-empty-text]');
      var countBadge = document.querySelector('[data-count-badge-travelers]');
      selectionList.innerHTML = '';
      if (!travelerSelected.size) {
        emptyText.classList.remove('d-none');
      } else {
        emptyText.classList.add('d-none');
      }
      travelerSelected.forEach(function(item, id) {
        var chip = document.createElement('span');
        chip.className = 'termo-selection-chip';

        var label = document.createElement('span');
        label.textContent = item.nome || item.label || 'Servidor';
        chip.appendChild(label);

        if (!readOnly) {
          var removeButton = document.createElement('button');
          removeButton.type = 'button';
          removeButton.className = 'btn btn-sm border-0 bg-transparent text-danger p-0';
          removeButton.innerHTML = '&times;';
          removeButton.addEventListener('click', function() {
            travelerSelected.delete(id);
            syncHiddenTravelers();
            renderTravelerSelection();
            renderSummary();
          });
          chip.appendChild(removeButton);
        }

        selectionList.appendChild(chip);
      });
      if (countBadge) {
        countBadge.textContent = String(travelerSelected.size);
      }
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
    }

    function renderVehicleSelection() {
      if (!vehicleWrapper) {
        return;
      }
      var selectionList = vehicleWrapper.querySelector('[data-selection-list]');
      var emptyText = vehicleWrapper.querySelector('[data-empty-text]');
      selectionList.innerHTML = '';
      if (!selectedVehicle || !selectedVehicle.id) {
        emptyText.classList.remove('d-none');
        return;
      }
      emptyText.classList.add('d-none');
      var chip = document.createElement('div');
      chip.className = 'termo-selection-chip termo-selection-chip--single';
      chip.innerHTML = '<span>' + (selectedVehicle.label || selectedVehicle.modelo || 'Viatura') + '</span>';
      if (!readOnly) {
        var removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.className = 'btn btn-sm border-0 bg-transparent text-danger p-0';
        removeButton.innerHTML = '&times;';
        removeButton.addEventListener('click', function() {
          selectedVehicle = null;
          syncHiddenVehicle();
          renderVehicleSelection();
          renderSummary();
        });
        chip.appendChild(removeButton);
      }
      selectionList.appendChild(chip);
    }

    function renderSummary() {
      var travelerItems = Array.from(travelerSelected.values());
      var selectedOficiosList = selectedOficios();
      var modeKey = inferMode(travelerItems.length, Boolean(selectedVehicle && selectedVehicle.id));
      var modeMeta = MODE_META[modeKey];
      var estimatedTerms = travelerItems.length > 0 ? travelerItems.length : 1;

      setText('[data-compact-periodo]', latestPreview.periodo_display || '-');
      setText('[data-compact-destinos]', latestPreview.destinos && latestPreview.destinos.length ? latestPreview.destinos.join(', ') : '-');
      setText('[data-compact-servidores]', String(travelerItems.length));
      setText('[data-compact-viaturas]', String(latestPreview.total_viaturas || 0));
      setText('[data-inference-modelo]', modeMeta.label);
      setText('[data-inference-template]', modeMeta.template);
      setText('[data-inference-estimativa]', String(estimatedTerms));

      if (oficiosEmptyText) {
        if (selectedOficiosList.length) {
          oficiosEmptyText.classList.add('d-none');
        } else {
          oficiosEmptyText.classList.remove('d-none');
        }
      }
    }

    function applyPreview(payload) {
      latestPreview = payload || latestPreview;
      var hasContext = Boolean(
        latestPreview.evento ||
        (latestPreview.oficios && latestPreview.oficios.length) ||
        latestPreview.roteiro
      );

      if (hasContext) {
        if (destinoInput) {
          destinoInput.value = latestPreview.destino || '';
        }
        if (dataEventoInput) {
          dataEventoInput.value = latestPreview.data_evento || '';
        }
        if (dataEventoFimInput) {
          dataEventoFimInput.value = latestPreview.data_evento_fim || '';
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

      renderTravelerSelection();
      renderVehicleSelection();
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
      if (roteiroSelect && roteiroSelect.value) {
        params.set('roteiro', roteiroSelect.value);
      }
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

    function attachAutocomplete(wrapper, onSelect, currentItemsGetter) {
      if (!wrapper || readOnly) {
        return;
      }
      var input = wrapper.querySelector('.termo-autocomplete-input');
      var results = wrapper.querySelector('.termo-autocomplete-results');
      var searchUrl = wrapper.getAttribute('data-search-url') || '';
      var debounceTimer = null;

      function renderResults(items) {
        if (!results) {
          return;
        }
        results.innerHTML = '';
        if (!items.length) {
          results.classList.add('d-none');
          return;
        }
        items.forEach(function(item) {
          if (currentItemsGetter().some(function(current) { return String(current.id) === String(item.id); })) {
            return;
          }
          results.appendChild(
            createSuggestionButton(item, function(choice) {
              onSelect(choice);
              input.value = '';
              results.classList.add('d-none');
            })
          );
        });
        if (!results.childNodes.length) {
          results.classList.add('d-none');
          return;
        }
        results.classList.remove('d-none');
      }

      async function fetchSuggestions(query) {
        if (!query || !searchUrl) {
          renderResults([]);
          return;
        }
        try {
          var response = await fetch(searchUrl + '?q=' + encodeURIComponent(query), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
          });
          if (!response.ok) {
            return;
          }
          var data = await response.json();
          renderResults(data.results || []);
        } catch (error) {
          renderResults([]);
        }
      }

      input.addEventListener('input', function() {
        window.clearTimeout(debounceTimer);
        debounceTimer = window.setTimeout(function() {
          fetchSuggestions(input.value.trim());
        }, 180);
      });

      input.addEventListener('blur', function() {
        window.setTimeout(function() {
          if (results) {
            results.classList.add('d-none');
          }
        }, 150);
      });
    }

    attachAutocomplete(travelerWrapper, function(choice) {
      travelerSelected.set(String(choice.id), choice);
      syncHiddenTravelers();
      renderTravelerSelection();
      renderSummary();
    }, function() {
      return Array.from(travelerSelected.values());
    });

    attachAutocomplete(vehicleWrapper, function(choice) {
      selectedVehicle = choice;
      syncHiddenVehicle();
      renderVehicleSelection();
      renderSummary();
    }, function() {
      return selectedVehicle ? [selectedVehicle] : [];
    });

    [eventoSelect, oficiosSelect, roteiroSelect].forEach(function(field) {
      if (!field || readOnly) {
        return;
      }
      field.addEventListener('change', fetchPreview);
    });

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

    syncHiddenTravelers();
    syncHiddenVehicle();
    renderTravelerSelection();
    renderVehicleSelection();
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
