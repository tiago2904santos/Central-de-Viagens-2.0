/**
 * Máscaras compartilhadas para o frontend.
 * Usa o atributo data-mask para aplicar formatação consistente em todo o projeto.
 */
(function (global) {
    'use strict';

    var RG_NAO_POSSUI = 'NÃO POSSUI RG';

    function onlyDigits(value) {
        if (value == null) {
            return '';
        }
        return String(value).replace(/\D/g, '');
    }

    function normalizePlaca(value) {
        if (value == null) {
            return '';
        }
        return String(value).replace(/[\s-]/g, '').toUpperCase();
    }

    function formatCpf(value) {
        var digits = onlyDigits(value).slice(0, 11);
        if (!digits) {
            return '';
        }
        if (digits.length <= 3) {
            return digits;
        }
        if (digits.length <= 6) {
            return digits.slice(0, 3) + '.' + digits.slice(3);
        }
        if (digits.length <= 9) {
            return digits.slice(0, 3) + '.' + digits.slice(3, 6) + '.' + digits.slice(6);
        }
        return digits.slice(0, 3) + '.' + digits.slice(3, 6) + '.' + digits.slice(6, 9) + '-' + digits.slice(9);
    }

    function formatRg(value) {
        var text = String(value || '').trim();
        if (!text) {
            return '';
        }
        if (text.toUpperCase() === 'NAO POSSUI RG' || text.toUpperCase() === RG_NAO_POSSUI) {
            return RG_NAO_POSSUI;
        }
        var digits = onlyDigits(text).slice(0, 9);
        if (!digits) {
            return text;
        }
        if (digits.length <= 1) {
            return digits;
        }
        if (digits.length <= 4) {
            return digits[0] + '.' + digits.slice(1);
        }
        if (digits.length <= 7) {
            return digits[0] + '.' + digits.slice(1, 4) + '.' + digits.slice(4);
        }
        if (digits.length === 8) {
            return digits[0] + '.' + digits.slice(1, 4) + '.' + digits.slice(4, 7) + '-' + digits[7];
        }
        return digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5, 8) + '-' + digits[8];
    }

    function formatPhone(value) {
        var digits = onlyDigits(value).slice(0, 11);
        if (!digits) {
            return '';
        }
        if (digits.length <= 2) {
            return '(' + digits;
        }
        if (digits.length <= 6) {
            return '(' + digits.slice(0, 2) + ') ' + digits.slice(2);
        }
        if (digits.length <= 10) {
            return '(' + digits.slice(0, 2) + ') ' + digits.slice(2, 6) + '-' + digits.slice(6);
        }
        return '(' + digits.slice(0, 2) + ') ' + digits.slice(2, 7) + '-' + digits.slice(7);
    }

    function formatCep(value) {
        var digits = onlyDigits(value).slice(0, 8);
        if (!digits) {
            return '';
        }
        if (digits.length <= 5) {
            return digits;
        }
        return digits.slice(0, 5) + '-' + digits.slice(5);
    }

    function formatProtocolo(value) {
        var digits = onlyDigits(value).slice(0, 9);
        if (!digits) {
            return '';
        }
        if (digits.length <= 2) {
            return digits;
        }
        if (digits.length <= 5) {
            return digits.slice(0, 2) + '.' + digits.slice(2);
        }
        if (digits.length <= 8) {
            return digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5);
        }
        return digits.slice(0, 2) + '.' + digits.slice(2, 5) + '.' + digits.slice(5, 8) + '-' + digits.slice(8);
    }

    function formatPlaca(value) {
        var placa = normalizePlaca(value);
        if (!placa) {
            return '';
        }
        if (/^[A-Z]{3}[0-9]{4}$/.test(placa)) {
            return placa.slice(0, 3) + '-' + placa.slice(3);
        }
        return placa;
    }

    var formatters = {
        cep: formatCep,
        cpf: formatCpf,
        phone: formatPhone,
        placa: formatPlaca,
        protocolo: formatProtocolo,
        rg: formatRg,
        telefone: formatPhone
    };

    function applyMaskToInput(input) {
        var maskName = input && input.dataset ? input.dataset.mask : '';
        var formatter = formatters[maskName];
        if (!formatter) {
            return;
        }
        input.value = formatter(input.value);
    }

    function bindMask(input) {
        if (!input || input.dataset.maskBound === 'true') {
            return;
        }
        input.dataset.maskBound = 'true';
        input.addEventListener('input', function () {
            applyMaskToInput(input);
        });
        applyMaskToInput(input);
    }

    function bindAll(root) {
        var scope = root || document;
        if (!scope || !scope.querySelectorAll) {
            return;
        }
        scope.querySelectorAll('[data-mask]').forEach(bindMask);
    }

    var Masks = {
        applyMaskToInput: applyMaskToInput,
        bindAll: bindAll,
        bindMask: bindMask,
        formatCep: formatCep,
        formatCpf: formatCpf,
        formatPhone: formatPhone,
        formatPlaca: formatPlaca,
        formatProtocolo: formatProtocolo,
        formatRg: formatRg,
        normalizePlaca: normalizePlaca,
        onlyDigits: onlyDigits
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = Masks;
    } else {
        global.Masks = Masks;
    }

    if (typeof document !== 'undefined') {
        document.addEventListener('DOMContentLoaded', function () {
            bindAll(document);
        });
    }
})(typeof window !== 'undefined' ? window : this);
