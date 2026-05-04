(function () {
  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function onlyAlnum(value) {
    return (value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  }

  function maskCpf(value) {
    const v = onlyDigits(value).slice(0, 11);
    if (v.length <= 3) return v;
    if (v.length <= 6) return `${v.slice(0, 3)}.${v.slice(3)}`;
    if (v.length <= 9) return `${v.slice(0, 3)}.${v.slice(3, 6)}.${v.slice(6)}`;
    return `${v.slice(0, 3)}.${v.slice(3, 6)}.${v.slice(6, 9)}-${v.slice(9)}`;
  }

  function maskRg(value) {
    const v = onlyAlnum(value).slice(0, 9);
    if (v.length <= 2) return v;
    if (v.length <= 5) return `${v.slice(0, 2)}.${v.slice(2)}`;
    if (v.length <= 8) return `${v.slice(0, 2)}.${v.slice(2, 5)}.${v.slice(5)}`;
    return `${v.slice(0, 2)}.${v.slice(2, 5)}.${v.slice(5, 8)}-${v.slice(8)}`;
  }

  function maskPlaca(value) {
    return onlyAlnum(value).slice(0, 7);
  }

  function maskUpper(value) {
    return (value || "").toUpperCase();
  }

  function applyMask(input) {
    const mask = input.dataset.mask;
    if (mask === "upper") input.value = maskUpper(input.value);
    if (mask === "cpf") input.value = maskCpf(input.value);
    if (mask === "rg") input.value = maskRg(input.value);
    if (mask === "placa") input.value = maskPlaca(input.value);
  }

  function initMasks() {
    document.querySelectorAll("input[data-mask]").forEach((input) => {
      applyMask(input);
      input.addEventListener("input", () => applyMask(input));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMasks);
  } else {
    initMasks();
  }
})();
