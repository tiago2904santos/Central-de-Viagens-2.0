(function () {
  function getCsrfToken(form) {
    var input = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : "";
  }

  function parseBooleanFromRadio(name) {
    var checked = document.querySelector('input[name="' + name + '"]:checked');
    return checked ? checked.value === "1" : false;
  }

  function formatCurrency(value) {
    var clean = String(value || "").replace(/[^\d,.-]/g, "").replace(",", ".");
    var parsed = Number(clean);
    if (Number.isNaN(parsed)) return "";
    return parsed.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  function init() {
    var form = document.getElementById("prestacao-rt-step1-form");
    if (!form || form.dataset.rtAutosaveInit === "1") return;
    form.dataset.rtAutosaveInit = "1";

    var autosaveUrl = form.getAttribute("data-autosave-url") || window.location.href;
    var statusElement = document.getElementById("rt-autosave-status");
    var docStatusElement = document.getElementById("rt-document-status");
    var debounceMs = 600;
    var timer = null;
    var isSaving = false;
    var pending = new Set();

    var transladoInput = document.getElementById("id_valor_translado");
    var passagemInput = document.getElementById("id_valor_passagem");
    var transladoWrap = document.querySelector('[data-money-wrapper="translado"]');
    var passagemWrap = document.querySelector('[data-money-wrapper="passagem"]');

    function setStatus(message) {
      if (statusElement) statusElement.textContent = message;
    }

    function setDocStale(stale) {
      if (!docStatusElement) return;
      docStatusElement.classList.toggle("is-stale", !!stale);
      docStatusElement.classList.toggle("is-updated", !stale);
      docStatusElement.textContent = stale ? "Documento desatualizado" : "Documento atualizado";
      if (stale) {
        setStatus("Salvo. Gere PDF/DOCX para atualizar o documento.");
      }
    }

    function setChoiceVisual(name) {
      form.querySelectorAll('input[name="' + name + '"]').forEach(function (input) {
        var option = input.closest(".oficio-step4-choice-option");
        if (!option) return;
        option.classList.toggle("is-selected", !!input.checked);
      });
    }

    function syncConditionalFields() {
      var teveTranslado = parseBooleanFromRadio("teve_translado");
      var tevePassagem = parseBooleanFromRadio("teve_passagem");
      if (transladoWrap) transladoWrap.style.display = teveTranslado ? "block" : "none";
      if (passagemWrap) passagemWrap.style.display = tevePassagem ? "block" : "none";
      if (!teveTranslado && transladoInput) transladoInput.value = "";
      if (!tevePassagem && passagemInput) passagemInput.value = "";
      setChoiceVisual("teve_translado");
      setChoiceVisual("teve_passagem");
    }

    function appendField(formData, fieldName) {
      if (fieldName === "atividade_codigos") {
        form.querySelectorAll('input[name="atividade_codigos"]:checked').forEach(function (checkbox) {
          formData.append("atividade_codigos", checkbox.value);
        });
        return;
      }
      var elements = form.querySelectorAll('[name="' + fieldName + '"]');
      if (!elements.length) return;
      var first = elements[0];
      if (first.type === "radio") {
        var checked = form.querySelector('[name="' + fieldName + '"]:checked');
        if (checked) formData.append(fieldName, checked.value);
        return;
      }
      formData.append(fieldName, first.value || "");
    }

    function collectPayload() {
      var formData = new FormData();
      formData.append("autosave", "1");
      formData.append("csrfmiddlewaretoken", getCsrfToken(form));
      pending.forEach(function (fieldName) {
        appendField(formData, fieldName);
      });
      return formData;
    }

    function queueSave(fieldName) {
      pending.add(fieldName);
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(saveNow, debounceMs);
    }

    function saveNow() {
      if (isSaving || pending.size === 0) return;
      isSaving = true;
      setStatus("Salvando...");
      var payload = collectPayload();
      pending.clear();
      fetch(autosaveUrl, {
        method: "POST",
        body: payload,
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCsrfToken(form) },
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (result.ok && result.data && result.data.ok) {
            setDocStale(true);
            return;
          }
          setStatus("Erro ao salvar.");
        })
        .catch(function () {
          setStatus("Erro ao salvar.");
        })
        .finally(function () {
          isSaving = false;
          if (pending.size > 0) saveNow();
        });
    }

    function bindTextField(fieldName, eventName) {
      var el = form.querySelector('[name="' + fieldName + '"]');
      if (!el) return;
      el.addEventListener(eventName, function () {
        queueSave(fieldName);
      });
    }

    function bindMoneyField(fieldName) {
      var el = form.querySelector('[name="' + fieldName + '"]');
      if (!el) return;
      el.addEventListener("input", function () {
        queueSave(fieldName);
      });
      el.addEventListener("blur", function () {
        el.value = formatCurrency(el.value);
        queueSave(fieldName);
      });
      if (el.value) el.value = formatCurrency(el.value);
    }

    form.querySelectorAll('input[name="teve_translado"], input[name="teve_passagem"]').forEach(function (input) {
      input.addEventListener("change", function () {
        syncConditionalFields();
        queueSave(input.name);
        if (input.name === "teve_translado") queueSave("valor_translado");
        if (input.name === "teve_passagem") queueSave("valor_passagem");
      });
    });

    form.querySelectorAll('input[name="atividade_codigos"]').forEach(function (checkbox) {
      checkbox.addEventListener("change", function () {
        queueSave("atividade_codigos");
      });
    });

    bindTextField("atividade", "input");
    bindTextField("conclusao", "input");
    bindTextField("medidas", "input");
    bindTextField("informacoes_complementares", "input");
    bindMoneyField("valor_translado");
    bindMoneyField("valor_passagem");

    [
      { modelField: "conclusao_modelo", textField: "conclusao" },
      { modelField: "medidas_modelo", textField: "medidas" },
      { modelField: "info_modelo", textField: "informacoes_complementares" },
    ].forEach(function (binding) {
      var select = form.querySelector('[name="' + binding.modelField + '"]');
      var textarea = form.querySelector('[name="' + binding.textField + '"]');
      if (!select || !textarea) return;
      select.addEventListener("change", function () {
        var option = select.options[select.selectedIndex];
        if (option && option.dataset.text) {
          textarea.value = option.dataset.text;
          queueSave(binding.textField);
        }
        queueSave(binding.modelField);
      });
    });

    form.querySelectorAll("[data-autosave-link]").forEach(function (link) {
      link.addEventListener("click", function (event) {
        if (pending.size === 0 || isSaving) return;
        event.preventDefault();
        saveNow();
        window.setTimeout(function () {
          window.location.href = link.href;
        }, 450);
      });
    });

    syncConditionalFields();
    setStatus("Autosave ativo.");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
