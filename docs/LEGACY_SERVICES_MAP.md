# Mapa de services e funções funcionais — legacy (Central de Viagens 2.0)

**Escopo:** auditoria apenas (documentação). Nenhuma implementação no projeto novo foi feita nesta fase.

**Raiz do código legado analisado:** `legacy/central de viagens 2.0/`  
(Paths no texto abaixo são relativos a essa raiz, salvo indicação.)

**Observação:** Não existem `legacy/eventos/document_renderer.py`, `document_generator.py`, `downloads.py`, `placeholders.py` nem `assinatura*` soltos na raiz de `eventos/` — a geração documental concentra-se em `eventos/services/documentos/` e módulos relacionados. `eventos/termos.py` complementa contexto de termos às views.

---

## Documentos DOCX/PDF

| Área | Onde no legacy | Conteúdo funcional | Dependências / notas |
|------|----------------|-------------------|----------------------|
| Pipeline principal | `eventos/services/documentos/__init__.py` | Reexporta context builders, validação, nomes de arquivo, tipos, backends, `render_document_bytes` (lazy import do renderer). | API estável usada por views e outros services. |
| Renderização DOCX + PDF | `eventos/services/documentos/renderer.py` | Criação de documentos programáticos (`create_base_document`, tabelas, assinaturas em bloco); resolução de templates (`get_document_template_path`, disponibilidade por tipo); extração/substituição de placeholders em parágrafos (`extract_placeholders_from_doc`, `safe_replace_placeholders`, `render_docx_template_bytes`); conversão `convert_docx_bytes_to_pdf_bytes` via LibreOffice ou Word COM; `render_document_bytes` roteando por `DocumentoOficioTipo` + formato. | `python-docx`; LibreOffice `soffice` ou Word COM (Windows); erros tipados em `types.py`. |
| Contexto comum e por documento | `eventos/services/documentos/context.py` | Formatação de exibição (`format_document_display`, datas BR); montagem de contexto para ofício, justificativa, termo, plano de trabalho e ordem de serviço; integra **diárias** (`calculate_periodized_diarias`), **justificativa** (texto/prazo), **plano_trabalho_domain** (atividades/recursos/efetivo); assinaturas por tipo (`get_assinaturas_documento`); trechos, retorno, custeio, viajantes, motorista, período de viagem. | Forte acoplamento a models `Oficio`, `Evento`, `PlanoTrabalho`, etc. |
| Ofício (template) | `eventos/services/documentos/oficio.py` | `build_oficio_template_context`, `render_oficio_docx`; colunas de roteiro ida/retorno, destino cabeçalho, custeio, motorista, assunto (autorização/convalidação). | Usado por fluxo principal de documentos do ofício. |
| Justificativa (DOCX) | `eventos/services/documentos/justificativa.py` | Contexto + `render_justificativa_docx`. | Acoplado a `justificativa.py` (regras de prazo). |
| Termo de autorização | `eventos/services/documentos/termo_autorizacao.py` | Variantes de template por modalidade/viatura; contexto por ofício, por participante do evento, termo salvo; validação `validate_evento_participante_termo_data`; renderização múltipla (`render_termo_autorizacao_docx`, `render_evento_participante_termo_docx`, `render_saved_termo_autorizacao_docx`). | Lógica rica de placeholders e pós-processamento visual do termo. |
| Plano de trabalho | `eventos/services/documentos/plano_trabalho.py` | Texto de efetivo, período, recursos; `render_plano_trabalho_docx` / `render_plano_trabalho_model_docx`. | Usa plano desacoplado ou via ofício. |
| Ordem de serviço | `eventos/services/documentos/ordem_servico.py` | Número da ordem, datas por extenso, equipe/deslocamento, destinos; `build_ordem_servico_*_context`, renders DOCX. | Integra `get_primeira_saida_oficio` (justificativa). |
| Nomes de arquivo | `eventos/services/documentos/filenames.py` | `build_document_filename` normaliza partes e tipo/formato. | |
| Validação pré-geração | `eventos/services/documentos/validators.py` | Validação por tipo (ofício, justificativa, termo, PT, OS); `validate_oficio_for_document_generation`; `get_document_generation_status` (inclui formato DOCX/PDF e backends). | |
| Tipos e erros | `eventos/services/documentos/types.py` | `DocumentoFormato`, `DocumentoOficioTipo`, metadados, hierarquia de exceções de geração. | |
| Backends DOCX/PDF | `eventos/services/documentos/backends.py` | Detecção de LibreOffice/Word COM, cache de capacidades, `get_document_backend_availability`. | Ambiente Windows/Linux afeta disponibilidade de PDF. |

**Destino provável (projeto novo):** `documentos/services/renderer.py`, `context.py` (ou fatiar por tipo), `placeholders.py` (extração/substituição), `validators.py`, `downloads.py` (se downloads saírem das views), `templates.py` (paths e disponibilidade).

---

## Ofícios

| Área | Onde no legacy | Função |
|------|----------------|--------|
| Contexto e texto do ofício | `eventos/services/documentos/context.py`, `eventos/services/documentos/oficio.py` | Número exibido, protocolo (via máscaras em views/utils), trechos ida/volta, retorno, destino automático no cabeçalho, custeio, viajantes, motorista, viatura, resumo de roteiro, vínculo com justificativa (texto). |
| Assinatura do ofício (fluxo pedido público) | `eventos/services/oficio_assinatura.py` | Hash SHA-256, PDF canônico (`render_document_bytes`), criar/obter pedido, invalidar pendentes, status, validação CPF/token, telefone, URL pública, quebra por alteração (`assinatura_foi_invalidada_por_alteracao`). |
| Assinatura textual no PDF (canvas) | `eventos/services/pdf_signature.py` | Fontes, `apply_text_signature_on_pdf` para assinatura desenhada (fluxo alternativo/complementar). |
| Máscaras / protocolo | `core/utils/masks.py` | `format_protocolo`, `normalize_protocolo`, CPF, telefone, placa, etc. — usado em formulários e exibição. |
| Schema JSON da justificativa no ofício | `eventos/services/oficio_schema.py` | Cache de schema disponível para campo estruturado de justificativa. |

**Destino provável:** `oficios/services.py`, `oficios/selectors.py`, `oficios/presenters.py`, `assinaturas/services.py`, `documentos/services/`.

---

## Roteiros

| Área | Onde no legacy | Função |
|------|----------------|--------|
| Provedor de rota (OSRM) | `eventos/services/routing_provider.py` | `RouteResult`, `OSRMRoutingProvider`, `get_default_routing_provider`. |
| Estimativa local (km, tempo, perfil) | `eventos/services/estimativa_local.py` | Haversine, fator rodoviário, faixas de distância, calibração, ETA por rota e fallback, buffer operacional, integração com `corredores_pr` e `routing_provider`. |
| Corredores PR (macro/fino) | `eventos/services/corredores_pr.py` | Classificação geográfica fina (litoral, serra, etc.), inferência de município, atributos de rota. |
| Orquestração na view | `eventos/views.py` (imports no topo) | Chama `estimativa_local`, `diarias`, integração com formulários de trechos — **parte da lógica permanece inline na view**; migrar para services de roteiro. |

**Destino provável:** `roteiros/services.py`, `roteiros/selectors.py`, `roteiros/presenters.py` (+ possível `integracoes/osrm` ou settings).

---

## Diárias

| Onde | Funções-chave |
|------|----------------|
| `eventos/services/diarias.py` | `PeriodMarker`, classificação de destino (`classify`, `infer_tipo_destino_from_paradas`), pernoites (`count_pernoites`, segmentos), `build_periods`, `calculate_periodized_diarias`, formatação monetária (`formatar_valor_diarias`, `calcular_diarias_com_valor`). |

**Consumidor direto:** `documentos/context.py` (plano de trabalho e contexto comum), e views globais (`views_global.py`) para simulação/resumo.

**Destino provável:** `roteiros/services.py`, `planos_trabalho/services.py`, `documentos/services/` (extensão de contexto).

---

## Termos

| Onde | Conteúdo |
|------|----------|
| `eventos/services/documentos/termo_autorizacao.py` | Geração DOCX por modalidade, viatura, participante, termo persistido; validação de dados. |
| `eventos/termos.py` | `build_termo_context`, `build_termo_preview_payload` — contexto de UI/preview (sobreposição parcial com `contexto_evento.py`). |
| `eventos/services/contexto_evento.py` | `build_contexto_termo_from_evento`, `ensure_termo_generico_evento`, `attach_termo_derivacoes` — vínculo evento/ofício/roteiro e termos múltiplos. |

**Destino provável:** `termos/services.py` (+ consolidar duplicação com `contexto_evento`).

---

## Justificativas

| Onde | Conteúdo |
|------|----------|
| `eventos/services/justificativa.py` | Prazo (`get_prazo_justificativa_dias`), primeira saída, antecedência, se exige justificativa, texto agregado, `oficio_tem_justificativa`. |
| `eventos/services/oficio_schema.py` | Disponibilidade de schema JSON para justificativa estruturada. |
| `eventos/services/documentos/justificativa.py` | Render DOCX de justificativa. |

**Destino provável:** `justificativas/services.py`.

---

## Plano de Trabalho

| Onde | Conteúdo |
|------|----------|
| `eventos/services/plano_trabalho_domain.py` | Catálogo de atividades (`get_atividades_catalogo`), formatação de atividades/metas/recursos, flags unidade móvel. |
| `eventos/services/plano_trabalho_step2.py` | Seleção de roteiro mais caro, defaults do passo 2, reconciliação de estado (`reconcile_plano_step2_state`). |
| `eventos/services/documentos/context.py` + `plano_trabalho.py` | Contexto numérico/textual (número próximo, coordenação, diárias agregadas), render DOCX. |
| `eventos/services/documento_snapshots.py` | `snapshot_plano` e comparação de períodos (dirty/consistência). |

**Destino provável:** `planos_trabalho/services.py` (+ `selectors`/`presenters` para telas globais).

---

## Ordem de Serviço

| Onde | Conteúdo |
|------|----------|
| `eventos/services/documentos/ordem_servico.py` | Montagem de contexto (número, ano implícito no texto, motivo implícito nos templates), equipe, destinos, datas por extenso; render DOCX por ofício ou modelo `OrdemServico`. |

**Destino provável:** `ordens_servico/services.py`, `documentos/services/`.

---

## Prestação de Contas

| Arquivo | Funções / papel |
|---------|-----------------|
| `prestacao_contas/services/sincronizacao.py` | `sincronizar_prestacoes_do_oficio` — cria/atualiza prestações a partir do ofício (descrição, servidor). |
| `prestacao_contas/services/relatorio_tecnico.py` | Dados do servidor, diária automática, `obter_ou_criar_rt`, `montar_contexto_rt`, validação de placeholders (`_validar_placeholders_bytes`), `gerar_docx_rt` / `gerar_pdf_rt` (usa `renderer` do eventos). |
| `prestacao_contas/services/dossie_final.py` | Nome do PDF final, reúne anexos (ofício assinado automático), `compilar_pdf_prestacao`; invalidação se assinatura quebrada (`assinatura_foi_invalidada_por_alteracao`). |

**Destino provável:** `prestacoes_contas/services.py`.

---

## Diário de Bordo

| Arquivo | Conteúdo |
|---------|----------|
| `diario_bordo/services.py` | Manipulação OpenXML do XLSX (shared strings, merges, fórmulas); `render_xlsx_diario_bordo`, validação de placeholders remanescentes; `gerar_diario_bordo_xlsx`, conversão PDF (Excel COM ou LibreOffice) `gerar_diario_bordo_pdf`; descoberta de trechos a partir de roteiro/ofício `inicializar_trechos_diario_bordo`. |

**Destino provável:** `diario_bordo/services.py`.

---

## Assinaturas

| Escopo | Arquivo | Conteúdo |
|--------|---------|----------|
| Ofício (pedido + PDF canônico) | `eventos/services/oficio_assinatura.py` | Fluxo completo do pedido público e hash de conteúdo. |
| Desenho da assinatura no PDF | `eventos/services/pdf_signature.py` | Texto/fontes. |
| Assinaturas genéricas (carimbo, ICP-Brasil dev, validação) | `documentos/services/assinaturas.py` | SHA-256, QR, layout, overlay, `aplicar_assinatura_pdf_real`, validação técnica, `assinar_documento_pdf`, upload de validação pública. |

**Destino provável:** `assinaturas/services.py`, `documentos/services/` (geração PDF).

---

## Integrações

| Arquivo | Conteúdo |
|---------|----------|
| `integracoes/services/google_drive/oauth_service.py` | OAuth2 Google: fluxo, state na sessão, troca de código, persistência em `GoogleDriveIntegration`. |
| `integracoes/services/google_drive/drive_service.py` | Cliente autenticado, pastas, upload, pasta raiz do usuário, disconnect. |
| `documentos/services/exportacao_google_drive.py` | `ExportacaoEventoGoogleDriveService` — gera DOCX/PDF de vários tipos de documento do evento e envia ao Drive; sanitização de nomes. |

**Destino provável:** `integracoes/google_drive/services.py` (e camada de aplicação em `documentos/` para exportação).

---

## Outros módulos reutilizáveis

| Arquivo | Papel |
|---------|--------|
| `eventos/utils.py` | Tempo `hhmm`/`minutes`, mapeamento tipo viatura → ofício, buscas autocomplete de viajantes/veículos, serialização para JSON de UI. |
| `eventos/services/documento_vinculos.py` | Resolve vínculos semânticos entre ofício, ordem, plano, evento (para telas e ajuda ao usuário). |
| `eventos/services/documento_selectors.py` | Querysets base e ofícios “linkáveis”. |
| `eventos/services/documento_presenters.py` | URLs e rótulos de vínculos para UI. |
| `eventos/services/documento_snapshots.py` | Snapshots JSON para comparação período/local/ofício e resgate de documentos. |
| `eventos/services/evento_resgate.py` | Pontuação de candidatos de evento para documento órfão, auto-anexação segura, `resgatar_documentos_orfaos_para_evento`. |
| `eventos/services/evento_pacote.py` | Pacote de links de documentos por evento (hub). |
| `utils/valor_extenso.py` | `valor_por_extenso_ptbr` — usado em views globais (ex.: contexto financeiro). |
| `cadastros/management/commands/` | `importar_base_geografica`, `importar_coordenadas_cidades`, `importar_servidores_csv`, `importar_unidades_lotacao` — **importação offline**, não é runtime da aplicação web, mas é regra operacional de dados. |

**Nota:** `cadastros/services.py` **não existe** no legacy analisado.

---

## Views grandes — acoplamento (para migração)

- **`eventos/views.py`:** importa estimativa, diárias, justificativa, schema, vínculos, pacote de documentos, resgate, contextos, `documentos.*`, renderer, termos, assinatura, exportação Google Drive, sincronização de prestações, máscaras. Centraliza orquestração HTTP + muita regra; na migração, extrair para services conforme domínio.
- **`eventos/views_global.py`:** telas globais de PT/OS/termo — diárias, documentos, `plano_trabalho_domain`, `plano_trabalho_step2`, selectors/presenters, status assinatura, `valor_extenso`.
- **`eventos/views_assinatura.py`:** delega a `oficio_assinatura` e `pdf_signature`.
- **`prestacao_contas/views.py`:** RT, dossiê, diário de bordo (geração/inicialização de trechos).

---

## Matriz (resumo por módulo)

| Serviço/função legacy | Arquivo legacy | Usado por view / consumidor | App novo destino | Status | Observação |
|------------------------|----------------|------------------------------|------------------|--------|------------|
| Pipeline `render_document_bytes` + tipos | `eventos/services/documentos/*.py` | `eventos/views.py`, `views_global.py`, assinatura | `documentos` | ADAPTAR | Acoplado a models legados e backends locais. |
| Contexto ofício/PT/OS/justificativa/termo | `documentos/context.py`, `oficio.py`, etc. | `eventos/views*.py` | `documentos` + domínios | ADAPTAR | Reaproveitar regras de texto; mudar imports de models. |
| Placeholders DOCX | `documentos/renderer.py` | Mesmas views + `relatorio_tecnico` | `documentos/services` | COPIAR / ADAPTAR | Testar templates novos. |
| Conversão DOCX→PDF | `documentos/renderer.py` | Geração geral | `documentos/services` | ADAPTAR | LibreOffice vs COM conforme deploy. |
| Validação pré-geração | `documentos/validators.py` | Antes de download/preview | `documentos/validators.py` | COPIAR / ADAPTAR | |
| Nomes de arquivo | `documentos/filenames.py` | Downloads | `documentos/services` | COPIAR | |
| Backends | `documentos/backends.py` | Status na UI / validators | `documentos/services` | REVER | Depende do ambiente servidor. |
| Estimativa rota + ETA | `estimativa_local.py`, `routing_provider.py`, `corredores_pr.py` | `eventos/views.py`, APIs JSON, testes | `roteiros` | ADAPTAR | OSRM e calibração são sensíveis a config. |
| Diárias | `diarias.py` | `context.py`, `views_global.py` | `roteiros` / `planos_trabalho` | COPIAR / ADAPTAR | Regra de negócio central. |
| Justificativa (regra) | `justificativa.py`, `oficio_schema.py` | `forms.py`, `views.py` | `justificativas` | ADAPTAR | Schema JSON pode mudar de armazenamento. |
| Termos (DOCX + contexto) | `documentos/termo_autorizacao.py`, `termos.py`, `contexto_evento.py` | `views.py`, `views_global.py` | `termos` | ADAPTAR | Unificar `termos.py` vs `contexto_evento`. |
| Plano trabalho domínio + step2 | `plano_trabalho_domain.py`, `plano_trabalho_step2.py` | `views_global.py`, `prestacao` forms/views | `planos_trabalho` | COPIAR / ADAPTAR | |
| Ordem de serviço DOCX | `documentos/ordem_servico.py` | `views_global.py` | `ordens_servico` | ADAPTAR | |
| Vínculos documentais | `documento_vinculos.py`, `documento_presenters.py`, `documento_selectors.py` | `views_global.py`, testes | vários `selectors`/`presenters` | ADAPTAR | |
| Snapshots | `documento_snapshots.py` | Resgate, consistência | `documentos` ou `eventos` | ADAPTAR | |
| Resgate órfãos | `evento_resgate.py` | `views.py` | `eventos` | REVER | Política de segurança ao auto-vincular. |
| Assinatura ofício | `oficio_assinatura.py`, `pdf_signature.py` | `views_assinatura.py` | `assinaturas` | ADAPTAR | Fluxo público + PDF. |
| Assinaturas genéricas PDF | `documentos/services/assinaturas.py` | Views em `documentos` (não listadas aqui) | `assinaturas` | ADAPTAR | PKCS#12 / validação. |
| Prestação sync + RT + dossiê | `prestacao_contas/services/*.py` | `prestacao_contas/views.py` | `prestacoes_contas` | ADAPTAR | |
| Diário de bordo XLSX/PDF | `diario_bordo/services.py` | `prestacao_contas/views.py`, `diario_bordo/views.py` | `diario_bordo` | ADAPTAR | Excel COM só Windows. |
| Google Drive | `integracoes/...`, `exportacao_google_drive.py` | `eventos/views.py` | `integracoes` | ADAPTAR | OAuth por usuário. |
| Máscaras | `core/utils/masks.py` | Várias views/forms | `core` ou `shared` | COPIAR | |
| Utilidades tempo/autocomplete | `eventos/utils.py` | `views*.py`, APIs | `eventos` / `cadastros` | ADAPTAR | |
| Valor por extenso | `utils/valor_extenso.py` | `views_global.py` | `shared` ou `documentos` | COPIAR | Função pequena. |
| Comandos importação cadastros | `cadastros/management/commands/*.py` | CLI | `cadastros` / ops | REVER | Não é request cycle. |

---

## Regras para migração de services

1. Não colocar regra pesada nas views novas.
2. Views novas apenas orquestram (HTTP, permissão, redirect, escolha de service).
3. **Selectors** encapsulam consultas e querysets reutilizáveis.
4. **Services** concentram regra funcional e efeitos colaterais transacionais.
5. **Presenters** montam DTOs para templates e JSON de tela.
6. Geração documental (DOCX/PDF/placeholders/conversão) permanece sob `documentos/services/` no novo projeto, chamada pelos domínios.
7. Regras de negócio devem ser **transportadas do legacy** (código e comentários), não reinventadas.
8. HTML/CSS legados não são o alvo final de migração estrutural.
9. Testes de integração pesados ficam para o fechamento de cada bloco funcional migrado.

---

## Próximos passos sugeridos

1. Congelar esta matriz e cruzar com `LEGACY_VIEWS_MAP.md` para cada fluxo (ofício → documentos → assinatura → prestação).
2. Priorizar extração do núcleo `documentos/` + `diarias` + `estimativa_local` (maior risco e maior reuso).
3. Decidir estratégia única de PDF (LibreOffice no servidor vs fila de conversão) antes de portar `renderer.py` e `diario_bordo/services.py`.
