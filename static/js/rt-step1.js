(function() {
  function parseBooleanFromRadio(name) {
    var checked = document.querySelector('input[name="' + name + '"]:checked');
    return checked && checked.value === '1';
  }

  function formatCurrency(value) {
    var clean = String(value || "").replace(/[^\d,.-]/g, "").replace(",", ".");
    var parsed = Number(clean);
    if (Number.isNaN(parsed)) {
      return "";
    }
    return parsed.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  function init() {
    var form = document.getElementById("prestacao-rt-step1-form");
    if (!form || form.dataset.rtStepInit === "1") {
      return;
    }
    form.dataset.rtStepInit = "1";

    var autosaveUrl = form.getAttribute("data-autosave-url") || window.location.href;
    var statusElement = document.getElementById("rt-autosave-status");
    var docStatusElement = document.getElementById("rt-document-status");

    function setDocumentStatus(stale) {
      if (!docStatusElement) {
        return;
      }
      docStatusElement.classList.toggle("is-stale", !!stale);
      docStatusElement.classList.toggle("is-updated", !stale);
      docStatusElement.textContent = stale ? "Documento desatualizado" : "Documento atualizado";
    }

    var autosave = window.OficioWizard && typeof window.OficioWizard.createAutosave === "function"
      ? window.OficioWizard.createAutosave({
          form: form,
          url: autosaveUrl,
          statusElement: statusElement,
          statusMessages: {
            idle: "Autosave ativo.",
            saving: "Salvando...",
            saved: "Salvo.",
            error: "Erro ao salvar."
          },
          onSuccess: function(payload) {
            setDocumentStatus(payload.documento_status !== "atualizado");
          }
        })
      : null;

    function scheduleAutosave() {
      if (autosave) {
        autosave.schedule();
      }
      setDocumentStatus(true);
    }

    function bindMoneyField(input) {
      if (!input) {
        return;
      }
      input.addEventListener("blur", function() {
        input.value = formatCurrency(input.value);
      });
      if (input.value) {
        input.value = formatCurrency(input.value);
      }
    }

    var transladoInput = document.getElementById("id_valor_translado");
    var passagemInput = document.getElementById("id_valor_passagem");
    var transladoWrap = document.querySelector('[data-money-wrapper="translado"]');
    var passagemWrap = document.querySelector('[data-money-wrapper="passagem"]');

    function syncChoiceVisual(name) {
      form.querySelectorAll('input[name="' + name + '"]').forEach(function(input) {
        var option = input.closest(".oficio-step4-choice-option");
        if (!option) {
          return;
        }
        option.classList.toggle("is-selected", !!input.checked);
      });
    }

    function syncConditionalFields() {
      var teveTranslado = parseBooleanFromRadio("teve_translado");
      var tevePassagem = parseBooleanFromRadio("teve_passagem");
      if (transladoWrap) {
        transladoWrap.style.display = teveTranslado ? "block" : "none";
      }
      if (!teveTranslado && transladoInput) {
        transladoInput.value = "";
      }
      if (passagemWrap) {
        passagemWrap.style.display = tevePassagem ? "block" : "none";
      }
      if (!tevePassagem && passagemInput) {
        passagemInput.value = "";
      }
      syncChoiceVisual("teve_translado");
      syncChoiceVisual("teve_passagem");
    }

    form.querySelectorAll('input[name="teve_translado"], input[name="teve_passagem"]').forEach(function(input) {
      input.addEventListener("change", function() {
        syncConditionalFields();
        scheduleAutosave();
      });
    });

    [
      { select: "id_conclusao_modelo", target: "id_conclusao" },
      { select: "id_medidas_modelo", target: "id_medidas" },
      { select: "id_info_modelo", target: "id_informacoes_complementares" }
    ].forEach(function(binding) {
      var select = document.getElementById(binding.select);
      var textarea = document.getElementById(binding.target);
      if (!select || !textarea) {
        return;
      }
      select.addEventListener("change", function() {
        var option = select.options[select.selectedIndex];
        if (!option) {
          return;
        }
        if (option.dataset.text) {
          textarea.value = option.dataset.text;
        }
        scheduleAutosave();
      });
      textarea.addEventListener("input", scheduleAutosave);
    });

    bindMoneyField(transladoInput);
    bindMoneyField(passagemInput);
    syncConditionalFields();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
