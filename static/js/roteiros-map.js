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

  var mapInstance = null;
  var routeLayer = null;
  var markerLayer = null;
  var lastRouteBounds = null;
  var lastFocusedPointKey = null;
  var LEG_COLORS = ['#0f5f8f', '#1d74a3'];
  var initial = readJsonScript('roteiro-mapa-inicial') || {};
  var mapConfig = window.ROTEIRO_MAP_CONFIG || {};
  // Prioriza sempre o valor resolvido no backend (CEP/configuração do sistema).
  // O config global fica como fallback de compatibilidade.
  var defaultCenter = Array.isArray(initial.default_center)
    ? initial.default_center
    : (Array.isArray(mapConfig.defaultCenter) ? mapConfig.defaultCenter : [-24.89, -51.55]);
  var defaultZoom = Number.isFinite(Number(initial.default_zoom))
    ? Number(initial.default_zoom)
    : (Number.isFinite(Number(mapConfig.defaultZoom)) ? Number(mapConfig.defaultZoom) : 7);
  var rid = initial.roteiro_id;
  var hadGeometry = !!(initial.route && initial.route.geometry && initial.route.geometry.type === 'LineString');

  function $(id) {
    return document.getElementById(id);
  }

  function persistRouteInForm(route, points) {
    var geometryInput = $('id_map_route_geometry_json');
    var pointsInput = $('id_map_route_points_json');
    var distanceInput = $('id_map_route_distance_km');
    var durationInput = $('id_map_route_duration_minutes');
    var providerInput = $('id_map_route_provider');
    var calculatedAtInput = $('id_map_route_calculated_at');
    if (!geometryInput || !pointsInput) return;

    var geometry = route && route.geometry ? route.geometry : null;
    geometryInput.value = geometry ? JSON.stringify(geometry) : '';
    pointsInput.value = Array.isArray(points) ? JSON.stringify(points) : '';
    if (distanceInput) {
      distanceInput.value =
        route && route.distance_km != null ? String(route.distance_km) : '';
    }
    if (durationInput) {
      durationInput.value =
        route && route.duration_minutes != null ? String(route.duration_minutes) : '';
    }
    if (providerInput) {
      providerInput.value = route && route.provider ? String(route.provider) : '';
    }
    if (calculatedAtInput) {
      var calculatedAt = route && (route.calculated_at_iso || route.calculated_at);
      calculatedAtInput.value = calculatedAt ? String(calculatedAt) : '';
    }
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

  function isDailyRoundTripActive() {
    var toggle = document.getElementById('id_bate_volta_diario_ativo');
    return !!(toggle && toggle.checked);
  }

  function setRecalcularEnabled(on) {
    var b = $('btn-recalcular-rota-mapa');
    if (!b) return;
    b.disabled = !on;
    b.setAttribute('aria-disabled', on ? 'false' : 'true');
  }

  function currentDateTimeBr() {
    try {
      return new Intl.DateTimeFormat('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(new Date());
    } catch (e) {
      return '—';
    }
  }

  function resolveCalculatedAt(route) {
    if (!route) return '—';
    return route.calculated_at_display || route.calculated_at || currentDateTimeBr();
  }

  function updateSummary(route, extra) {
    var box = $('roteiro-mapa-summary');
    if (!box) return;
    showElement(box);
    var dist = $('roteiro-mapa-distancia');
    var tempo = $('roteiro-mapa-tempo');
    var fonte = $('roteiro-mapa-fonte');
    var em = $('roteiro-mapa-calculada-em');
    if (!route) {
      if (dist) dist.textContent = '—';
      if (tempo) tempo.textContent = '—';
      if (fonte) fonte.textContent = '—';
      if (em) em.textContent = '—';
      return;
    }
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
    if (em) em.textContent = resolveCalculatedAt(route);
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
      mapInstance = L.map(container, { scrollWheelZoom: false }).setView(defaultCenter, defaultZoom);
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

  function clearMapLayers() {
    if (routeLayer && mapInstance) {
      mapInstance.removeLayer(routeLayer);
      routeLayer = null;
    }
    if (markerLayer && mapInstance) {
      mapInstance.removeLayer(markerLayer);
      markerLayer = null;
    }
    lastRouteBounds = null;
    lastFocusedPointKey = null;
  }

  function buildLatLngBounds() {
    return L.latLngBounds([]);
  }

  function addPointMarkers(points, bounds) {
    if (!Array.isArray(points) || !points.length || !mapInstance) return;
    if (!markerLayer) markerLayer = L.layerGroup().addTo(mapInstance);
    var seen = {};
    points.forEach(function (p) {
      if (p == null) return;
      var lat = Number(p.lat);
      var lng = Number(p.lng);
      if (Number.isNaN(lat) || Number.isNaN(lng)) return;
      var label = String(p.label || '');
      var key = lat.toFixed(6) + '|' + lng.toFixed(6) + '|' + label;
      if (seen[key]) return;
      seen[key] = true;
      var pointId = String(p.id || '');
      var inferredKind = pointId.indexOf('origem-') === 0 ? 'origem' : (pointId.indexOf('destino-') === 0 ? 'destino' : '');
      var kind = String(p.kind || inferredKind).toLowerCase();
      var isSede = kind === 'origem';
      var marker = L.circleMarker([lat, lng], {
        radius: isSede ? 7 : 6,
        color: isSede ? '#0b3f67' : '#0f6e8f',
        weight: isSede ? 3 : 2,
        fillColor: '#ffffff',
        fillOpacity: 1,
      });
      if (label) {
        marker.bindTooltip(label, {
          permanent: true,
          interactive: true,
          direction: 'top',
          offset: [0, -12],
          className:
            'roteiro-mapa__city-tooltip ' +
            (isSede ? 'roteiro-mapa__city-tooltip--sede' : 'roteiro-mapa__city-tooltip--destino'),
        });
      }
      marker.on('click', function () {
        focusMapPoint(lat, lng, { zoom: 12 });
      });
      marker.addTo(markerLayer);
      if (bounds) bounds.extend([lat, lng]);
    });
  }

  function focusMapPoint(lat, lng, options) {
    ensureMap();
    if (!mapInstance) return;
    var zoom = (options && Number(options.zoom)) || 12;
    var pointKey = lat.toFixed(6) + '|' + lng.toFixed(6);
    var center = mapInstance.getCenter();
    var alreadyFocused =
      lastFocusedPointKey === pointKey &&
      mapInstance.getZoom() >= zoom &&
      Math.abs(center.lat - lat) < 0.00005 &&
      Math.abs(center.lng - lng) < 0.00005;
    if (alreadyFocused) return;
    lastFocusedPointKey = pointKey;
    mapInstance.flyTo([lat, lng], zoom, {
      animate: true,
      duration: 0.75,
    });
  }

  function fitFullRoute() {
    if (!mapInstance || !lastRouteBounds || !lastRouteBounds.isValid()) return;
    mapInstance.fitBounds(lastRouteBounds, {
      padding: [40, 40],
      maxZoom: 12,
    });
  }

  function addStyledLine(layerParent, geometry, color) {
    var halo = L.geoJSON(
      { type: 'Feature', properties: {}, geometry: geometry },
      { style: { color: '#ffffff', weight: 9, opacity: 0.85, lineCap: 'round', lineJoin: 'round' } }
    );
    var line = L.geoJSON(
      { type: 'Feature', properties: {}, geometry: geometry },
      { style: { color: color, weight: 5, opacity: 0.96, lineCap: 'round', lineJoin: 'round' } }
    );
    halo.addTo(layerParent);
    line.addTo(layerParent);
    return line;
  }

  /**
   * Desenha rota (segmentada por leg quando disponível). Retorna true se desenhou algo.
   */
  function drawRoute(geometry, geomWarning, legs, points) {
    ensureMap();
    var container = $('roteiro-mapa-container');
    if (!container || typeof L === 'undefined') return false;

    clearMapLayers();

    var warn = geomWarning || '';
    var bounds = buildLatLngBounds();
    var drewSomething = false;
    routeLayer = L.layerGroup().addTo(mapInstance);

    var legsWithGeometry = Array.isArray(legs)
      ? legs.filter(function (leg) {
          return (
            leg &&
            leg.geometry &&
            leg.geometry.type === 'LineString' &&
            Array.isArray(leg.geometry.coordinates) &&
            leg.geometry.coordinates.length
          );
        })
      : [];

    if (legsWithGeometry.length) {
      legsWithGeometry.forEach(function (leg, idx) {
        try {
          var color = LEG_COLORS[(Number(leg.color_index) || idx) % LEG_COLORS.length];
          var layer = addStyledLine(routeLayer, leg.geometry, color);
          if (layer.getBounds && layer.getBounds().isValid()) bounds.extend(layer.getBounds());
          drewSomething = true;
        } catch (e) {
          /* ignore leg geometry error and continue */
        }
      });
    }

    if (!drewSomething) {
      if (
        !geometry ||
        geometry.type !== 'LineString' ||
        !geometry.coordinates ||
        !geometry.coordinates.length
      ) {
        setFramePlaceholder(true);
        addPointMarkers(points, bounds);
        if (bounds.isValid()) mapInstance.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
        if (warn) showError(warn);
        return false;
      }
      try {
        var single = addStyledLine(routeLayer, geometry, '#0f5f8f');
        if (single.getBounds && single.getBounds().isValid()) bounds.extend(single.getBounds());
        drewSomething = true;
      } catch (e) {
        showError(MSG_GEOM_DESENHO);
        setFramePlaceholder(true);
        return false;
      }
    }

    addPointMarkers(points, bounds);

    try {
      setFramePlaceholder(false);
      if (bounds.isValid()) {
        lastRouteBounds = bounds;
        fitFullRoute();
      } else {
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

  function toggleFit(show) {
    var b3 = $('btn-fit-rota-mapa');
    if (!b3) return;
    if (show) showElement(b3);
    else hideElement(b3);
  }

  function postCalcular(force) {
    var form = document.getElementById('oficio-step3-form');
    if (!form) return;
    var urlPersistido = form.getAttribute('data-api-calcular-rota-url');
    var urlPreview = form.getAttribute('data-api-calcular-rota-preview-url');
    var hasSaved = !!rid;
    var step3 = window.RoteirosStep3;
    if (isDailyRoundTripActive()) {
      showError('Desative o modo bate-volta diário para calcular a rota pelo mapa.');
      return;
    }
    if (!hasSaved && (!step3 || !step3.canCalculateRoutePreview || !step3.canCalculateRoutePreview())) {
      showError('Defina origem e destinos antes de calcular a rota.');
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
      showError('Defina origem e destinos antes de calcular a rota.');
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
        initial.legs = Array.isArray(res.body.legs) ? res.body.legs : [];
        initial.points = Array.isArray(res.body.points) ? res.body.points : [];
        persistRouteInForm(route, initial.points);
        initial.status = route.status || 'calculada';
        hadGeometry = !!(route.geometry && route.geometry.type === 'LineString');
        updateSummary(route, { status: initial.status });

        var gw = route.geometry_warning || res.body.geometry_warning;
        var drew = drawRoute(route.geometry, gw, res.body.legs, res.body.points);
        if (!drew && route.distance_km != null && !gw) {
          showError(MSG_GEOM_DESENHO);
        } else if (!drew && gw) {
          showError(gw);
        } else if (drew) {
          showError('');
        }

        toggleRecalc(true);
        toggleFit(!!lastRouteBounds);
        hideElement($('roteiro-mapa-stale-hint'));
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
    var step3 = window.RoteirosStep3;
    var canPreview = !!(step3 && step3.canCalculateRoutePreview && step3.canCalculateRoutePreview());
    var blockedByLoop = isDailyRoundTripActive();
    var canCalculate = !blockedByLoop && (rid || canPreview);
    setCalcularEnabled(canCalculate);
    setRecalcularEnabled(!blockedByLoop && !!rid);
    if (blockedByLoop) {
      showError('Desative o modo bate-volta diário para calcular a rota pelo mapa.');
    } else if (($('roteiro-mapa-error') || {}).textContent === 'Desative o modo bate-volta diário para calcular a rota pelo mapa.') {
      showError('');
    }
  }

  function init() {
    var form = document.getElementById('oficio-step3-form');
    var container = $('roteiro-mapa-container');
    if (!form || !container) return;

    hideElement($('roteiro-mapa-loading'));
    hideElement($('roteiro-mapa-error'));

    var stale = $('roteiro-mapa-stale-hint');

    if (!rid) {
      setCalcularEnabled(false);
      hideElement($('btn-recalcular-rota-mapa'));
      hideElement($('btn-fit-rota-mapa'));
      hideElement(stale);
      updateSummary(null, null);
      ensureMap();
      setFramePlaceholder(true);
      toggleRecalc(false);
    } else {
      setCalcularEnabled(true);
      if (initial.route) {
        persistRouteInForm(initial.route, initial.points);
        updateSummary(initial.route, { status: initial.status });
        var gwInit = initial.route.geometry_warning;
        var drew = drawRoute(initial.route.geometry, gwInit, initial.legs, initial.points);
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
        toggleFit(!!lastRouteBounds);
      } else {
        updateSummary(null, null);
        toggleRecalc(false);
        toggleFit(false);
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
    var bFit = $('btn-fit-rota-mapa');
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
    if (bFit) {
      bFit.addEventListener('click', function () {
        fitFullRoute();
      });
    }
    document.addEventListener('click', function (event) {
      var trigger = event.target && event.target.closest
        ? event.target.closest('[data-map-focus-lat][data-map-focus-lng]')
        : null;
      if (!trigger) return;
      var lat = Number(trigger.getAttribute('data-map-focus-lat'));
      var lng = Number(trigger.getAttribute('data-map-focus-lng'));
      if (Number.isNaN(lat) || Number.isNaN(lng)) return;
      var mapSection = document.getElementById('sec-mapa-rota');
      if (mapSection && mapSection.scrollIntoView) {
        mapSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      setTimeout(function () {
        focusMapPoint(lat, lng, { zoom: 12 });
      }, 350);
    });
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
