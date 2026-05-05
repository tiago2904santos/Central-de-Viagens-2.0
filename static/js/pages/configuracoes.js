(function () {
  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function setAlert(form, message) {
    const alert = form.querySelector("[data-cep-alert]");
    if (!alert) return;
    if (!message) {
      alert.textContent = "";
      alert.hidden = true;
      return;
    }
    alert.textContent = message;
    alert.hidden = false;
  }

  function buildCepUrl(templateUrl, cep) {
    return (templateUrl || "").replace("00000000", cep);
  }

  function fillAddress(form, data) {
    const mapping = {
      id_logradouro: data.logradouro || "",
      id_bairro: data.bairro || "",
      id_cidade_endereco: data.cidade || "",
      id_uf: data.uf || "",
    };
    Object.entries(mapping).forEach(([id, value]) => {
      const input = form.querySelector(`#${id}`);
      if (input) input.value = value;
    });
    const cep = form.querySelector("#id_cep");
    if (cep && data.cep) cep.value = data.cep;
  }

  async function consultarCep(form) {
    const cepInput = form.querySelector("#id_cep");
    if (!cepInput) return;

    const cep = onlyDigits(cepInput.value);
    if (cep.length !== 8) return;

    setAlert(form, "");
    try {
      const response = await fetch(buildCepUrl(form.dataset.cepApiUrl, cep), {
        headers: { Accept: "application/json" },
      });
      const data = await response.json();
      if (!response.ok) {
        setAlert(form, data.erro || "Não foi possível consultar o CEP.");
        return;
      }
      fillAddress(form, data);
    } catch (_error) {
      setAlert(form, "Não foi possível consultar o CEP.");
    }
  }

  function initConfiguracoesForm(form) {
    ["#id_divisao", "#id_unidade", "#id_sigla_orgao", "#id_uf"].forEach((selector) => {
      const input = form.querySelector(selector);
      if (!input) return;
      input.addEventListener("input", () => {
        input.value = input.value.toUpperCase();
      });
    });

    const cepInput = form.querySelector("#id_cep");
    if (cepInput) {
      cepInput.addEventListener("input", () => {
        if (onlyDigits(cepInput.value).length === 8) consultarCep(form);
      });
      cepInput.addEventListener("blur", () => consultarCep(form));
    }
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
