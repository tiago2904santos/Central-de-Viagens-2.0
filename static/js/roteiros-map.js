/* global L */
(function () {
  'use strict';

  var MSG_GEOM_DESENHO =
    'Rota calculada, mas a geometria retornada não pôde ser desenhada no mapa.';

  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el || !el.textContent) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function getCookie(name) {
    var prefix = name + '=';
    var parts = document.cookie.split(';');
    for (var i = 0; i < parts.length; i++) {
      var p = parts[i].trim();
      if (p.indexOf(prefix) === 0) return decodeURIComponent(p.slice(prefix.length));
    }
    return '';
  }

  function showElement(el) {
    if (!el) return;
    el.hidden = false;
    el.removeAttribute('hidden');
    el.classList.remove('d-none');
  }

  function hideElement(el) {
    if (!el) return;
    el.hidden = true;
    el.setAttribute('hidden', 'hidden');
    el.classList.add('d-none');
  }

  function statusLabel(status) {
    var map = {
      pendente: 'Pendente',
      calculada: 'Calculada',
      manual: 'Manual',
      erro: 'Erro',
      desatualizada: 'Desatualizada',
    };
    return map[status] || status || '—';
  }

  var mapInstance = null;
  var routeLayer = null;
  var initial = readJsonScript('roteiro-mapa-inicial') || {};
  var rid = initial.roteiro_id;
  var hadGeometry = !!(initial.route && initial.route.geometry && initial.route.geometry.type === 'LineString');

  function $(id) {
    return document.getElementById(id);
  }

  function setLoading(on) {
    var el = $('roteiro-mapa-loading');
    if (!el) return;
    if (on) showElement(el);
    else hideElement(el);
  }

  function showError(msg) {
    var el = $('roteiro-mapa-error');
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      showElement(el);
    } else {
      el.textContent = '';
      hideElement(el);
    }
  }

  function setCalcularEnabled(on) {
    var b = $('btn-calcular-rota-mapa');
    if (!b) return;
    b.disabled = !on;
    b.setAttribute('aria-disabled', on ? 'false' : 'true');
    if (on) b.classList.remove('roteiro-mapa__btn--blocked');
    else b.classList.add('roteiro-mapa__btn--blocked');
  }

  function updateSummary(route, extra) {
    var box = $('roteiro-mapa-summary');
    if (!box) return;
    if (!route) {
      hideElement(box);
      return;
    }
    showElement(box);
    var dist = $('roteiro-mapa-distancia');
    var tempo = $('roteiro-mapa-tempo');
    var fonte = $('roteiro-mapa-fonte');
    var em = $('roteiro-mapa-calculada-em');
    var st = $('roteiro-mapa-status');
    var manual = $('roteiro-mapa-manual-blurb');
    if (dist) {
      var dAuto = route.distance_km_auto;
      var dShow = route.distance_km;
      var txt = dShow != null ? String(dShow) + ' km' : '—';
      if (dAuto != null && route.distancia_manual_km != null) {
        txt =
          String(route.distancia_manual_km) +
          ' km (ajustado; automático: ' +
          String(dAuto) +
          ' km)';
      }
      dist.textContent = txt;
    }
    if (tempo) {
      var tAuto = route.duration_human_auto;
      var tShow = route.duration_human;
      var txtT = tShow || '—';
      if (route.duracao_manual_min != null && tAuto) {
        txtT = tShow + ' (ajustado; automático: ' + tAuto + ')';
      }
      tempo.textContent = txtT;
    }
    if (fonte) fonte.textContent = route.provider || '—';
    if (em) em.textContent = route.calculated_at || '—';
    if (st) st.textContent = statusLabel((route && route.status) || (extra && extra.status));
    if (manual) {
      var j = (route.ajuste_justificativa || '').trim();
      if (j) {
        manual.hidden = false;
        manual.removeAttribute('hidden');
        manual.textContent = 'Justificativa registrada: ' + j;
      } else {
        manual.hidden = true;
        manual.textContent = '';
      }
    }
  }

  function setFramePlaceholder(on) {
    var container = $('roteiro-mapa-container');
    if (!container) return;
    if (on) container.classList.add('roteiro-mapa__frame--placeholder');
    else container.classList.remove('roteiro-mapa__frame--placeholder');
  }

  function ensureMap() {
    var container = $('roteiro-mapa-container');
    if (!container || typeof L === 'undefined') return;
    if (!mapInstance) {
      mapInstance = L.map(container, { scrollWheelZoom: false }).setView([-14.235, -51.9253], 4);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap',
      }).addTo(mapInstance);
      setTimeout(function () {
        try {
          mapInstance.invalidateSize();
        } catch (e) {
          /* ignore */
        }
      }, 0);
    }
  }

  /**
   * Desenha geometria LineString normalizada. Retorna true se desenhou.
   */
  function drawRoute(geometry, geomWarning) {
    ensureMap();
    var container = $('roteiro-mapa-container');
    if (!container || typeof L === 'undefined') return false;

    if (routeLayer) {
      mapInstance.removeLayer(routeLayer);
      routeLayer = null;
    }

    var warn = geomWarning || '';

    if (
      !geometry ||
      geometry.type !== 'LineString' ||
      !geometry.coordinates ||
      !geometry.coordinates.length
    ) {
      setFramePlaceholder(true);
      if (warn) showError(warn);
      return false;
    }

    try {
      routeLayer = L.geoJSON(
        { type: 'Feature', properties: {}, geometry: geometry },
        {
          style: { color: '#0f365d', weight: 5, opacity: 0.9 },
        }
      ).addTo(mapInstance);
      setFramePlaceholder(false);
      try {
        mapInstance.fitBounds(routeLayer.getBounds(), { padding: [24, 24], maxZoom: 12 });
      } catch (e) {
        showError(MSG_GEOM_DESENHO);
        setFramePlaceholder(true);
        return false;
      }
      return true;
    } catch (e) {
      showError(MSG_GEOM_DESENHO);
      setFramePlaceholder(true);
      return false;
    }
  }

  function toggleRecalc(show) {
    var b2 = $('btn-recalcular-rota-mapa');
    if (!b2) return;
    if (show) showElement(b2);
    else hideElement(b2);
  }

  function postCalcular(force) {
    var form = document.getElementById('oficio-step3-form');
    if (!form) return;
    var urlPersistido = form.getAttribute('data-api-calcular-rota-url');
    var urlPreview = form.getAttribute('data-api-calcular-rota-preview-url');
    var hasSaved = !!rid;
    var step3 = window.RoteirosStep3;
    if (!hasSaved && (!step3 || !step3.canCalculateRoutePreview || !step3.canCalculateRoutePreview())) {
      showError('Selecione a sede e ao menos um destino para calcular a rota.');
      return;
    }
    var targetUrl = hasSaved ? urlPersistido : (urlPreview || (step3 && step3.getPreviewEndpointUrl && step3.getPreviewEndpointUrl()));
    if (!targetUrl) return;

    showError('');
    setLoading(true);

    var token =
      getCookie('csrftoken') ||
      (form.querySelector('[name=csrfmiddlewaretoken]') &&
        form.querySelector('[name=csrfmiddlewaretoken]').value);

    var payload = hasSaved
      ? { roteiro_id: rid, force_recalculate: !!force }
      : ((step3 && step3.buildRoutePreviewPayload && step3.buildRoutePreviewPayload()) || null);
    if (!payload) {
      setLoading(false);
      showError('Selecione a sede e ao menos um destino para calcular a rota.');
      return;
    }

    fetch(targetUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': token || '',
      },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, status: r.status, body: body };
        });
      })
      .then(function (res) {
        if (!res.body || !res.body.ok) {
          showError((res.body && res.body.message) || 'Não foi possível calcular a rota.');
          return;
        }
        var route = res.body.route;
        if (!hasSaved && step3 && typeof step3.applyRoutePreviewResult === 'function') {
          step3.applyRoutePreviewResult(res.body, { overwriteAdditional: !!force });
        }
        initial.route = route;
        initial.status = route.status || 'calculada';
        hadGeometry = !!(route.geometry && route.geometry.type === 'LineString');
        updateSummary(route, { status: initial.status });

        var gw = route.geometry_warning || res.body.geometry_warning;
        var drew = drawRoute(route.geometry, gw);
        if (!drew && route.distance_km != null && !gw) {
          showError(MSG_GEOM_DESENHO);
        } else if (!drew && gw) {
          showError(gw);
        } else if (drew) {
          showError('');
        }

        toggleRecalc(true);
        hideElement($('roteiro-mapa-stale-hint'));
        hideElement($('roteiro-mapa-novo-hint'));
        hideElement($('roteiro-mapa-ready-hint'));
      })
      .catch(function () {
        showError('Falha de rede ao calcular a rota. Tente novamente.');
      })
      .finally(function () {
        setLoading(false);
        refreshRouteReadyState();
      });
  }

  function refreshRouteReadyState() {
    var hintNovo = $('roteiro-mapa-novo-hint');
    var hintReady = $('roteiro-mapa-ready-hint');
    var step3 = window.RoteirosStep3;
    var canPreview = !!(step3 && step3.canCalculateRoutePreview && step3.canCalculateRoutePreview());
    if (rid || canPreview) {
      setCalcularEnabled(true);
      if (!rid && canPreview) {
        hideElement(hintNovo);
        showElement(hintReady);
      } else {
        hideElement(hintNovo);
        hideElement(hintReady);
      }
    } else {
      setCalcularEnabled(false);
      showElement(hintNovo);
      hideElement(hintReady);
    }
  }

  function init() {
    var form = document.getElementById('oficio-step3-form');
    var container = $('roteiro-mapa-container');
    if (!form || !container) return;

    hideElement($('roteiro-mapa-loading'));
    hideElement($('roteiro-mapa-error'));

    var hintNovo = $('roteiro-mapa-novo-hint');
    var stale = $('roteiro-mapa-stale-hint');

    if (!rid) {
      setCalcularEnabled(false);
      hideElement($('btn-recalcular-rota-mapa'));
      hideElement(stale);
      showElement(hintNovo);
      hideElement($('roteiro-mapa-ready-hint'));
      hideElement($('roteiro-mapa-summary'));
      ensureMap();
      setFramePlaceholder(true);
      toggleRecalc(false);
    } else {
      hideElement(hintNovo);
      setCalcularEnabled(true);
      if (initial.route) {
        updateSummary(initial.route, { status: initial.status });
        var gwInit = initial.route.geometry_warning;
        var drew = drawRoute(initial.route.geometry, gwInit);
        if (!drew && initial.route.geometry_warning) {
          showError(initial.route.geometry_warning);
        } else if (!drew && initial.route.distance_km != null && !initial.route.geometry) {
          showError(MSG_GEOM_DESENHO);
        }
        var hasLine =
          initial.route.geometry && initial.route.geometry.type === 'LineString';
        if (initial.status === 'desatualizada') {
          toggleRecalc(true);
        } else {
          toggleRecalc(!!hasLine);
        }
      } else {
        hideElement($('roteiro-mapa-summary'));
        toggleRecalc(false);
        ensureMap();
        setFramePlaceholder(true);
      }

      if (
        rid &&
        initial.status === 'desatualizada' &&
        (hadGeometry || (initial.route && (initial.route.distance_km != null || initial.route.geometry)))
      ) {
        showElement(stale);
      } else {
        hideElement(stale);
      }
    }

    var bCalc = $('btn-calcular-rota-mapa');
    var bRecalc = $('btn-recalcular-rota-mapa');
    if (bCalc) {
      bCalc.addEventListener('click', function () {
        if (bCalc.disabled) return;
        postCalcular(false);
      });
    }
    if (bRecalc) {
      bRecalc.addEventListener('click', function () {
        postCalcular(true);
      });
    }
    window.addEventListener('roteiros:route-state-changed', refreshRouteReadyState);
    refreshRouteReadyState();
  }

  function onDestinosReordered() {
    if (!rid || !hadGeometry) return;
    showElement($('roteiro-mapa-stale-hint'));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.RoteirosMap = { onDestinosReordered: onDestinosReordered };
})();
