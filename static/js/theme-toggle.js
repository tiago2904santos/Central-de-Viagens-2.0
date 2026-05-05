(function () {
  "use strict";

  var STORAGE_KEY = "cv-theme";

  function getStoredTheme() {
    try {
      var saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "light" || saved === "dark") {
        return saved;
      }
    } catch (e) {}
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    if (theme !== "light" && theme !== "dark") {
      theme = "light";
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
      }
    } catch (e) {}

    document.querySelectorAll("[data-theme-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-theme-mode");
        if (mode === "light" || mode === "dark") {
          applyTheme(mode);
        }
      });
    });
  });
})();
