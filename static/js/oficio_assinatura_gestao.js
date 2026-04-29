document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.oficio-lazy-frame').forEach(function (frame) {
        const panel = frame.closest('details');
        if (!panel) return;
        const loadFrame = function () {
            if (!panel.open) return;
            if (frame.getAttribute('src')) return;
            const src = frame.getAttribute('data-src');
            if (src) frame.setAttribute('src', src);
        };
        panel.addEventListener('toggle', loadFrame);
        loadFrame();
    });

    const btn = document.getElementById('gestao-copiar-link');
    const input = document.getElementById('gestao-url-publica');
    if (!btn || !input) return;

    btn.addEventListener('click', async function () {
        const text = input.value || '';
        if (!text) return;
        const original = btn.textContent;
        try {
            await navigator.clipboard.writeText(text);
        } catch (_err) {
            input.select();
            document.execCommand('copy');
        }
        btn.textContent = 'Copiado';
        window.setTimeout(function () {
            btn.textContent = original;
        }, 1800);
    });
});
