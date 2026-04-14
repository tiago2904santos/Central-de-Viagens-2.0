(function() {
  var form = document.querySelector('[data-evento-etapa1]');
  if (!form) {
    return;
  }

  var apiCidadesUrl = form.getAttribute('data-api-cidades-url') || '';
  var estadoPrId = form.getAttribute('data-estado-pr-id') || '';
  var tipoOutrosPk = form.getAttribute('data-tipo-outros-pk') || '';
  var headingFallback = form.getAttribute('data-evento-heading-fallback') || '';
  var baseCidade = form.getAttribute('data-evento-base-cidade') || '';
  var baseUf = form.getAttribute('data-evento-base-uf') || '';

  var estadosOptions = [];
  try {
    estadosOptions = JSON.parse(form.getAttribute('data-estados-json') || '[]');
  } catch (error) {
    estadosOptions = [];
  }

  var dataUnicaInput = document.getElementById('id_data_unica');
  var dataInicioInput = document.getElementById('id_data_inicio');
  var dataFimInput = document.getElementById('id_data_fim');
  var dataUnicaState = form.querySelector('[data-data-unica-state]');
  var conviteInput = document.getElementById('id_tem_convite_ou_oficio_evento');
  var conviteState = form.querySelector('[data-convite-state]');
  var conviteUploadWrap = form.querySelector('[data-convite-upload-wrap]');
  var conviteFilesInput = document.getElementById('id_convite_documentos');
  var hasConviteAnexos = form.getAttribute('data-has-convite-anexos') === '1';
  var wrapDescricao = document.getElementById('wrap-descricao');
  var destinosContainer = document.getElementById('destinos-container');
  var btnAdicionarDestino = document.getElementById('btn-adicionar-destino');
  var autosaveStatus = document.getElementById('evento-etapa1-autosave-status');

  function getWizard() {
    return window.OficioWizard && typeof window.OficioWizard.setGlanceValue === 'function' ? window.OficioWizard : null;
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

  function getSelectedText(select) {
    if (!select) {
      return '';
    }
    var option = select.options && select.selectedIndex >= 0 ? select.options[select.selectedIndex] : null;
    var text = option ? String(option.textContent || '').trim() : '';
    return text && text !== 'Selecione' ? text : '';
  }

  function getEstadoUf(select) {
    var text = getSelectedText(select);
    if (!text) {
      return '';
    }
    var match = text.match(/\(([^)]+)\)\s*$/);
    if (match && match[1]) {
      return match[1].trim();
    }
    return text;
  }

  function getSelectedTiposLabels() {
    var labels = [];
    form.querySelectorAll('input[name="tipos_demanda"]:checked').forEach(function(input) {
      var card = input.closest('[data-demand-card]');
      var labelNode = card ? card.querySelector('strong') : null;
      var label = labelNode ? String(labelNode.textContent || '').trim() : '';
      if (label) {
        labels.push(label);
      }
    });
    return labels;
  }

  function getDestinos() {
    var destinos = [];
    destinosContainer.querySelectorAll('[data-destino-row]').forEach(function(row) {
      var isPlaceholder = row.getAttribute('data-destino-placeholder') === '1';
      var estadoSelect = row.querySelector('.destino-estado');
      var cidadeSelect = row.querySelector('.destino-cidade');
      var cidadeText = getSelectedText(cidadeSelect);
      var estadoUf = getEstadoUf(estadoSelect);
      var estadoText = getSelectedText(estadoSelect);
      if (isPlaceholder && !cidadeText && !estadoText) {
        return;
      }
      if (isPlaceholder && !cidadeText && estadoSelect && String(estadoSelect.value || '') === String(estadoPrId || '')) {
        return;
      }
      if (cidadeText && estadoUf) {
        destinos.push(cidadeText + '/' + estadoUf);
      } else if (estadoText) {
        destinos.push(estadoText + ' / cidade a definir');
      }
    });
    return destinos;
  }

  function buildDestinoHeading() {
    var destinos = getDestinos();
    if (!destinos.length) {
      if (baseCidade && baseUf) {
        return baseCidade + '/' + baseUf;
      }
      if (baseCidade) {
        return baseCidade;
      }
      return 'Destino a definir';
    }
    if (destinos.length === 1) {
      return destinos[0];
    }
    if (destinos.length === 2) {
      return destinos[0] + ' e ' + destinos[1];
    }
    return destinos[0] + ' + ' + (destinos.length - 1) + ' destino(s)';
  }

  function buildPeriodoLabel() {
    if (!dataInicioInput || !dataInicioInput.value) {
      return 'Período a definir';
    }
    var inicio = parseDateParts(dataInicioInput.value);
    if (!inicio) {
      return 'Período a definir';
    }
    var fim = dataFimInput && dataFimInput.value ? parseDateParts(dataFimInput.value) : '';
    if (dataUnicaInput && dataUnicaInput.checked) {
      return inicio;
    }
    if (fim && fim !== inicio) {
      return inicio + ' a ' + fim;
    }
    return inicio;
  }

  function buildHeadingLabel() {
    var periodo = buildPeriodoLabel();
    var destino = buildDestinoHeading();
    if (!periodo || periodo === 'Período a definir') {
      return headingFallback || 'Evento';
    }
    return 'Evento ' + destino + ' - ' + periodo;
  }

  function updateHeaderSummary() {
    var wizard = getWizard();
    if (!wizard) {
      return;
    }
    var tiposLabel = getSelectedTiposLabels().join(' / ');
    wizard.setGlanceValue('guiado-etapa1-heading', buildHeadingLabel());
    wizard.setGlanceValue('guiado-etapa1-periodo', buildPeriodoLabel());
    wizard.setGlanceValue('guiado-etapa1-tipos', tiposLabel || 'Tipo a definir');
    wizard.setGlanceValue('guiado-etapa1-destinos', buildDestinoHeading());
  }

  var autosave = window.OficioWizard && typeof window.OficioWizard.createAutosave === 'function'
    ? window.OficioWizard.createAutosave({
        form: form,
        statusElement: autosaveStatus,
        shouldSchedule: shouldScheduleAutosave
      })
    : null;

  function scheduleAutosave() {
    if (autosave) {
      autosave.schedule();
    }
  }

  function shouldScheduleAutosave(event) {
    var target = event && event.target;
    if (!target) {
      return true;
    }
    if (target.classList && target.classList.contains('destino-estado')) {
      return false;
    }
    if (target.classList && target.classList.contains('destino-cidade')) {
      var row = target.closest('[data-destino-row]');
      var estadoSelect = row ? row.querySelector('.destino-estado') : null;
      return !!(estadoSelect && estadoSelect.value && target.value);
    }
    return true;
  }

  function getCidadesUrl(estadoId) {
    return apiCidadesUrl.replace(/\/0\/?$/, '/' + String(estadoId) + '/');
  }

  function toggleDescricao() {
    if (!wrapDescricao) {
      return;
    }
    var show = false;
    if (tipoOutrosPk) {
      var outrosInput = document.getElementById('id_tipos_demanda_' + tipoOutrosPk);
      show = !!(outrosInput && outrosInput.checked);
    }
    wrapDescricao.classList.toggle('d-none', !show);
  }

  function updateDemandCards() {
    form.querySelectorAll('[data-demand-card]').forEach(function(card) {
      var input = card.querySelector('input[name="tipos_demanda"]');
      card.classList.toggle('is-selected', !!(input && input.checked));
    });
  }

  function updateDataUnica() {
    if (!dataUnicaInput || !dataFimInput) {
      return;
    }

    var active = !!dataUnicaInput.checked;
    setStatusLabel(dataUnicaState, active, 'LIGADA', 'DESLIGADA');

    dataFimInput.readOnly = active;
    dataFimInput.classList.toggle('is-locked', active);

    if (active && dataInicioInput) {
      dataFimInput.value = dataInicioInput.value;
    }
    updateHeaderSummary();
  }

  function updateConvite() {
    if (!conviteInput) {
      return;
    }
    var temUploadSelecionado = !!(conviteFilesInput && conviteFilesInput.files && conviteFilesInput.files.length);
    var ativo = !!conviteInput.checked || hasConviteAnexos || temUploadSelecionado;
    setStatusLabel(conviteState, ativo, 'SIM', 'NÃO');
    if (conviteUploadWrap) {
      conviteUploadWrap.classList.toggle('d-none', !ativo);
    }
    updateHeaderSummary();
  }

  function loadCidadesForSelect(selectCidade, estadoId, selectedCidadeId) {
    if (!selectCidade) {
      return Promise.resolve();
    }

    selectCidade.innerHTML = '<option value="">Selecione</option>';

    if (!estadoId) {
      selectCidade.disabled = true;
      return Promise.resolve();
    }

    selectCidade.disabled = true;
    return fetch(getCidadesUrl(estadoId), {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function(response) {
        if (!response.ok) {
          throw new Error('Falha ao carregar cidades');
        }
        return response.json();
      })
      .then(function(payload) {
        var cidades = Array.isArray(payload) ? payload : (payload.cidades || []);
        cidades.forEach(function(cidade) {
          var option = document.createElement('option');
          option.value = String(cidade.id);
          option.textContent = cidade.nome;
          if (selectedCidadeId && String(selectedCidadeId) === String(cidade.id)) {
            option.selected = true;
          }
          selectCidade.appendChild(option);
        });
      })
      .catch(function() {
        selectCidade.innerHTML = '<option value="">Selecione</option>';
      })
      .finally(function() {
        selectCidade.disabled = false;
      });
  }

  function nextDestinoIndex() {
    var max = -1;
    destinosContainer.querySelectorAll('.destino-estado').forEach(function(select) {
      var match = (select.name || '').match(/destino_estado_(\d+)/);
      if (match) {
        max = Math.max(max, parseInt(match[1], 10));
      }
    });
    return max + 1;
  }

  function buildEstadosOptions(selectedId) {
    var html = '<option value="">Selecione</option>';
    estadosOptions.forEach(function(estado) {
      var selected = String(estado.id) === String(selectedId) ? ' selected' : '';
      html += '<option value="' + estado.id + '"' + selected + '>' + estado.nome + ' (' + estado.sigla + ')</option>';
    });
    return html;
  }

  function bindDestinoRow(row) {
    if (!row) {
      return;
    }

    var estadoSelect = row.querySelector('.destino-estado');
    var cidadeSelect = row.querySelector('.destino-cidade');
    var removeButton = row.querySelector('.btn-remover-destino');

    var selectedCidadeId = cidadeSelect ? cidadeSelect.getAttribute('data-cidade-id') : '';

    if (estadoSelect && !estadoSelect.value && estadoPrId) {
      estadoSelect.value = estadoPrId;
    }

    if (estadoSelect && cidadeSelect) {
      if (estadoSelect.value) {
        loadCidadesForSelect(cidadeSelect, estadoSelect.value, selectedCidadeId).finally(updateHeaderSummary);
      }

      estadoSelect.addEventListener('change', function() {
        row.setAttribute('data-destino-placeholder', '0');
        cidadeSelect.removeAttribute('data-cidade-id');
        loadCidadesForSelect(cidadeSelect, estadoSelect.value, null).finally(updateHeaderSummary);
        updateHeaderSummary();
      });
    }

    if (cidadeSelect) {
      cidadeSelect.addEventListener('change', function() {
        updateHeaderSummary();
        scheduleAutosave();
      });
    }

    if (removeButton) {
      removeButton.addEventListener('click', function() {
        var rows = destinosContainer.querySelectorAll('[data-destino-row]');
        if (rows.length <= 1) {
          return;
        }
        row.remove();
        updateHeaderSummary();
        scheduleAutosave();
      });
    }
  }

  function createDestinoRow() {
    var index = nextDestinoIndex();
    var row = document.createElement('div');
    row.className = 'evento-destino-row';
    row.setAttribute('data-destino-row', '1');
    row.setAttribute('data-destino-placeholder', '0');
    row.innerHTML =
      '<div class="evento-destino-field evento-destino-field--uf">' +
        '<label>ESTADO</label>' +
        '<select name="destino_estado_' + index + '" class="destino-estado form-select">' + buildEstadosOptions(estadoPrId || '') + '</select>' +
      '</div>' +
      '<div class="evento-destino-field evento-destino-field--cidade">' +
        '<label>CIDADE</label>' +
        '<select name="destino_cidade_' + index + '" class="destino-cidade form-select">' +
          '<option value="">Selecione</option>' +
        '</select>' +
      '</div>' +
      '<div class="evento-destino-remove">' +
        '<button type="button" class="btn btn-remover-destino" title="Remover destino">&times;</button>' +
      '</div>';

    destinosContainer.appendChild(row);
    bindDestinoRow(row);
    updateHeaderSummary();
  }

  form.querySelectorAll('input[name="tipos_demanda"]').forEach(function(input) {
    input.addEventListener('change', function() {
      updateDemandCards();
      toggleDescricao();
      updateHeaderSummary();
      scheduleAutosave();
    });
  });

  if (dataUnicaInput) {
    dataUnicaInput.addEventListener('change', function() {
      updateDataUnica();
      scheduleAutosave();
    });
  }
  if (dataInicioInput) {
    dataInicioInput.addEventListener('change', function() {
      if (dataUnicaInput && dataUnicaInput.checked && dataFimInput) {
        dataFimInput.value = dataInicioInput.value;
      }
      updateHeaderSummary();
      scheduleAutosave();
    });
  }
  if (dataFimInput) {
    dataFimInput.addEventListener('change', function() {
      updateHeaderSummary();
      scheduleAutosave();
    });
  }
  if (conviteInput) {
    conviteInput.addEventListener('change', function() {
      updateConvite();
      scheduleAutosave();
    });
  }
  if (conviteFilesInput) {
    conviteFilesInput.addEventListener('change', function() {
      if (conviteFilesInput.files && conviteFilesInput.files.length && conviteInput) {
        conviteInput.checked = true;
      }
      updateConvite();
      scheduleAutosave();
    });
  }

  if (btnAdicionarDestino) {
    btnAdicionarDestino.addEventListener('click', function() {
      createDestinoRow();
    });
  }

  destinosContainer.querySelectorAll('[data-destino-row]').forEach(bindDestinoRow);

  updateDemandCards();
  toggleDescricao();
  updateDataUnica();
  updateConvite();
  updateHeaderSummary();
})();
