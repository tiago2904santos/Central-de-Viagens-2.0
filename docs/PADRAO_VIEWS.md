# Padrão de Views

## View magra

Fluxo padrão:

1. Ler request.
2. Instanciar form.
3. Consultar selector.
4. Executar service.
5. Preparar contexto/presenter.
6. Mensagem e redirect/render.

## Não permitido

- Query relevante direto em view (quando for reutilizável).
- `transaction.atomic` em view, salvo exceção documentada.
- Lógica de apresentação pesada dentro da view.
