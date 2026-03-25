(function() {
  function onlyDigits(value) {
    return String(value || '').replace(/\D/g, '');
  }

  function formatProtocolDisplay(value) {
    var digits = onlyDigits(value).slice(0, 9);
    if (!digits) {
      return '';
    }
    if (digits.length <= 2) {
      return digits;
    }
    if (digits.length <= 5) {
      return digits.slice(0, 2) + '.' + digits.slice(2);
    }
    if (digits.length <= 8) {
      return digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5);
    }
    return digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5, 8) + '-' + digits.slice(8);
  }

  function qs(selector) {
    return document.querySelector(selector);
  }

  function getWizardPage() {
    var header = qs('[data-oficio-sticky-header]');
    return header ? header.closest('.oficio-wizard-page') : qs('.oficio-wizard-page');
  }

  function getEmptyText(element, fallback) {
    if (!element) {
      return fallback || '—';
    }
    return element.getAttribute('data-empty-text') || fallback || '—';
  }

  function setGlanceValue(id, value, fallback) {
    var element = document.getElementById(id);
    if (!element) {
      return;
    }
    var text = String(value || '').trim();
    if (id === 'summary-protocolo') {
      text = formatProtocolDisplay(text);
    }
    element.textContent = text || getEmptyText(element, fallback);
  }

  function renderGlanceTravelers(items) {
    var list = document.getElementById('summary-viajantes-list');
    var meta = document.getElementById('summary-viajantes-meta');
    var travelers = Array.isArray(items) ? items : [];

    if (meta) {
      meta.textContent = travelers.length
        ? (travelers.length + ' servidor' + (travelers.length > 1 ? 'es' : ''))
        : getEmptyText(meta, 'Nenhum servidor');
    }

    if (!list) {
      return;
    }

    list.innerHTML = '';
    if (!travelers.length) {
      var empty = document.createElement('span');
      empty.className = 'oficio-glance-empty';
      empty.textContent = 'Adicione ao menos um servidor para visualizar a equipe aqui.';
      list.appendChild(empty);
      return;
    }

    travelers.forEach(function(item) {
      var name = typeof item === 'string'
        ? item
        : String((item && (item.nome || item.label || item.name)) || '').trim();
      if (!name) {
        return;
      }
      var chip = document.createElement('div');
      chip.className = 'oficio-glance-chip';
      var nomeSpan = document.createElement('span');
      nomeSpan.className = 'oficio-glance-chip-nome';
      nomeSpan.textContent = name;
      chip.appendChild(nomeSpan);
      if (typeof item !== 'string') {
        var lotacao = String((item && item.lotacao) || '').trim();
        if (lotacao) {
          var lotacaoSpan = document.createElement('span');
          lotacaoSpan.className = 'oficio-glance-chip-sub';
          lotacaoSpan.textContent = lotacao;
          chip.appendChild(lotacaoSpan);
        }
      }
      list.appendChild(chip);
    });
  }

  function bindStickyLayout() {
    var header = qs('[data-oficio-sticky-header]');
    var page = getWizardPage();
    if (!header || !page) {
      return;
    }
    // Keep the sticky anchor deterministic. Reading the header's own viewport
    // top on scroll and feeding that back into CSS was causing the header to drift.
    page.style.removeProperty('--oficio-sticky-header-height');
    page.style.removeProperty('--oficio-sticky-header-top');
    header.style.removeProperty('top');
    header.style.removeProperty('transform');
    header.style.removeProperty('translate');
  }

  function bindGlanceDrawer() {
    var page = getWizardPage();
    var panel = qs('[data-oficio-glance-panel]');
    var toggles = Array.prototype.slice.call(document.querySelectorAll('[data-oficio-glance-toggle]'));

    if (!page || !panel || !toggles.length) {
      return;
    }

    function applyState(isOpen) {
      var open = !!isOpen;
      page.setAttribute('data-glance-state', open ? 'open' : 'closed');
      panel.setAttribute('aria-hidden', open ? 'false' : 'true');

      toggles.forEach(function(button) {
        var label = button.querySelector('[data-oficio-glance-toggle-label]');
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        button.classList.toggle('is-active', open);
        if (label) {
          label.textContent = open ? 'Recolher painel' : 'Expandir painel';
        }
      });
    }

    toggles.forEach(function(button) {
      button.addEventListener('click', function() {
        applyState(page.getAttribute('data-glance-state') !== 'open');
      });
    });

    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape' && page.getAttribute('data-glance-state') === 'open') {
        applyState(false);
      }
    });

    applyState(page.getAttribute('data-glance-state') === 'open');
  }

  function createAutosave(options) {
    var form = options && options.form;
    if (!form) {
      return null;
    }
    var statusElement = options.statusElement || null;
    var url = options.url || window.location.href;
    var beforeSerialize = typeof options.beforeSerialize === 'function' ? options.beforeSerialize : function() {};
    var captureSubmit = options.captureSubmit !== false;
    var dirty = false;
    var timer = null;
    var activeRequest = null;
    var queuedAfterActive = false;

    function setStatus(state) {
      if (!statusElement) {
        return;
      }
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
      setStatus('saving');
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
            setStatus('saved');
            return true;
          });
        })
        .catch(function(error) {
          dirty = true;
          setStatus('error');
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
        var nextUrl = (submitter && submitter.getAttribute('data-autosave-navigate')) || '';
        event.preventDefault();
        var p = flush();
        if (nextUrl) {
          p.finally(function() { window.location.href = nextUrl; });
        }
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

    setStatus('idle');
    return {
      schedule: schedule,
      flush: flush,
      setStatus: setStatus
    };
  }

  window.OficioWizard = {
    bindStickyLayout: bindStickyLayout,
    bindGlanceDrawer: bindGlanceDrawer,
    createAutosave: createAutosave,
    setGlanceValue: setGlanceValue,
    renderGlanceTravelers: renderGlanceTravelers
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      bindStickyLayout();
      bindGlanceDrawer();
    });
  } else {
    bindStickyLayout();
    bindGlanceDrawer();
  }
})();
