# Autosave Global

Esta base foi criada para permitir autosave reutilizável em qualquer cadastro.

## Frontend

1. Adicione no `<form>`:
   - `data-autosave="true"`
   - `data-autosave-model="nome-modelo"`
   - `data-autosave-url` (edição)
   - `data-autosave-create-url` (criação)
   - `data-autosave-object-id` (id atual ou vazio)
2. Inclua `static/js/autosave.js`.
3. Registre snapshots específicos (opcional):
   - `window.AppAutosaveSnapshots.meu_modelo = function(form) { ... }`
4. Registre regra mínima para criar rascunho (opcional):
   - `window.AppAutosaveValidators.meu_modelo = function(payload) { ... }`

## Backend

1. Use `core.autosave.parse_autosave_payload` para validar contrato JSON.
2. Filtre campos com allowlist (`filter_allowed_fields`).
3. Atualize apenas campos presentes em `dirty_fields`.
4. Trate snapshots separadamente e com persistência defensiva.
5. Responda com `autosave_json_response`.

## Regras de segurança

- Campo ausente no payload não pode ser alterado no banco.
- Campo fora da allowlist deve ser ignorado.
- CSRF deve ser obrigatório.
- Autosave não substitui submit manual.
