(function () {
  'use strict';

  function toggleBySelect(selectId, targetId, valueToShow) {
    var select = document.getElementById(selectId);
    var target = document.getElementById(targetId);
    if (!select || !target) return;
    target.classList.toggle('d-none', select.value !== valueToShow);
  }

  function initStep1() {
    var custeioProprio = document.getElementById('custeio_proprio');
    var custeioExterno = document.getElementById('custeio_externo');
    var instituicao = document.getElementById('div_instituicao');

    function toggleCusteio() {
      if (!instituicao || !custeioExterno) return;
      instituicao.classList.toggle('d-none', !custeioExterno.checked);
    }

    if (custeioProprio) custeioProprio.addEventListener('change', toggleCusteio);
    if (custeioExterno) custeioExterno.addEventListener('change', toggleCusteio);
    toggleCusteio();

    var eventoSelect = document.getElementById('id_evento_id');
    if (eventoSelect) {
      eventoSelect.addEventListener('change', function () {
        toggleBySelect('id_evento_id', 'div_novo_evento', 'novo');
      });
      toggleBySelect('id_evento_id', 'div_novo_evento', 'novo');
    }

    var buscaViajante = document.getElementById('busca_viajante');
    if (buscaViajante) {
      buscaViajante.addEventListener('input', function () {
        var q = this.value.toLowerCase();
        document.querySelectorAll('.viajante-item').forEach(function (el) {
          el.classList.toggle('d-none', !el.dataset.nome.includes(q));
        });
      });
    }

    var modeloMotivo = document.getElementById('id_modelo_motivo');
    if (modeloMotivo) {
      modeloMotivo.addEventListener('change', function () {
        var opt = this.options[this.selectedIndex];
        var texto = opt ? opt.dataset.texto : '';
        if (!texto) return;
        var ta = document.getElementById('id_motivo');
        if (ta && !ta.value) ta.value = texto;
      });
    }
  }

  function initStep2() {
    var select = document.getElementById('id_veiculo_id');
    var manual = document.getElementById('div_veiculo_manual');
    if (!select || !manual) return;
    function sync() {
      manual.classList.toggle('d-none', !!select.value);
    }
    select.addEventListener('change', sync);
    sync();
  }

  function initStep3() {
    var radios = document.querySelectorAll('input[name="roteiro_opcao"]');
    var existente = document.getElementById('div_roteiro_existente');
    var novo = document.getElementById('div_roteiro_novo');

    function selectedValue() {
      var checked = document.querySelector('input[name="roteiro_opcao"]:checked');
      return checked ? checked.value : 'nenhum';
    }

    function toggleRoteiro() {
      var val = selectedValue();
      if (existente) existente.classList.toggle('d-none', val !== 'existente');
      if (novo) novo.classList.toggle('d-none', val !== 'novo');
    }

    radios.forEach(function (radio) {
      radio.addEventListener('change', toggleRoteiro);
    });
    toggleRoteiro();

    var trechosContainer = document.getElementById('trechos_container');
    if (!trechosContainer) return;

    function reindexTrechos() {
      trechosContainer.querySelectorAll('.trecho-row').forEach(function (row, i) {
        var cb = row.querySelector('input[name="trecho_retorno"]');
        if (cb) cb.value = String(i + 1);
      });
    }

    function trechoTemplate(idx) {
      return '<div class="row g-2 mb-3 trecho-row border rounded p-2">' +
        '<div class="col-md-3"><label class="form-label small">Origem</label><input type="text" name="trecho_origem" class="form-control form-control-sm"></div>' +
        '<div class="col-md-3"><label class="form-label small">Destino</label><input type="text" name="trecho_destino" class="form-control form-control-sm"></div>' +
        '<div class="col-md-2"><label class="form-label small">Data saída</label><input type="date" name="trecho_data_saida" class="form-control form-control-sm"></div>' +
        '<div class="col-md-2"><label class="form-label small">Data chegada</label><input type="date" name="trecho_data_chegada" class="form-control form-control-sm"></div>' +
        '<div class="col-md-1 d-flex align-items-end"><div class="form-check"><input class="form-check-input" type="checkbox" name="trecho_retorno" value="' + idx + '"><label class="form-check-label small">Retorno</label></div></div>' +
        '<div class="col-md-1 d-flex align-items-end"><button type="button" class="btn btn-sm btn-outline-danger" data-trecho-remove="1"><i class="bi bi-trash"></i></button></div>' +
        '</div>';
    }

    var addButton = document.querySelector('[data-trecho-add="1"]');
    if (addButton) {
      addButton.addEventListener('click', function () {
        var idx = trechosContainer.querySelectorAll('.trecho-row').length + 1;
        trechosContainer.insertAdjacentHTML('beforeend', trechoTemplate(idx));
        reindexTrechos();
      });
    }

    trechosContainer.addEventListener('click', function (event) {
      var button = event.target.closest('[data-trecho-remove="1"]');
      if (!button) return;
      var row = button.closest('.trecho-row');
      if (row) row.remove();
      reindexTrechos();
    });

    reindexTrechos();

    if (window.OficioWizard && typeof window.OficioWizard.bindDiariasCalc === "function") {
      window.OficioWizard.bindDiariasCalc();
    }
  }

  function initJustificativaPages() {
    document.querySelectorAll('[data-modelo-texto-target]').forEach(function (button) {
      if (button.dataset.bound === '1') return;
      button.dataset.bound = '1';
      button.addEventListener('click', function () {
        var targetSelector = button.dataset.modeloTextoTarget;
        var hiddenSelector = button.dataset.modeloHiddenTarget;
        var texto = button.dataset.texto || '';
        var id = button.dataset.modeloId || '';

        var target = document.querySelector(targetSelector);
        if (target) target.value = texto;
        var hidden = document.querySelector(hiddenSelector);
        if (hidden) hidden.value = id;

        document.querySelectorAll('[data-modelo-texto-target]').forEach(function (el) {
          el.classList.remove('active');
        });
        button.classList.add('active');
      });
    });

    var modeloSelect = document.getElementById('id_modelo_select');
    if (modeloSelect) {
      modeloSelect.addEventListener('change', function () {
        var opt = this.options[this.selectedIndex];
        var texto = opt ? opt.getAttribute('data-texto') : '';
        if (!texto) return;
        var textarea = document.getElementById('id_texto');
        if (textarea) textarea.value = texto;
      });
    }
  }

  function initOficiosSteps() {
    initStep1();
    initStep2();
    initStep3();
    initJustificativaPages();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOficiosSteps);
  } else {
    initOficiosSteps();
  }
})();
