(function() {
  function qs(selector) {
    return document.querySelector(selector);
  }

  function getWizardPage() {
    var header = qs('[data-oficio-sticky-header]');
    return header ? header.closest('.oficio-wizard-page') : qs('.oficio-wizard-page');
  }

  function setStickyHeaderOffset() {
    var header = qs('[data-oficio-sticky-header]');
    if (!header) {
      return;
    }
    var page = getWizardPage() || document.documentElement;
    var computed = window.getComputedStyle(header);
    var marginTop = parseFloat(computed.marginTop || '0') || 0;
    var marginBottom = parseFloat(computed.marginBottom || '0') || 0;
    var rect = header.getBoundingClientRect();
    var height = Math.ceil(rect.height + marginTop + marginBottom);
    var headerTop = Math.max(Math.floor(rect.top - marginTop), 0);
    var stickyGap = parseFloat(
      window.getComputedStyle(page).getPropertyValue('--oficio-sticky-gap') || '12'
    ) || 12;
    var quickReportTop = Math.max(Math.ceil(rect.bottom + marginBottom + stickyGap), stickyGap);
    page.style.setProperty('--oficio-sticky-header-height', height + 'px');
    page.style.setProperty('--oficio-sticky-header-top', headerTop + 'px');
    page.style.setProperty('--oficio-quick-report-top', quickReportTop + 'px');
  }

  function syncQuickReportLayout() {
    var page = getWizardPage();
    var reports = document.querySelectorAll('.oficio-quick-report-column .oficio-quick-report');
    if (!reports.length) {
      return;
    }
    var styles = page ? window.getComputedStyle(page) : window.getComputedStyle(document.documentElement);
    var quickReportTop = parseFloat(styles.getPropertyValue('--oficio-quick-report-top') || '0') || 0;
    var viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    var maxHeight = Math.max(Math.floor(viewportHeight - quickReportTop - 12), 240);
    if (page) {
      page.style.setProperty('--oficio-quick-report-max-height', maxHeight + 'px');
    }
    reports.forEach(function(report) {
      report.classList.remove('is-viewport-fixed');
      report.style.removeProperty('--oficio-quick-report-left');
      report.style.removeProperty('--oficio-quick-report-width');
      report.style.removeProperty('--oficio-quick-report-height');
    });
  }

  function bindStickyLayout() {
    var header = qs('[data-oficio-sticky-header]');
    var scheduled = false;
    function refreshLayout() {
      if (scheduled) {
        return;
      }
      scheduled = true;
      window.requestAnimationFrame(function() {
        scheduled = false;
        setStickyHeaderOffset();
        syncQuickReportLayout();
      });
    }
    function forceRefreshLayout() {
      setStickyHeaderOffset();
      syncQuickReportLayout();
    }
    forceRefreshLayout();
    refreshLayout();
    window.setTimeout(forceRefreshLayout, 0);
    window.addEventListener('resize', refreshLayout, { passive: true });
    window.addEventListener('load', forceRefreshLayout);
    window.addEventListener('scroll', refreshLayout, { passive: true });
    document.addEventListener('scroll', refreshLayout, { passive: true });
    if (typeof ResizeObserver === 'function') {
      var observer = new ResizeObserver(forceRefreshLayout);
      if (header) {
        observer.observe(header);
      }
      var page = getWizardPage();
      if (page) {
        observer.observe(page);
      }
      observer.observe(document.body);
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

  window.OficioWizard = {
    bindStickyLayout: bindStickyLayout,
    createAutosave: createAutosave,
    syncQuickReportLayout: syncQuickReportLayout
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindStickyLayout);
  } else {
    bindStickyLayout();
  }
})();
