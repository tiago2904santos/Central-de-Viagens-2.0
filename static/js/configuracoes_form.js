(function () {
  'use strict';

  function onlyDigits(str) {
    return (str || '').replace(/\D/g, '');
  }

  function initConfiguracoesForm() {
    var form = document.getElementById('form-configuracoes');
    if (!form) return;

    var apiCepUrl = form.dataset.apiCepUrl || '';
    var cepInput = document.getElementById('id_cep');
    var cepErroAlert = document.getElementById('cep-erro-alert');

    function hideCepError() {
      if (cepErroAlert) cepErroAlert.classList.add('d-none');
    }

    function showCepError(message) {
      if (!cepErroAlert) return;
      cepErroAlert.textContent = message || 'CEP inválido ou não encontrado.';
      cepErroAlert.classList.remove('d-none');
    }

    function buscaCep() {
      if (!cepInput || !apiCepUrl) return;
      var cepDigits = onlyDigits(cepInput.value);
      if (cepDigits.length !== 8) return;

      var url = apiCepUrl.replace('00000000', cepDigits);
      hideCepError();

      fetch(url)
        .then(function (r) {
          if (r.status === 400 || r.status === 404) {
            return r.json().then(function (data) {
              throw new Error(data.erro || 'CEP inválido ou não encontrado.');
            });
          }
          if (!r.ok) throw new Error('Erro ao consultar CEP.');
          return r.json();
        })
        .then(function (data) {
          var logradouro = document.getElementById('id_logradouro');
          var bairro = document.getElementById('id_bairro');
          var cidadeEndereco = document.getElementById('id_cidade_endereco');
          var uf = document.getElementById('id_uf');

          if (logradouro) logradouro.value = data.logradouro || '';
          if (bairro) bairro.value = data.bairro || '';
          if (cidadeEndereco) cidadeEndereco.value = data.cidade || '';
          if (uf) uf.value = (data.uf || '').toUpperCase();
          if (cepInput && data.cep) cepInput.value = data.cep;
        })
        .catch(function (err) {
          showCepError(err && err.message ? err.message : 'CEP inválido ou não encontrado.');
        });
    }

    if (cepInput) {
      cepInput.addEventListener('input', function () {
        hideCepError();
        if (onlyDigits(this.value).length === 8) buscaCep();
      });
      cepInput.addEventListener('blur', buscaCep);
    }

    if (window.CadastrosForms && window.CadastrosForms.bindUppercase) {
      window.CadastrosForms.bindUppercase(form);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initConfiguracoesForm);
  } else {
    initConfiguracoesForm();
  }
})();
