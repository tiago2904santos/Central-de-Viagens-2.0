(function() {
    'use strict';

    function init() {
        var form = document.getElementById('form-finalizacao');
        if (!form || !window.OficioWizard) {
            return;
        }

        var autosave = window.OficioWizard.createAutosave({
            form: form,
            statusElement: document.getElementById('guiado-finalizacao-autosave-status'),
            captureSubmit: false
        });

        var textarea = document.getElementById('id_observacoes_finais');
        if (textarea) {
            textarea.addEventListener('input', function() {
                autosave.schedule();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
