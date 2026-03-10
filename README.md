# Central de Viagens 2.0

Sistema de gestão de viagens institucionais. Este repositório contém a **base limpa** do projeto Django, pronta para evoluir por módulos.

## Requisitos

- Python 3.10+
- pip
- **PostgreSQL** — banco padrão em desenvolvimento; configure as variáveis `POSTGRES_*` no `.env`. Nos testes (`manage.py test`), SQLite é usado quando `POSTGRES_DB` não está definido.

## Setup

1. **Clone ou acesse o projeto** e crie um ambiente virtual:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # ou: source .venv/bin/activate   # Linux/macOS
   ```

2. **Instale as dependências:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure variáveis de ambiente:**

   - **`.env.example`** é apenas **modelo** (documentação das variáveis); o projeto **não** carrega esse arquivo.
   - O projeto carrega as variáveis a partir do arquivo **`.env`** (raiz do projeto). Crie-o copiando o modelo:

   ```bash
   copy .env.example .env   # Windows
   # ou: cp .env.example .env   # Linux/macOS
   ```

   Depois **edite `.env`** e preencha as variáveis reais (o `.env` não deve ser commitado). Para desenvolvimento, defina as variáveis **PostgreSQL**:
   - `POSTGRES_DB` — nome do banco
   - `POSTGRES_USER` — usuário
   - `POSTGRES_PASSWORD` — senha
   - `POSTGRES_HOST` — host (ex.: localhost)
   - `POSTGRES_PORT` — porta (ex.: 5432)

   Crie o banco no PostgreSQL antes das migrações:
   ```sql
   CREATE DATABASE central_viagens;
   ```

4. **Migrações e superusuário:**

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Execute o servidor:**

   ```bash
   python manage.py runserver
   ```

   Acesse: **http://127.0.0.1:8000/**

   Faça login com o usuário criado no passo 4.

## Base geográfica (Estados e Cidades)

Estados e Cidades são **base fixa de referência** (IBGE), importada por CSV — não são cadastros manuais.

### Importar base geográfica

```bash
python manage.py importar_base_geografica --estados data/geografia/estados.csv --cidades data/geografia/municipios.csv
```

(Se os CSVs estiverem em outro diretório, use os caminhos correspondentes.)

- **estados.csv** (UTF-8): colunas `COD`, `NOME`, `SIGLA`. Ex.: `35,São Paulo,SP`
- **municipios.csv** (UTF-8): colunas `COD UF`, `COD`, `NOME`. Ex.: `35,3550308,São Paulo`
- O comando é **idempotente**: pode ser reexecutado sem duplicar dados (usa `codigo_ibge` como chave).
- Cidades que referenciarem estado inexistente são ignoradas (aviso no terminal).
- A **cidade sede padrão** em Configurações é definida automaticamente a partir do endereço (UF + cidade do rodapé), desde que a base geográfica esteja importada.

### API de cidades por estado

Para uso em formulários (ex.: Configurações, Eventos):

## Unidades de lotação (Viajantes)

As **unidades de lotação** são base fixa importada por CSV — não há CRUD manual no menu. Elas alimentam o campo *Unidade de lotação* no cadastro de Viajantes (select no formulário).

### Onde colocar o CSV

Coloque o arquivo em:

```
data/lotacao/unidades.csv
```

(UTF-8, separador vírgula.)

### Comando de importação

```bash
python manage.py importar_unidades_lotacao
```

Usa por padrão `data/lotacao/unidades.csv`. Para outro arquivo:

```bash
python manage.py importar_unidades_lotacao caminho/para/outro.csv
```

- O comando é **idempotente**: pode ser reexecutado sem duplicar (chave: `nome` normalizado).
- Coluna obrigatória: **NOME** (normalizado: strip + colapsar espaços + maiúsculo).
- Relatório no terminal: criadas, atualizadas, ignoradas (linhas vazias).

### Exemplo de CSV

```csv
NOME
DEFENSORIA PÚBLICA DO ESTADO
CORREGEDORIA GERAL DA JUSTIÇA
ASSESSORIA DE COMUNICAÇÃO
```

### API de cidades por estado

Para uso em formulários (ex.: Configurações, Eventos):

```
GET /cadastros/api/cidades-por-estado/<estado_id>/
```

Requer login. Retorna JSON: `[{"id": 1, "nome": "São Paulo"}, ...]` ordenado por nome.

## Como rodar os testes

```bash
python manage.py test core cadastros
```

## Estrutura do projeto

```
central de viagens 2.0/
├── config/                 # Configuração do projeto
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/                   # Núcleo: layout, auth, dashboard, em-breve
│   ├── views/
│   │   ├── auth_views.py   # login, logout
│   │   ├── dashboard.py
│   │   └── placeholder.py # em_breve_view
│   ├── navigation.py       # Sidebar configurável
│   ├── urls.py
│   └── tests/
├── cadastros/              # Configurações do sistema + API cidades
├── eventos/                # App presente (models); rotas não expostas nesta entrega
├── documentos/             # App presente; rotas não expostas
├── templates/              # Templates globais
│   ├── base.html           # Layout com sidebar
│   └── core/
│       ├── login.html
│       ├── dashboard.html
│       └── em_breve.html
├── static/
│   └── css/
│       └── style.css       # Estilos centralizados
├── media/                  # Uploads (criado em runtime)
├── .env.example
├── requirements.txt
└── manage.py
```

## Apps e responsabilidades (estado atual)

| App         | Responsabilidade                                      | Estado   |
|------------|--------------------------------------------------------|----------|
| **core**   | Login, logout, dashboard, layout base, página “Em breve” | Implementado |
| **cadastros** | Configurações do sistema (singleton); API cidades por estado; base geográfica (Estados/Cidades ref. IBGE) | Implementado (apenas Configurações exposto) |
| **eventos**   | Models presentes; rotas não expostas nesta entrega   | Em breve |
| **documentos** | App presente; rotas não expostas                     | Em breve |

## Páginas que já funcionam

- **Login** (`/`, `/login/`) — formulário de autenticação; redireciona para o dashboard se já logado.
- **Dashboard** (`/dashboard/`) — painel com cards de resumo; links dos cards levam à página “Em breve”.
- **Configurações** (`/cadastros/configuracoes/`) — edição do singleton (prazo justificativa, nome/sigla órgão, cidade sede padrão com Estado → Cidade dependente).
- **Em breve** (`/em-breve/`) — página única para módulos não implementados.
- **Layout base** — sidebar honesta (apenas Painel e Configurações clicáveis; demais itens com badge “Em breve”), header, área principal, mensagens, responsivo.
- **Logout** — encerra sessão e redireciona para a tela de login.

## Módulos desabilitados na sidebar (“Em breve”)

Itens visíveis na sidebar mas sem link (badge “Em breve”):

- Simulação de Diárias, Eventos, Roteiros, Ofícios, Planos de Trabalho, Ordens de Serviço, Justificativas, Termos de Autorização
- Viajantes, Veículos

## Próximos passos recomendados

1. **Viajantes e Veículos** — Reativar rotas em `cadastros/urls.py` e habilitar itens na sidebar.
2. **Eventos** — Reativar rotas em `config/urls.py` e habilitar módulo na sidebar (model e CRUD já existem).
3. **Ofícios, Planos de Trabalho, Ordens de Serviço** — Implementar models e telas.
4. **Termos e justificativas** — Models e fluxo de geração/assinatura.
5. **Documentos** — Upload, geração de PDFs e exportação em ZIP.
6. **Permissões** — Grupos e permissões por módulo quando necessário.

## Critérios de aceite (entrega UI + Configurações)

- [x] Projeto roda sem erros
- [x] Login e dashboard funcionam
- [x] Sidebar honesta: só Painel e Configurações com link; demais “Em breve” sem 404
- [x] Configurações do sistema com seções e Estado → Cidade dependente
- [x] Testes core e cadastros passando

---

## Relatório da primeira entrega

### 1. Estrutura de pastas criada

```
config/           # settings, urls, wsgi, asgi
core/             # views (auth, dashboard, placeholder), urls, tests
cadastros/        # urls, views placeholder
eventos/          # urls, views placeholder
documentos/       # urls, views placeholder
templates/        # base.html, core/login.html, dashboard.html, placeholder.html
static/css/       # style.css
```

### 2. Apps criadas

- **core** — autenticação, dashboard, layout, placeholders dos módulos (ofícios, termos, justificativas, simulação, roteiros)
- **cadastros** — placeholders: Viajantes, Veículos, Configurações
- **eventos** — placeholder lista
- **documentos** — placeholder lista

### 3. Arquivos principais criados/alterados

- `config/settings.py`, `config/urls.py` — configuração do projeto
- `core/views/auth_views.py`, `dashboard.py`, `placeholder.py` — lógica de telas
- `core/urls.py` — rotas (login, logout, dashboard, oficios, termos, etc.)
- `templates/base.html` — layout com sidebar e header
- `templates/core/login.html`, `dashboard.html`, `placeholder.html`
- `static/css/style.css` — padrão visual
- `requirements.txt`, `.env.example`, `.gitignore`
- `core/tests/test_auth.py`, `test_dashboard.py`, `test_placeholders.py`

### 4. Como rodar o projeto

Ver seção **Setup** no início deste README (venv, `pip install -r requirements.txt`, `migrate`, `createsuperuser`, `runserver`).

### 5. Páginas que já funcionam

- Login (`/`, `/login/`)
- Dashboard (`/dashboard/`)
- Logout
- Todas as páginas placeholder acessíveis pela sidebar (com usuário logado)

### 6. Módulos como placeholder

Eventos, Ofícios, Termos de autorização, Justificativas, Documentos, Simulação de diárias, Roteiros, Viajantes, Veículos, Configurações — todos exibem “Em construção”.

### 7. Próximos passos recomendados

Ver seção **Próximos passos recomendados** acima.
