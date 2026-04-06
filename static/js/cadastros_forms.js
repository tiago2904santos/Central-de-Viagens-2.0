(function () {
  'use strict';

  function bindUppercase(root) {
    (root || document).querySelectorAll('[data-uppercase="1"]').forEach(function (input) {
      if (input.dataset.uppercaseBound === '1') return;
      input.dataset.uppercaseBound = '1';
      input.addEventListener('input', function () {
        input.value = input.value.toUpperCase();
      });
      if (input.value) input.value = input.value.toUpperCase();
    });
  }

  function bindSemRgToggle() {
    var semRgCheck = document.getElementById('id_sem_rg');
    var rgInput = document.getElementById('id_rg');
    if (!semRgCheck || !rgInput) return;

    function toggle(clearValue) {
      if (semRgCheck.checked) {
        rgInput.disabled = true;
        rgInput.value = 'NÃO POSSUI RG';
        rgInput.setAttribute('readonly', 'readonly');
      } else {
        rgInput.removeAttribute('readonly');
        rgInput.disabled = false;
        if (clearValue) {
          rgInput.value = '';
        } else if (window.Masks) {
          window.Masks.applyMaskToInput(rgInput);
        }
      }
    }

    semRgCheck.addEventListener('change', function () { toggle(true); });
    toggle(false);
  }

  function initCadastrosForms() {
    bindUppercase(document);
    bindSemRgToggle();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCadastrosForms);
  } else {
    initCadastrosForms();
  }

  window.CadastrosForms = {
    bindUppercase: bindUppercase
  };
})();
