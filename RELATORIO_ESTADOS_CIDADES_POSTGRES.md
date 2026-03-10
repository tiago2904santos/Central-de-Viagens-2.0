# Relatório — Correção: PostgreSQL, Estados/Cidades como base fixa e importação CSV

## 1. Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| **config/settings.py** | `DATABASES` passou a usar `_get_db_config()`: PostgreSQL quando `POSTGRES_DB` está definido, SQLite como fallback quando não está. |
| **requirements.txt** | Inclusão de `psycopg[binary]>=3.1`. |
| **.env.example** | Variáveis `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`. |
| **README.md** | Requisito PostgreSQL, setup com variáveis de ambiente, seção “Base geográfica” (importação e API), comando de testes. |
| **cadastros/models.py** | `Estado` e `Cidade`: campo `codigo_ibge` (único, null/blank para migração). Comentários indicando base fixa (importação CSV). |
| **cadastros/migrations/0002_add_codigo_ibge.py** | Nova migração adicionando `codigo_ibge` em Estado e Cidade. |
| **core/navigation.py** | Remoção dos itens “Estados” e “Cidades” do grupo Cadastros; permanecem Viajantes, Veículos, Configurações. |
| **cadastros/urls.py** | Removidas rotas de estado/cidade (lista, cadastrar, editar). Incluída rota `api/cidades-por-estado/<estado_id>/`. |
| **cadastros/views/__init__.py** | Remoção das views de estado e cidade; inclusão de `api_cidades_por_estado`. |
| **cadastros/views/api.py** | Novo: view `api_cidades_por_estado` (JSON, login obrigatório, ordenação por nome). |
| **cadastros/forms.py** | Remoção de `EstadoForm` e `CidadeForm`. |
| **cadastros/admin.py** | `EstadoAdmin` e `CidadeAdmin`: `list_display` e `readonly_fields` com `codigo_ibge`. |
| **cadastros/management/commands/importar_base_geografica.py** | Novo comando: `--estados` e `--cidades`, importação idempotente por `codigo_ibge`. |
| **cadastros/tests/test_cadastros.py** | Ajustes: remoção de testes de CRUD de estado/cidade; testes de config PostgreSQL, import estados/cidades, idempotência, API cidades por estado, sidebar sem Estados/Cidades. |
| **Removidos** | `cadastros/views/estados.py`, `cadastros/views/cidades.py`, `templates/cadastros/estado_lista.html`, `estado_form.html`, `cidade_lista.html`, `cidade_form.html`. |

---

## 2. Como ficou a configuração PostgreSQL

- **settings.py**: função `_get_db_config()` lê variáveis de ambiente. Se `POSTGRES_DB` estiver definido, retorna configuração PostgreSQL (`ENGINE`, `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT`). Caso contrário, retorna SQLite (fallback para ambiente sem PostgreSQL).
- Variáveis usadas: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` (default `localhost`), `POSTGRES_PORT` (default `5432`).
- Driver: `psycopg[binary]` no `requirements.txt`.

---

## 3. Como rodar o projeto com PostgreSQL

1. Instalar e subir o PostgreSQL; criar o banco, por exemplo: `CREATE DATABASE central_viagens;`
2. Copiar `.env.example` para `.env` e preencher:
   - `POSTGRES_DB=central_viagens`
   - `POSTGRES_USER=...`
   - `POSTGRES_PASSWORD=...`
   - `POSTGRES_HOST=localhost`
   - `POSTGRES_PORT=5432`
3. `pip install -r requirements.txt`
4. `python manage.py migrate`
5. `python manage.py createsuperuser`
6. (Opcional) Importar base geográfica: `python manage.py importar_base_geografica --estados estados.csv --cidades municipios.csv`
7. `python manage.py runserver`

Sem nenhuma variável `POSTGRES_*` no `.env`, o projeto usa SQLite (útil para testes locais rápidos).

---

## 4. Como funcionam os comandos de importação

Um único comando:

```bash
python manage.py importar_base_geografica --estados <caminho_estados.csv> --cidades <caminho_municipios.csv>
```

- Pode informar só `--estados`, só `--cidades` ou ambos.
- **Estados**: lê o CSV com codificação UTF-8; para cada linha, usa `COD` como `codigo_ibge`, `NOME` e `SIGLA` (com `strip()`). `update_or_create(codigo_ibge=...)` garante idempotência.
- **Cidades**: lê o CSV; usa `COD UF` para localizar o estado por `Estado.codigo_ibge`; `COD` como `codigo_ibge` da cidade, `NOME` com `strip()`. `update_or_create(codigo_ibge=...)` para idempotência. Se o estado não existir, registra aviso e não insere a cidade (não interrompe o resto).
- Reexecutar o comando não duplica registros; atualiza nome/sigla quando já existir o `codigo_ibge`.

---

## 5. Formato esperado dos CSVs

**estados.csv** (UTF-8, com cabeçalho):

| Coluna | Uso |
|--------|-----|
| COD | `Estado.codigo_ibge` (único) |
| NOME | `Estado.nome` (strip aplicado) |
| SIGLA | `Estado.sigla` (strip aplicado) |

Exemplo: `35,São Paulo,SP`

**municipios.csv** (UTF-8, com cabeçalho):

| Coluna | Uso |
|--------|-----|
| COD UF | Código IBGE do estado (relaciona com `Estado.codigo_ibge`) |
| COD | `Cidade.codigo_ibge` (único) |
| NOME | `Cidade.nome` (strip aplicado) |

Exemplo: `35,3550308,São Paulo`

O comando aceita o cabeçalho exatamente como vier no arquivo (ex.: `COD UF` com espaço).

---

## 6. O que foi removido/ajustado de Estados e Cidades

- **Removido do fluxo do usuário**: listagens, formulários de cadastro e edição de Estados e Cidades; rotas correspondentes; itens “Estados” e “Cidades” no menu lateral.
- **Mantido**: models `Estado` e `Cidade` com `codigo_ibge` (único), nome, sigla (estado), estado FK (cidade), ativo, timestamps. Registro no **admin** do Django para consulta/gestão da base.
- **Novo**: comando `importar_base_geografica` para popular/atualizar a base a partir dos CSVs; endpoint JSON `GET /cadastros/api/cidades-por-estado/<estado_id>/` para uso em formulários (ex.: cidade sede em Configurações).

---

## 7. Como testar manualmente

1. **PostgreSQL**: Definir `POSTGRES_DB` (e demais variáveis) no `.env`, rodar `migrate` e acessar o sistema; conferir no admin que os dados persistem no PostgreSQL.
2. **Importação**: Criar `estados.csv` e `municipios.csv` no formato acima; rodar `importar_base_geografica --estados estados.csv --cidades municipios.csv`; repetir e verificar que não há duplicação; no admin, conferir Estados e Cidades com `codigo_ibge` correto.
3. **API**: Logar no sistema; abrir `GET /cadastros/api/cidades-por-estado/<id_estado>/` (substituir pelo id de um estado existente); conferir resposta JSON com lista de cidades ordenadas por nome.
4. **Sidebar**: Logar e verificar que no grupo “Cadastros” aparecem apenas Viajantes, Veículos e Configurações (sem Estados nem Cidades).
5. **Admin**: Acessar `/admin/`, abrir Estados e Cidades; conferir list_display com `codigo_ibge` e que não há opção de adicionar estado/cidade “livre” no fluxo normal do sistema.

---

## 8. Checklist de aceite

| Item | Status |
|------|--------|
| Projeto configurado para PostgreSQL (env) | OK |
| Fallback para SQLite quando POSTGRES_DB ausente | OK |
| requirements.txt e .env.example atualizados | OK |
| README com instruções PostgreSQL e importação | OK |
| Estado e Cidade com codigo_ibge (único) | OK |
| Estados e Cidades fora do menu lateral | OK |
| Rotas/views de CRUD público de Estado/Cidade removidas | OK |
| Comando importar_base_geografica (--estados, --cidades) | OK |
| Importação idempotente por codigo_ibge | OK |
| Cidade com estado inexistente: aviso e não quebra | OK |
| strip() em campos textuais no import | OK |
| Endpoint GET cidades-por-estado retornando JSON ordenado | OK |
| Login obrigatório no endpoint | OK |
| Admin com codigo_ibge para Estado e Cidade | OK |
| Testes: config, import, idempotência, API, sidebar | OK |
