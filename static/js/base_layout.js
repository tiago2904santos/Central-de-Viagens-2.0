document.addEventListener('DOMContentLoaded', function() {
    var sidebar = document.getElementById('sidebar');
    var sidebarToggle = document.getElementById('sidebarToggle');
    var sidebarBackdrop = document.getElementById('sidebarBackdrop');
    var sidebarGroups = Array.from(document.querySelectorAll('[data-sidebar-group]'));
    var sidebarStorageKey = 'central-viagens.sidebar.open-group';
    var syncingGroups = false;

    function isPdfUrl(url) {
        if (!url) {
            return false;
        }
        var normalized = String(url).toLowerCase();
        var cleanUrl = normalized.split('?')[0].split('#')[0];
        if (cleanUrl.endsWith('.pdf')) {
            return true;
        }
        if (/\/pdf\/?$/.test(cleanUrl)) {
            return true;
        }
        if (/[?&](format|tipo|extensao)=pdf(?:[&#]|$)/.test(normalized)) {
            return true;
        }
        return false;
    }

    function buildPreviewUrl(url) {
        var normalized = String(url || '').trim();
        if (!normalized) {
            return '';
        }
        try {
            var parsed = new URL(normalized, window.location.origin);
            var hashlessPath = parsed.pathname + parsed.search;
            var separator = hashlessPath.indexOf('?') >= 0 ? '&' : '?';
            return hashlessPath + separator + 'preview=1';
        } catch (error) {
            var hashIndex = normalized.indexOf('#');
            var baseWithoutHash = hashIndex >= 0 ? normalized.slice(0, hashIndex) : normalized;
            var separatorFallback = baseWithoutHash.indexOf('?') >= 0 ? '&' : '?';
            return baseWithoutHash + separatorFallback + 'preview=1';
        }
    }

    function openPdfPreview(pdfUrl) {
        if (!isPdfUrl(pdfUrl)) {
            window.alert('Visualizacao disponivel apenas para arquivos PDF.');
            return;
        }

        var previewWindow = window.open('about:blank', '_blank');
        if (!previewWindow) {
            window.alert('Nao foi possivel abrir nova guia. Verifique o bloqueador de pop-ups.');
            return;
        }

        previewWindow.document.title = 'Carregando PDF...';
        previewWindow.document.body.innerHTML = [
            '<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#f8f9fa;">',
            '  <div style="text-align:center;font-family:Arial,sans-serif;color:#1f2937;">',
            '    <img',
            '      src="data:image/gif;base64,R0lGODlhEAAQAPIAAP///wAAAMLCwkJCQv///wAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQJCgAAACwAAAAAEAAQAAADMwi63P4wyklrE2MIOggZnAdOmGYJRbExwroUm2qvuk2kFADs="',
            '      alt="Carregando..."',
            '      width="48"',
            '      height="48"',
            '      style="image-rendering:auto;display:block;margin:0 auto 14px auto;"',
            '    >',
            '    <p style="margin:0;font-size:16px;">Carregando visualizacao do PDF...</p>',
            '  </div>',
            '</div>'
        ].join('');

        fetch(buildPreviewUrl(pdfUrl), {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/pdf'
            }
        })
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Falha ao carregar o PDF para preview.');
                }
                return response.blob();
            })
            .then(function(blob) {
                if (!blob || (blob.type && blob.type.toLowerCase().indexOf('pdf') === -1)) {
                    throw new Error('O arquivo retornado nao e um PDF valido para preview.');
                }
                var blobUrl = URL.createObjectURL(blob);
                previewWindow.location.replace(blobUrl + '#toolbar=0');
            })
            .catch(function(error) {
                try {
                    previewWindow.close();
                } catch (closeError) {
                }
                window.alert(error && error.message ? error.message : 'Nao foi possivel abrir o preview do PDF.');
            });
    }
    window.openPdfPreview = openPdfPreview;

    function copyTextToClipboard(text) {
        var value = String(text || '').trim();
        if (!value) {
            return Promise.resolve(false);
        }
        if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
            return navigator.clipboard.writeText(value).then(function() {
                return true;
            });
        }

        return new Promise(function(resolve) {
            var textarea = document.createElement('textarea');
            textarea.value = value;
            textarea.setAttribute('readonly', 'readonly');
            textarea.style.position = 'fixed';
            textarea.style.top = '-9999px';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.select();

            var success = false;
            try {
                success = document.execCommand('copy');
            } catch (error) {
                success = false;
            }

            if (textarea.parentNode) {
                textarea.parentNode.removeChild(textarea);
            }
            resolve(success);
        });
    }

    function bindSharedActionHandlers() {
        document.addEventListener('click', function(event) {
            var copyTrigger = event.target.closest('[data-copy-text]');
            if (copyTrigger) {
                event.preventDefault();
                copyTextToClipboard(copyTrigger.getAttribute('data-copy-text') || '');
                return;
            }

            var previewTrigger = event.target.closest('[data-pdf-preview-trigger]');
            if (previewTrigger) {
                event.preventDefault();
                openPdfPreview(previewTrigger.getAttribute('data-pdf-url') || '');
            }
        });

        document.addEventListener('submit', function(event) {
            var confirmForm = event.target.closest('form[data-confirm-message]');
            if (!confirmForm) {
                return;
            }

            var message = confirmForm.getAttribute('data-confirm-message') || '';
            if (message && !window.confirm(message)) {
                event.preventDefault();
            }
        });
    }

    function removeTopRightCreateButtons() {
        var createTerms = ['novo', 'nova', 'cadastrar', 'criar'];
        var topRightContainers = [
            '.system-list-header__controls',
            '.list-page-header__actions',
            '.card-header',
            '.page-header',
            '.d-flex.justify-content-end'
        ];

        var candidates = document.querySelectorAll(
            '.system-list-header__controls .btn, ' +
            '.list-page-header__actions .btn, ' +
            '.card-header .btn, ' +
            '.page-header .btn, ' +
            '.d-flex.justify-content-end .btn'
        );

        candidates.forEach(function(button) {
            if (button.closest('.system-list-fab-group')) {
                return;
            }
            var label = (button.textContent || '').trim().toLowerCase();
            if (!label) {
                return;
            }

            var isCreateAction = createTerms.some(function(term) {
                return label.indexOf(term) !== -1;
            });
            if (!isCreateAction) {
                return;
            }

            var isTopRightAction = topRightContainers.some(function(selector) {
                return Boolean(button.closest(selector));
            });
            if (isTopRightAction) {
                button.remove();
            }
        });
    }

    function normalizeActionText(value) {
        return (value || '')
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .trim()
            .toLowerCase();
    }

    function isEditAction(control) {
        if (!control) {
            return false;
        }
        if (control.hasAttribute('data-essential-open-action')) {
            return false;
        }
        var text = normalizeActionText(control.textContent);
        var title = normalizeActionText(control.getAttribute('title'));
        var ariaLabel = normalizeActionText(control.getAttribute('aria-label'));
        var href = normalizeActionText(control.getAttribute('href'));
        var labels = [text, title, ariaLabel];

        var hasOpenTerm = labels.some(function(value) {
            return value.indexOf('abrir') !== -1 || value.indexOf('visualizar') !== -1;
        });
        if (hasOpenTerm) {
            return false;
        }

        var hasEditTerm = labels.some(function(value) {
            return value.indexOf('editar') !== -1 || value.indexOf('edicao') !== -1;
        });
        if (hasEditTerm) {
            return true;
        }

        var hasExplicitLabel = labels.some(function(value) {
            return !!value;
        });
        if (!hasExplicitLabel && href && (href.indexOf('/editar/') !== -1 || href.indexOf('-editar') !== -1)) {
            return true;
        }
        return false;
    }

    function removeAllEditButtons() {
        var selectors = [
            'a.btn',
            'button.btn',
            'a.dropdown-item',
            'button.dropdown-item'
        ];
        document.querySelectorAll(selectors.join(', ')).forEach(function(control) {
            if (isEditAction(control)) {
                control.remove();
            }
        });
    }

    function observeAndRemoveEditButtons() {
        var observer = new MutationObserver(function() {
            removeAllEditButtons();
        });
        observer.observe(document.body, { childList: true, subtree: true });
    }

    function setSidebarOpen(isOpen) {
        if (!sidebar) {
            return;
        }
        sidebar.classList.toggle('show', isOpen);
        if (sidebarBackdrop) {
            sidebarBackdrop.classList.toggle('show', isOpen);
        }
        document.body.classList.toggle('sidebar-open', isOpen);
    }

    function syncSidebarGroups(openGroupId, persist) {
        syncingGroups = true;
        sidebarGroups.forEach(function(group) {
            group.open = group.dataset.groupId === openGroupId;
        });
        syncingGroups = false;
        if (!persist) {
            return;
        }
        if (openGroupId) {
            window.localStorage.setItem(sidebarStorageKey, openGroupId);
        } else {
            window.localStorage.removeItem(sidebarStorageKey);
        }
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            setSidebarOpen(!(sidebar && sidebar.classList.contains('show')));
        });
    }

    if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', function() {
            setSidebarOpen(false);
        });
    }

    if (sidebarGroups.length) {
        var activeGroup = sidebarGroups.find(function(group) {
            return group.dataset.active === 'true';
        });
        var storedGroupId = window.localStorage.getItem(sidebarStorageKey);
        var initialGroupId = activeGroup ? activeGroup.dataset.groupId : storedGroupId;
        if (initialGroupId) {
            syncSidebarGroups(initialGroupId, Boolean(activeGroup));
        }

        sidebarGroups.forEach(function(group) {
            group.addEventListener('toggle', function() {
                if (syncingGroups) {
                    return;
                }
                if (group.open) {
                    syncSidebarGroups(group.dataset.groupId, true);
                } else if (window.localStorage.getItem(sidebarStorageKey) === group.dataset.groupId) {
                    window.localStorage.removeItem(sidebarStorageKey);
                }
            });
        });
    }

    document.addEventListener('click', function(event) {
        if (!event.target.closest('.sidebar-subnav-link')) {
            return;
        }
        if (window.innerWidth < 992) {
            setSidebarOpen(false);
        }
    });

    var alerts = document.querySelectorAll('.alert[data-autodismiss="true"]');
    alerts.forEach(function(el) {
        window.setTimeout(function() {
            el.classList.add('fade-out');
            window.setTimeout(function() {
                if (el.parentNode) {
                    el.parentNode.removeChild(el);
                }
            }, 500);
        }, 3000);
    });

    removeTopRightCreateButtons();
    removeAllEditButtons();
    observeAndRemoveEditButtons();
    bindSharedActionHandlers();
});
