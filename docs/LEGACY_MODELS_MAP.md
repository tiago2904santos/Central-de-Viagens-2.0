# Mapa de models do legacy vs projeto novo

Documento de auditoria para guiar migração funcional. **Fonte:** pasta `legacy/central de viagens 2.0/` (consulta apenas; o projeto novo não importa legacy em runtime).

## Organização do código legacy

| App Django (legacy) | Arquivo `models.py` | Observação |
|---------------------|---------------------|------------|
| `cadastros` | `cadastros/models.py` | Cadastros base. |
| `eventos` | `eventos/models.py` | **Arquivo muito grande:** além de eventos, concentra Ofício, Roteiro de evento, Plano de Trabalho, Ordem de Serviço, Termos, Justificativa, modelos auxiliares e integrações de fluxo. |
| `documentos` | `documentos/models.py` | Assinaturas genéricas (`AssinaturaDocumento`, `ValidacaoAssinaturaDocumento`). |
| `diario_bordo` | `diario_bordo/models.py` | Diário de bordo e trechos. |
| `prestacao_contas` | `prestacao_contas/models.py` | Prestação de contas, RT, comprovantes, textos padrão. |
| `integracoes` | `integracoes/models.py` | OAuth Google Drive (`GoogleDriveIntegration`). |
| `core` | `core/models.py` | Vazio (apenas import). |

---

## Cadastros

### Estado (`cadastros.Estado`)

- **Campos:** `codigo_ibge` (CharField, unique, opcional), `nome`, `sigla` (unique), `ativo`, `created_at`, `updated_at`.
- **Relacionamentos:** `cidades` (reverse FK).
- **Choices / constraints:** unique em `codigo_ibge`, `sigla`.
- **Save/custom:** nenhum especial além de docstring (base IBGE).
- **Copiar para o novo:** base fixa + import CSV (regra de negócio textual).
- **Descartar no novo:** flag `ativo` — no projeto novo estados não usam ativo/inativo (documentado em regras de negócio).
- **App novo:** `cadastros` → **Status na matriz:** `ADAPTAR` / **JÁ MIGRADO** (campos parcialmente divergentes: novo usa `codigo_ibge` como inteiro opcional).

### Cidade (`cadastros.Cidade`)

- **Campos:** `codigo_ibge`, `nome`, `estado` (FK PROTECT), lat/long, `ativo`, timestamps.
- **Relacionamentos:** FK para `Estado`.
- **Copiar:** unicidade e vínculo obrigatório com estado; coordenadas para estimativa de rota.
- **Descartar:** `ativo` (novo não usa).
- **App novo:** `cadastros` → **JÁ MIGRADO** + campo `capital`, `uf` espelhada, constraints diferentes.

### Cargo (`cadastros.Cargo`)

- **Campos:** `nome` (unique), `is_padrao`, timestamps.
- **Save:** normaliza nome maiúsculo; **um único** `is_padrao=True` por transação (`select_for_update` nos demais).
- **Copiar:** unicidade e normalização de nome.
- **Descartar / REVER:** conceito de cargo “padrão” — novo **não** tem `is_padrao` hoje.
- **App novo:** `cadastros.Cargo` → **ADAPTAR**.

### UnidadeLotacao (`cadastros.UnidadeLotacao`)

- **Campos:** `nome` (unique), timestamps.
- **Save:** nome em maiúsculo normalizado.
- **Copiar:** cadastro de unidade para lotação de servidores.
- **App novo:** corresponde conceitualmente a `cadastros.Unidade` (nome + sigla no novo; legacy só nome). → **ADAPTAR**.

### Viajante (`cadastros.Viajante`)

- **Campos:** `nome`, `status` (RASCUNHO/FINALIZADO), `cargo` (FK SET_NULL), `rg`, `sem_rg`, `cpf`, `telefone`, `unidade_lotacao` (FK), timestamps.
- **Constraints:** unicidade condicional em nome, cpf, rg, telefone (parcialmente preenchidos).
- **Propriedades:** `rg_formatado`, `cpf_formatado`, `telefone_formatado`; método `esta_completo()` com regras rígidas de CPF (11 dígitos), telefone 10/11, lotação, RG ou `sem_rg`.
- **Save:** `sem_rg` força RG canônico (`RG_NAO_POSSUI_CANONICAL`).
- **Copiar:** máscaras, validação de completude para uso em documentos, vínculo cargo/unidade.
- **Descartar:** fluxo de **status rascunho/finalizado** se o novo produto for “cadastro sempre pronto” (decisão de produto).
- **App novo:** `cadastros.Servidor` — sem telefone no model atual, sem status, sem `sem_rg` explícito. → **ADAPTAR** / **REVER**.

### CombustivelVeiculo (`cadastros.CombustivelVeiculo`)

- **Campos:** `nome` (unique), `is_padrao`, timestamps.
- **Save:** mesmo padrão de exclusividade de “padrão” que `Cargo`.
- **App novo:** `cadastros.Combustivel` — sem `is_padrao`. → **ADAPTAR**.

### Veiculo (`cadastros.Veiculo`)

- **Campos:** `placa`, `modelo`, `combustivel` (FK), `tipo` (CARACTERIZADO/DESCARACTERIZADO), `status` (RASCUNHO/FINALIZADO), timestamps.
- **Constraints:** placa unique se preenchida.
- **Métodos:** `_placa_valida()`, `esta_completo()`, `placa_formatada`; save normaliza placa.
- **App novo:** `cadastros.Viatura` — tipo com strings diferentes (`CARACTERIZADA`), sem status de rascunho. → **ADAPTAR** / **REVER**.

### ConfiguracaoSingleton (`cadastros.ConfiguracaoSistema`)

- **Campos:** sede (`cidade_sede_padrao`), prazo justificativa, nome/sigla órgão, cabeçalho (divisão/unidade), endereço via CEP, contato, chefia, FK `coordenador_adm_plano_trabalho` → Viajante, numeração PT (`pt_ultimo_numero`, `pt_ano`), `updated_at`.
- **Métodos:** `get_singleton()`, propriedades de máscara CEP/telefone.
- **Copiar:** ideia de **configuração única** institucional e parâmetros de numeração/documento.
- **App novo:** ausente como model dedicado (pode ir para `core` ou app de configuração). → **REVER** / **MOVER PARA OUTRO APP**.

### AssinaturaConfiguracao (`cadastros.AssinaturaConfiguracao`)

- **Campos:** FK `configuracao`, `tipo` (OFICIO, JUSTIFICATIVA, PLANO_TRABALHO, ORDEM_SERVICO, TERMO_AUTORIZACAO), `ordem`, FK `viajante`, `ativo`, timestamps.
- **Constraints:** unique (`configuracao`, `tipo`, `ordem`).
- **Copiar:** ordem e papéis de assinatura por tipo de documento.
- **App novo:** `assinaturas` ainda placeholder. → **ADAPTAR** para app `assinaturas` ou serviço de política.

---

## Eventos

### TipoDemandaEvento (`eventos.TipoDemandaEvento`)

- **Campos:** `nome`, `descricao_padrao`, `ordem`, `ativo`, `is_outros`, timestamps.
- **Save:** nome maiúsculo.
- **Copiar:** catálogo de tipos com texto padrão e flag “Outros”.
- **App novo:** `eventos` (placeholder). → **ADAPTAR**.

### Evento (`eventos.Evento`)

- **Campos:** `titulo`, `tipo_demanda` (legado char choices), M2M `tipos_demanda` → `TipoDemandaEvento`, `descricao`, `data_inicio`, `data_fim`, `data_unica`, FKs estado/cidade principal e cidade base, flags convite, `status` (rascunho/em andamento/finalizado/arquivado), FK `veiculo`, FK `motorista` (Viajante), `observacoes_operacionais`, timestamps.
- **Métodos:** `gerar_titulo()`, `montar_descricao_padrao()`.
- **Copiar:** ciclo de vida do evento, composição com tipos de demanda e datas.
- **Descartar:** eventual redundância `tipo_demanda` legado vs M2M (marcado como legado no próprio field).
- **App novo:** comentário único em `eventos/models.py`. → **COPIAR** / **ADAPTAR** (modelagem futura).

### EventoAnexoSolicitante (`eventos.EventoAnexoSolicitante`)

- **Campos:** FK evento, `FileField`, `nome_original`, `ordem`, `uploaded_at`.
- **Clean:** apenas PDF.
- **App novo:** não existe. → **ADAPTAR**.

### EventoParticipante (`eventos.EventoParticipante`)

- **Campos:** FK evento, FK Viajante, `ordem`, unique (evento, viajante).
- **App novo:** não existe. → **COPIAR**.

### EventoDestino (`eventos.EventoDestino`)

- **Campos:** FK evento, FK estado, FK cidade, `ordem`, timestamps.
- **App novo:** não existe. → **COPIAR**.

### EventoFinalizacao (`eventos.EventoFinalizacao`)

- **OneToOne** evento, observações, `finalizado_em`, `finalizado_por` (User).
- **App novo:** não existe. → **ADAPTAR**.

### EventoResgateAuditoria / EventoDocumentoSugestao (`eventos`)

- **Uso:** resgate documento→evento, ContentTypes, JSON de candidatos.
- **App novo:** não existe. → **REVER** (fluxo avançado).

---

## Roteiros (domínio legacy: `RoteiroEvento`)

### RoteiroEvento (`eventos.RoteiroEvento`)

- **Campos:** FK `evento` (nullable — permite avulso), origem estado/cidade (sede), `saida_dt`, `duracao_min`, `chegada_dt`, retorno (`retorno_saida_dt`, `retorno_duracao_min`, `retorno_chegada_dt`), campos texto/decimal de **diárias**, `observacoes`, `status`, `tipo` (EVENTO vs AVULSO), timestamps.
- **Relacionamentos:** `destinos` (`RoteiroEventoDestino`), `trechos` (`RoteiroEventoTrecho`), referenciado por Ofício, PlanoTrabalho, TermoAutorizacao, DiarioBordo.
- **Métodos:** `aplicar_diarias_calculadas`, `periodo_total_min`, `esta_completo()`, save recalcula status finalizado/rascunho e normaliza observações **maiúsculas**.
- **Copiar:** distinção roteiro **vinculado a evento** vs **avulso**; composição sede + destinos; ligação com ofício e documentos.
- **Descartar / ADAPTAR:** no projeto novo, `roteiros.Roteiro` é **linha única origem→destino** + trechos simples **sem** vínculo obrigatório a evento — modelo legacy é **mais rico** (diárias agregadas no cabeçalho, retorno, tipo IDA/RETORNO nos trechos).
- **App novo:** `roteiros` (entidades diferentes: `Roteiro`, `TrechoRoteiro`). → **ADAPTAR** (fundir conceitos: parte vai para `roteiros`, parte permanece acoplada a `eventos` no legacy).

### RoteiroEventoDestino (`eventos.RoteiroEventoDestino`)

- **Campos:** FK roteiro, FK estado, FK cidade, `ordem`.
- **App novo:** não há “lista de destinos” separada — novo usa só origem/destino principais + trechos. → **ADAPTAR** / **REVER**.

### RoteiroEventoTrecho (`eventos.RoteiroEventoTrecho`)

- **Campos:** FK roteiro, `ordem`, `tipo` (IDA/RETORNO), origem/destino estado e cidade, `saida_dt`, `chegada_dt`, **distância km**, durações e tempos (cru + adicional), `rota_fonte`, `rota_calculada_em`.
- **Property:** `tempo_total_final_min`.
- **App novo:** `roteiros.TrechoRoteiro` tem apenas origem/destino cidade, datas opcionais, sem km/tempo ainda. → **ADAPTAR** (campos de cálculo de rota/diária virão depois, alinhados ao legacy).

---

## Ofícios

### Oficio (`eventos.Oficio`)

- **Campos principais:** vínculo N:N com `Evento` via `OficioEventoVinculo`; FK `roteiro_evento`; M2M `viajantes`; FK `veiculo`, `motorista_viajante`, `carona_oficio_referencia`; `tipo_origem` (AVULSO/EVENTO); numeração `numero`/`ano`, `protocolo`, `data_criacao`, modelo motivo, texto motivo, assunto (autorização/convalidação), custeio, tipo destino (interior/capital/brasília), `roteiro_modo`, sede estado/cidade; bloco transporte (placa/modelo/combustível texto, tipo viatura, porte armas); bloco motorista texto e **retorno** com km/tempo/diárias; `status`, timestamps.
- **Constraints:** unique (`ano`, `numero`).
- **Métodos:** numeração por lacuna (`get_next_available_numero`), normalização protocolo, `compute_assunto_tipo`, integração com trechos e evento principal, `esta_vinculado_a_evento`.
- **Copiar:** quase todo o conjunto de regras de negócio de ofício (exceto detalhes de UX).
- **App novo:** `oficios` placeholder. → **COPIAR** / **ADAPTAR**.

### OficioEventoVinculo (`eventos.OficioEventoVinculo`)

- **Campos:** FK ofício, FK evento, unique (ofício, evento).
- **Copiar:** N:N explícito (substitui FK único antigo — comentários no código legacy).
- **App novo:** não existe. → **COPIAR**.

### OficioTrecho (`eventos.OficioTrecho`)

- **Campos:** FK ofício, ordem, origem/destino estado/cidade, saída/chegada data+hora, **distância/tempo/rota**, unique (ofício, ordem).
- **Property:** `tempo_total_final_min`.
- **Copiar:** trechos de **ida** (retorno no próprio Ofício).
- **App novo:** não existe. → **COPIAR**.

### OficioAssinaturaPedido (`eventos.OficioAssinaturaPedido`)

- **Campos:** token público, status, assinante esperado, PDFs, hashes, auditoria JSON, expiração, fontes para assinatura.
- **App novo:** não existe (assinatura genérica está em `documentos` legacy). → **ADAPTAR** entre `oficios` e `assinaturas`.

### ModeloMotivoViagem (`eventos.ModeloMotivoViagem`)

- **Catálogo** para motivo OS/Ofício; usado por `OrdemServico` e `Oficio`.
- **App novo:** não existe. → **ADAPTAR** (pode ficar em `ordens_servico` ou `oficios`). → **REVER**.

---

## Termos

### EventoTermoParticipante (`eventos.EventoTermoParticipante`)

- **Campos:** FK evento, FK Viajante, status (pendente/dispensado/gerado/concluído), modalidade (completo/semipreenchido), última geração, formato PDF/DOCX.
- **Copiar:** máquina de estados do termo por participante.
- **App novo:** `termos` placeholder. → **COPIAR** / **ADAPTAR**.

### TermoAutorizacao (`eventos.TermoAutorizacao`)

- **Campos extensos:** modos de geração (genérico, rápido, automático com/sem viatura), derivação de termos pai/filho, FK evento/roteiro/ofício/M2M ofícios, FK viajante/viatura, snapshots de servidor e viatura, datas evento, usuário criador, status rascunho/gerado, `clean`/`save` com sincronização de contexto e validações cruzadas ofício/evento/roteiro.
- **Copiar:** regra de snapshots e modos de geração.
- **App novo:** não existe. → **COPIAR** / **ADAPTAR** em `termos`.

---

## Justificativas

### ModeloJustificativa (`eventos.ModeloJustificativa`)

- **Campos:** nome, texto, `padrao`, `ativo`; save garante um `padrao`.
- **App novo:** não existe. → **ADAPTAR** em `justificativas`.

### Justificativa (`eventos.Justificativa`)

- **OneToOne** com `Oficio` (nullable no schema mas conceito 1:1), FK modelo, texto.
- **App novo:** não existe. → **COPIAR** em `justificativas` (vínculo com ofício).

---

## Plano de Trabalho (todos em `eventos/models.py` no legacy)

### SolicitantePlanoTrabalho, HorarioAtendimentoPlanoTrabalho, CoordenadorOperacional, AtividadePlanoTrabalho

- **Papel:** catálogos reutilizáveis (solicitante, horário, coordenadores, atividades com código único e meta/recursos).
- **AtividadePlanoTrabalho.save:** normaliza código slug-like uppercase.
- **App novo:** não existe. → **COPIAR** / **ADAPTAR** em `planos_trabalho`.

### PlanoTrabalho (`eventos.PlanoTrabalho`)

- **Campos:** número/ano, datas, status, FK opcional evento, FK/M2M ofício(s), FK `RoteiroEvento`, solicitante, coordenadores (FK + M2M + texto), destinos JSON, campos de datas/horas sede, simulação **diárias** (vários formatos), recursos, observações, JSON etapa 2, etc.
- **Métodos:** resolução de evento canônico vs herdado, labels de destinos, `clean`/`save` com sincronização de vínculos.
- **App novo:** placeholder `planos_trabalho`. → **COPIAR** / **ADAPTAR**.

### EfetivoPlanoTrabalhoDocumento / EfetivoPlanoTrabalho

- **Documento:** FK plano + cargo + quantidade, unique (plano, cargo).
- **Por evento:** FK evento + cargo + quantidade, unique (evento, cargo).
- **App novo:** não existe. → **ADAPTAR** (dois níveis no legacy — consolidar no novo desenho).

---

## Ordem de Serviço

### OrdemServico (`eventos.OrdemServico`)

- **Campos:** número/ano, datas, status, FK evento/ofício, datas deslocamento, FK `ModeloMotivoViagem`, texto motivo, M2M viajantes, `destinos_json`, finalidade, responsáveis.
- **Métodos:** numeração com retry, herança de viajantes do ofício, validação ofício↔evento, `clean`/`save`.
- **App novo:** placeholder `ordens_servico`. → **COPIAR** / **ADAPTAR**.

---

## Prestação de contas (`prestacao_contas`)

### PrestacaoConta e relacionados

- **PrestacaoConta:** FK obrigatório para `eventos.Oficio`, arquivos (despacho, comprovante, ofício assinado), status de fluxo, vínculos com RT e DB.
- **Outros models no arquivo:** `PrestacaoComprovanteTransferencia`, `RelatorioTecnicoPrestacao`, `TextoPadraoDocumento` (conteúdo real de templates).
- **App novo:** `prestacoes_contas` placeholder. → **ADAPTAR**.

---

## Diário de bordo (`diario_bordo`)

### DiarioBordo, DiarioBordoTrecho

- **DiarioBordo:** FK opcional ofício, prestação, roteiro, viatura, motorista; campos de cabeçalho/cópia; status; vários `FileField`; FKs para `eventos` e `prestacao_contas`.
- **Trechos:** datas, km inicial/final, origem/destino **texto livre**, abastecimento, observação.
- **App novo:** placeholder `diario_bordo`. → **ADAPTAR** (trechos legacy são texto; novo pode usar cidades depois).

---

## Documentos (`documentos`) — legacy

### AssinaturaDocumento / ValidacaoAssinaturaDocumento

- **Generic FK** para qualquer documento; hashes SHA-256, PDF assinado, método de autenticação, status, validações.
- **App novo:** `documentos` e `assinaturas` placeholders; integração Google em `integracoes` novo também placeholder. → **ADAPTAR** / **MOVER** parte para `assinaturas`.

---

## Integrações (`integracoes`)

### GoogleDriveIntegration

- Tokens criptografados (Fernet), OAuth, pasta raiz.
- **App novo:** `integracoes.google_drive` sem models ainda. → **ADAPTAR**.

---

## Matriz resumo legacy → novo

| Entidade legacy | App legacy | Entidade nova | App novo | Status |
|-----------------|-------------|---------------|----------|--------|
| Estado | cadastros | Estado | cadastros | JÁ MIGRADO / ADAPTAR |
| Cidade | cadastros | Cidade | cadastros | JÁ MIGRADO / ADAPTAR |
| Cargo | cadastros | Cargo | cadastros | ADAPTAR |
| UnidadeLotacao | cadastros | Unidade | cadastros | ADAPTAR |
| Viajante | cadastros | Servidor | cadastros | ADAPTAR / REVER |
| CombustivelVeiculo | cadastros | Combustivel | cadastros | ADAPTAR |
| Veiculo | cadastros | Viatura | cadastros | ADAPTAR |
| ConfiguracaoSistema | cadastros | — | core ou config | REVER / MOVER PARA OUTRO APP |
| AssinaturaConfiguracao | cadastros | — | assinaturas | ADAPTAR |
| TipoDemandaEvento | eventos | — | eventos | ADAPTAR |
| Evento | eventos | — | eventos | COPIAR / ADAPTAR |
| EventoDestino | eventos | — | eventos | COPIAR |
| EventoParticipante | eventos | — | eventos | COPIAR |
| EventoAnexoSolicitante | eventos | — | eventos | ADAPTAR |
| EventoFinalizacao | eventos | — | eventos | ADAPTAR |
| RoteiroEvento | eventos | Roteiro + TrechoRoteiro (parcial) | roteiros + eventos | ADAPTAR |
| RoteiroEventoDestino | eventos | — | roteiros ou eventos | REVER |
| RoteiroEventoTrecho | eventos | TrechoRoteiro | roteiros | ADAPTAR |
| Oficio | eventos | — | oficios | COPIAR / ADAPTAR |
| OficioEventoVinculo | eventos | — | oficios / eventos | COPIAR |
| OficioTrecho | eventos | — | oficios | COPIAR |
| OficioAssinaturaPedido | eventos | — | oficios / assinaturas | ADAPTAR |
| ModeloMotivoViagem | eventos | — | ordens_servico ou oficios | REVER |
| ModeloJustificativa | eventos | — | justificativas | ADAPTAR |
| Justificativa | eventos | — | justificativas | COPIAR |
| EventoTermoParticipante | eventos | — | termos | COPIAR / ADAPTAR |
| TermoAutorizacao | eventos | — | termos | COPIAR / ADAPTAR |
| SolicitantePlanoTrabalho | eventos | — | planos_trabalho | COPIAR / ADAPTAR |
| HorarioAtendimentoPlanoTrabalho | eventos | — | planos_trabalho | COPIAR / ADAPTAR |
| CoordenadorOperacional | eventos | — | planos_trabalho | COPIAR / ADAPTAR |
| AtividadePlanoTrabalho | eventos | — | planos_trabalho | COPIAR / ADAPTAR |
| PlanoTrabalho | eventos | — | planos_trabalho | COPIAR / ADAPTAR |
| EfetivoPlanoTrabalhoDocumento | eventos | — | planos_trabalho | ADAPTAR |
| EfetivoPlanoTrabalho | eventos | — | planos_trabalho / eventos | ADAPTAR |
| OrdemServico | eventos | — | ordens_servico | COPIAR / ADAPTAR |
| EventoResgateAuditoria | eventos | — | eventos / documentos | REVER |
| EventoDocumentoSugestao | eventos | — | eventos | REVER |
| PrestacaoConta (+ anexos RT) | prestacao_contas | — | prestacoes_contas | ADAPTAR |
| DiarioBordo / DiarioBordoTrecho | diario_bordo | — | diario_bordo | ADAPTAR |
| AssinaturaDocumento | documentos | — | documentos / assinaturas | ADAPTAR |
| GoogleDriveIntegration | integracoes | — | integracoes.google_drive | ADAPTAR |

---

## Síntese executiva

| Ação | Exemplos |
|------|----------|
| **Copiar/adaptar regra** | Ofício (número, protocolo, trechos, vínculo evento); Ordem de Serviço; Plano de Trabalho e catálogos; termos e participação; justificativa 1:1; roteiro de evento (vs roteiro avulso novo); participantes e destinos de evento. |
| **Já migrado (cadastros)** | Estado, Cidade, Cargo, Combustível, Servidor, Viatura, Unidade — com divergências (sem status rascunho, sem telefone, sem “padrão” em cargo/combustível). |
| **Descartar ou simplificar** | `ativo` em estado/cidade legacy; possível status RASCUNHO em viajante/viatura se o novo for sempre “pronto para uso”. |
| **Rever com produto** | Configuração singleton institucional; resgates/sugestões documento→evento; onde ficam `ModeloMotivoViagem` e destinos múltiplos do roteiro legacy vs modelo novo mais simples. |

---

## Próximo passo recomendado

1. **Congelar** este mapa como baseline e priorizar domínios na ordem de dependência: **Cadastros (fechar lacunas Viajante→Servidor)** → **Evento + vínculos** → **Ofício + trechos + justificativa** → **Roteiro evento vs roteiro avulso** (decisão explícita de produto) → **Termos / OS / PT / Prestação / Diário**.
2. Para cada app placeholder (`eventos`, `oficios`, …), abrir **épico** alinhado às linhas **COPIAR/ADAPTAR** da matriz, extraindo services e validações do legacy **sem importar código**, apenas reimplementando.
3. Manter **estimativa de rota / diárias** como camada de serviço espelhando campos já presentes em `RoteiroEventoTrecho`, `OficioTrecho` e blocos de retorno do `Oficio`, conforme decisões já documentadas no novo projeto (não reimplementar nesta etapa).

---

*Gerado na branch `auditoria/mapa-funcional-legacy`. Validação: `python manage.py check` após adição do documento.*
