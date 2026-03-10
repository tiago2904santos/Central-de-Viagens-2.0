# Relatório: Especificação extraída do legacy e plano de implementação

Referência: projeto antigo em `/legacy` (Automacao-Central-de-Viagens).  
Objetivo: usar o legacy **apenas como referência** para implementar no projeto novo de forma limpa, **sem migrar/copiar arquivos**.

---

## PARTE 1 — Especificação extraída do legacy

### 1.1 Entidades (models e campos relevantes)

| Entidade | Campos / observações |
|----------|----------------------|
| **Viajante** | nome, rg, cpf, cargo, telefone, **is_ascom** (se True, não exige Termo no pacote). Validação: RG 9/10 dígitos, CPF 11, telefone 10/11. |
| **Cargo** | nome (unique), ordem, ativo, is_coordenador. Ordenação por ordem/nome. |
| **Efetivo** | OneToOne Cargo, quantidade. Usado em Plano de Trabalho (efetivo por cargo). |
| **Veiculo** | placa (unique), modelo, combustivel, tipo_viatura (CARACTERIZADA/DESCARACTERIZADA). |
| **Estado** | sigla (unique), nome. Legacy sem codigo_ibge; novo já tem codigo_ibge (IBGE). |
| **Cidade** | nome, estado (FK). Legacy sem codigo_ibge; novo já tem codigo_ibge. |
| **ConfiguracaoOficio** | Singleton (pk=1): nome_chefia, cargo_chefia, orgao_origem, orgao_destino_padrao, rodape. |
| **OficioConfig** | Singleton: unidade_nome, origem_nome, endereço (cep, logradouro, bairro, cidade, uf, numero, complemento, telefone, email), **assinante** (FK Viajante), **assinante_justificativa** (FK Viajante), **sede_cidade_default** (FK Cidade). |
| **ModeloJustificativa** | codigo (unique), label, texto, ordem, ativo, **padrao** (um só padrão no gerador). Para justificativas quando prazo < 10 dias. |
| **OficioCounter / PlanoTrabalhoCounter / OrdemServicoCounter** | ano (unique), last_numero/last_num. Numeração sequencial por ano. |
| **Evento** | titulo, tipo_demanda (PCPR_NA_COMUNIDADE, OPERACAO_POLICIAL, PARANA_EM_ACAO, OUTRO), cidade_base (FK Cidade), data_inicio, data_fim, **tem_convite_ou_oficio_evento** (se False, exige PT ou OS). Ordenação -created_at. |
| **DocumentoEventoArquivo** | evento (FK), **tipo** (OFICIO_ASSINADO, SOLICITACAO_FORMAL_ASSINADA, PLANO_ASSINADO, ORDEM_ASSINADO, JUSTIFICATIVA_ASSINADA, TERMO_ASSINADO), oficio (FK, null), viajante (FK, null para termo), arquivo (FileField), original_name, mime_type, **is_active** (um ativo por evento+tipo+oficio/viajante). |
| **EventoProtocoloArquivo** | evento (FK), pdf_compilado (FileField), compilado_em, compilado_por_id, hash_sha256, **versao**. |
| **AcaoInstitucional** | titulo, descricao. Ligada 1:1 a Oficio (ensure_acao) e a PlanoTrabalho / OrdemServico. |
| **TermoAutorizacao** | acao (FK, opcional), oficio (FK), evento (FK), **viajante** (FK). data_inicio, data_fim, data_unica, destinos (JSON). **dispensado**, dispensa_motivo. motorista_nome, veiculo_*, combustivel. Unique (oficio, viajante) quando não dispensado. |
| **Oficio** | acao (FK), evento (FK), **roteiro** (FK Roteiro, opcional). numero, ano, protocolo (9 dígitos). status (DRAFT/FINAL). assunto, assunto_tipo (AUTORIZACAO/CONVALIDACAO). tipo_destino (INTERIOR/CAPITAL/BRASILIA). estado_sede, cidade_sede, estado_destino, cidade_destino. Campos de roteiro (ida/volta: saida/chegada local e datahora). retorno_*, quantidade_diarias, valor_*. tipo_viatura, tipo_custeio, custeio_texto_override, custos, nome_instituicao_custeio. **justificativa_modelo**, **justificativa_texto** (prazo < 10 dias; preenchido desbloqueia geração). Motorista: placa, modelo, combustivel, motorista, motorista_oficio/numero/ano, motorista_protocolo, motorista_carona, motorista_viajante, carona_oficio_referencia. viajantes (M2M), veiculo (FK). Unique (ano, numero). |
| **Roteiro** | evento (FK). nome, descricao. estado_sede, cidade_sede. uf_origem, cidade_origem, uf_destino, cidade_destino. retorno_* (saida/chegada cidade, data, hora). tempo_viagem, distancia_km, tipo_deslocamento (INTERIOR/CAPITAL/OUTRO). criado_automaticamente, ativo. |
| **TrechoRoteiro** | roteiro (FK), ordem. origem/destino estado e cidade (FK + uf/cidade texto). saida/chegada data e hora, retorno_*. tempo_viagem_minutos, distancia_km, modal (veiculo_proprio, onibus, aviao, etc.), observacao. |
| **OficioRoteiro** | Vinculo M2M-like: oficio (FK), roteiro (FK). unique_together (oficio, roteiro). |
| **Trecho** | Ofício “antigo”: oficio (FK), ordem, origem/destino estado e cidade (FK), saida/chegada data e hora. Usado nos trechos do ofício (não no Roteiro reutilizável). |
| **PlanoTrabalho** | OneToOne Oficio, OneToOne AcaoInstitucional (opcional). numero, ano. sigla_unidade, programa_projeto, solicitantes_json, destino, destinos_json, solicitante, contexto_solicitacao. local, data_inicio, data_fim, horario_*, efetivo_json, efetivo_formatado, unidade_movel, estrutura_apoio, efetivo_por_dia, quantidade_servidores, composicao_diarias, valor_*, coordenador (plano/municipal). Unique (ano, numero). |
| **PlanoTrabalhoMeta / Atividade / Recurso / LocalAtuacao** | FK PlanoTrabalho, ordem, descricao (ou data+local). |
| **CoordenadorMunicipal** | nome, cargo, cidade, ativo. |
| **OrdemServico** | OneToOne Oficio, OneToOne AcaoInstitucional. numero, ano, referencia, determinante_*, finalidade, texto_override. Unique (ano, numero). |

---

### 1.2 Fluxos existentes no legacy

1. **Evento (pacote) e wizard guiado (6 etapas)**  
   - Etapa 1: Cadastro do evento (título, tipo, datas, cidade_base, tem_convite_ou_oficio_evento).  
   - Etapa 2: Roteiro (criar/editar roteiro do evento com trechos).  
   - Etapa 3: Ofícios do evento (listar/criar ofícios vinculados ao evento).  
   - Etapa 4: Plano de trabalho / Ordem de serviço (obrigatório só se **não** tem convite/ofício; senão “dispensado”).  
   - Etapa 5: Termos de autorização (por ofício e por viajante **não-ASCOM**; gerar em lote; dispensar com motivo).  
   - Etapa 6: Finalização (uploads dos assinados + checklist + gerar PDF compilado + export ZIP).  
   - Painel do evento: progresso por etapa e “próximo passo”.

2. **Ofício**  
   - Criado no contexto do evento (etapa 3) ou standalone.  
   - Wizard do ofício (etapas 1–4): dados gerais, trechos (ida/volta), viajantes/veículo/motorista, finalização.  
   - Numeração automática por ano (OficioCounter).  
   - Justificativa (prazo < 10 dias): bloqueia “finalizar” até texto preenchido; modelo de justificativa selecionável.  
   - Vinculação a Roteiro (OficioRoteiro) e cópia de dados do roteiro para o ofício.  
   - Geração DOCX/PDF (documentos), Termo por (ofício, viajante), Plano/OS.

3. **Roteiros**  
   - Roteiro reutilizável com TrechoRoteiro (ordem, origem/destino, datas/horas, modal, distância).  
   - Pode ser vinculado a um evento.  
   - Ofício pode usar um roteiro (vinculação); alteração no ofício pode clonar roteiro (criado_automaticamente).

4. **Trechos (do ofício)**  
   - Trecho (model) ligado ao Ofício: origem/destino estado e cidade, saida/chegada.  
   - Usado para calcular destino automático (GAB/SESP), diárias e para termos.

5. **Termos de autorização**  
   - Um termo por (ofício, viajante) quando viajante **não é ASCOM**.  
   - Pode ser **dispensado** (dispensado=True, dispensa_motivo).  
   - Geração em lote na etapa 5; edição contextual (evento+ofício+viajante).  
   - Upload do assinado no pacote do evento (DocumentoEventoArquivo TERMO_ASSINADO).

6. **Justificativa (prazo < 10 dias)**  
   - Regra: antecedência = (data_início_viagem − data_criação_ofício) em dias; se < 10, **exige** justificativa.  
   - Ofício tem justificativa_modelo (código) e justificativa_texto.  
   - ModeloJustificativa: textos pré-prontos; um pode ser “padrao”.  
   - Gerador: seleção de modelo + texto; assinante_justificativa em OficioConfig.  
   - Upload do assinado no pacote (JUSTIFICATIVA_ASSINADA por ofício).

7. **Plano de trabalho (PT) e Ordem de serviço (OS)**  
   - PT: wizard multi-etapa (dados, metas/atividades/recursos, locais, etc.); numeração por ano.  
   - OS: 1:1 com ofício; numeração por ano.  
   - Exigência: apenas quando evento **não** tem convite/ofício (tem_convite_ou_oficio_evento=False).  
   - Upload: um PLANO_ASSINADO ou um ORDEM_ASSINADO no pacote (conforme o caso).

8. **Uploads e compilação**  
   - Upload por tipo: OFICIO_ASSINADO (por ofício), SOLICITACAO_FORMAL_ASSINADA (se tem convite), PLANO_ASSINADO, ORDEM_ASSINADO, JUSTIFICATIVA_ASSINADA (por ofício que exige), TERMO_ASSINADO (por ofício+viajante).  
   - Apenas um arquivo **ativo** por (evento, tipo, oficio?, viajante?) conta no checklist.  
   - **Pronto para compilar**: todos os obrigatórios com upload (e termos dispensados contam como ok).  
   - Compilação: merge dos PDFs na ordem do protocolo → EventoProtocoloArquivo (versão).  
   - Export ZIP: compilado + arquivos separados + pasta Prestação de Contas (conforme evento_export_zip).

9. **Simulação de diárias**  
   - Cálculo de diárias (legacy: diarias.py, telas simulacao_diarias). Não detalhado aqui; manter como referência para etapa futura.

---

### 1.3 Regras de negócio importantes

- **Justificativa < 10 dias:** Antecedência = data_início_viagem (menor saida_data dos trechos do ofício) − data de criação do ofício. Se < 10 dias, o ofício **exige** justificativa (texto preenchido) para poder finalizar; o upload da justificativa assinada é no pacote. O prazo (10) pode ser configurável (novo projeto já tem `ConfiguracaoSistema.prazo_justificativa_dias`).
- **Termo por servidor:** Um termo por (ofício, viajante). Apenas viajantes **não-ASCOM** exigem termo; ASCOM não exige. Unique (oficio, viajante) quando não dispensado.
- **Dispensas:** Termo pode ser dispensado (campo dispensado + dispensa_motivo); dispensado conta como “ok” no checklist e não exige upload.
- **PT/OS obrigatório:** Apenas quando o evento **não** tem convite/ofício solicitante (tem_convite_ou_oficio_evento=False). Um PT ou uma OS por evento (vinculados a ofícios do evento) satisfaz a etapa 4.
- **Numeração:** Ofício, Plano e Ordem com numeração sequencial por ano (counters por ano).
- **Protocolo:** 9 dígitos; motorista_protocolo idem. Validação no clean do Ofício.
- **Destino automático do ofício:** Calculado pelos trechos: se algum destino fora do PR → SESP; senão GAB.
- **Checklist “pronto para protocolar”:** Roteiro preenchido + (Plano ou Ordem se exigido) + todos os ofícios com justificativa ok (quando exigido) + todos os termos (ou dispensados) por viajante não-ASCOM.
- **Pronto para compilar (PDF):** Todos os uploads obrigatórios presentes (ofícios assinados, solicitação formal ou plano/ordem, justificativas onde exige, termos não dispensados).

---

### 1.4 Ordem dos documentos e checklist final

**Ordem dos PDFs no protocolo compilado (legacy: `_ordenar_pdfs_para_protocolo`):**

1. Por **ofício** (ordem id): (a) Ofício assinado; (b) Justificativa assinada desse ofício (se existir).  
2. **Solicitação formal** assinada (se evento tem convite/ofício).  
3. **Plano de trabalho** assinado **ou** **Ordem de serviço** assinada (um só).  
4. **Termos** assinados (por nome do servidor / ordem do status).

**Checklist final (Etapa 6) — blocos na UI:**

1. **Ofícios assinados** — um upload por ofício do evento.  
2. **Solicitação formal ou PT/OS** — se tem convite: 1 upload solicitação formal; se não tem: 1 upload de Plano ou de Ordem.  
3. **Justificativas** — um upload por ofício que **exige** justificativa (antecedência < 10 dias).  
4. **Termos** — um upload por (ofício, viajante) não-ASCOM não dispensado.

**Pronto para compilar:** todos os itens obrigatórios dos blocos acima com upload. **Export ZIP:** após compilação; inclui PDF compilado + arquivos separados + estrutura Prestação de Contas.

---

## PARTE 2 — Comparação com o projeto novo

### 2.1 O que já existe e está alinhado

- **Estados e Cidades:** Base fixa com codigo_ibge; importação CSV idempotente; API cidades por estado. Novo não expõe CRUD de Estado/Cidade no menu (apenas admin); legacy tinha CRUD. **Alinhado.**  
- **Viajante:** nome, cargo, rg, cpf, telefone, email, unidade_lotacao, **is_ascom**, ativo. Novo não tem validação RG/CPF/telefone igual ao legacy; dá para acrescentar depois. **Alinhado em estrutura.**  
- **Veículo:** placa, modelo, combustivel, ativo; novo tem prefixo. Legacy tem tipo_viatura; novo não. **Parcialmente alinhado.**  
- **ConfiguracaoSistema (novo):** cidade_sede_padrao, **prazo_justificativa_dias** (default 10), nome_orgao, sigla_orgao. Legacy tem ConfiguracaoOficio + OficioConfig (chefia, órgão, assinantes, sede). **Novo tem prazo justificativa; falta config de ofício/assinantes.**  
- **Evento (novo):** titulo, tipo_demanda, descricao, data_inicio, data_fim, estado_principal, cidade_principal, cidade_base, tem_convite_ou_oficio_evento, status. **Alinhado em campos principais;** novo tem status e estado_principal/cidade_principal que o legacy não tinha.  
- **Navegação e layout:** Sidebar configurável, dashboard, login, placeholders para módulos. **Alinhado.**  
- **Autenticação e proteção de rotas:** Login obrigatório, redirect. **Alinhado.**

### 2.2 O que existe mas está incompleto

- **Evento:** CRUD e listagem ok; **falta** vínculo com Roteiros, Ofícios, Documentos e fluxo guiado (wizard 6 etapas).  
- **ConfiguracaoSistema:** Tem cidade_sede e prazo_justificativa; **falta** configurações de ofício (chefia, órgão, assinante padrão, assinante justificativa, sede padrão) equivalentes ao OficioConfig/ConfiguracaoOficio.  
- **Cadastros:** Viajante sem validação RG/CPF/telefone; Veículo sem tipo_viatura; **não existe** Cargo/Efetivo nem CoordenadorMunicipal nem ModeloJustificativa.

### 2.3 O que falta

- **Roteiro e TrechoRoteiro:** Model e CRUD; vínculo com Evento; uso no Ofício.  
- **Ofício:** Model completo (campos do legacy); numeração por ano; wizard ou fluxo por etapas; vínculo Evento + Roteiro; trechos do ofício (Trecho).  
- **AcaoInstitucional:** Conceito 1:1 com Ofício e com PT/OS (ou equivalente no novo).  
- **TermoAutorizacao:** Model; regra por (ofício, viajante) não-ASCOM; dispensa; geração em lote e contextual.  
- **PlanoTrabalho e OrdemServico:** Models; numeração; wizard PT; vínculo Ofício/Ação; exigência condicionada a tem_convite_ou_oficio_evento.  
- **Justificativa:** ModeloJustificativa (cadastro); regra “antecedência < prazo_justificativa_dias”; justificativa_texto/modelo no Ofício; gerador e bloqueio de finalização.  
- **DocumentoEventoArquivo e EventoProtocoloArquivo:** Upload por tipo; is_active; compilação PDF na ordem correta; versão.  
- **Fluxo guiado (wizard) do evento:** 6 etapas + painel de progresso + “próximo passo”.  
- **Compilação e export:** Serviço de compilação PDF (ordem definida); export ZIP (compilado + separados + Prestação de Contas).  
- **Simulação de diárias:** Cálculo e tela (manter referência no legacy).  
- **Configurações de ofício:** Equivalente a ConfiguracaoOficio + OficioConfig (chefia, órgão, assinantes, sede).

---

## PARTE 3 — Saída obrigatória

### A) Regras do domínio (bullet points)

- Evento é a unidade central do pacote (agrupa roteiro, ofícios, PT/OS, termos, justificativas).  
- Um evento tem título, tipo_demanda, datas, cidade_base e **tem_convite_ou_oficio_evento**.  
- Se **tem_convite_ou_oficio_evento = False**, o evento exige pelo menos um Plano de Trabalho ou uma Ordem de Serviço (vinculados a ofícios do evento).  
- Roteiro pode ser vinculado ao evento; ofícios podem usar roteiro e trechos (origem/destino, datas/horas).  
- Ofício tem numeração única (numero, ano) por ano; protocolo 9 dígitos.  
- **Justificativa:** Se antecedência (data início viagem − data criação ofício) < N dias (N configurável, ex.: 10), o ofício exige texto de justificativa para poder ser finalizado; modelo de justificativa opcional.  
- **Termo de autorização:** Um termo por (ofício, viajante). Apenas viajantes **não-ASCOM** exigem termo. Termo pode ser **dispensado** (com motivo); dispensado não exige geração nem upload.  
- **Checklist “pronto para protocolar”:** Roteiro preenchido + (PT ou OS se exigido) + ofícios com justificativa ok quando exigido + todos os termos (gerados ou dispensados) para não-ASCOM.  
- **Pronto para compilar:** Todos os uploads obrigatórios do pacote (ofícios assinados, solicitação formal ou PT/OS, justificativas onde exige, termos não dispensados).  
- **Ordem do protocolo compilado:** Por ofício (ofício assinado + justificativa desse ofício) → Solicitação formal (se tem convite) → Plano ou Ordem → Termos (ordenados).  
- Destino do ofício (GAB/SESP) pode ser calculado pelos trechos (destino fora do PR → SESP).  
- Numeração de Ofício, Plano e Ordem: sequencial por ano (counters).

---

### B) Blueprint do fluxo linear

```
Evento (cadastro)
    → Roteiro(s) (trechos: origem/destino, datas, modal)
        → Ofícios (vinculados ao evento; podem usar roteiro; trechos do ofício; viajantes; veículo/motorista)
            → [Se não tem convite] Plano de Trabalho OU Ordem de Serviço (1 por evento)
            → Justificativa (por ofício, se antecedência < N dias): texto + modelo
            → Termos (por ofício × viajante não-ASCOM; ou dispensa)
    → Uploads (assinados): ofício, solicitação formal ou PT/OS, justificativas, termos
    → Compilação PDF (ordem fixa do protocolo)
    → Export ZIP (compilado + separados + Prestação de Contas)
```

---

### C) Plano de implementação (8–12 etapas)

| # | Objetivo | Telas/rotas | Models a criar/alterar | Serviços a criar | Critérios de aceite |
|---|----------|-------------|------------------------|------------------|----------------------|
| **1** | Completar base do Evento e preparar vínculos | Evento: lista, cadastrar, editar, detalhe (já existem). Opcional: link “Abrir fluxo guiado” no detalhe. | Evento: garantir FK cidade_base e tem_convite_ou_oficio_evento alinhados ao legacy. | Nenhum novo. | Evento estável; pronto para ligar Roteiro e Ofício. |
| **2** | Roteiro e TrechoRoteiro | Lista/cadastrar/editar roteiro; trechos (ordem, origem/destino, datas/horas, modal, distância). Opcional: vínculo “pertence ao evento” na lista. | Criar Roteiro (evento FK, nome, sede, origem/destino, retorno, tempo_viagem, tipo_deslocamento, ativo). Criar TrechoRoteiro (roteiro FK, ordem, origem/destino estado/cidade, datas/horas, modal, distancia_km, observacao). | Serviço para gerar nome do roteiro a partir dos trechos (comportamento observado no legacy). | CRUD roteiro com trechos; ordenação; validação data_fim ≥ data_inicio por trecho. |
| **3** | Ofício (model e numeração) | Lista de ofícios (filtro por evento); cadastrar/editar ofício (dados gerais: evento, roteiro opcional, numero/ano, protocolo, status, destino, sede/destino, assunto). | Criar Oficio (evento, roteiro, numero, ano, protocolo, status, assunto, tipo_destino, estado_sede/cidade_sede, estado_destino/cidade_destino, campos de roteiro ida/volta, retorno, diárias, custeio, motorista, justificativa_modelo/texto, viajantes M2M, veiculo). Criar OficioCounter (ano, last_numero). | Serviço de reserva de número por ano (comportamento observado no legacy). Validação protocolo 9 dígitos. | Ofício criado com número único no ano; listagem por evento; edição de dados gerais. |
| **4** | Trechos do ofício e destino | Na edição do ofício: trechos (ordem, origem/destino, saida/chegada). | Criar Trecho (oficio FK, ordem, origem/destino estado/cidade, saida/chegada data e hora). | Serviço para calcular destino automático (GAB/SESP) a partir dos trechos (comportamento observado no legacy). | Trechos do ofício salvos; destino calculado; exibição na listagem/detalhe. |
| **5** | Justificativa (prazo < N dias) | Config: prazo em dias (já existe). Cadastro ModeloJustificativa. No ofício: campo justificativa (modelo + texto); bloqueio de “finalizar” se exige e não preenchido. Gerador de justificativa (página ou aba). | Criar ModeloJustificativa (codigo, label, texto, ordem, ativo, padrao). Oficio já tem justificativa_modelo e justificativa_texto. Config: assinante_justificativa (FK Viajante) se necessário. | Serviço “exige_justificativa(oficio)”: antecedência = data_início_viagem − created_at; comparar com ConfiguracaoSistema.prazo_justificativa_dias. Serviço “justificativa_preenchida(oficio)”. | Antecedência < N → exige texto; finalizar bloqueado até preencher; modelos listados no gerador. |
| **6** | Plano de Trabalho e Ordem de Serviço | Lista PT/OS; criar PT (wizard ou formulário) vinculado a ofício; criar OS vinculada a ofício. Etapa “PT/OS” no fluxo do evento: exibir só se evento não tem convite; links “Criar PT” / “Criar OS”. | Criar AcaoInstitucional (titulo, descricao). Criar PlanoTrabalho (oficio OneToOne, acao OneToOne, numero, ano, campos do legacy: sigla_unidade, destino, datas, efetivo, valores, coordenador, etc.). Criar PlanoTrabalhoMeta/Atividade/Recurso/LocalAtuacao se necessário. Criar OrdemServico (oficio OneToOne, acao OneToOne, numero, ano, referencia, determinante, finalidade). Counters por ano. | Serviço get_plano(oficio) / get_ordem(oficio). Numeração PT/OS por ano (comportamento observado no legacy). | PT e OS criados e vinculados ao ofício; numeração única por ano; etapa 4 do evento satisfeita quando existe PT ou OS. |
| **7** | Termos de autorização | Lista termos (filtro evento/ofício). Gerar termo (ofício + viajante). Edição contextual (evento, ofício, viajante). Dispensar termo (motivo). Geração em lote na “etapa 5” do evento. | Criar TermoAutorizacao (evento, oficio, viajante, data_inicio/fim, data_unica, destinos JSON, dispensado, dispensa_motivo, motorista, veiculo_*, combustivel). UniqueConstraint (oficio, viajante) quando não dispensado. | Serviço para listar “termos necessários” por evento (por ofício × viajante não-ASCOM); serviço “gerar em lote” (criar termo para cada par faltante com prefill). | Termos criados por (ofício, viajante); dispensa com motivo; etapa 5 do evento com “gerar lote” e lista. |
| **8** | Configurações de ofício e documentos | Tela de configuração: chefia, órgão, assinante padrão, assinante justificativa, cidade sede padrão (ou estender ConfiguracaoSistema). | Estender ConfiguracaoSistema ou criar OficioConfig singleton (nome_chefia, cargo_chefia, orgao_*, assinante FK, assinante_justificativa FK, sede_cidade_default). | Nenhum. | Configurações salvas e usadas na geração de ofício/justificativa. |
| **9** | Uploads do pacote (assinados) | Tela “Pacote do evento” ou “Etapa 6”: checklist em blocos (ofícios, solicitação/PT-OS, justificativas, termos). Upload por tipo (ofício, solicitação, plano, ordem, justificativa por ofício, termo por ofício+viajante). Remover/desativar arquivo. | Criar DocumentoEventoArquivo (evento, tipo enum, oficio null, viajante null, arquivo, original_name, mime_type, is_active, uploaded_at). | Serviço get_status_assinados_evento(evento) (comportamento observado no legacy). Serviço is_evento_pronto_para_compilar(evento). Serviço listar_pendencias_compilacao(evento). | Checklist exibido; upload por item; apenas um ativo por (evento, tipo, oficio?, viajante?); “pronto para compilar” quando todos obrigatórios ok. |
| **10** | Compilação PDF e export ZIP | Botão “Gerar PDF do protocolo” (habilitado só se pronto para compilar). Download do compilado. Botão “Exportar ZIP” (compilado + pastas/arquivos separados + Prestação de Contas). | Criar EventoProtocoloArquivo (evento, pdf_compilado, compilado_em, compilado_por_id, versao). | Serviço _ordenar_pdfs_para_protocolo(evento) (ordem: ofícios+justificativas → solicitação → plano/ordem → termos). Serviço compilar_pdf_protocolo(evento) (merge PDFs, salvar nova versão). Serviço build_evento_zip(evento) (ZIP com compilado + arquivos + estrutura). | PDF compilado na ordem correta; download; ZIP contém compilado e estrutura esperada. |
| **11** | Fluxo guiado (wizard) do evento | Painel do evento: 6 etapas com status (ok/pendente/não necessário) e link “Próximo passo”. Rotas: evento/<id>/guiado/painel, etapa-1 a etapa-6. Redirecionamento “novo evento” → etapa 1. | Nenhum model novo. Usar Evento, Roteiro, Oficio, Termo, DocumentoEventoArquivo, etc. | Serviço build_evento_guiado_progresso(evento) (comportamento observado no legacy: etapa1 título; etapa2 roteiros; etapa3 ofícios; etapa4 PT/OS se não tem convite; etapa5 termos; etapa6 uploads). | Painel acessível; etapas com links; “próximo passo” coerente; redirecionamento pós-criação para etapa 1. |
| **12** | Simulação de diárias e ajustes finais | Tela de simulação de diárias (cálculo com base em datas/valor). Ajustes de permissões, listagens e relatórios conforme necessidade. | Nenhum obrigatório. Possível DiariaSimulacao ou apenas cálculo em memória. | Serviço de cálculo de diárias com base no comportamento observado no legacy (diarias.py). | Simulação exibida; valores coerentes; integração opcional com ofício/evento. |

---

### D) Riscos e decisões técnicas (sem migração)

- **Risco:** Legacy muito acoplado (views gigantes, sessão para wizard). **Decisão:** No novo, implementar serviços enxutos (evento_guiado, evento_assinados, evento_compilacao, justificativa_helpers, documentos_manager) e views que apenas orquestram; evitar estado de wizard em sessão onde for possível (usar URLs e FKs).  
- **Risco:** Múltiplos singletons (ConfiguracaoOficio, OficioConfig). **Decisão:** Unificar em ConfiguracaoSistema onde fizer sentido (ex.: prazo_justificativa já está); adicionar campos ou um único “OficioConfig” para chefia, órgão, assinantes, sede.  
- **Risco:** Geração DOCX/PDF dependente de templates e bibliotecas (python-docx, etc.). **Decisão:** Implementar geração de documentos em etapas dedicadas; manter templates e placeholders inspirados no legacy, mas reescrever código de geração de forma modular.  
- **Risco:** Ordem de compilação e regras de “pronto para compilar” divergirem do legacy. **Decisão:** Documentar ordem e regras neste relatório e replicar nos serviços do novo (evento_compilacao, evento_assinados) sem copiar arquivos.  
- **Risco:** Numeração (ofício, PT, OS) concorrente. **Decisão:** Usar select_for_update em transação ao reservar número (comportamento observado no legacy).  
- **Risco:** Upload de arquivos (tamanho, tipo, vírus). **Decisão:** Limites de tamanho e tipos permitidos (ex.: PDF, DOCX, imagens); armazenamento em MEDIA; sem migração de arquivos do legacy.  
- **Risco:** Performance em eventos com muitos ofícios/termos. **Decisão:** Prefetch_related/select_related nos serviços de checklist e compilação; paginação na listagem onde fizer sentido.

---

*Documento gerado com base na análise do código em `/legacy`. Nenhum arquivo do legacy foi migrado para o projeto novo.*
