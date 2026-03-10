# Relatório — Unidades de Lotação (somente NOME)

## Resumo

O cadastro de **Unidades de Lotação** foi simplificado: removido o campo **sigla**; importação e uso passam a ser apenas pelo **NOME** via CSV. O Viajante continua selecionando a unidade em um SELECT (sem digitação livre).

---

## A) Model

### UnidadeLotacao (`cadastros/models.py`)

- **Removido:** campo `sigla`.
- **Mantido:**
  - `nome` — CharField(160, unique=True)
  - `created_at`, `updated_at`
- **Normalização no `save()`:** `nome` em MAIÚSCULO, strip + colapsar espaços.
- **Meta:** `ordering = ['nome']`.
- **`__str__`:** retorna `self.nome` (apenas o nome).

### Viajante

- `unidade_lotacao` continua como **ForeignKey(UnidadeLotacao, null=True, blank=True, on_delete=SET_NULL)**. Nenhuma alteração de schema.

---

## B) Comando de importação

**Arquivo:** `cadastros/management/commands/importar_unidades_lotacao.py`

- **CSV esperado:** uma coluna **NOME** (exatamente esse nome).
- **Regras:**
  - Ler CSV UTF-8; normalizar cada valor (strip + colapsar espaços + UPPER).
  - **update_or_create** por `nome` (idempotente).
  - Linhas com NOME vazio após normalização: contadas como **ignoradas**.
  - Se a coluna NOME não existir no CSV: erro claro e comando encerra.
- **Relatório no terminal:** `X criadas, Y atualizadas, Z ignoradas.`

**Como rodar:**

```bash
python manage.py importar_unidades_lotacao
```

Usa por padrão `data/lotacao/unidades.csv`. Para outro arquivo:

```bash
python manage.py importar_unidades_lotacao caminho/para/arquivo.csv
```

---

## C) Form de Viajante

- Campo **unidade_lotacao:** `ModelChoiceField` (select) com `queryset = UnidadeLotacao.objects.all().order_by('nome')`.
- O select exibe **apenas o nome** (sem sigla), pois `UnidadeLotacao.__str__` retorna `self.nome`.
- Sem digitação livre; apenas seleção.

---

## D) Migração de dados

**Arquivo:** `cadastros/migrations/0017_unidade_lotacao_somente_nome.py`

1. **RunPython (mesclar_duplicados_e_remover_sigla):**
   - Normaliza todos os `nome` existentes (UPPER + trim + colapsar espaços).
   - Agrupa registros por `nome` normalizado.
   - Para cada grupo com duplicados: mantém o de **menor pk**; reassigna todos os Viajantes que apontavam para os demais para esse registro; remove os registros duplicados (log em `logger.info` quando houver reassign).
2. **RemoveField:** remove o campo `sigla` de `UnidadeLotacao`.
3. **AlterModelOptions:** `ordering` passa a `['nome']`.

Assim, dados antigos com sigla são preservados apenas pelo nome; duplicados por nome são mesclados antes de remover a sigla.

---

## E) Outras alterações

- **Admin:** `UnidadeLotacaoAdmin` — `list_display` e `search_fields` apenas com `nome`; `ordering = ('nome',)`.
- **ViajanteAdmin:** `search_fields` sem `unidade_lotacao__sigla`; mantido `unidade_lotacao__nome`.
- **Lista de viajantes (view):** filtro de busca por `unidade_lotacao__nome` (removida referência a sigla).
- **Template lista viajantes:** coluna Unidade exibe `{{ obj.unidade_lotacao.nome }}` (sem sigla).
- **Menu:** Unidades de lotação continuam fora do menu lateral; acesso apenas por import e uso no cadastro de Viajantes.

---

## CSV esperado

**Local:** `data/lotacao/unidades.csv` (ou outro caminho informado ao comando)

**Formato:**

- Uma coluna de cabeçalho: **NOME**
- Uma linha por unidade; valor livre (será normalizado no import)

Exemplo:

```csv
NOME
DEFENSORIA PÚBLICA DO ESTADO
CORREGEDORIA GERAL DA JUSTIÇA
ASSESSORIA DE COMUNICAÇÃO
```

O arquivo `data/lotacao/unidades.csv` foi ajustado para usar o cabeçalho **NOME** (em maiúsculas).

---

## Testes

- **Import:** `test_import_cria_unidades` — cria unidades a partir do CSV de fixture (coluna NOME); verifica quantidade e nomes.
- **Import:** `test_import_idempotente` — rodar 2x não duplica registros.
- **Viajante:** `test_viajante_form_exibe_select_unidade` — form exibe select com nome da unidade.
- **Viajante:** `test_viajante_criar_com_unidade_lotacao` — salva viajante com unidade FK.
- **Viajante:** `test_viajante_lista_e_form_mostram_unidade_pelo_nome` — lista e form de edição exibem a unidade pelo nome (sem sigla).
- **Import:** `test_import_falha_sem_coluna_nome` — CSV sem coluna NOME não importa e emite mensagem de erro; nenhuma unidade é criada.

Fixture de teste: `cadastros/tests/fixtures/unidades_lotacao.csv` — apenas coluna **NOME**.

---

## Como testar manualmente

1. **Migrar:**  
   `python manage.py migrate cadastros`

2. **Importar unidades:**  
   `python manage.py importar_unidades_lotacao`  
   (ou passar outro CSV com coluna NOME.)  
   Verificar no terminal: criadas/atualizadas/ignoradas.

3. **Cadastro de Viajante:**  
   - Acessar Viajantes → Cadastrar (ou Editar).  
   - Campo "Unidade de lotação" deve ser um select com apenas os nomes (sem sigla).  
   - Selecionar uma unidade e salvar; na lista, a coluna Unidade deve mostrar só o nome.

4. **Busca na lista de viajantes:**  
   Buscar por parte do nome da unidade e conferir se o filtro funciona.

5. **Idempotência:**  
   Rodar de novo `importar_unidades_lotacao` com o mesmo CSV; não deve criar registros duplicados (apenas "atualizadas" ou 0 criadas).

6. **CSV sem coluna NOME:**  
   Usar um CSV sem a coluna NOME; o comando deve exibir erro e não importar.

---

## Checklist de aceite

| Item | Status |
|------|--------|
| Model UnidadeLotacao sem sigla; apenas nome (unique), created_at, updated_at | OK |
| Nome normalizado no save() (UPPER + strip + colapsar espaços) | OK |
| Viajante com unidade_lotacao FK (sem alteração de schema) | OK |
| Comando import com coluna NOME; update_or_create por nome | OK |
| Relatório: criadas/atualizadas/ignoradas | OK |
| Erro claro se coluna NOME não existir | OK |
| Form Viajante: select apenas com nome (sem sigla) | OK |
| Lista viajantes: coluna Unidade exibe só nome | OK |
| Migração 0017: mesclar duplicados por nome, remover sigla | OK |
| Testes: import, idempotência, viajante com unidade, lista/form pelo nome | OK |
| Unidades não aparecem no menu lateral | OK |
| README atualizado (CSV e comando) | OK |
