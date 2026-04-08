(function() {
  var form = document.querySelector('[data-evento-etapa1]');
  if (!form) {
    return;
  }

  var apiCidadesUrl = form.getAttribute('data-api-cidades-url') || '';
  var estadoPrId = form.getAttribute('data-estado-pr-id') || '';
  var tipoOutrosPk = form.getAttribute('data-tipo-outros-pk') || '';

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
  var wrapDescricao = document.getElementById('wrap-descricao');
  var destinosContainer = document.getElementById('destinos-container');
  var btnAdicionarDestino = document.getElementById('btn-adicionar-destino');

  function getCidadesUrl(estadoId) {
    return apiCidadesUrl.replace(/\/0\/?$/, '/' + String(estadoId) + '/');
  }

  function setStateLabel(node, enabled, onText, offText) {
    if (!node) {
      return;
    }
    node.textContent = enabled ? onText : offText;
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
    var cards = form.querySelectorAll('[data-demand-card]');
    cards.forEach(function(card) {
      var input = card.querySelector('input[name="tipos_demanda"]');
      card.classList.toggle('is-selected', !!(input && input.checked));
    });
  }

  function updateDataUnica() {
    if (!dataUnicaInput || !dataFimInput) {
      return;
    }

    var active = !!dataUnicaInput.checked;
    setStateLabel(dataUnicaState, active, 'LIGADA', 'DESLIGADA');

    dataFimInput.readOnly = active;
    dataFimInput.classList.toggle('is-locked', active);

    if (active && dataInicioInput) {
      dataFimInput.value = dataInicioInput.value;
    }
  }

  function updateConvite() {
    if (!conviteInput) {
      return;
    }
    setStateLabel(conviteState, !!conviteInput.checked, 'SIM', 'NÃO');
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
        loadCidadesForSelect(cidadeSelect, estadoSelect.value, selectedCidadeId);
      }

      estadoSelect.addEventListener('change', function() {
        cidadeSelect.removeAttribute('data-cidade-id');
        loadCidadesForSelect(cidadeSelect, estadoSelect.value, null);
      });
    }

    if (removeButton) {
      removeButton.addEventListener('click', function() {
        var rows = destinosContainer.querySelectorAll('[data-destino-row]');
        if (rows.length <= 1) {
          return;
        }
        row.remove();
      });
    }
  }

  function buildEstadosOptions(selectedId) {
    var html = '<option value="">Selecione</option>';
    estadosOptions.forEach(function(estado) {
      var selected = String(estado.id) === String(selectedId) ? ' selected' : '';
      html += '<option value="' + estado.id + '"' + selected + '>' + estado.nome + ' (' + estado.sigla + ')</option>';
    });
    return html;
  }

  function createDestinoRow() {
    var index = nextDestinoIndex();
    var row = document.createElement('div');
    row.className = 'evento-destino-row';
    row.setAttribute('data-destino-row', '1');
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
  }

  form.querySelectorAll('input[name="tipos_demanda"]').forEach(function(input) {
    input.addEventListener('change', function() {
      updateDemandCards();
      toggleDescricao();
    });
  });

  if (dataUnicaInput) {
    dataUnicaInput.addEventListener('change', updateDataUnica);
  }
  if (dataInicioInput) {
    dataInicioInput.addEventListener('change', function() {
      if (dataUnicaInput && dataUnicaInput.checked && dataFimInput) {
        dataFimInput.value = dataInicioInput.value;
      }
    });
  }
  if (conviteInput) {
    conviteInput.addEventListener('change', updateConvite);
  }

  if (btnAdicionarDestino) {
    btnAdicionarDestino.addEventListener('click', createDestinoRow);
  }

  destinosContainer.querySelectorAll('[data-destino-row]').forEach(bindDestinoRow);

  updateDemandCards();
  toggleDescricao();
  updateDataUnica();
  updateConvite();
})();
