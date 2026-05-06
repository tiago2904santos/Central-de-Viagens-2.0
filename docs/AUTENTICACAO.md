# Autenticacao

## Modelo

- A aplicacao usa **autenticacao padrao do Django** (modelo `User`, sessao, `AuthenticationForm` e `LoginView`).
- Nao ha **cadastro publico** de usuarios; contas sao criadas pelo **Django admin** ou por modulos futuros.
- Nao ha **recuperacao de senha** nem **login social** nesta fase; isso evita fluxos e integracoes extras.

## Rotas

| Rota        | Nome            | Uso                          |
|------------|-----------------|------------------------------|
| `/login/`  | `core:login`    | Formulario usuario e senha  |
| `/logout/` | `core:logout`   | Encerrar sessao (POST)      |

Apos login com sucesso, o destino padrao e o **dashboard** (`core:dashboard`, rota `""` — raiz do site). Apos logout, redirecionamento para `core:login`.

## Configuracao (settings)

Em `config/settings/base.py`:

- `LOGIN_URL = "core:login"`
- `LOGIN_REDIRECT_URL = "core:dashboard"`
- `LOGOUT_REDIRECT_URL = "core:login"`
- `LoginRequiredMiddleware` exige sessao autenticada em todas as views, exceto as isentas pelo framework (ex.: tela de login do proprio Django `LoginView`).

`dev.py` e `prod.py` nao duplicam esses valores; herdam de `base.py`.

## Protecao de rotas

Rotas internas (dashboard, cadastros, roteiros, documentos, demais apps) exigem usuario autenticado via middleware. Acesso nao autenticado redireciona para `/login/?next=...` com o caminho original em `next` (validado pelo Django apos o login).

## Contrato para testes automatizados

- Testes de paginas internas devem autenticar o `client` com `client.force_login(user)`.
- Testes de acesso anonimo devem esperar `302` para `/login/?next=...`.
- Esse contrato evita falso negativo `302 != 200` em suites de CRUD protegidas por autenticacao.

## Tela de login

- Template: `templates/core/login.html`.
- **Nao** estende o layout com sidebar nem topbar; e uma pagina dedicada.
- Estilos: `static/css/auth.css` (tokens em `static/css/tokens.css`). Sem CSS/JS inline.
- O agregador `static/css/style.css` importa `auth.css` para manter o design system alinhado; a tela de login carrega apenas `tokens` + `auth` para carregar menos CSS.

## Logout na interface

- O link de saida fica no **rodape da sidebar** (formulario POST para `core:logout`, com `{% csrf_token %}`), visivel quando `user.is_authenticated`.

## Permissoes

- Nao ha perfis ou permissoes granulares nesta etapa; apenas distincao entre usuario autenticado ou nao.
