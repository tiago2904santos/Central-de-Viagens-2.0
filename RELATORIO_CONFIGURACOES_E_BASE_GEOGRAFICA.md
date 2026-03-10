# Relatório — Correção Configurações e base geográfica

## 1. Arquivos alterados

| Arquivo | Alteração |
|---------|-----------|
| `cadastros/forms.py` | Removidos prazo_justificativa_dias, nome_orgao, estado, cidade_sede_padrao do form. Cabeçalho com divisao, unidade, sigla_orgao (todos .strip().upper()). Removido clean de estado/cidade. |
| `cadastros/views/configuracoes.py` | Removida lógica de estado/cidade_sede_padrao no form. Após save, resolve cidade_sede_padrao a partir de uf + cidade_endereco (Estado por sigla, Cidade por nome normalizado). Warning se não encontrar. |
| `templates/cadastros/configuracao_form.html` | Removida seção "Base do sistema" e "Local padrão (sede)". sigla_orgao no Cabeçalho. JS só CEP, telefone e uppercase (divisao, unidade, sigla_orgao). Removido JS de estado/cidade. |
| `config/settings.py` | Comentário sobre PostgreSQL padrão. Em `test` + sem POSTGRES_DB usa SQLite :memory: para testes. |
| `.env.example` | Texto ajustado: PostgreSQL como banco padrão em desenvolvimento. |
| `README.md` | Requisitos e setup com PostgreSQL padrão; import com caminho data/geografia; nota sobre cidade sede derivada do endereço. |
| `cadastros/tests/test_cadastros.py` | _post_config_base sem prazo, nome_orgao, estado, cidade_sede_padrao. Testes de maiúsculo incluem sigla_orgao. Teste cidade_sede_padrao definida quando Estado/Cidade existem. Teste warning quando cidade não encontrada. |

---

## 2. O que saiu da tela e o que permanece no model

**Removido da tela (não aparecem no form/template e não são enviados no POST):**
- Seção **Base do sistema** inteira
- Campo **prazo_justificativa_dias**
- Campo **nome_orgao**
- Bloco **Local padrão (sede)** (Estado + Cidade)
- Campos **estado** e **cidade_sede_padrao** no formulário

**Permanecem no model (sem mudança de migration):**
- `prazo_justificativa_dias`, `nome_orgao` — continuam no `ConfiguracaoSistema`; não são exibidos nem validados no form.
- `cidade_sede_padrao` — continua no model; passou a ser **definida no backend** a partir do endereço (UF + cidade do rodapé), não mais por seleção na tela.

**Na tela agora:**
- **Cabeçalho:** divisao, unidade, sigla_orgao (todos maiúsculos, client + server).
- **Rodapé:** CEP, logradouro, bairro, cidade_endereco, uf, numero (CEP preenche via API).
- **Contato:** telefone, email.
- **Assinaturas:** os 5 FKs para Viajante.

---

## 3. Como funciona cidade_sede_padrao derivada do CEP

1. O usuário preenche o **endereço** (CEP pode preencher logradouro, bairro, cidade, UF via API; número é manual).
2. Ao **salvar**, a view:
   - Persiste os dados do form normalmente.
   - Lê `uf` e `cidade_endereco` (do rodapé).
   - Busca **Estado** por `sigla == uf` (strip, upper), ativo.
   - Busca **Cidade** do mesmo estado cujo **nome** seja igual a `cidade_endereco` em comparação **case-insensitive e tolerante a acentos** (normalização NFD e remoção de acentos).
   - Se encontrar: define `config.cidade_sede_padrao = Cidade` e salva.
   - Se **não** encontrar (UF/cidade vazios, estado inexistente ou cidade sem match): mantém `cidade_sede_padrao = None`, salva e adiciona mensagem de **warning**: *"Base geográfica não importada ou cidade não encontrada; cidade sede padrão não foi definida."*

Assim, a cidade sede padrão depende da **base geográfica importada** (Estados/Cidades) e do **endereço** preenchido no rodapé.

---

## 4. Settings PostgreSQL e variáveis

- **Uso:** PostgreSQL é o banco padrão em desenvolvimento quando as variáveis de ambiente estão definidas.
- **Variáveis** (no `.env`):
  - `POSTGRES_DB` — nome do banco
  - `POSTGRES_USER` — usuário
  - `POSTGRES_PASSWORD` — senha
  - `POSTGRES_HOST` — host (default `localhost`)
  - `POSTGRES_PORT` — porta (default `5432`)

- **Lógica em `config/settings.py`:**
  - Se `test` está em `sys.argv` e `POSTGRES_DB` **não** está definido → usa **SQLite em memória** (`:memory:`) para testes.
  - Se `POSTGRES_DB` está definido → usa **PostgreSQL** com as variáveis acima.
  - Se `POSTGRES_DB` não está definido (e não é teste) → usa **SQLite** em arquivo (`db.sqlite3`) como fallback.

- **Requisito:** `psycopg[binary]` no `requirements.txt` (já presente).

---

## 5. Como rodar migrate e importar estados/municípios

**Migrate (com PostgreSQL):**
```bash
# Configure .env com POSTGRES_* e crie o banco no PostgreSQL, depois:
python manage.py migrate
```

**Importar base geográfica (idempotente):**
```bash
python manage.py importar_base_geografica --estados data/geografia/estados.csv --cidades data/geografia/municipios.csv
```

- Pode usar outros caminhos; o comando aceita qualquer path.
- **estados.csv** (UTF-8): colunas `COD`, `NOME`, `SIGLA`.
- **municipios.csv** (UTF-8): colunas `COD UF`, `COD`, `NOME`.
- Idempotente por `codigo_ibge`; cidades com estado inexistente são ignoradas com aviso.

---

## 6. Testes: o que foi ajustado e como rodar

**Ajustes:**
- `_post_config_base`: não envia mais `estado`, `cidade_sede_padrao`, `prazo_justificativa_dias`, `nome_orgao`.
- `test_configuracoes_post_atualiza_singleton`: verifica apenas `sigla_orgao` e singleton (sem prazo/nome_orgao).
- `test_configuracoes_post_divisao_unidade_sigla_maiusculo`: inclui `sigla_orgao` em maiúsculo.
- **Novos:**
  - `test_configuracoes_cidade_sede_padrao_definida_quando_estado_cidade_existem`: cria Estado PR e Cidade Curitiba; envia uf=PR e cidade_endereco=Curitiba; verifica que `cidade_sede_padrao` foi setada.
  - `test_configuracoes_cidade_nao_encontrada_nao_quebra_e_gera_warning`: envia UF + cidade inexistente; verifica que `cidade_sede_padrao` permanece null e que existe mensagem de aviso.

**Como rodar:**
```bash
python manage.py test cadastros.tests.test_cadastros
```

Ou só Configurações:
```bash
python manage.py test cadastros.tests.test_cadastros.ConfiguracoesViewTest
```
