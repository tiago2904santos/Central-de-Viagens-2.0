(function() {
    'use strict';

    function init() {
        const form = document.getElementById('oficio-justificativa-form');
        if (!form) {
            return;
        }
        const select = document.getElementById('id_modelo_justificativa');
        const textarea = document.getElementById('id_justificativa_texto');
        const button = document.getElementById('btnAplicarModelo');
        const counter = document.getElementById('justificativa-counter');
        const template = form.getAttribute('data-modelo-api-url') || '';
        const autosave = window.OficioWizard ? window.OficioWizard.createAutosave({ form: form }) : null;

        function scheduleAutosave() {
            if (autosave) {
                autosave.schedule();
            }
        }

        function syncPreview() {
            const text = textarea ? (textarea.value || '').trim() : '';
            if (counter) {
                counter.textContent = String(text.length);
            }
        }

        async function aplicarModelo() {
            if (!select || !textarea || !select.value || !template) {
                return;
            }
            const response = await fetch(template.replace('/0/texto/', '/' + select.value + '/texto/'));
            if (!response.ok) {
                return;
            }
            const payload = await response.json();
            if (payload.ok) {
                textarea.value = payload.texto || '';
                syncPreview();
                scheduleAutosave();
            }
        }

        textarea?.addEventListener('input', syncPreview);
        button?.addEventListener('click', aplicarModelo);
        syncPreview();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
