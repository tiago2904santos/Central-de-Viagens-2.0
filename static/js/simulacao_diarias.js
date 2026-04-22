(function() {
    'use strict';

    function init() {
        var wrapper = document.getElementById('periodos-wrapper');
        var countInput = document.getElementById('period-count');
        var addButton = document.getElementById('add-periodo');

        if (!wrapper || !countInput || !addButton) {
            return;
        }

        function syncRows() {
            var rows = wrapper.querySelectorAll('.periodo-row');
            countInput.value = rows.length || 1;
            rows.forEach(function(row, index) {
                row.querySelectorAll('input').forEach(function(input) {
                    var prefix = input.name.split('_').slice(0, -1).join('_');
                    input.name = prefix + '_' + index;
                });
            });
        }

        function bindRemoveButtons() {
            wrapper.querySelectorAll('.remove-periodo').forEach(function(button) {
                button.addEventListener('click', function() {
                    if (wrapper.querySelectorAll('.periodo-row').length === 1) {
                        wrapper.querySelector('.periodo-row input').focus();
                        return;
                    }
                    button.closest('.periodo-row').remove();
                    syncRows();
                });
            });
        }

        addButton.addEventListener('click', function() {
            var rows = wrapper.querySelectorAll('.periodo-row');
            var clone = rows[rows.length - 1].cloneNode(true);
            clone.querySelectorAll('input').forEach(function(input) {
                input.value = '';
            });
            wrapper.appendChild(clone);
            syncRows();
            bindRemoveButtons();
        });

        bindRemoveButtons();
        syncRows();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
