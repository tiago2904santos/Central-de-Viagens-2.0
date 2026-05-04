# Padrao CRUD

## Objetivo

Este padrao foi consolidado no app `cadastros` para `Unidade`, `Cidade`, `Servidor`, `Motorista` e `Viatura`. Ele deve ser replicado nos proximos modulos antes de evoluir para fluxos mais complexos.

## Estrutura

- `forms.py`: valida entrada e normaliza dados.
- `selectors.py`: concentra consultas e `get_object_or_404`.
- `services.py`: concentra criacao, atualizacao e exclusao.
- `presenters.py`: transforma objetos em dicionarios para cards.
- `views.py`: orquestra request, form, selector, service, messages e redirect.
- `urls.py`: define rotas nomeadas e previsiveis.
- `templates/`: compoe tela com components globais.

## URLs

Padrao para listagem, criacao, edicao e exclusao (exemplo `Unidade`):

```text
/cadastros/unidades/
/cadastros/unidades/novo/
/cadastros/unidades/<pk>/editar/
/cadastros/unidades/<pk>/excluir/
```

Entidades com rotas equivalentes no mesmo app: `Cidade`, `Servidor`, `Motorista`, `Viatura` (verbos de criacao: novo/nova conforme o nome da rota).

## Forms

Forms devem ser `ModelForm`, usar widgets com classes globais e normalizar campos simples no `clean_<campo>`. Mascara visual fica para etapa de frontend.

## Services

Views nao devem chamar `save()` ou alterar status diretamente quando houver service. O service pode ser simples no inicio, mas fixa o ponto de extensao para regras futuras.

## Selectors

Views devem chamar selectors para consultas. Busca simples por `q` (querystring) deve ficar no selector, nao na view nem no template. A view apenas repassa `q` obtido de `request.GET`.

## Exclusao

Cadastros nao possuem estado ativo/inativo. A exclusao deve remover fisicamente o registro quando nao houver vinculos importantes. Se houver vinculos impeditivos, a exclusao deve ser bloqueada e a view deve exibir a mensagem:

```text
Não foi possível excluir este cadastro porque ele está vinculado a outros registros.
```

Nao criar `desativar_*`, `ativar_*`, checkbox Ativo/Ativa ou status Ativo/Inativo para cadastros.

## Messages

Mensagens usam `django.contrib.messages`, no genero e numero corretos da entidade (ex.: servidor criado, viatura excluida).

## Templates

Templates devem estender `base.html` e usar components de layout, forms, lists, cards, buttons e feedback. CSS e JS por pagina seguem proibidos.

## Testes minimos

Para cada entidade CRUD:

- GET listagem retorna 200.
- GET criacao retorna 200.
- POST criacao valida cria e redireciona.
- GET edicao retorna 200.
- POST edicao altera e redireciona.
- POST exclusao remove o registro ou bloqueia quando houver vinculo importante.
