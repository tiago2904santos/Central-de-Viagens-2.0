(function () {
  function initConfiguracoesForm(form) {
    ["#id_divisao", "#id_unidade", "#id_cidade_endereco"].forEach((selector) => {
      const input = form.querySelector(selector);
      if (!input) return;
      input.addEventListener("input", () => {
        input.value = input.value.toUpperCase();
      });
    });
  }

  function init() {
    document.querySelectorAll("[data-configuracoes-form]").forEach(initConfiguracoesForm);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
