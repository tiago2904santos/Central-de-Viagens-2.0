(function () {
  'use strict';

  function csrfFromForm(form) {
    var tokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return (tokenInput && tokenInput.value) || '';
  }

  function fieldValue(input) {
    if (!input) return null;
    if (input.type === 'checkbox') return !!input.checked;
    if (input.type === 'radio') return !!input.checked ? input.value : null;
    return input.value;
  }

  function createFormAutosave(form, options) {
    var model = (options && options.model) || form.dataset.autosaveModel || '';
    var statusElement = options && options.statusElement;
    var dirtyFields = new Set();
    var dirtySnapshots = new Set();
    var inputTimer = null;
    var paused = false;
    var submitting = false;
    var inFlight = null;
    var abortController = null;
    var queueAfterFlight = false;

    function emit(name, detail) {
      form.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    }

    function setState(state) {
      form.dataset.autosaveState = state;
      if (statusElement) statusElement.dataset.state = state;
    }

    function objectId() {
      return String(form.dataset.autosaveObjectId || '');
    }

    function autosaveUrl() {
      return objectId() ? String(form.dataset.autosaveUrl || '') : String(form.dataset.autosaveCreateUrl || '');
    }

    function buildPayload() {
      var fields = {};
      dirtyFields.forEach(function (name) {
        var input = form.querySelector('[name="' + name + '"]');
        if (!input) return;
        var val = fieldValue(input);
        if (val === null) return;
        fields[name] = val;
      });

      var snapshots = {};
      var provider = (window.AppAutosaveSnapshots || {})[model];
      if (typeof provider === 'function') {
        snapshots = provider(form, { dirtySnapshots: Array.from(dirtySnapshots) }) || {};
      }
      return {
        object_id: objectId(),
        form_id: form.id || '',
        model: model,
        dirty_fields: Array.from(dirtyFields),
        fields: fields,
        snapshots: snapshots
      };
    }

    function shouldCreate(payload) {
      if (payload.object_id) return true;
      var validator = (window.AppAutosaveValidators || {})[model];
      if (typeof validator !== 'function') return true;
      return !!validator(payload, form);
    }

    function applyCreation(data) {
      if (!data || !data.created || !data.object_id) return;
      form.dataset.autosaveObjectId = String(data.object_id);
      var editUrl = form.dataset.autosaveEditUrlTemplate || '';
      if (editUrl.indexOf('__ID__') !== -1) {
        form.dataset.autosaveUrl = editUrl.replace('__ID__', String(data.object_id));
      }
      emit('autosave:created', data);
    }

    function send() {
      if (paused || submitting) return Promise.resolve(false);
      var url = autosaveUrl();
      if (!url) return Promise.resolve(false);

      var payload = buildPayload();
      if (!payload.dirty_fields.length && !dirtySnapshots.size) return Promise.resolve(false);
      if (!shouldCreate(payload)) return Promise.resolve(false);
      if (inFlight) {
        queueAfterFlight = true;
        return inFlight;
      }

      setState('saving');
      emit('autosave:before', payload);
      abortController = new AbortController();
      inFlight = fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfFromForm(form),
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify(payload),
        signal: abortController.signal
      }).then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data.ok) throw new Error((data && data.message) || 'Falha no autosave.');
          dirtyFields.clear();
          dirtySnapshots.clear();
          applyCreation(data);
          setState('saved');
          emit('autosave:success', data);
          return true;
        });
      }).catch(function (error) {
        if (error && error.name === 'AbortError') return false;
        setState('error');
        emit('autosave:error', { message: error && error.message ? error.message : 'Falha no autosave.' });
        return false;
      }).finally(function () {
        inFlight = null;
        abortController = null;
        if (queueAfterFlight) {
          queueAfterFlight = false;
          schedule(450);
        }
      });
      return inFlight;
    }

    function schedule(delay) {
      if (paused || submitting) return;
      window.clearTimeout(inputTimer);
      inputTimer = window.setTimeout(send, typeof delay === 'number' ? delay : 1200);
    }

    function markDirty(fieldName) {
      if (!fieldName) return;
      dirtyFields.add(String(fieldName));
    }

    function markSnapshotChanged(name) {
      dirtySnapshots.add(name || 'default');
    }

    form.addEventListener('input', function (event) {
      var target = event.target;
      if (!target || !target.name || target.type === 'hidden') return;
      markDirty(target.name);
      schedule(1200);
    });
    form.addEventListener('change', function (event) {
      var target = event.target;
      if (!target || !target.name) return;
      markDirty(target.name);
      schedule(900);
    });
    form.addEventListener('blur', function (event) {
      var target = event.target;
      if (!target || !target.name) return;
      markDirty(target.name);
      schedule(350);
    }, true);

    form.addEventListener('submit', function () {
      submitting = true;
      window.clearTimeout(inputTimer);
      if (abortController) abortController.abort();
      paused = true;
    }, true);

    window.addEventListener('beforeunload', function () {
      if (!navigator.sendBeacon) return;
      if (paused || submitting) return;
      var url = autosaveUrl();
      if (!url) return;
      var payload = buildPayload();
      if (!payload.dirty_fields.length && !dirtySnapshots.size) return;
      if (!shouldCreate(payload)) return;
      var blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
      navigator.sendBeacon(url, blob);
    });

    return {
      schedule: schedule,
      flush: function () {
        window.clearTimeout(inputTimer);
        return send();
      },
      pause: function () { paused = true; },
      resume: function () { paused = false; },
      markDirty: markDirty,
      markSnapshotChanged: markSnapshotChanged
    };
  }

  var forms = new WeakMap();
  window.AppAutosave = {
    init: function () {
      var nodes = document.querySelectorAll('form[data-autosave="true"]');
      nodes.forEach(function (form) {
        if (forms.has(form)) return;
        forms.set(form, createFormAutosave(form, {}));
      });
    },
    registerForm: function (form, options) {
      if (!form) return null;
      if (forms.has(form)) return forms.get(form);
      var instance = createFormAutosave(form, options || {});
      forms.set(form, instance);
      return instance;
    },
    flush: function (form) {
      var instance = forms.get(form);
      return instance ? instance.flush() : Promise.resolve(false);
    },
    pause: function (form) {
      var instance = forms.get(form);
      if (instance) instance.pause();
    },
    resume: function (form) {
      var instance = forms.get(form);
      if (instance) instance.resume();
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { window.AppAutosave.init(); });
  } else {
    window.AppAutosave.init();
  }
})();
