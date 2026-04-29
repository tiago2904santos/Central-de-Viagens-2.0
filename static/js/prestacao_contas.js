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
});
