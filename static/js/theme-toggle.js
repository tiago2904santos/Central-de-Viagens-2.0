(function () {
  "use strict";

  var STORAGE_KEY = "cv-theme";
  var VALID_THEMES = ["dark-light", "dark-dark", "light-light", "light-dark"];

  function normalizeTheme(raw) {
    if (VALID_THEMES.indexOf(raw) >= 0) {
      return raw;
    }
    if (raw === "variant-a") {
      return "dark-light";
    }
    if (raw === "variant-b") {
      return "light-light";
    }
    if (raw === "dark") {
      return "dark-light";
    }
    if (raw === "light") {
      return "light-light";
    }
    return null;
  }

  function getStoredTheme() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      var n = normalizeTheme(saved);
      if (n) {
        return n;
      }
    } catch (e) {}
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark-light" : "light-light";
  }

  function applyTheme(theme) {
    if (VALID_THEMES.indexOf(theme) < 0) {
      theme = "light-light";
    }
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}

    document.querySelectorAll("[data-theme-mode]").forEach(function (btn) {
      var mode = btn.getAttribute("data-theme-mode");
      var pressed = mode === theme;
      btn.setAttribute("aria-pressed", pressed ? "true" : "false");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var initial = getStoredTheme();
    applyTheme(initial);
    try {
      if (localStorage.getItem(STORAGE_KEY) === null) {
        localStorage.setItem(STORAGE_KEY, initial);
      } else {
        var raw = localStorage.getItem(STORAGE_KEY);
        if (normalizeTheme(raw) !== raw) {
          localStorage.setItem(STORAGE_KEY, initial);
        }
      }
    } catch (e) {}

    document.querySelectorAll("[data-theme-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-theme-mode");
        if (VALID_THEMES.indexOf(mode) >= 0) {
          applyTheme(mode);
        }
      });
    });
  });
})();
