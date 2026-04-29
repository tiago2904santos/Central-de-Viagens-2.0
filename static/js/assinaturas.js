document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-copy-target]').forEach(function (btn) {
        btn.addEventListener('click', async function () {
            const targetId = btn.getAttribute('data-copy-target');
            const input = document.getElementById(targetId);
            if (!input) return;
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
            }, 1500);
        });
    });
});
