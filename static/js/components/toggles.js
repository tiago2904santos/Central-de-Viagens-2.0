(function () {
  function syncToggle(root) {
    const input = root.querySelector('input[type="checkbox"]');
    if (!input) return;
    root.classList.toggle("is-checked", input.checked);
    input.setAttribute("aria-checked", input.checked ? "true" : "false");
  }

  function initAppToggles() {
    document.querySelectorAll("[data-app-toggle]").forEach((root) => {
      const input = root.querySelector('input[type="checkbox"]');
      if (!input) return;
      syncToggle(root);
      input.addEventListener("change", () => syncToggle(root));
    });
  }

  function applyServidorSemRgUi(form, opts) {
    const semRg = form.querySelector("#id_sem_rg");
    const rg = form.querySelector("#id_rg");
    const wrap = form.querySelector("[data-rg-field-wrap]");
    if (!semRg || !rg || !wrap) return;

    const active = semRg.checked;
    rg.disabled = active;
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
    initAppToggles();
    initServidorSemRg();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
