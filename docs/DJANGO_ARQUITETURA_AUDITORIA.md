# Auditoria Global de Arquitetura Django

## Escopo

Apps auditados: `config`, `core`, `usuarios`, `cadastros`, `roteiros`, `eventos`, `documentos`, `oficios`, `termos`, `justificativas`, `planos_trabalho`, `ordens_servico`, `prestacoes_contas`, `diario_bordo`, `assinaturas`, `integracoes`, `templates`, `docs`.

## Tabela de achados

| Área | Repetição/problema | Arquivos | Decisão | Padrão criado |
|---|---|---|---|---|
| Models (ALTO) | Normalização repetida em `save()` | `cadastros/models.py` | Extrair normalizadores sem alterar regra | `core/normalizers.py` |
| Models (MÉDIO) | `TimeStampedModel` ainda local em `cadastros` | `cadastros/models.py`, `roteiros/models.py` | Manter como está por segurança (pendência controlada) | Documentação em `PADRAO_MODELS.md` |
| Forms (ALTO) | `clean_nome` e normalização duplicados | `cadastros/forms.py` | Reutilizar helper comum | `_normalize_nome_obrigatorio` + `core/normalizers.py` |
| Views (MÉDIO) | Mensagens/CRUD repetitivos | `cadastros/views.py` | Manter por segurança nesta rodada, padronizar em docs e auditoria | `PADRAO_VIEWS.md` |
| Selectors (DOCUMENTAR) | Nomenclatura parcialmente heterogênea entre apps | `cadastros/selectors.py`, `roteiros/selectors.py`, `oficios/selectors.py` | Não quebrar agora | `PADRAO_SELECTORS.md` |
| Services (CRÍTICO) | Tratamento `ProtectedError` repetido | `cadastros/services.py` | Centralizar helper de exclusão protegida | `core/deletion.py` |
| Presenters (ALTO) | Ações e meta repetidas | `cadastros/presenters.py`, `roteiros/presenters.py` | Extrair builders de presenter | `core/presenters/*` |
| URLs (DOCUMENTAR) | Convenções mistas `novo/nova`, `*_index` etc. | `*/urls.py` | Preservar rotas existentes | `PADRAO_APP.md` |
| Templates (BAIXO) | Base já componentizada; risco de regressão visual | `templates/components/**` | Sem refactor agressivo | `PADRAO_TEMPLATES.md` |
| Components (DOCUMENTAR) | Domínio roteiros é referência congelada | `templates/components/domain/**` | Manter contrato atual | `PADRAO_TEMPLATES.md` |
| Tests (MÉDIO) | Cobertura desigual entre apps | `cadastros/tests`, `roteiros/tests` | Rodar smoke tests definidos | Validação técnica |
| Docs (ALTO) | Ausência de padrão granular por camada | `docs/` | Criar guias por camada | `PADRAO_*.md` |

## Pendências controladas

1. Centralização de `TimeStampedModel` em `core` adiada para evitar risco de migration/regressão.
2. Refatoração massiva de views CRUD para helper genérico adiada (alto risco de regressão funcional).
3. Padronização total de nomes de URLs adiada para evitar quebra de links já usados.
