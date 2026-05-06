/* global L */
(function () {
  'use strict';

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
  var hadGeometry = !!(initial.route && initial.route.geometry);

  function $(id) {
    return document.getElementById(id);
  }

  function setLoading(on) {
    var el = $('roteiro-mapa-loading');
    if (el) el.classList.toggle('d-none', !on);
  }

  function showError(msg) {
    var el = $('roteiro-mapa-error');
    if (!el) return;
    if (msg) {
      el.textContent = msg;
      el.classList.remove('d-none');
    } else {
      el.textContent = '';
      el.classList.add('d-none');
    }
  }

  function updateSummary(route, extra) {
    var box = $('roteiro-mapa-summary');
    if (!box) return;
    if (!route) {
      box.hidden = true;
      return;
    }
    box.hidden = false;
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
        manual.textContent = 'Justificativa registrada: ' + j;
      } else {
        manual.hidden = true;
        manual.textContent = '';
      }
    }
  }

  function drawRoute(geometry) {
    var container = $('roteiro-mapa-container');
    if (!container || typeof L === 'undefined') return;

    if (!mapInstance) {
      mapInstance = L.map(container, { scrollWheelZoom: false }).setView([-14.235, -51.9253], 4);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap',
      }).addTo(mapInstance);
    }

    if (routeLayer) {
      mapInstance.removeLayer(routeLayer);
      routeLayer = null;
    }

    if (!geometry || geometry.type !== 'LineString' || !geometry.coordinates || !geometry.coordinates.length) {
      return;
    }

    routeLayer = L.geoJSON(
      { type: 'Feature', properties: {}, geometry: geometry },
      {
        style: { color: '#0f365d', weight: 5, opacity: 0.9 },
      }
    ).addTo(mapInstance);

    try {
      mapInstance.fitBounds(routeLayer.getBounds(), { padding: [24, 24], maxZoom: 12 });
    } catch (e) {
      /* ignore */
    }
  }

  function toggleRecalc(hasRoute) {
    var b1 = $('btn-calcular-rota-mapa');
    var b2 = $('btn-recalcular-rota-mapa');
    if (b1 && b2) {
      if (hasRoute) {
        b2.classList.remove('d-none');
      } else {
        b2.classList.add('d-none');
      }
    }
  }

  function postCalcular(force) {
    var form = document.getElementById('oficio-step3-form');
    if (!form) return;
    var url = form.getAttribute('data-api-calcular-rota-url');
    if (!url) return;
    var rid = initial.roteiro_id;
    if (!rid) {
      showError('Salve o roteiro antes de calcular a rota no mapa.');
      return;
    }
    showError('');
    setLoading(true);
    fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') || form.querySelector('[name=csrfmiddlewaretoken]').value,
      },
      body: JSON.stringify({ roteiro_id: rid, force_recalculate: !!force }),
    })
      .then(function (r) {
        return r.json().then(function (body) {
          return { ok: r.ok, status: r.status, body: body };
        });
      })
      .then(function (res) {
        setLoading(false);
        if (!res.body || !res.body.ok) {
          showError((res.body && res.body.message) || 'Não foi possível calcular a rota.');
          return;
        }
        var route = res.body.route;
        initial.route = route;
        initial.status = route.status || 'calculada';
        hadGeometry = true;
        updateSummary(route, { status: initial.status });
        drawRoute(route.geometry);
        toggleRecalc(true);
        var stale = $('roteiro-mapa-stale-hint');
        if (stale) stale.classList.add('d-none');
        if (route.from_cache) {
          showError('');
        }
      })
      .catch(function () {
        setLoading(false);
        showError('Falha de rede ao calcular a rota. Tente novamente.');
      });
  }

  function init() {
    var form = document.getElementById('oficio-step3-form');
    var container = $('roteiro-mapa-container');
    if (!form || !container) return;

    var bCalc = $('btn-calcular-rota-mapa');
    var bRecalc = $('btn-recalcular-rota-mapa');
    if (bCalc) {
      bCalc.addEventListener('click', function () {
        postCalcular(false);
      });
    }
    if (bRecalc) {
      bRecalc.addEventListener('click', function () {
        postCalcular(true);
      });
    }

    if (!initial.roteiro_id && bCalc) {
      bCalc.setAttribute('title', 'Salve o roteiro para habilitar o cálculo.');
    }

    if (initial.route) {
      updateSummary(initial.route, { status: initial.status });
      drawRoute(initial.route.geometry);
      toggleRecalc(!!initial.route.geometry);
    } else {
      toggleRecalc(false);
    }

    if (initial.status === 'desatualizada') {
      var stale = $('roteiro-mapa-stale-hint');
      if (stale) stale.classList.remove('d-none');
    }
  }

  function onDestinosReordered() {
    if (!hadGeometry) return;
    var stale = $('roteiro-mapa-stale-hint');
    if (stale) stale.classList.remove('d-none');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.RoteirosMap = { onDestinosReordered: onDestinosReordered };
})();
