(function () {
  "use strict";

  var VALID_THEMES = ["dark-light", "dark-dark", "light-light", "light-dark"];
  var STORAGE_KEY = "cv-theme";

  function normalizeTheme(raw) {
    if (VALID_THEMES.indexOf(raw) >= 0) return raw;
    if (raw === "variant-a") return "dark-light";
    if (raw === "variant-b") return "light-light";
    if (raw === "dark") return "dark-light";
    if (raw === "light") return "light-light";
    return null;
  }

  function getInitialTheme() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      var normalized = normalizeTheme(saved);
      if (normalized) return normalized;
    } catch (e) {}

    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark-light" : "light-light";
  }

  var theme = getInitialTheme();
  document.documentElement.setAttribute("data-theme", theme);
})();
