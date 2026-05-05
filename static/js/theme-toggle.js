(function () {
  "use strict";

  var STORAGE_KEY = "cv-theme";

  function normalizeTheme(raw) {
    if (raw === "variant-a" || raw === "variant-b") {
      return raw;
    }
    if (raw === "dark") {
      return "variant-a";
    }
    if (raw === "light") {
      return "variant-b";
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
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "variant-a" : "variant-b";
  }

  function applyTheme(theme) {
    if (theme !== "variant-a" && theme !== "variant-b") {
      theme = "variant-b";
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
        if (raw === "light" || raw === "dark") {
          localStorage.setItem(STORAGE_KEY, initial);
        }
      }
    } catch (e) {}

    document.querySelectorAll("[data-theme-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-theme-mode");
        if (mode === "variant-a" || mode === "variant-b") {
          applyTheme(mode);
        }
      });
    });
  });
})();
