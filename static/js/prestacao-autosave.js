(function() {
  function init() {
    if (!window.OficioWizard || typeof window.OficioWizard.createAutosave !== "function") {
      return;
    }
    document.querySelectorAll('form[data-prestacao-autosave="1"]').forEach(function(form) {
      if (form.dataset.prestacaoAutosaveInit === "1") {
        return;
      }
      form.dataset.prestacaoAutosaveInit = "1";
      var autosaveUrl = form.getAttribute("data-autosave-url") || window.location.href;
      window.OficioWizard.createAutosave({
        form: form,
        url: autosaveUrl,
        shouldSchedule: function(event) {
          var target = event && event.target;
          if (!target) return true;
          if (target.type === "file") return false;
          return true;
        },
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
