document.addEventListener("DOMContentLoaded", () => {
  const transladoToggle = document.getElementById("id_teve_translado");
  const passagemToggle = document.getElementById("id_teve_passagem");
  const transladoWrap = document.querySelector('[data-money-wrapper="translado"]');
  const passagemWrap = document.querySelector('[data-money-wrapper="passagem"]');
  const transladoInput = document.getElementById("id_valor_translado");
  const passagemInput = document.getElementById("id_valor_passagem");

  const formatMoney = (value) => {
    const clean = String(value || "").replace(/[^\d,.-]/g, "").replace(",", ".");
    const parsed = Number(clean);
    if (Number.isNaN(parsed)) {
      return "";
    }
    return parsed.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  };

  const bindCurrencyField = (input) => {
    if (!input) return;
    input.addEventListener("blur", () => {
      input.value = formatMoney(input.value);
    });
    if (input.value) {
      input.value = formatMoney(input.value);
    }
  };

  const syncToggles = () => {
    if (transladoWrap && transladoToggle) {
      transladoWrap.style.display = transladoToggle.checked ? "block" : "none";
      if (!transladoToggle.checked && transladoInput) transladoInput.value = "";
    }
    if (passagemWrap && passagemToggle) {
      passagemWrap.style.display = passagemToggle.checked ? "block" : "none";
      if (!passagemToggle.checked && passagemInput) passagemInput.value = "";
    }
  };

  if (transladoToggle) transladoToggle.addEventListener("change", syncToggles);
  if (passagemToggle) passagemToggle.addEventListener("change", syncToggles);
  bindCurrencyField(transladoInput);
  bindCurrencyField(passagemInput);
  syncToggles();

  const modelBindings = [
    { selectId: "id_conclusao_modelo", textareaId: "id_conclusao" },
    { selectId: "id_medidas_modelo", textareaId: "id_medidas" },
    { selectId: "id_info_modelo", textareaId: "id_informacoes_complementares" },
  ];
  modelBindings.forEach(({ selectId, textareaId }) => {
    const select = document.getElementById(selectId);
    const textarea = document.getElementById(textareaId);
    if (!select || !textarea) return;
    select.addEventListener("change", () => {
      const option = select.options[select.selectedIndex];
      if (!option || !option.value) return;
      const text = option.dataset.text || "";
      if (text) textarea.value = text;
    });
  });

  const copyText = async (text) => {
    const value = String(text || "");
    if (!value) return false;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return true;
      } catch (error) {
      }
    }
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    document.body.appendChild(textarea);
    textarea.select();
    let copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (error) {
      copied = false;
    }
    textarea.remove();
    return copied;
  };

  const showCopyFeedback = (button) => {
    if (!button) return;
    const label = button.querySelector("span") || button;
    const original = label.textContent;
    const feedback = button.getAttribute("data-copy-feedback") || "Copiado";
    button.classList.add("is-copied");
    label.textContent = feedback;
    window.setTimeout(() => {
      button.classList.remove("is-copied");
      label.textContent = original;
    }, 1800);
  };

  document.querySelectorAll("[data-copy-line]").forEach((button) => {
    button.addEventListener("click", async () => {
      const row = button.closest(".prestacao-copy-row");
      const textElement = row ? row.querySelector("[data-copy-text]") : null;
      const copied = await copyText(textElement ? textElement.textContent.trim() : "");
      if (copied) showCopyFeedback(button);
    });
  });

  document.querySelectorAll("[data-copy-all]").forEach((button) => {
    button.addEventListener("click", async () => {
      const root = document.querySelector("[data-copy-list]");
      const lines = Array.from(root ? root.querySelectorAll("[data-copy-text]") : [])
        .map((element) => element.textContent.trim())
        .filter(Boolean);
      const copied = await copyText(lines.join("\n"));
      if (copied) showCopyFeedback(button);
    });
  });
});
