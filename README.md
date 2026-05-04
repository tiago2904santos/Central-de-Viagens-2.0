# Central de Viagens 3

Base Django modular e document-centric para o novo sistema `central-viagens-3`.

`legacy/` e apenas referencia de consulta. O projeto novo nao deve importar codigo, templates, static ou settings da estrutura antiga.

## Arquitetura

O sistema e separado por apps de dominio: cadastros, roteiros, eventos, documentos, oficios, termos, justificativas, planos de trabalho, ordens de servico, prestacoes de contas, diario de bordo, assinaturas e integracoes.

Documentos sao o centro da arquitetura. Eventos podem agrupar documentos, mas nao sao obrigatorios para criar ou evoluir fluxos.

## Criar ambiente virtual

```powershell
python -m venv .venv
```

## Ativar ambiente virtual no Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

Se a politica de execucao bloquear scripts, use o CMD.

## Ativar ambiente virtual no CMD

```cmd
.venv\Scripts\activate
```

## Instalar dependencias

```powershell
pip install -r requirements/dev.txt
```

## Configurar .env

Copie `.env.example` para `.env` e ajuste as variaveis locais:

```env
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DB_ENGINE=django.db.backends.postgresql
DB_NAME=central_viagens_3
DB_USER=central_viagens_user
DB_PASSWORD=central_viagens_dev
DB_HOST=127.0.0.1
DB_PORT=5432

TIME_ZONE=America/Sao_Paulo
LANGUAGE_CODE=pt-br
```

`.env` nao deve ser versionado. `.env.example` deve ser mantido como referencia.

## Criar banco PostgreSQL local

O banco de desenvolvimento e PostgreSQL instalado localmente no Windows. Nao ha fallback para SQLite em `config.settings.dev`.

Instale o PostgreSQL para Windows pelo instalador oficial e marque a opcao de instalar as ferramentas de linha de comando.

Se o comando `psql` nao estiver disponivel depois da instalacao, adicione uma destas pastas ao PATH do Windows, conforme a versao instalada:

```powershell
C:\Program Files\PostgreSQL\16\bin
C:\Program Files\PostgreSQL\17\bin
```

Feche e abra o terminal novamente, depois valide:

```powershell
psql --version
```

Crie o usuario e o banco esperados pelo `.env`:

```powershell
psql -U postgres -c "CREATE USER central_viagens_user WITH PASSWORD 'central_viagens_dev';"
psql -U postgres -c "CREATE DATABASE central_viagens_3 OWNER central_viagens_user;"
psql -U postgres -d central_viagens_3 -c "GRANT ALL ON SCHEMA public TO central_viagens_user;"
```

Se o usuario ou banco ja existirem, siga para as migrations.

## Rodar migrations

```powershell
.venv\Scripts\activate
python manage.py migrate
```

## Validar projeto

```powershell
python manage.py check
```

## Rodar servidor

```powershell
python manage.py runserver
```

Settings locais usam `config.settings.dev` por padrao em `manage.py`.

SQLite so pode ser usado em `config.settings.test`, para testes automatizados.
