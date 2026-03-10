# Relatório — Refatoração Etapa 1 do Evento Guiado

## 1) Models criados/alterados

### Novos models

- **TipoDemandaEvento** (`eventos/models.py`)
  - `nome` (CharField 120, unique, salvo em MAIÚSCULO no `save`)
  - `descricao_padrao` (TextField, blank, default="")
  - `ordem` (PositiveIntegerField, default=100)
  - `ativo` (BooleanField, default=True)
  - `is_outros` (BooleanField, default=False)
  - `created_at`, `updated_at`

- **EventoDestino** (`eventos/models.py`)
  - `evento` (FK → Evento, CASCADE, related_name='destinos')
  - `estado` (FK → Estado, PROTECT)
  - `cidade` (FK → Cidade, PROTECT)
  - `ordem` (PositiveIntegerField, default=0)
  - `created_at`, `updated_at`

### Alterações no model Evento

- **titulo**: `blank=True` (preenchido automaticamente na Etapa 1).
- **tipo_demanda**: `null=True`, `blank=True` (legado; exibição em lista/detalhe usa `tipos_demanda` quando existir).
- **tipos_demanda**: `ManyToManyField(TipoDemandaEvento, blank=True, related_name='eventos')`.
- **data_unica**: `BooleanField(default=False)` — quando True, usa só `data_inicio` e no backend `data_fim = data_inicio`.
- Métodos adicionados:
  - `gerar_titulo()` — monta o título a partir de tipos, destinos e datas.
  - `montar_descricao_padrao()` — concatena `descricao_padrao` dos tipos (exceto `is_outros`).

### Migrações

- `0003_etapa1_tipos_demanda_destinos.py`: cria TipoDemandaEvento, EventoDestino, adiciona `data_unica` e `tipos_demanda` em Evento, altera `titulo`/`tipo_demanda` para aceitar blank/null.
- `0004_populate_tipos_demanda.py`: dados iniciais — cria os 4 tipos a partir de TIPO_CHOICES e associa eventos existentes ao tipo correspondente.

---

## 2) Rotas criadas

| Rota | Nome | Descrição |
|------|------|-----------|
| `GET /eventos/tipos-demanda/` | `eventos:tipos-demanda-lista` | Lista de tipos de demanda |
| `GET+POST /eventos/tipos-demanda/cadastrar/` | `eventos:tipos-demanda-cadastrar` | Cadastrar tipo |
| `GET+POST /eventos/tipos-demanda/<pk>/editar/` | `eventos:tipos-demanda-editar` | Editar tipo |
| `POST /eventos/tipos-demanda/<pk>/excluir/` | `eventos:tipos-demanda-excluir` | Excluir tipo (bloqueado se em uso) |

Query string opcional: `?volta_etapa1=<pk_evento>` para redirecionar de volta à Etapa 1 após salvar/editar/excluir.

---

## 3) Como ficou a Etapa 1

- **Tipos de demanda**: seleção múltipla (checkboxes). Botão "Gerenciar tipos de demanda" abre a lista de tipos (com link de volta para a Etapa 1).
- **Datas**: checkbox "Evento em um único dia". Se marcado: só "Data do evento" (`data_inicio`); `data_fim` fica oculto e no backend é igual a `data_inicio`. Se desmarcado: "Data de início" e "Data de término".
- **Destinos**: lista dinâmica (estado + cidade por linha), botões "Adicionar destino" e "Remover". Estado padrão da primeira linha = PR quando existir. Pelo menos 1 destino obrigatório.
- **Descrição**: textarea; se houver tipo "Outros" selecionado, descrição obrigatória (livre).
- **Não exibidos**: título manual, cidade base, estado/cidade principal.

O título é gerado e salvo no backend ao salvar a Etapa 1; não há campo de título na tela.

---

## 4) Como o título é gerado

Método `Evento.gerar_titulo()`:

1. **Tipos**: nomes dos tipos de demanda (ativos, ordenados por `ordem` e `nome`), separados por ` / `.
2. **Destinos**: nomes das cidades (ou sigla do estado se não houver cidade), em maiúsculas. Um destino: só o nome; dois: "X E Y"; três ou mais: "PRIMEIRA E OUTRAS CIDADES".
3. **Data**: `data_inicio` em d/m/Y. Se não for data única e `data_fim != data_inicio`: "DD/MM/AAAA A DD/MM/AAAA".

Partes são unidas com ` - `. Exemplos:

- `PCPR NA COMUNIDADE - CURITIBA - 12/03/2026`
- `OPERAÇÃO POLICIAL / PARANÁ EM AÇÃO - MARINGÁ E LONDRINA - 12/03/2026 A 14/03/2026`

Na view da Etapa 1, após salvar evento e destinos, é chamado `obj.titulo = obj.gerar_titulo()` e `obj.save(update_fields=['titulo'])`.

---

## 5) Como a descrição automática funciona

- Ao salvar a Etapa 1, se **nenhum** tipo com `is_outros=True` estiver selecionado, a descrição do evento é sobrescrita com `obj.montar_descricao_padrao()`: concatenação dos `descricao_padrao` dos tipos selecionados (exceto "Outros"), separados por `\n\n`.
- Se **houver** tipo "Outros" selecionado, a descrição é obrigatória no formulário e o valor informado pelo usuário é mantido (não é sobrescrito).

---

## 6) Como testar manualmente

1. **Tipos de demanda**
   - Acessar `/eventos/<id>/guiado/etapa-1/` (criar evento pelo "Novo (fluxo guiado)" se necessário).
   - Marcar um ou mais tipos; clicar em "Gerenciar tipos de demanda", cadastrar/editar/excluir um tipo (excluir com tipo em uso deve exibir mensagem e não excluir).

2. **Datas**
   - Marcar "Evento em um único dia": só um campo de data; salvar e conferir no banco que `data_fim = data_inicio`.
   - Desmarcar: preencher início e término; validar que término ≥ início.

3. **Destinos**
   - Adicionar vários destinos (estado + cidade). Remover um. Salvar e conferir que o título inclui os destinos (e "E OUTRAS CIDADES" se > 2).
   - Enviar um destino com cidade de outro estado: deve dar erro de validação.

4. **Descrição**
   - Só tipos sem "Outros": salvar e conferir descrição gerada a partir dos textos padrão dos tipos.
   - Com "Outros" selecionado e descrição vazia: erro de validação. Preencher descrição e salvar.

5. **Painel**
   - Com evento sem tipos/destinos/título: Etapa 1 deve aparecer como Pendente.
   - Preencher tipos, destinos, datas e (se "Outros") descrição; salvar: título gerado e Etapa 1 deve aparecer como OK.

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Tipos de demanda configuráveis (model + CRUD) | OK |
| Relação N:N Evento ↔ TipoDemandaEvento | OK |
| Model EventoDestino (evento, estado, cidade, ordem) | OK |
| Evento com data_unica, data_inicio, data_fim | OK |
| Título gerado automaticamente (gerar_titulo) e salvo na Etapa 1 | OK |
| Descrição automática a partir dos tipos; OUTROS exige texto livre | OK |
| Etapa 1 sem título manual e sem cidade base | OK |
| Etapa 1: múltiplos tipos, data única ou intervalo, múltiplos destinos | OK |
| CRUD tipos de demanda com bloqueio de exclusão em uso | OK |
| Validações: ≥1 tipo, ≥1 destino, cidade no estado, datas, OUTROS → descrição | OK |
| Painel: Etapa 1 OK quando tipos, destinos, datas, descrição e título válidos | OK |
| Testes: múltiplos tipos, título automático, data única, múltiplos destinos, descrição, OUTROS, painel, CRUD tipos | OK |
| Roteiros, ofícios, termos, justificativas, pacote | Não implementado (fora do escopo) |

---

*Refatoração concluída: apenas Etapa 1 do evento guiado; foco em funcionalidade e modelagem.*
