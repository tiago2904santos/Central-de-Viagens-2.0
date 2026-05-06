(function () {
  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function maskCep(value) {
    const digits = onlyDigits(value).slice(0, 8);
    if (digits.length <= 5) return digits;
    return `${digits.slice(0, 5)}-${digits.slice(5)}`;
  }

  function setFieldError(input, message) {
    if (!input) return;
    input.setCustomValidity(message || "");
    input.classList.toggle("is-invalid", Boolean(message));
    if (message) input.reportValidity();
  }

  async function buscarCep(cepInput, fields) {
    const cepDigits = onlyDigits(cepInput.value);
    if (!cepDigits) {
      setFieldError(cepInput, "");
      return;
    }
    if (cepDigits.length !== 8) {
      setFieldError(cepInput, "CEP deve conter 8 dígitos.");
      return;
    }

    setFieldError(cepInput, "");
    const endpoint = cepInput.dataset.cepLookupUrlTemplate.replace("00000000", cepDigits);

    try {
      const response = await fetch(endpoint, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      const payload = await response.json();
      if (!response.ok) {
        setFieldError(cepInput, payload.erro || "CEP inválido.");
        return;
      }

      if (fields.logradouro) fields.logradouro.value = payload.logradouro || "";
      if (fields.bairro) fields.bairro.value = payload.bairro || "";
      if (fields.cidade) fields.cidade.value = (payload.cidade || "").toUpperCase();
      if (fields.uf) fields.uf.value = (payload.uf || "").toUpperCase();
    } catch (_error) {
      setFieldError(cepInput, "Não foi possível consultar o CEP agora.");
    }
  }

  function initConfiguracoesForm(form) {
    ["#id_divisao", "#id_unidade", "#id_logradouro", "#id_bairro", "#id_cidade_endereco", "#id_uf"].forEach(
      (selector) => {
        const input = form.querySelector(selector);
        if (!input) return;
        input.addEventListener("input", () => {
          input.value = input.value.toUpperCase();
        });
      }
    );

    const cepInput = form.querySelector("#id_cep");
    const lookupUrlTemplate = form.dataset.cepLookupUrlTemplate || "";
    if (!cepInput || !lookupUrlTemplate) return;
    cepInput.dataset.cepLookupUrlTemplate = lookupUrlTemplate;

    const fields = {
      logradouro: form.querySelector("#id_logradouro"),
      bairro: form.querySelector("#id_bairro"),
      cidade: form.querySelector("#id_cidade_endereco"),
      uf: form.querySelector("#id_uf"),
    };

    let lastCepLookup = "";
    const maybeLookup = () => {
      cepInput.value = maskCep(cepInput.value);
      const cepDigits = onlyDigits(cepInput.value);
      if (cepDigits.length !== 8) return;
      if (cepDigits === lastCepLookup) return;
      lastCepLookup = cepDigits;
      buscarCep(cepInput, fields);
    };

    cepInput.addEventListener("input", maybeLookup);
    cepInput.addEventListener("blur", maybeLookup);

    const ufInput = form.querySelector("#id_uf");
    if (ufInput) {
      ufInput.addEventListener("blur", () => {
        ufInput.value = (ufInput.value || "").toUpperCase().slice(0, 2);
      });
    }

    const telefoneInput = form.querySelector("#id_telefone");
    if (telefoneInput) {
      telefoneInput.addEventListener("input", () => {
        telefoneInput.value = telefoneInput.value.replace(/[^\d() -]/g, "");
      });
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
