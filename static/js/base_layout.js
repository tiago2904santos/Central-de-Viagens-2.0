(function () {
  'use strict';

  function initSidebarAndAlerts() {
    var sidebar = document.getElementById('sidebar');
    var sidebarToggle = document.getElementById('sidebarToggle');
    var sidebarBackdrop = document.getElementById('sidebarBackdrop');
    var sidebarGroups = Array.from(document.querySelectorAll('[data-sidebar-group]'));
    var sidebarStorageKey = 'central-viagens.sidebar.open-group';
    var syncingGroups = false;

    function setSidebarOpen(isOpen) {
      if (!sidebar) return;
      sidebar.classList.toggle('show', isOpen);
      if (sidebarBackdrop) sidebarBackdrop.classList.toggle('show', isOpen);
      document.body.classList.toggle('sidebar-open', isOpen);
    }

    function syncSidebarGroups(openGroupId, persist) {
      syncingGroups = true;
      sidebarGroups.forEach(function (group) {
        group.open = group.dataset.groupId === openGroupId;
      });
      syncingGroups = false;
      if (!persist) return;
      if (openGroupId) {
        window.localStorage.setItem(sidebarStorageKey, openGroupId);
      } else {
        window.localStorage.removeItem(sidebarStorageKey);
      }
    }

    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', function () {
        setSidebarOpen(!(sidebar && sidebar.classList.contains('show')));
      });
    }

    if (sidebarBackdrop) {
      sidebarBackdrop.addEventListener('click', function () {
        setSidebarOpen(false);
      });
    }

    var activeGroup = sidebarGroups.find(function (group) {
      return group.dataset.active === 'true';
    });
    var storedGroupId = window.localStorage.getItem(sidebarStorageKey);
    var initialGroupId = activeGroup ? activeGroup.dataset.groupId : storedGroupId;
    if (initialGroupId) {
      syncSidebarGroups(initialGroupId, Boolean(activeGroup));
    }

    sidebarGroups.forEach(function (group) {
      group.addEventListener('toggle', function () {
        if (syncingGroups) return;
        if (group.open) {
          syncSidebarGroups(group.dataset.groupId, true);
        } else if (window.localStorage.getItem(sidebarStorageKey) === group.dataset.groupId) {
          window.localStorage.removeItem(sidebarStorageKey);
        }
      });
    });

    document.querySelectorAll('.sidebar-subnav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth < 992) {
          setSidebarOpen(false);
        }
      });
    });

    document.querySelectorAll('.alert[data-autodismiss="true"]').forEach(function (el) {
      setTimeout(function () {
        el.classList.add('fade-out');
        setTimeout(function () {
          if (el.parentNode) el.parentNode.removeChild(el);
        }, 500);
      }, 3000);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebarAndAlerts);
  } else {
    initSidebarAndAlerts();
  }
})();
