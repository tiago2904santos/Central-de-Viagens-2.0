(function () {
  function getLabels(root) {
    return {
      on: root.dataset.onLabel || "LIGADA",
      off: root.dataset.offLabel || "DESLIGADA",
    };
  }

  function syncCardToggle(root) {
    const input = root.querySelector('input[type="checkbox"]');
    if (!input) return;

    const labels = getLabels(root);
    const state = root.querySelector("[data-card-toggle-state]");

    root.classList.toggle("is-checked", input.checked);
    root.classList.toggle("is-disabled", input.disabled);
    input.setAttribute("aria-checked", input.checked ? "true" : "false");

    if (state) {
      state.textContent = input.checked ? labels.on : labels.off;
    }
  }

  function initCardToggles() {
    document.querySelectorAll("[data-card-toggle]").forEach((root) => {
      const input = root.querySelector('input[type="checkbox"]');
      if (!input) return;

      syncCardToggle(root);
      input.addEventListener("change", () => syncCardToggle(root));
    });
  }

  function applyServidorSemRgUi(form, opts) {
    const semRg = form.querySelector("#id_sem_rg");
    const rg = form.querySelector("#id_rg");
    const wrap = form.querySelector("[data-rg-field-wrap]");
    if (!semRg || !rg || !wrap) return;

    const active = semRg.checked;
    rg.disabled = active;
    rg.setAttribute("aria-disabled", active ? "true" : "false");
    wrap.classList.toggle("field--locked", active);

    if (opts && opts.clearRgOnLock && active) {
      rg.value = "";
    }
  }

  function initServidorSemRg() {
    const form = document.querySelector("[data-servidor-sem-rg-form]");
    if (!form) return;

    const semRg = form.querySelector("#id_sem_rg");
    if (!semRg) return;

    applyServidorSemRgUi(form, { clearRgOnLock: false });
    semRg.addEventListener("change", () => applyServidorSemRgUi(form, { clearRgOnLock: true }));
  }

  function boot() {
    initCardToggles();
    initServidorSemRg();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
