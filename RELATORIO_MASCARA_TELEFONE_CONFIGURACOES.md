# Relatório — Máscara do telefone no carregamento (Configurações)

## Arquivo alterado

- **Template:** `templates/cadastros/configuracao_form.html`

## Alterações no JS

1. **Função `formatTelefone(raw)`** — adicionada após `onlyDigits`:
   - Remove tudo que não for dígito.
   - 10 dígitos → `(XX) XXXX-XXXX`
   - 11 dígitos → `(XX) XXXXX-XXXX`
   - Caso contrário → devolve o valor recebido, sem quebrar.

2. **`DOMContentLoaded`** — ao carregar a página:
   - Obtém o input do telefone por `id_telefone`.
   - Se houver valor, aplica `formatTelefone` e atribui de volta ao input.

3. **Máscara ao digitar** — o listener `input` do telefone foi mantido como já estava.

Trecho incluído:

```javascript
function formatTelefone(raw) {
    var d = onlyDigits(raw || '');
    if (d.length === 10) {
        return '(' + d.slice(0, 2) + ') ' + d.slice(2, 6) + '-' + d.slice(6);
    }
    if (d.length === 11) {
        return '(' + d.slice(0, 2) + ') ' + d.slice(2, 7) + '-' + d.slice(7, 11);
    }
    return raw || '';
}

// ... (listener de input do telefone mantido) ...

document.addEventListener('DOMContentLoaded', function() {
    var tel = document.getElementById('id_telefone');
    if (tel && tel.value && tel.value.trim() !== '') {
        tel.value = formatTelefone(tel.value);
    }
});
```

## Backend

O formulário de Configurações já trata o telefone em `clean_telefone` (apenas dígitos, 10 ou 11). Nenhuma alteração no backend foi necessária; a máscara é apenas visual.

## Testes

- **ConfiguracoesViewTest:** 10 testes executados, todos passando.
- Comando: `python manage.py test cadastros.tests.test_cadastros.ConfiguracoesViewTest`

## Como testar manualmente

1. Fazer login e acessar **Configurações** (`/cadastros/configuracoes/`).
2. No campo **Telefone**, digitar apenas números (ex.: `41999998888`) e salvar.
3. Recarregar a página (F5 ou atualizar).
4. Verificar se o telefone aparece formatado: `(41) 99999-8888`.
5. Testar com 10 dígitos (ex.: `4133334444`), salvar e recarregar: deve aparecer `(41) 3333-4444`.
6. Digitar um novo telefone no campo e conferir se a máscara continua sendo aplicada enquanto digita.
