# Relatório — Refatoração do sistema de assinaturas (Configurações)

## Resumo

As assinaturas da configuração do sistema deixaram de ser campos fixos em `ConfiguracaoSistema` e passaram a ser armazenadas no modelo relacional `AssinaturaConfiguracao` (tipo + ordem), com edição na tela de configurações apenas para **ordem=1** de cada tipo. "Assinatura Ofícios 2" foi removida da UI (não é exibida), mas dados migrados ou criados no admin permanecem no banco com ordem=2.

---

## PARTE A — Model e migrations

### Model novo: `AssinaturaConfiguracao`

- **Arquivo:** `cadastros/models.py`
- **Campos:**
  - `configuracao` — FK para `ConfiguracaoSistema` (CASCADE, `related_name='assinaturas'`)
  - `tipo` — CharField com choices: `OFICIO`, `JUSTIFICATIVA`, `PLANO_TRABALHO`, `ORDEM_SERVICO`
  - `ordem` — PositiveSmallIntegerField (default=1)
  - `viajante` — FK para `Viajante` (SET_NULL, null=True, blank=True)
  - `ativo` — BooleanField (default=True)
  - `created_at`, `updated_at` — DateTimeField (auto)
- **Constraint:** `UniqueConstraint(fields=['configuracao','tipo','ordem'], name='uniq_assinatura_por_tipo_ordem')`

### Migration criada

- **Nome:** `cadastros/migrations/0004_assinatura_configuracao_relacional.py`
- **Operações (ordem):**
  1. `CreateModel(AssinaturaConfiguracao)` com todos os campos
  2. `AddConstraint` — `uniq_assinatura_por_tipo_ordem`
  3. `RunPython(migrate_assinaturas_para_novo_modelo, reverse_migrate_assinaturas)` — migra dados dos 5 campos antigos para `AssinaturaConfiguracao`
  4. `RemoveField(ConfiguracaoSistema, 'assinatura_oficio_1')`
  5. `RemoveField(ConfiguracaoSistema, 'assinatura_oficio_2')`
  6. `RemoveField(ConfiguracaoSistema, 'assinatura_justificativas')`
  7. `RemoveField(ConfiguracaoSistema, 'assinatura_planos_trabalho')`
  8. `RemoveField(ConfiguracaoSistema, 'assinatura_ordens_servico')`

### Campos antigos removidos de `ConfiguracaoSistema`

| Campo removido                 | Migrado para AssinaturaConfiguracao   |
|-------------------------------|----------------------------------------|
| `assinatura_oficio_1`         | tipo=OFICIO, ordem=1                   |
| `assinatura_oficio_2`         | tipo=OFICIO, ordem=2                   |
| `assinatura_justificativas`   | tipo=JUSTIFICATIVA, ordem=1            |
| `assinatura_planos_trabalho`  | tipo=PLANO_TRABALHO, ordem=1           |
| `assinatura_ordens_servico`   | tipo=ORDEM_SERVICO, ordem=1            |

Se o banco estiver vazio, a migração não quebra; o `RunPython` apenas não insere nada.

---

## PARTE B — Onde editar assinaturas e onde fica ordem=2

### Como editar assinaturas agora

- **Onde:** tela **Configurações do sistema** em `/cadastros/configuracoes/` (após login).
- **O que é salvo:** ao salvar o formulário, a view persiste os quatro campos extras no modelo `AssinaturaConfiguracao` com **ordem=1** para cada tipo:
  - Assinatura (Ofícios) → tipo=OFICIO, ordem=1  
  - Assinatura (Justificativas) → tipo=JUSTIFICATIVA, ordem=1  
  - Assinatura (Planos de Trabalho) → tipo=PLANO_TRABALHO, ordem=1  
  - Assinatura (Ordem de Serviço) → tipo=ORDEM_SERVICO, ordem=1  

Os selects continuam usando apenas **Viajantes ativos** (`Viajante.objects.filter(ativo=True).order_by('nome')`).

### Ordem=2 (ex.: “Assinatura Ofícios 2”)

- **UI:** não é exibida na tela de configurações (removida de propósito).
- **Admin:** é possível gerenciar assinaturas com ordem=2 (e qualquer outra ordem) em:
  - **Cadastros → Assinaturas (configuração)** — listagem e edição direta do modelo `AssinaturaConfiguracao`;
  - **Cadastros → Configurações do sistema** — inline tabular das assinaturas na edição da configuração, onde se pode adicionar/editar linhas com tipo OFICIO e ordem=2, etc.

Assim, dados migrados de `assinatura_oficio_2` (tipo=OFICIO, ordem=2) permanecem no banco e podem ser consultados/alterados apenas pelo admin.

---

## PARTE C — Testes

### Testes ajustados

- **Arquivo:** `cadastros/tests/test_cadastros.py`
- **Alterações:**
  - `_post_config_base`: payload passou a usar `assinatura_oficio`, `assinatura_justificativas`, `assinatura_planos_trabalho`, `assinatura_ordens_servico` (removidos `assinatura_oficio_1` e `assinatura_oficio_2`).
  - `test_configuracoes_post_assinatura_oficio_1_salva_fk` renomeado e reescrito para **`test_configuracoes_post_assinaturas_salvam_em_assinatura_configuracao`**: cria dois viajantes ativos, envia POST com `assinatura_oficio=viajante1` e `assinatura_justificativas=viajante2`, e verifica que existem registros em `AssinaturaConfiguracao` com (tipo OFICIO, ordem 1) → viajante1 e (tipo JUSTIFICATIVA, ordem 1) → viajante2.
  - **`test_configuracoes_ui_nao_mostra_assinatura_oficios_2`**: garante que a página de configurações não contém `id_assinatura_oficio_2` e que contém `id_assinatura_oficio` (apenas ordem=1 na UI).
  - `test_configuracoes_cidade_nao_encontrada_nao_quebra_e_gera_warning`: payload atualizado para os novos nomes de campos de assinatura.

### Como rodar os testes

```bash
python manage.py test cadastros.tests.test_cadastros
```

Ou só os testes de configurações:

```bash
python manage.py test cadastros.tests.test_cadastros.ConfiguracoesViewTest
```

---

## O que não foi alterado

- **Configurações existentes:** singleton e demais campos de `ConfiguracaoSistema` (cidade_sede_padrao, CEP, endereço, cabeçalho, contato) seguem iguais.
- **Regra de cidade_sede_padrao via CEP:** lógica em `_resolve_cidade_sede_from_endereco` e uso na view de configurações mantidos.
- **Fonte das assinaturas:** continuam sendo viajantes com `ativo=True` no banco (Viajantes).

---

## Admin

- **AssinaturaConfiguracao** está registrado em `cadastros/admin.py` (list_display, list_filter, autocomplete_fields para `viajante`).
- **ConfiguracaoSistema** possui **inline** `AssinaturaConfiguracaoInline` (tabular), permitindo gerenciar todas as ordens (incluindo ordem=2) na edição da configuração.
