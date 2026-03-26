(function() {
  function qs(selector) {
    return document.querySelector(selector);
  }

  function setStickyHeaderOffset() {
    var header = qs('[data-oficio-sticky-header]');
    if (!header) {
      return;
    }
    var computed = window.getComputedStyle(header);
    var marginTop = parseFloat(computed.marginTop || '0') || 0;
    var marginBottom = parseFloat(computed.marginBottom || '0') || 0;
    var height = Math.ceil(header.getBoundingClientRect().height + marginTop + marginBottom);
    document.documentElement.style.setProperty('--oficio-sticky-header-height', height + 'px');
  }

  function syncQuickReportLayout() {
    var reports = document.querySelectorAll('.oficio-quick-report-column .oficio-quick-report');
    if (!reports.length) {
      return;
    }
    var isDesktop = window.innerWidth >= 1200;
    var headerOffset = parseFloat(
      window.getComputedStyle(document.documentElement).getPropertyValue('--oficio-sticky-header-height') || '0'
    ) || 0;
    var topOffset = Math.max(Math.ceil(headerOffset + 8), 0);
    var viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    var viewportBottomGap = 12;
    reports.forEach(function(report) {
      var column = report.closest('.oficio-quick-report-column');
      if (!column || !isDesktop) {
        report.classList.remove('is-viewport-fixed');
        report.style.removeProperty('--oficio-quick-report-left');
        report.style.removeProperty('--oficio-quick-report-width');
        report.style.removeProperty('--oficio-quick-report-height');
        return;
      }
      var rect = column.getBoundingClientRect();
      var columnStyles = window.getComputedStyle(column);
      var paddingLeft = parseFloat(columnStyles.paddingLeft || '0') || 0;
      var paddingRight = parseFloat(columnStyles.paddingRight || '0') || 0;
      var width = Math.max(Math.round(rect.width - paddingLeft - paddingRight), 320);
      var height = Math.max(Math.floor(viewportHeight - topOffset - viewportBottomGap), 240);
      report.style.setProperty('--oficio-quick-report-left', Math.round(rect.left + paddingLeft) + 'px');
      report.style.setProperty('--oficio-quick-report-width', width + 'px');
      report.style.setProperty('--oficio-quick-report-height', height + 'px');
      report.classList.add('is-viewport-fixed');
    });
  }

  function bindStickyLayout() {
    var header = qs('[data-oficio-sticky-header]');
    function refreshLayout() {
      setStickyHeaderOffset();
      syncQuickReportLayout();
    }
    refreshLayout();
    window.addEventListener('resize', refreshLayout);
    if (typeof ResizeObserver === 'function') {
      var observer = new ResizeObserver(refreshLayout);
      if (header) {
        observer.observe(header);
      }
      document.querySelectorAll('.oficio-quick-report-column').forEach(function(column) {
        observer.observe(column);
      });
    }
  }

  function createAutosave(options) {
    var form = options && options.form;
    if (!form) {
      return null;
    }
    var statusElement = options.statusElement || qs('#oficio-autosave-status');
    var url = options.url || window.location.href;
    var beforeSerialize = typeof options.beforeSerialize === 'function' ? options.beforeSerialize : function() {};
    var captureSubmit = options.captureSubmit !== false;
    var dirty = false;
    var timer = null;
    var activeRequest = null;
    var queuedAfterActive = false;

    function setStatus(text, state) {
      if (!statusElement) {
        return;
      }
      statusElement.textContent = text;
      statusElement.dataset.state = state || '';
    }

    function buildPayload() {
      beforeSerialize();
      var data = new FormData(form);
      data.set('autosave', '1');
      return data;
    }

    function sendRequest(force) {
      if (activeRequest) {
        queuedAfterActive = true;
        return activeRequest;
      }
      if (!dirty && !force) {
        return Promise.resolve(true);
      }
      dirty = false;
      setStatus('Salvando...', 'saving');
      activeRequest = fetch(url, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        body: buildPayload()
      })
        .then(function(response) {
          return response.json().catch(function() { return {}; }).then(function(data) {
            if (!response.ok || data.ok === false) {
              throw new Error(data.error || 'Falha no autosave.');
            }
            var savedAt = data.saved_at || '';
            setStatus(savedAt ? ('Autosave salvo às ' + savedAt) : 'Autosave salvo', 'saved');
            return true;
          });
        })
        .catch(function(error) {
          dirty = true;
          setStatus(error && error.message ? error.message : 'Falha no autosave.', 'error');
          return false;
        })
        .finally(function() {
          activeRequest = null;
          if (queuedAfterActive) {
            queuedAfterActive = false;
            schedule();
          }
        });
      return activeRequest;
    }

    function schedule() {
      dirty = true;
      window.clearTimeout(timer);
      timer = window.setTimeout(function() {
        sendRequest(false);
      }, 500);
    }

    function flush() {
      window.clearTimeout(timer);
      return sendRequest(true);
    }

    function sendBeaconSave() {
      if (!dirty || !navigator.sendBeacon) {
        return;
      }
      beforeSerialize();
      var payload = new URLSearchParams(new FormData(form));
      payload.set('autosave', '1');
      navigator.sendBeacon(
        url,
        new Blob([payload.toString()], {
          type: 'application/x-www-form-urlencoded;charset=UTF-8'
        })
      );
      dirty = false;
    }

    form.addEventListener('input', function(event) {
      if (event.target && event.target.type === 'hidden') {
        return;
      }
      schedule();
    });
    form.addEventListener('change', schedule);

    if (captureSubmit) {
      form.addEventListener('submit', function(event) {
        var submitter = event.submitter;
        if (submitter && submitter.dataset && submitter.dataset.autosaveBypass === '1') {
          return;
        }
        event.preventDefault();
        flush();
      });
    }

    document.addEventListener('click', function(event) {
      var link = event.target.closest('[data-autosave-link="1"]');
      if (!link) {
        return;
      }
      if (link.target === '_blank' || link.hasAttribute('download')) {
        return;
      }
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
        return;
      }
      var href = link.getAttribute('href');
      if (!href || href.charAt(0) === '#') {
        return;
      }
      event.preventDefault();
      flush().finally(function() {
        window.location.href = href;
      });
    });

    window.addEventListener('pagehide', sendBeaconSave);
    document.addEventListener('visibilitychange', function() {
      if (document.visibilityState === 'hidden') {
        sendBeaconSave();
      }
    });

    setStatus('Autosave ativo', 'idle');
    return {
      schedule: schedule,
      flush: flush,
      setStatus: setStatus
    };
  }

  var UNIDADES = ['zero', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove',
    'dez', 'onze', 'doze', 'treze', 'quatorze', 'quinze', 'dezesseis', 'dezessete', 'dezoito', 'dezenove'];
  var DEZENAS = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta', 'oitenta', 'noventa'];
  var CENTENAS = ['', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos',
    'seiscentos', 'setecentos', 'oitocentos', 'novecentos'];

  function numeroPorExtenso(n) {
    if (n < 0) { return ''; }
    if (n < 20) { return UNIDADES[n]; }
    if (n < 100) {
      var d = Math.floor(n / 10);
      var u = n % 10;
      return u ? DEZENAS[d] + ' e ' + UNIDADES[u] : DEZENAS[d];
    }
    if (n === 100) { return 'cem'; }
    if (n < 1000) {
      var c = Math.floor(n / 100);
      var r = n % 100;
      return r ? CENTENAS[c] + ' e ' + numeroPorExtenso(r) : CENTENAS[c];
    }
    if (n < 2000) {
      var r = n % 1000;
      if (!r) { return 'mil'; }
      var restStr = numeroPorExtenso(r);
      return (r < 100 || r % 100 === 0) ? 'mil e ' + restStr : 'mil ' + restStr;
    }
    if (n < 1000000) {
      var m = Math.floor(n / 1000);
      var r = n % 1000;
      var milStr = numeroPorExtenso(m) + ' mil';
      if (!r) { return milStr; }
      var restStr = numeroPorExtenso(r);
      return (r < 100 || r % 100 === 0) ? milStr + ' e ' + restStr : milStr + ' ' + restStr;
    }
    return String(n);
  }

  function valorBrlPorExtenso(valor) {
    var num = parseFloat(String(valor).replace(',', '.'));
    if (isNaN(num) || num <= 0) { return ''; }
    var centavosTotal = Math.round(num * 100);
    var reais = Math.floor(centavosTotal / 100);
    var centavos = centavosTotal % 100;
    var parts = [];
    if (reais > 0) {
      parts.push(numeroPorExtenso(reais) + (reais === 1 ? ' real' : ' reais'));
    }
    if (centavos > 0) {
      parts.push(numeroPorExtenso(centavos) + (centavos === 1 ? ' centavo' : ' centavos'));
    }
    return parts.join(' e ');
  }

  function bindDiariasCalc(options) {
    var opts = options || {};
    var valorInput = opts.valorInput || document.querySelector('[name="valor_diarias"]');
    var extensoInput = opts.extensoInput || document.querySelector('[name="valor_diarias_extenso"]');
    if (!valorInput || !extensoInput) { return; }

    function updateExtenso() {
      var v = valorInput.value;
      if (!v) { extensoInput.value = ''; return; }
      var resultado = valorBrlPorExtenso(v);
      if (resultado) { extensoInput.value = resultado; }
    }

    valorInput.addEventListener('change', updateExtenso);
    valorInput.addEventListener('blur', updateExtenso);
  }

  window.OficioWizard = {
    bindDiariasCalc: bindDiariasCalc,
    bindStickyLayout: bindStickyLayout,
    createAutosave: createAutosave,
    numeroPorExtenso: numeroPorExtenso,
    syncQuickReportLayout: syncQuickReportLayout,
    valorBrlPorExtenso: valorBrlPorExtenso
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindStickyLayout);
  } else {
    bindStickyLayout();
  }
})();
