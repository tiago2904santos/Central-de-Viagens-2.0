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
    const toggle = item.querySelector(":scope > .sidebar-row--top > .sidebar-toggle");
    item.classList.toggle("is-open", isOpen);
    if (toggle) {
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    const openItems = readOpenItems();

    document.querySelectorAll(".sidebar-item--collapsible").forEach(function (item) {
      const itemId = item.getAttribute("data-sidebar-item");
      const hasActiveChild = Boolean(item.querySelector(".sidebar-panel .sidebar-link.is-active"));

      if (openItems.has(itemId) || hasActiveChild || item.classList.contains("is-open")) {
        setOpenState(item, true);
        openItems.add(itemId);
      }

      const toggle = item.querySelector(":scope > .sidebar-row--top > .sidebar-toggle");
      if (!toggle) {
        return;
      }

      toggle.addEventListener("click", function () {
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
