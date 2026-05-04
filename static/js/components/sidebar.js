(function () {
  const storageKey = "centralViagens.sidebar.openItems";

  function readOpenItems() {
    try {
      return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
    } catch (_error) {
      return new Set();
    }
  }

  function writeOpenItems(openItems) {
    localStorage.setItem(storageKey, JSON.stringify(Array.from(openItems)));
  }

  function isCadastrosPath() {
    const p = window.location.pathname;
    return p === "/cadastros" || p.startsWith("/cadastros/");
  }

  function setOpenState(item, isOpen) {
    const toggle = item.querySelector("[data-sidebar-toggle]");
    item.classList.toggle("is-open", isOpen);
    if (toggle) {
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  }

  function getCollapsibleItems() {
    return document.querySelectorAll(".sidebar-item--collapsible");
  }

  function closeAllCollapsible(openItems) {
    getCollapsibleItems().forEach(function (item) {
      const itemId = item.getAttribute("data-sidebar-item");
      setOpenState(item, false);
      if (itemId) {
        openItems.delete(itemId);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    let openItems = readOpenItems();
    const onCadastros = isCadastrosPath();

    if (!onCadastros) {
      closeAllCollapsible(openItems);
      writeOpenItems(openItems);
    }

    getCollapsibleItems().forEach(function (item) {
      const itemId = item.getAttribute("data-sidebar-item");

      if (onCadastros) {
        setOpenState(item, true);
        if (itemId) {
          openItems.add(itemId);
        }
      }

      const toggle = item.querySelector("[data-sidebar-toggle]");
      if (!toggle) {
        return;
      }

      toggle.addEventListener("click", function (event) {
        event.stopPropagation();
        const shouldOpen = !item.classList.contains("is-open");
        setOpenState(item, shouldOpen);
        if (itemId) {
          if (shouldOpen) {
            openItems.add(itemId);
          } else {
            openItems.delete(itemId);
          }
          writeOpenItems(openItems);
        }
      });
    });

    if (onCadastros) {
      writeOpenItems(openItems);
    }

    document.querySelectorAll("[data-sidebar-root-link]").forEach(function (link) {
      link.addEventListener("click", function () {
        openItems = readOpenItems();
        closeAllCollapsible(openItems);
        writeOpenItems(openItems);
      });
    });
  });
})();
