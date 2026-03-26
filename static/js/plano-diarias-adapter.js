(function () {
  function bindDiariasInputs(ctx) {
    const map = [
      ['saida_data', 'saida_data'],
      ['saida_hora', 'saida_hora'],
      ['chegada_data', 'chegada_data'],
      ['chegada_hora', 'chegada_hora'],
    ];

    map.forEach(function (entry) {
      var id = entry[0];
      var key = entry[1];
      var el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('change', function (e) {
        ctx.planoState.deslocamento[key] = e.target.value || null;
        if (ctx.realtime) {
          calcularDiariasPlano(ctx);
        }
      });
    });

    var button = document.getElementById('btn-calcular');
    if (button) {
      button.addEventListener('click', function () {
        calcularDiariasPlano(ctx);
      });
    }
  }

  function updateDiariasUI(ctx) {
    var qtdEl = document.getElementById('qtd-diarias');
    var totalEl = document.getElementById('valor-total');
    var extensoEl = document.getElementById('valor-extenso');

    if (qtdEl) qtdEl.innerText = String(ctx.planoState.diarias.qtd || 0);
    if (totalEl) totalEl.innerText = ctx.formatCurrency(ctx.planoState.diarias.total || 0);
    if (extensoEl) extensoEl.innerText = ctx.planoState.diarias.valor_extenso || '—';

    if (typeof ctx.afterUpdate === 'function') {
      ctx.afterUpdate();
    }
  }

  async function calcularDiariasPlano(ctx) {
    var state = ctx.planoState;

    var payload = {
      data_saida: state.deslocamento.saida_data,
      hora_saida: state.deslocamento.saida_hora,
      data_retorno: state.deslocamento.chegada_data,
      hora_retorno: state.deslocamento.chegada_hora,
      pessoas: ctx.getQuantidadePessoas(),
      valor: Number((state.diarias && (state.diarias.valor_unitario || state.diarias.unitario)) || 0),
      apiUrl: ctx.apiUrl,
      csrfToken: ctx.csrfToken,
    };

    try {
      var result = await window.calcularDiariasEngine(payload);
      state.diarias.qtd = result.qtd_diarias;
      state.diarias.total = result.valor_total;
      state.diarias.valor_extenso = result.valor_extenso;
      updateDiariasUI(ctx);
      if (typeof ctx.notify === 'function') ctx.notify();
    } catch (error) {
      if (typeof ctx.onError === 'function') {
        ctx.onError(error.message || 'Erro ao calcular diárias.');
      }
    }
  }

  function init(config) {
    var ctx = {
      planoState: config.planoState,
      getQuantidadePessoas: config.getQuantidadePessoas,
      formatCurrency: config.formatCurrency,
      apiUrl: config.apiUrl,
      csrfToken: config.csrfToken,
      notify: config.notify,
      onError: config.onError,
      afterUpdate: config.afterUpdate,
      realtime: config.realtime !== false,
    };

    bindDiariasInputs(ctx);
    updateDiariasUI(ctx);

    return {
      recalculate: function () {
        return calcularDiariasPlano(ctx);
      },
      updateUi: function () {
        updateDiariasUI(ctx);
      },
    };
  }

  window.PlanoDiariasAdapter = {
    init: init,
  };
  window.calcularDiariasPlano = function () {
    if (!window.__planoDiariasAdapterInstance) return Promise.resolve();
    return window.__planoDiariasAdapterInstance.recalculate();
  };
})();
