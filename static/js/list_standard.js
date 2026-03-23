document.addEventListener('DOMContentLoaded', function() {
    var roots = Array.prototype.slice.call(
        document.querySelectorAll('[data-list-view-root], [data-oficios-view-root]')
    );

    roots.forEach(function(root, index) {
        var storageKey = root.getAttribute('data-view-storage-key') || ('central-viagens.list.view-mode.' + index);
        var allowedModes = { rich: true, basic: true };
        var toggleButtons = Array.prototype.slice.call(
            root.querySelectorAll('[data-list-view-toggle], [data-oficios-view-toggle]')
        );

        function getButtonMode(button) {
            return button.getAttribute('data-list-view-toggle') || button.getAttribute('data-oficios-view-toggle');
        }

        function applyMode(mode, persist) {
            if (!toggleButtons.length) {
                return;
            }
            var nextMode = allowedModes[mode] ? mode : 'rich';
            root.setAttribute('data-view-mode', nextMode);
            toggleButtons.forEach(function(button) {
                var isActive = getButtonMode(button) === nextMode;
                button.classList.toggle('is-active', isActive);
                button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });
            if (persist) {
                window.localStorage.setItem(storageKey, nextMode);
            }
        }

        if (toggleButtons.length) {
            applyMode(window.localStorage.getItem(storageKey), false);
            toggleButtons.forEach(function(button) {
                button.addEventListener('click', function() {
                    applyMode(getButtonMode(button), true);
                });
            });
        }

        var form = root.querySelector('[data-list-autosubmit-form], [data-oficios-filters-form]');
        if (!form) {
            return;
        }

        var fields = Array.prototype.slice.call(
            form.querySelectorAll('[data-list-autosubmit], [data-oficios-autosubmit]')
        );
        var timerId = null;

        function submitNow() {
            if (timerId) {
                window.clearTimeout(timerId);
                timerId = null;
            }
            form.submit();
        }

        function scheduleSubmit(delay) {
            if (timerId) {
                window.clearTimeout(timerId);
            }
            timerId = window.setTimeout(submitNow, delay);
        }

        fields.forEach(function(field) {
            var tagName = (field.tagName || '').toLowerCase();
            var type = (field.getAttribute('type') || '').toLowerCase();
            if (tagName === 'input' && (type === 'text' || type === 'search')) {
                field.addEventListener('input', function() {
                    scheduleSubmit(280);
                });
                field.addEventListener('keydown', function(event) {
                    if (event.key === 'Enter') {
                        event.preventDefault();
                        submitNow();
                    }
                });
                return;
            }
            field.addEventListener('change', function() {
                scheduleSubmit(40);
            });
        });
    });
});
