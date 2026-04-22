(function() {
    'use strict';

    var conviteFormUrl = window.location.pathname + window.location.search;

    function initConviteFlow() {
        var conviteSection = document.querySelector('.evento-section-convite');
        var conviteForm = document.getElementById('form-etapa4-convite');
        var conviteInput = document.getElementById('id_tem_convite_ou_oficio_evento');
        var conviteState = document.querySelector('[data-convite-state]');
        var conviteUploadWrap = document.querySelector('[data-convite-upload-wrap]');
        var conviteSaveWrap = document.querySelector('[data-convite-save-wrap]');
        var conviteFilesInput = document.getElementById('id_convite_documentos');
        var conviteRemoveAllInput = document.querySelector('[data-convite-remove-all]');
        var conviteSaveButton = document.querySelector('[data-convite-save-button]');
        var conviteRemoveAllButton = document.querySelector('[data-convite-remove-all-button]');
        var convitePill = document.querySelector('[data-convite-pill]');
        var conviteHasAnexos = !!(convitePill && convitePill.getAttribute('data-has-anexos') === '1');
        var isSubmitting = false;

        if (!conviteSection || !conviteForm || !conviteInput || !conviteState || !conviteUploadWrap) {
            return;
        }

        function setBusy(isBusy) {
            isSubmitting = isBusy;
            if (conviteSaveButton) {
                conviteSaveButton.disabled = isBusy;
            }
            if (conviteRemoveAllButton) {
                conviteRemoveAllButton.disabled = isBusy;
            }
            if (conviteFilesInput) {
                conviteFilesInput.disabled = isBusy;
            }
            if (conviteInput) {
                conviteInput.disabled = isBusy;
            }
        }

        function updateConviteUi() {
            var temUploadSelecionado = !!(conviteFilesInput && conviteFilesInput.files && conviteFilesInput.files.length);
            var ativo = !!conviteInput.checked || temUploadSelecionado;
            if (convitePill) {
                convitePill.classList.toggle('is-on', ativo);
                convitePill.classList.toggle('is-off', !ativo);
            }
            conviteState.textContent = ativo ? 'SIM' : 'NÃO';
            conviteUploadWrap.classList.toggle('d-none', !(ativo || conviteHasAnexos));
            if (conviteSaveWrap) {
                conviteSaveWrap.classList.toggle('d-none', !(conviteInput.checked || conviteHasAnexos));
            }
        }

        function replaceConviteSection(html) {
            var wrapper = document.createElement('div');
            wrapper.innerHTML = html;
            var nextSection = wrapper.querySelector('.evento-section-convite');
            if (nextSection) {
                conviteSection.outerHTML = nextSection.outerHTML;
                initConviteFlow();
            } else {
                window.location.reload();
            }
        }

        async function submitConviteForm() {
            if (isSubmitting) {
                return;
            }
            var payload = new FormData(conviteForm);
            setBusy(true);
            try {
                var response = await fetch(conviteFormUrl, {
                    method: 'POST',
                    body: payload,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    credentials: 'same-origin'
                });
                if (!response.ok) {
                    var errorPayload = {};
                    try {
                        errorPayload = await response.json();
                    } catch (error) {
                        errorPayload = {};
                    }
                    window.alert(errorPayload.error || 'Falha ao salvar os anexos do convite.');
                    return;
                }
                var responsePayload = await response.json();
                if (responsePayload && responsePayload.ok && responsePayload.html) {
                    replaceConviteSection(responsePayload.html);
                    return;
                }
                window.location.reload();
            } catch (error) {
                window.location.reload();
            } finally {
                setBusy(false);
            }
        }

        conviteForm.addEventListener('submit', function(event) {
            event.preventDefault();
            if (conviteRemoveAllInput) {
                conviteRemoveAllInput.value = '0';
            }
            submitConviteForm();
        });

        if (conviteSaveButton) {
            conviteSaveButton.addEventListener('click', function() {
                if (conviteRemoveAllInput) {
                    conviteRemoveAllInput.value = '0';
                }
            });
        }

        if (conviteRemoveAllButton) {
            conviteRemoveAllButton.addEventListener('click', function(event) {
                event.preventDefault();
                if (!conviteHasAnexos && !(conviteFilesInput && conviteFilesInput.files && conviteFilesInput.files.length)) {
                    return;
                }
                if (!window.confirm('Deseja excluir todos os arquivos anexados do convite/oficio solicitante?')) {
                    return;
                }
                if (conviteFilesInput) {
                    conviteFilesInput.value = '';
                }
                conviteInput.checked = false;
                if (conviteRemoveAllInput) {
                    conviteRemoveAllInput.value = '1';
                }
                updateConviteUi();
                submitConviteForm();
            });
        }

        conviteInput.addEventListener('change', function() {
            if (!conviteInput.checked) {
                if (conviteHasAnexos) {
                    if (!window.confirm('Deseja excluir todos os arquivos anexados do convite/oficio solicitante?')) {
                        conviteInput.checked = true;
                        updateConviteUi();
                        return;
                    }
                    if (conviteFilesInput) {
                        conviteFilesInput.value = '';
                    }
                    if (conviteRemoveAllInput) {
                        conviteRemoveAllInput.value = '1';
                    }
                    updateConviteUi();
                    submitConviteForm();
                    return;
                }
                if (conviteRemoveAllInput) {
                    conviteRemoveAllInput.value = '0';
                }
                updateConviteUi();
                submitConviteForm();
                return;
            }

            if (conviteRemoveAllInput) {
                conviteRemoveAllInput.value = '0';
            }
            updateConviteUi();
        });

        if (conviteFilesInput) {
            conviteFilesInput.addEventListener('change', function() {
                if (conviteFilesInput.files && conviteFilesInput.files.length) {
                    conviteInput.checked = true;
                }
                if (conviteRemoveAllInput) {
                    conviteRemoveAllInput.value = '0';
                }
                updateConviteUi();
            });
        }

        updateConviteUi();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initConviteFlow);
    } else {
        initConviteFlow();
    }
})();
