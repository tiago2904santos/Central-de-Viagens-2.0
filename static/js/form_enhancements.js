(function() {
    'use strict';

    function toUpper(value) {
        return String(value || '').toUpperCase();
    }

    function onlyDigits(value) {
        return String(value || '').replace(/\D/g, '');
    }

    function resolveElement(root, selectorOrId) {
        if (!selectorOrId) {
            return null;
        }
        var selector = String(selectorOrId).trim();
        if (!selector) {
            return null;
        }
        if (selector.charAt(0) === '#') {
            return (root || document).querySelector(selector) || document.querySelector(selector) || document.getElementById(selector.slice(1));
        }
        return (root || document).querySelector(selector) || document.getElementById(selector);
    }

    function normalizeUppercaseField(field) {
        if (!field || field.dataset.autoUppercaseBound === '1') {
            return;
        }

        field.dataset.autoUppercaseBound = '1';

        var applyUppercase = function() {
            var current = field.value || '';
            var next = toUpper(current);
            if (current !== next) {
                field.value = next;
            }
        };

        field.addEventListener('input', applyUppercase);
        field.addEventListener('change', applyUppercase);
        applyUppercase();
    }

    function bindUppercaseFields(root) {
        Array.prototype.slice.call((root || document).querySelectorAll('[data-auto-uppercase]')).forEach(normalizeUppercaseField);
    }

    function setCepError(errorEl, message) {
        if (!errorEl) {
            return;
        }
        errorEl.textContent = message || '';
        errorEl.classList.toggle('d-none', !message);
    }

    function bindCepAutofill(form) {
        if (!form || form.dataset.cepAutofillBound === '1') {
            return;
        }

        if (form.getAttribute('data-cep-autofill') !== '1') {
            return;
        }

        var apiUrl = form.getAttribute('data-cep-api-url') || '';
        var cepInput = form.querySelector('#id_cep, [name="cep"]');
        if (!apiUrl || !cepInput) {
            return;
        }

        var errorTarget = form.getAttribute('data-cep-error-target') || '';
        var errorEl = resolveElement(form, errorTarget);
        var logradouro = resolveElement(form, '#id_logradouro');
        var bairro = resolveElement(form, '#id_bairro');
        var cidade = resolveElement(form, '#id_cidade_endereco');
        var uf = resolveElement(form, '#id_uf');

        form.dataset.cepAutofillBound = '1';

        function getCepUrl(cepDigits) {
            if (apiUrl.indexOf('00000000') !== -1) {
                return apiUrl.replace('00000000', cepDigits);
            }
            return apiUrl.replace(/\/0\/?$/, '/' + cepDigits + '/');
        }

        function fillFields(data) {
            if (logradouro) {
                logradouro.value = data.logradouro || '';
            }
            if (bairro) {
                bairro.value = data.bairro || '';
            }
            if (cidade) {
                cidade.value = data.cidade || '';
            }
            if (uf) {
                uf.value = toUpper(data.uf || '');
            }
            if (cepInput && data.cep) {
                cepInput.value = data.cep;
            }
        }

        function fetchCep() {
            var cepDigits = onlyDigits(cepInput.value);
            if (cepDigits.length !== 8) {
                return;
            }

            setCepError(errorEl, '');

            fetch(getCepUrl(cepDigits))
                .then(function(response) {
                    if (response.status === 400 || response.status === 404) {
                        return response.json().then(function(data) {
                            throw new Error((data && data.erro) || 'CEP inválido ou não encontrado.');
                        });
                    }
                    if (!response.ok) {
                        throw new Error('Erro ao consultar CEP.');
                    }
                    return response.json();
                })
                .then(function(data) {
                    fillFields(data || {});
                })
                .catch(function(error) {
                    setCepError(errorEl, (error && error.message) || 'CEP inválido ou não encontrado.');
                });
        }

        cepInput.addEventListener('input', function() {
            setCepError(errorEl, '');
            if (onlyDigits(cepInput.value).length === 8) {
                fetchCep();
            }
        });

        cepInput.addEventListener('blur', fetchCep);
    }

    function bindCepAutofillForms(root) {
        Array.prototype.slice.call((root || document).querySelectorAll('form[data-cep-autofill="1"]')).forEach(bindCepAutofill);
    }

    function refreshSelectPickers(root) {
        if (window.OficioSelectPicker && typeof window.OficioSelectPicker.refresh === 'function') {
            window.OficioSelectPicker.refresh(root || document);
        }
    }

    function bindDependentSelect(form) {
        if (!form || form.dataset.dependentSelectBound === '1') {
            return;
        }

        if (form.getAttribute('data-dependent-select') !== '1') {
            return;
        }

        var apiUrl = form.getAttribute('data-dependent-select-url') || '';
        var parentSelector = form.getAttribute('data-dependent-select-parent') || '#id_estado_base';
        var childSelector = form.getAttribute('data-dependent-select-target') || '#id_cidade_base';
        var defaultValue = form.getAttribute('data-dependent-select-default') || '';
        var parent = resolveElement(form, parentSelector);
        var child = resolveElement(form, childSelector);

        if (!apiUrl || !parent || !child) {
            return;
        }

        form.dataset.dependentSelectBound = '1';

        function getUrl(estadoId) {
            return apiUrl.replace(/\/0\/?$/, '/' + estadoId + '/');
        }

        function rebuildOptions(estadoId, selectedValue) {
            var nextState = String(estadoId || '').trim();
            child.innerHTML = '<option value="">Selecione...</option>';
            child.disabled = !nextState;

            if (!nextState) {
                refreshSelectPickers(form);
                return Promise.resolve();
            }

            return fetch(getUrl(nextState), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(function(response) {
                    if (!response.ok) {
                        throw new Error('Falha ao carregar cidades.');
                    }
                    return response.json();
                })
                .then(function(cidades) {
                    (Array.isArray(cidades) ? cidades : []).forEach(function(cidade) {
                        var option = document.createElement('option');
                        option.value = String(cidade.id);
                        option.textContent = cidade.nome;
                        if (selectedValue && String(selectedValue) === String(cidade.id)) {
                            option.selected = true;
                        }
                        child.appendChild(option);
                    });
                    child.disabled = false;
                    refreshSelectPickers(form);
                })
                .catch(function() {
                    child.disabled = false;
                    refreshSelectPickers(form);
                });
        }

        function ensureDefaultState() {
            if (!String(parent.value || '').trim() && defaultValue) {
                parent.value = defaultValue;
            }
        }

        parent.addEventListener('change', function() {
            rebuildOptions(parent.value, '');
        });

        ensureDefaultState();
        rebuildOptions(parent.value, child.value);
    }

    function bindDependentSelectForms(root) {
        Array.prototype.slice.call((root || document).querySelectorAll('form[data-dependent-select="1"]')).forEach(bindDependentSelect);
    }

    function init(root) {
        bindUppercaseFields(root);
        bindCepAutofillForms(root);
        bindDependentSelectForms(root);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            init(document);
        });
    } else {
        init(document);
    }

    window.FormEnhancements = {
        refresh: function(root) {
            init(root || document);
        }
    };
})();
