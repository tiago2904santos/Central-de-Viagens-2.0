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
      return false;
    }
    if (cepDigits.length !== 8) {
      setFieldError(cepInput, "CEP deve conter 8 dígitos.");
      return false;
    }

    setFieldError(cepInput, "");
    const endpoint = cepInput.dataset.cepLookupUrlTemplate.replace("00000000", cepDigits);

    try {
      const response = await fetch(endpoint, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      let payload = {};
      try {
        payload = await response.json();
      } catch (_jsonError) {
        payload = {};
      }
      if (response.redirected) {
        setFieldError(cepInput, "Sessão expirada. Atualize a página e tente novamente.");
        return false;
      }
      if (!response.ok) {
        if (response.status === 401) {
          setFieldError(cepInput, "Sessão expirada. Atualize a página e tente novamente.");
          return false;
        }
        setFieldError(cepInput, payload.erro || "CEP inválido.");
        return false;
      }
      if (!payload || typeof payload !== "object" || (!payload.logradouro && !payload.bairro && !payload.cidade && !payload.uf)) {
        setFieldError(cepInput, "Não foi possível consultar o CEP agora.");
        return false;
      }

      if (fields.logradouro) fields.logradouro.value = payload.logradouro || "";
      if (fields.bairro) fields.bairro.value = payload.bairro || "";
      if (fields.cidade) fields.cidade.value = (payload.cidade || "").toUpperCase();
      if (fields.uf) fields.uf.value = (payload.uf || "").toUpperCase();
      return true;
    } catch (_error) {
      setFieldError(cepInput, "Não foi possível consultar o CEP agora.");
      return false;
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
    const lookupUrlTemplate =
      cepInput?.dataset?.cepLookupUrlTemplate ||
      form.dataset.cepLookupUrlTemplate ||
      "/cadastros/api/cep/00000000/";
    if (!cepInput || !lookupUrlTemplate) return;
    cepInput.dataset.cepLookupUrlTemplate = lookupUrlTemplate;

    const fields = {
      logradouro: form.querySelector("#id_logradouro"),
      bairro: form.querySelector("#id_bairro"),
      cidade: form.querySelector("#id_cidade_endereco"),
      uf: form.querySelector("#id_uf"),
    };

    let lastCepLookup = "";
    const maybeLookup = async () => {
      cepInput.value = maskCep(cepInput.value);
      const cepDigits = onlyDigits(cepInput.value);
      if (cepDigits.length !== 8) return;
      if (cepDigits === lastCepLookup) return;
      const ok = await buscarCep(cepInput, fields);
      if (ok) {
        lastCepLookup = cepDigits;
      } else {
        lastCepLookup = "";
      }
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
