document.addEventListener('DOMContentLoaded', function() {
    var scrollTopButtons = Array.prototype.slice.call(
        document.querySelectorAll('[data-scroll-top]')
    );

    scrollTopButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            event.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });

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
        var liveRegion = root.querySelector('[data-list-live-region]');
        var timerId = null;
        var inflightController = null;
        var lastQuery = window.location.search;
        var defaultSearchDelay = parseInt(form.getAttribute('data-list-autosubmit-delay') || '500', 10);
        if (!defaultSearchDelay || defaultSearchDelay < 0) {
            defaultSearchDelay = 500;
        }
        var fields = Array.prototype.slice.call(
            form.querySelectorAll('[data-list-autosubmit], [data-oficios-autosubmit]')
        );

        function rehydrateUi() {
            if (window.OficioSelectPicker && typeof window.OficioSelectPicker.refresh === 'function') {
                window.OficioSelectPicker.refresh(root);
            }
        }

        function submitWithAjax() {
            if (!liveRegion) {
                form.submit();
                return;
            }
            var active = document.activeElement;
            var activeName = active && active.getAttribute ? active.getAttribute('name') : '';
            var start = active && typeof active.selectionStart === 'number' ? active.selectionStart : null;
            var end = active && typeof active.selectionEnd === 'number' ? active.selectionEnd : null;
            var params = new URLSearchParams(new FormData(form));
            var query = params.toString();
            var nextUrl = window.location.pathname + (query ? ('?' + query) : '');
            if (query === lastQuery.replace(/^\?/, '')) {
                return;
            }
            lastQuery = query ? ('?' + query) : '';
            if (inflightController) {
                inflightController.abort();
            }
            inflightController = new AbortController();
            form.setAttribute('data-list-loading', 'true');
            fetch(nextUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: inflightController.signal
            })
                .then(function(response) { return response.text(); })
                .then(function(html) {
                    var parser = new DOMParser();
                    var doc = parser.parseFromString(html, 'text/html');
                    var nextRegion = doc.querySelector('[data-list-live-region]');
                    if (!nextRegion) {
                        window.location.href = nextUrl;
                        return;
                    }
                    liveRegion.innerHTML = nextRegion.innerHTML;
                    window.history.replaceState({}, '', nextUrl);
                    rehydrateUi();
                    if (activeName) {
                        var nextField = form.querySelector('[name="' + CSS.escape(activeName) + '"]');
                        if (nextField && typeof nextField.focus === 'function') {
                            nextField.focus({ preventScroll: true });
                            if (start !== null && end !== null && typeof nextField.setSelectionRange === 'function') {
                                nextField.setSelectionRange(start, end);
                            }
                        }
                    }
                })
                .catch(function(error) {
                    if (error && error.name === 'AbortError') {
                        return;
                    }
                })
                .finally(function() {
                    form.removeAttribute('data-list-loading');
                });
        }

        function submitNow() {
            if (timerId) {
                window.clearTimeout(timerId);
                timerId = null;
            }
            submitWithAjax();
        }

        function scheduleSubmit(delay) {
            if (timerId) {
                window.clearTimeout(timerId);
            }
            timerId = window.setTimeout(submitNow, delay);
        }

        form.addEventListener('submit', function(event) {
            if (!liveRegion) {
                return;
            }
            event.preventDefault();
            submitNow();
        });

        fields.forEach(function(field) {
            var tagName = (field.tagName || '').toLowerCase();
            var type = (field.getAttribute('type') || '').toLowerCase();
            if (tagName === 'input' && (type === 'text' || type === 'search')) {
                var isComposing = false;
                field.addEventListener('compositionstart', function() {
                    isComposing = true;
                });
                field.addEventListener('compositionend', function() {
                    isComposing = false;
                    scheduleSubmit(defaultSearchDelay);
                });
                field.addEventListener('input', function() {
                    if (isComposing) {
                        return;
                    }
                    scheduleSubmit(defaultSearchDelay);
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
                scheduleSubmit(120);
            });
        });
    });
});
