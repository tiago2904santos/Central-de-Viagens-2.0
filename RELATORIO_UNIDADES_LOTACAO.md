# Relatório — Cadastro fixo de Unidades de Lotação (CSV) e uso em Viajantes

## Resumo

Implementado cadastro fixo de **Unidades de Lotação** importado por CSV (sem CRUD no menu), com model `UnidadeLotacao` (sigla e nome únicos, normalizados em maiúsculo). O campo *Unidade de lotação* no **Viajante** passou de texto livre para **ForeignKey** para `UnidadeLotacao`, com select no formulário e coluna na lista. Comando de importação idempotente; migração de dados para viajantes que tinham texto em `unidade_lotacao` (casamento por sigla ou nome, ou NULL com aviso).

---

## 1. Migrations

### 0013_unidade_lotacao_model.py
- **CreateModel** `UnidadeLotacao`:
  - `sigla` — CharField(max_length=30, unique=True)
  - `nome` — CharField(max_length=160, unique=True)
  - `created_at`, `updated_at`
  - Meta: ordering por `sigla`, verbose_name "Unidade de lotação"

### 0014_viajante_unidade_lotacao_fk.py
- **AddField** `Viajante.unidade_lotacao_fk` — ForeignKey(UnidadeLotacao, null=True, blank=True, on_delete=SET_NULL)
- **RunPython** `migrar_unidade_lotacao`:
  - Para cada viajante com o antigo campo `unidade_lotacao` (CharField) preenchido:
    - Normaliza o texto (strip + UPPER + colapsar espaços)
    - Busca `UnidadeLotacao` por `sigla` ou por `nome` (igual ao normalizado)
    - Se encontrar: define `unidade_lotacao_fk_id`
    - Se não encontrar: define `unidade_lotacao_fk_id = None` e registra aviso no log (ex.: "Viajante pk=1: unidade_lotacao 'ASCOM' não encontrada; definido como NULL.")
  - Viajantes com texto vazio continuam com unidade NULL
- **RemoveField** `Viajante.unidade_lotacao` (CharField)
- **RenameField** `unidade_lotacao_fk` → `unidade_lotacao`

**Ordem:** rodar primeiro a importação do CSV (`importar_unidades_lotacao`) se quiser que dados antigos casem com unidades já existentes; em seguida as migrações. Se rodar a migração antes de importar, textos que não existirem na tabela `UnidadeLotacao` ficarão NULL (e o aviso aparece no log).

---

## 2. Comando de importação e como rodar

**Comando:** `importar_unidades_lotacao`

**Uso:**
```bash
python manage.py importar_unidades_lotacao
```
Usa por padrão o arquivo `data/lotacao/unidades.csv`.

**Outro arquivo:**
```bash
python manage.py importar_unidades_lotacao data/lotacao/unidades.csv
python manage.py importar_unidades_lotacao cadastros/tests/fixtures/unidades_lotacao.csv
```

**Regras:**
- CSV UTF-8, colunas exatamente **SIGLA** e **NOME**
- Valores normalizados: strip, colapsar espaços, UPPER
- **Idempotente:** `update_or_create` por `sigla` (não duplica ao rodar várias vezes)
- Se o **nome** já existir em outra linha com **sigla** diferente, a linha é **ignorada** e contada como erro (evita dois registros com o mesmo nome)
- Saída no terminal: "X criadas, Y atualizadas, Z erros/ignoradas"

---

## 3. Como o viajante passa a selecionar unidade

- **Formulário (cadastrar/editar viajante):** o campo *Unidade de lotação* é um **select** (`ModelChoiceField`), com opções vindas de `UnidadeLotacao.objects.all().order_by('sigla')`.
- Cada opção é exibida no formato **SIGLA — NOME** (via `UnidadeLotacao.__str__`).
- Campo opcional (empty_label "---------").
- **Lista de viajantes:** nova coluna **Unidade**, exibindo "SIGLA — NOME" quando houver unidade, ou "—" quando for NULL.
- **Busca:** o filtro por texto continua considerando unidade: busca por `unidade_lotacao__sigla__icontains` e `unidade_lotacao__nome__icontains`.
- Não há mais digitação livre; apenas escolha entre as unidades importadas pelo CSV.

---

## 4. Tratamento da migração de dados antigos

- Existia o campo **CharField** `Viajante.unidade_lotacao` (texto livre).
- Na migração **0014**, para cada viajante com valor preenchido:
  1. Texto é normalizado (strip + UPPER + colapsar espaços).
  2. Procura-se uma `UnidadeLotacao` com:
     - `sigla == texto_normalizado` **ou**
     - `nome == texto_normalizado`
  3. **Se encontrar:** o viajante recebe `unidade_lotacao_fk` apontando para essa unidade.
  4. **Se não encontrar:** `unidade_lotacao_fk` fica NULL e é registrado um aviso no log (ex.: "Viajante pk=1: unidade_lotacao 'ASCOM' não encontrada; definido como NULL.").
- Recomendação: importar o CSV (`importar_unidades_lotacao`) **antes** de rodar a migração 0014 se quiser que valores como "ASCOM" casem com uma unidade (ex.: sigla ASCOM no CSV). Caso contrário, esses viajantes ficam sem unidade (NULL) até que o CSV seja importado e os dados reatribuídos manualmente ou por script.

---

## 5. Arquivos criados/alterados

| Arquivo | Alteração |
|--------|-----------|
| `cadastros/models.py` | Model `UnidadeLotacao`; `Viajante.unidade_lotacao` → FK |
| `cadastros/migrations/0013_unidade_lotacao_model.py` | CreateModel UnidadeLotacao |
| `cadastros/migrations/0014_viajante_unidade_lotacao_fk.py` | AddField FK, RunPython, RemoveField, RenameField |
| `cadastros/management/commands/importar_unidades_lotacao.py` | Comando de importação CSV |
| `cadastros/forms.py` | ViajanteForm: unidade_lotacao como Select, queryset UnidadeLotacao.order_by('sigla') |
| `cadastros/views/viajantes.py` | Filtro de busca por unidade_lotacao__sigla e __nome |
| `templates/cadastros/viajantes/lista.html` | Coluna Unidade (SIGLA — NOME) |
| `cadastros/admin.py` | UnidadeLotacaoAdmin (somente leitura); ViajanteAdmin search_fields com unidade |
| `data/lotacao/unidades.csv` | CSV de exemplo |
| `cadastros/tests/fixtures/unidades_lotacao.csv` | Fixture para testes |
| `cadastros/tests/test_cadastros.py` | ImportUnidadesLotacaoTest; testes viajante form/unidade |
| `README.md` | Seção Unidades de lotação (CSV, comando, exemplo) |

---

## 6. Como testar manualmente

1. **Importar unidades**
   - Criar/editar `data/lotacao/unidades.csv` com colunas SIGLA e NOME.
   - Rodar: `python manage.py importar_unidades_lotacao`.
   - Conferir saída: criadas/atualizadas/erros.
   - Rodar de novo e conferir que não duplica (idempotência).

2. **Viajante**
   - Cadastros → Viajantes → Cadastrar.
   - Verificar que *Unidade de lotação* é um select com opções "SIGLA — NOME".
   - Cadastrar um viajante escolhendo uma unidade e salvar.
   - Na lista, conferir a coluna Unidade com "SIGLA — NOME".
   - Buscar por sigla ou nome da unidade e conferir que o viajante aparece.

3. **Conflito de nome no CSV**
   - Incluir no CSV duas linhas com o mesmo NOME e SIGLAs diferentes.
   - Rodar o comando e conferir que a segunda linha é ignorada e contada como erro.

---

## 7. Checklist de aceite

| Item | Status |
|------|--------|
| Model UnidadeLotacao (sigla, nome únicos; save normaliza UPPER) | OK |
| Sem CRUD de Unidades no menu (apenas importação CSV) | OK |
| Importação idempotente (update_or_create por sigla) | OK |
| Sigla e nome em maiúsculo no banco | OK |
| Conflito nome com outra sigla: linha ignorada, relatório de erro | OK |
| Viajante.unidade_lotacao = FK(UnidadeLotacao) | OK |
| Migração de dados antigos (casar por sigla/nome ou NULL + aviso) | OK |
| Form viajante: select de unidades (SIGLA — NOME) | OK |
| Lista viajantes: coluna Unidade; busca por sigla/nome | OK |
| Comando: `importar_unidades_lotacao [caminho]`; default data/lotacao/unidades.csv | OK |
| Testes: import cria unidades; idempotência; form exibe select; criar viajante com unidade | OK |
| README: onde colocar CSV, comando, exemplo | OK |
