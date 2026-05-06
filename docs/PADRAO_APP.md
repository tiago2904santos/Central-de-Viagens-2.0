# Padrão de App Django

## Estrutura mínima por app

- `models.py`: entidades, constraints, `__str__`, métodos simples.
- `forms.py`: validação e normalização de entrada.
- `selectors.py`: consultas reutilizáveis e otimização (`select_related`/`prefetch_related`).
- `services.py` ou `services/`: regra funcional, transação e persistência.
- `presenters.py`: dados de tela sem HTML.
- `views.py`: orquestra `request + form + selector + service + presenter`.
- `urls.py`: nomes previsíveis (`*_index`, `*_create`, `*_update`, `*_delete`).

## Como criar novo CRUD

1. Definir model e form.
2. Criar selectors de listagem e get por id.
3. Criar services de criar/atualizar/excluir.
4. Criar presenter de linha/card.
5. Criar views magras.
6. Ligar urls nomeadas.
7. Compor templates por components globais.

## Proibições

- Não usar `legacy/` em runtime.
- Não colocar regra pesada em form.
- Não colocar query relevante em template.
- Não retornar HTML em service/presenter.
- Não usar `href="#"`, CSS inline ou JS inline.
