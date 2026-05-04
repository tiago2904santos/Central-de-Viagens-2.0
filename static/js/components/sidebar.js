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

  function setOpenState(item, isOpen) {
    const toggle = item.querySelector(":scope > .sidebar-row > .sidebar-toggle");
    item.classList.toggle("is-open", isOpen);
    if (toggle) {
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const openItems = readOpenItems();
    const items = document.querySelectorAll("[data-sidebar-item]");

    items.forEach(function (item) {
      const itemId = item.getAttribute("data-sidebar-item");
      const hasActiveDescendant = Boolean(item.querySelector(".sidebar-link.is-active"));
      if (openItems.has(itemId) || hasActiveDescendant || item.classList.contains("is-open")) {
        setOpenState(item, true);
        openItems.add(itemId);
      }
    });

    document.querySelectorAll(".sidebar-toggle").forEach(function (toggle) {
      toggle.addEventListener("click", function () {
        const item = toggle.closest("[data-sidebar-item]");
        const itemId = item.getAttribute("data-sidebar-item");
        const shouldOpen = !item.classList.contains("is-open");

        setOpenState(item, shouldOpen);
        if (shouldOpen) {
          openItems.add(itemId);
        } else {
          openItems.delete(itemId);
        }
        writeOpenItems(openItems);
      });
    });
  });
})();
