(function () {
  function updateIndexes(root) {
    const rows = Array.from(root.querySelectorAll("[data-diario-trecho-row]")).filter((row) => row.style.display !== "none");
    rows.forEach((row, index) => {
      const ordem = row.querySelector('input[name$="-ordem"]');
      if (ordem) ordem.value = String(index);
      row.querySelectorAll("input, select, textarea, label").forEach((element) => {
        ["name", "id", "for"].forEach((attr) => {
          const value = element.getAttribute(attr);
          if (value) element.setAttribute(attr, value.replace(/trechos-(\d+|__prefix__)-/g, "trechos-" + index + "-"));
        });
      });
    });
  }

  function syncNextKm(root) {
    const rows = Array.from(root.querySelectorAll("[data-diario-trecho-row]")).filter((row) => row.style.display !== "none");
    rows.forEach((row, index) => {
      const finalInput = row.querySelector('input[name$="-km_final"]');
      const next = rows[index + 1];
      if (!next || !finalInput) return;
      const nextInitial = next.querySelector('input[name$="-km_inicial"]');
      if (nextInitial && !nextInitial.value && finalInput.value) {
        nextInitial.value = finalInput.value;
      }
    });
  }

  function validateKm(row) {
    const inicial = row.querySelector('input[name$="-km_inicial"]');
    const final = row.querySelector('input[name$="-km_final"]');
    if (!inicial || !final || !inicial.value || !final.value) return;
    const invalid = Number(final.value) < Number(inicial.value);
    final.classList.toggle("is-invalid", invalid);
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("[data-diario-trechos-form]");
    if (!form) return;
    const list = form.querySelector("[data-diario-trechos-list]");
    const template = form.querySelector("[data-empty-trecho-template]");
    const totalInput = form.querySelector('input[name="trechos-TOTAL_FORMS"]');
    if (!list || !template || !totalInput) return;

    form.addEventListener("input", function (event) {
      const row = event.target.closest("[data-diario-trecho-row]");
      if (!row) return;
      if (event.target.name && event.target.name.endsWith("-km_final")) syncNextKm(list);
      validateKm(row);
    });

    form.addEventListener("click", function (event) {
      const add = event.target.closest("[data-add-trecho]");
      if (add) {
        const index = Number(totalInput.value || "0");
        const wrapper = document.createElement("div");
        wrapper.innerHTML = template.innerHTML.replace(/__prefix__/g, String(index));
        const row = wrapper.firstElementChild;
        list.appendChild(row);
        totalInput.value = String(index + 1);
        updateIndexes(list);
        syncNextKm(list);
        return;
      }
      const remove = event.target.closest("[data-remove-trecho]");
      if (remove) {
        const row = remove.closest("[data-diario-trecho-row]");
        const deleteInput = row ? row.querySelector('input[name$="-DELETE"]') : null;
        if (deleteInput) {
          deleteInput.checked = true;
          row.style.display = "none";
        } else if (row) {
          row.remove();
          totalInput.value = String(Math.max(0, Number(totalInput.value || "0") - 1));
        }
        updateIndexes(list);
        syncNextKm(list);
      }
    });
  });
})();
