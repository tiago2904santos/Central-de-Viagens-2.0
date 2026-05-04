# Mapa de forms funcionais — legacy (Central de Viagens 2.0)

**Escopo:** somente documentação de auditoria; nenhuma alteração ao projeto novo.

**Raiz do código legado:** `legacy/central de viagens 2.0/`

**Inventário:** existem **quatro** arquivos `forms.py` (`cadastros`, `eventos`, `prestacao_contas`, `diario_bordo`). **Não há** `legacy/**/forms/*.py` nem `documentos/forms.py` nem `integracoes/**/forms.py` — validações nesses apps tendem a estar em views/services ou POST manual.

**Mixin comum:** `FormComErroInvalidMixin` (em `cadastros/forms.py` e `eventos/forms.py`, cópias quase idênticas) remove classes especiais de `<select>`, atributos de searchable-select, e marca `is-invalid` nos widgets após `full_clean`.

---

## Convenções de status

| Status | Uso |
|--------|-----|
| COPIAR | Regras estáveis; pouca dependência de modelo legado. |
| ADAPTAR | Depende de FK/models/views novos; mantém regra do legacy. |
| REESCREVER | Form monolítico ou mistura UI/backend demais; fatiar em form + service. |
| DESCARTAR | Órfão ou substituído por fluxo novo. |
| JÁ MIGRADO | Quando existir equivalente no projeto novo (verificar repo). |
| REVER | Uso incerto ou import morto na view. |

**Nomes novos (mapeamento):** Viajante → Servidor; Veículo → Viatura; CombustivelVeiculo → Combustível.

---

## Cadastros

**Arquivo:** `cadastros/forms.py`

| Classe | Model | Campos principais | Validação / normalização | Views legacy |
|--------|-------|---------------------|---------------------------|--------------|
| `CargoForm` | `Cargo` | `nome`, `is_padrao` | `clean_nome`: trim, upper, único | `cadastros/views/cargos.py` |
| `UnidadeLotacaoForm` | `UnidadeLotacao` | `nome` | Idem padrão único | `cadastros/views/unidades.py` |
| `ViajanteForm` | `Viajante` | nome, cargo, rg, sem_rg, cpf, telefone, unidade | Máscaras via attrs (`data-mask`); `clean_cpf` dígitos + dígitos verificadores; unicidade CPF/RG/tel; RG especial `RG_NAO_POSSUI_CANONICAL`; **cargo/unidade opcionais** com empty_label | `cadastros/views/viajantes.py` |
| `CombustivelVeiculoForm` | `CombustivelVeiculo` | `nome`, `is_padrao` | Nome único upper | `cadastros/views/veiculos.py` |
| `VeiculoForm` | `Veiculo` | placa, modelo, combustivel, tipo | `clean_placa`: Mercosul/antiga via regex; default tipo DESCARACTERIZADO; combustível padrão opcional | `cadastros/views/veiculos.py` |
| `ConfiguracaoSistemaForm` | `ConfiguracaoSistema` + extras | Model: divisão, unidade, sigla, sede, chefia, coord. adm PT, CEP, endereço, tel, email; **extra:** `assinatura_oficio`, `assinatura_justificativas`, `assinatura_planos_trabalho`, `assinatura_ordens_servico` (ModelChoice Viajante operacional) | CEP 8 dígitos; UF 2 letras; telefone 10/11 dígitos; upper em divisão/unidade/sigla; inicial AssinaturaConfig por tipo | `cadastros/views/configuracoes.py` |

**AssinaturaConfiguracao:** não há form dedicado — campos são **espelhados** em `ConfiguracaoSistemaForm` via `AssinaturaConfiguracao` (ordem=1 por tipo).

**Estado/Cidade:** não há CRUD público nestes `forms.py` (internos ao sistema).

**Destino provável:** `cadastros/forms.py` novo + eventual `core/forms.py` para mixin/`FormComErroInvalidMixin`.

**Status geral:** ADAPTAR (FK e nomes); trechos de unicidade e CPF **COPIAR** conceito.

---

## Eventos

**Arquivo:** `eventos/forms.py`

| Classe | Model | Observações |
|--------|-------|-------------|
| `EventoForm` | `Evento` | CRUD “completo” com estado/cidade principal/base; `clean` datas e cidade∈estado. **Uso atual:** fluxo guiado substitui edição livre — ver `RELATORIO_EVENTOS_UNIFICACAO.md`; classe **permanece no arquivo**. Status: **REVER** (pode estar só legado/tests). |
| `EventoEtapa1Form` | `Evento` | M2M `tipos_demanda`; `data_unica`; datas; descrição obrigatória se tipo “Outros”. Usado no fluxo guiado. **eventos/views.py** (`guiado_etapa_1`, `evento_guiado_*`). ADAPTAR. |
| `EventoFinalizacaoForm` | `EventoFinalizacao` | Somente observações. Views com etapa 6 / finalizar. ADAPTAR. |
| `TipoDemandaEventoForm` | `TipoDemandaEvento` | CRUD administração de tipos. **eventos/views.py**. ADAPTAR. |
| `CoordenadorOperacionalForm` | `CoordenadorOperacional` | Campos extras estado/cidade/cargo/lotação (FK) → persistidos como texto em `cargo`, `unidade`, `cidade` (“Nome/UF”). Validação nome único. **eventos/views.py**. ADAPTAR. |

**Participantes / Etapa 3:** `EventoEtapa3Form` (veículo, motorista, participantes finalizados, observações) existe em **forms.py** mas o fluxo atual da Etapa 3 foi trocado por hub de ofícios — form **não é usado** na view de etapa 3 (ver `RELATORIO_ETAPA3_OFICIOS_LEGADO.md`). Status: **REVER** (manter regra para possível wizard de ofício ou remover).

---

## Roteiros

| Classe | Model | Campos Meta | Validação |
|--------|-------|---------------|-----------|
| `RoteiroEventoForm` | `RoteiroEvento` | `origem_estado`, `origem_cidade`, `saida_dt`, `retorno_saida_dt`, `observacoes` | Cidade sede ∈ estado; observações upper strip; datetime-local input_formats |

**Uso:** `eventos/views.py` — roteiro vinculado ao evento (`guiado_etapa_2`, edição) e fluxos **roteiro avulso** (`roteiro_avulso_*`): **mesma classe de form**, templates diferentes (`guiado/roteiro_form.html` vs `global/roteiro_avulso_form.html`). Destinos/trechos são tratados **no template + POST/service**, não como fields deste ModelForm.

**Diferença avulso vs evento:** apenas contexto (`tipo=TIPO_AVULSO` no model) e UI — reaproveitar validação de sede/datas; adaptar vínculo `evento` nulo.

**Destino provável:** `roteiros/forms.py`. Status: **ADAPTAR**.

---

## Ofícios

| Classe | Tipo | Função |
|--------|------|--------|
| `ModeloMotivoViagemForm` | ModelForm | CRUD textos motivo (apoio Step 1). **eventos/views.py**. |
| `OficioStep1Form` | Form | Protocolo (máscara, `normalize_protocolo`, 9 dígitos), data criação, modelo+motivo, custeio (`CUSTEIO_CHOICES`), instituição se custeio externo, viajantes hidden (≥1). **eventos/views.py** wizard. |
| `OficioStep2Form` | Form | Transporte atual: placa (`normalize_placa`), modelo, combustível, tipo viatura, porte armas; motorista via hidden + payload JS (`motorista_choices_payload`); carona → número/ano/protocolo obrigatórios; integração `buscar_veiculo_finalizado_por_placa`, `mapear_tipo_viatura_para_oficio`. **Principal.** ADAPTAR / REESCREVER (fat UI vs validação). |
| `LegacyOficioStep2Form` | Form | Variante antiga com `motorista_carona` boolean explícito; **não usado pela view ativa** (docs internos). **DESCARTAR** ou REVER. |

**Passos 3–4 wizard:** não há classes `OficioStep3Form`/`Step4Form` — trechos, retorno e documentos são **views + POST manual + templates** (`eventos/views.py`). Mapear nas views (`LEGACY_VIEWS_MAP.md`).

**Justificativa do ofício:** ver seção Justificativas (`OficioJustificativaForm`).

---

## Termos

| Classe | Model | Destaque |
|--------|-------|----------|
| `TermoAutorizacaoForm` | `TermoAutorizacao` + extras | `oficios` M2M (UI força **apenas 1** na `clean`); hidden `viajantes_ids`, `veiculo_id`; datas; integra `build_contexto_termo_from_evento`, preview; `save_terms()` gera árvore root + derivados por servidor / modo rápido. **views_global.py**. |
| `TermoAutorizacaoEdicaoForm` | Idem | Edição sem fluxo de `save_terms`; `save` seta `oficio` único e `oficios`. **views_global.py**. |

Status: **ADAPTAR** + services já mapeados em `LEGACY_SERVICES_MAP.md` (`contexto_evento`, `termo_autorizacao.py`).

---

## Justificativas

| Classe | Model | Destaque |
|--------|-------|----------|
| `ModeloJustificativaForm` | `ModeloJustificativa` | CRUD textos. |
| `OficioJustificativaForm` | Form | Depende de `oficio_justificativa_schema_available()`; se schema ausente, queryset vazio; prefill modelo/texto via **services** `get_oficio_justificativa*`. **eventos/views.py**. |
| `JustificativaForm` | `Justificativa` | Ofício opcional; unicidade 1 justificativa por ofício na criação; modelo preenche texto se vazio. **views_global.py**. |

Status: **ADAPTAR** (schema JSON pode mudar armazenamento).

---

## Plano de Trabalho

| Classe | Uso real | Notas |
|--------|----------|-------|
| `SolicitantePlanoTrabalhoForm` | CRUD gerenciador | `save`: único `is_padrao`. Views **eventos/views.py**. |
| `HorarioAtendimentoPlanoTrabalhoForm` | CRUD | Regex horário `HH:MM até HH:MM`; único padrão. |
| `AtividadePlanoTrabalhoForm` | CRUD catálogo PT | Código `[A-Z0-9_]`; meta e recurso obrigatórios. |
| `PlanoTrabalhoForm` | **Form único principal** (tela global PT) | Campos hidden `destinos_payload`, `roteiro_json`, `coordenadores_ids`; M2M `oficios_relacionados`; integra **`reconcile_plano_step2_state`**, **`calculate_periodized_diarias`**, **`get_atividades_catalogo`**, **`build_metas_formatada`**, parsing JSON destinos, validação evento/ofício/roteiro coerentes, número automático. **views_global.py**. Status: **REESCREVER** em fatias (form + services já previstos). |
| `PlanoTrabalhoStep1Form` … `Step4Form` | ModelForm mínimos | Apenas `Meta.fields` — **sem uso em views** localizado (só **tests**). Status: **REVER/DESCARTAR** como API pública. |

**FormSet:** `PlanoTrabalhoEfetivoFormSet` definido em **views_global.py** (`inlineformset_factory` para `EfetivoPlanoTrabalhoDocumento`), não em `forms.py`.

---

## Ordem de Serviço

| Classe | Model | Destaque |
|--------|-------|----------|
| `OrdemServicoForm` | `OrdemServico` | `destinos_payload` hidden; prefill via `build_contexto_ordem_servico_from_evento`; filtros queryset ofício por evento; `clean` monta `destinos_json`; `save` status FINALIZADO vs RASCUNHO conforme campos; sincroniza viajantes/responsáveis texto. **views_global.py**. ADAPTAR. |

---

## Prestação de Contas

**Arquivo:** `prestacao_contas/forms.py`

| Classe | Model | Views (`prestacao_contas/views.py`) |
|--------|-------|-------------------------------------|
| `PrestacaoContaCreateForm` | `PrestacaoConta` | Criação (ofício, servidor, descrição). |
| `PrestacaoInformacoesForm` | idem | Descrição + despacho PDF; `clean_despacho_pdf` só PDF. |
| `PrestacaoComprovanteForm` | idem | Upload comprovante — **import na view, uso não encontrado** (possível código morto). **REVER**. |
| `PrestacaoDBForm` | — (JSON `dados_db`) | `save` grava dict em `prestacao.dados_db`; **sem uso em views** grep. **REVER**. |
| `RelatorioTecnicoPrestacaoForm` | `RelatorioTecnicoPrestacao` | Checkbox atividades do **service** `get_atividades_catalogo`; modelos `TextoPadraoDocumento` por categoria; `clean` mescla modelos em texto, regras translado/passagem BRL. |
| `TextoPadraoDocumentoForm` | `TextoPadraoDocumento` | Administração textos padrão RT. |

Integração **services:** RT usa `eventos.services.documentos.renderer` (geração) — ver `LEGACY_SERVICES_MAP.md`.

---

## Diário de Bordo

**Arquivo:** `diario_bordo/forms.py`

| Classe | Model | Views |
|--------|-------|-------|
| `DiarioIdentificacaoForm` | `DiarioBordo` | Ofício, e-protocolo, divisão, unidade cabeçalho, roteiro, prestação, status. |
| `DiarioVeiculoResponsavelForm` | idem | Veículo, tipo, combustível, placas, motorista, responsável. |
| `DiarioTrechoForm` | `DiarioBordoTrecho` | Datas/horas/km/origens; `clean` ordem temporal e km; `DiarioTrechoFormSet` inline (min 1). |
| `DiarioAssinadoForm` | `DiarioBordo` | PDF assinado. |

**diario_bordo/views.py** usa identificação, veículo, assinado; formset de trechos onde aplicável.

---

## Assinaturas

Não há `forms.py` em `eventos/views_assinatura.py` nem em `documentos/views.py` — fluxo de pedido/confirmção usa **POST manual** e validação em **services** (`oficio_assinatura`, `documentos/services/assinaturas.py`). Para migração: forms explícitos opcionais (ex.: token/CPF) podem ser extraídos das views.

---

## Integrações / Documentos

Sem formulários Django dedicados no legacy analisado.

---

## Cruzamento com mapas anteriores

| Relação | Detalhe |
|---------|---------|
| **LEGACY_MODELS_MAP.md** | Forms acoplados a `Oficio`, `PlanoTrabalho`, `RoteiroEvento`, `TermoAutorizacao`, `PrestacaoConta`, etc. — migração de model deve preceder ou alinhar choices/querysets. |
| **LEGACY_VIEWS_MAP.md** | Views grandes (`eventos/views.py`, `views_global.py`) instanciam os forms críticos; trechos do ofício sem Form dedicado. |
| **LEGACY_SERVICES_MAP.md** | `PlanoTrabalhoForm.clean` chama `diarias.calculate_periodized_diarias`, `plano_trabalho_step2.reconcile_*`, `plano_trabalho_domain.*`; `OficioJustificativaForm` chama services de justificativa/schema; RT chama renderer; termos chamam `contexto_evento` / `ensure_termo_generico_evento`. **Form valida + service executa** já é o padrão nos pontos críticos. |

**Forms que devem existir antes do fluxo:** cadastro operacional (`Viajante`, `Veiculo`, `ConfiguracaoSistema`) → depois wizard ofício e PT/OS globais.

---

## Matriz resumo

| Form legacy | Arquivo legacy | Model | View que usa | App novo | Form novo sugerido | Status | Observação |
|-------------|----------------|-------|--------------|----------|----------------------|--------|------------|
| CargoForm | cadastros/forms.py | Cargo | cargos.py | cadastros | CargoForm | ADAPTAR | Nome único upper |
| UnidadeLotacaoForm | cadastros/forms.py | UnidadeLotacao | unidades.py | cadastros | UnidadeLotacaoForm | ADAPTAR | |
| ViajanteForm | cadastros/forms.py | Viajante | viajantes.py | cadastros | ServidorForm | ADAPTAR | CPF/RG/tel; máscaras JS |
| CombustivelVeiculoForm | cadastros/forms.py | CombustivelVeiculo | veiculos.py | cadastros | CombustivelForm | ADAPTAR | |
| VeiculoForm | cadastros/forms.py | Veiculo | veiculos.py | cadastros | ViaturaForm | ADAPTAR | Placa Mercosul |
| ConfiguracaoSistemaForm | cadastros/forms.py | ConfiguracaoSistema | configuracoes.py | cadastros / core | ConfiguracaoSistemaForm | ADAPTAR | Assinaturas por tipo |
| EventoForm | eventos/forms.py | Evento | — | eventos | EventoForm | REVER | Fluxo guiado preferido |
| EventoEtapa1Form | eventos/forms.py | Evento | views.py guiado | eventos | EventoEtapa1Form | ADAPTAR | Tipos demanda |
| EventoFinalizacaoForm | eventos/forms.py | EventoFinalizacao | views.py | eventos | idem | ADAPTAR | |
| TipoDemandaEventoForm | eventos/forms.py | TipoDemandaEvento | views.py | eventos | idem | ADAPTAR | |
| CoordenadorOperacionalForm | eventos/forms.py | CoordenadorOperacional | views.py | eventos | idem | ADAPTAR | FK→texto |
| SolicitantePlanoTrabalhoForm | eventos/forms.py | SolicitantePlanoTrabalho | views.py | planos_trabalho | idem | ADAPTAR | |
| HorarioAtendimentoPlanoTrabalhoForm | eventos/forms.py | HorarioAtendimentoPlanoTrabalho | views.py | planos_trabalho | idem | ADAPTAR | Regex horário |
| AtividadePlanoTrabalhoForm | eventos/forms.py | AtividadePlanoTrabalho | views.py | planos_trabalho / catálogo | idem | ADAPTAR | |
| PlanoTrabalhoForm | eventos/forms.py | PlanoTrabalho | views_global.py | planos_trabalho | PT + steps/services | REESCREVER | Diárias + step2 + destinos JSON |
| PlanoTrabalhoStep1–4Form | eventos/forms.py | PlanoTrabalho | tests apenas | — | — | REVER | Shell vazio |
| OrdemServicoForm | eventos/forms.py | OrdemServico | views_global.py | ordens_servico | idem | ADAPTAR | destinos_json |
| TermoAutorizacaoForm | eventos/forms.py | TermoAutorizacao | views_global.py | termos | idem | ADAPTAR | save_terms complexo |
| TermoAutorizacaoEdicaoForm | eventos/forms.py | TermoAutorizacao | views_global.py | termos | idem | ADAPTAR | |
| ModeloMotivoViagemForm | eventos/forms.py | ModeloMotivoViagem | views.py | oficios / cadastros motivo | idem | ADAPTAR | |
| ModeloJustificativaForm | eventos/forms.py | ModeloJustificativa | views.py | justificativas | idem | ADAPTAR | |
| OficioJustificativaForm | eventos/forms.py | — | views.py | justificativas | idem | ADAPTAR | Schema opcional |
| JustificativaForm | eventos/forms.py | Justificativa | views_global.py | justificativas | idem | ADAPTAR | |
| RoteiroEventoForm | eventos/forms.py | RoteiroEvento | views.py | roteiros | idem | ADAPTAR | Evento + avulso |
| EventoEtapa3Form | eventos/forms.py | — | — | eventos | — | REVER | Substituído por hub ofícios |
| OficioStep1Form | eventos/forms.py | — | views.py | oficios | OficioStep1Form | ADAPTAR | Protocolo/custeio |
| LegacyOficioStep2Form | eventos/forms.py | — | — | — | — | DESCARTAR | Legado |
| OficioStep2Form | eventos/forms.py | — | views.py | oficios | OficioStep2Form | ADAPTAR | Motorista/carona |
| PrestacaoContaCreateForm | prestacao_contas/forms.py | PrestacaoConta | views.py | prestacoes_contas | idem | ADAPTAR | |
| PrestacaoInformacoesForm | prestacao_contas/forms.py | PrestacaoConta | views.py | prestacoes_contas | idem | ADAPTAR | PDF despacho |
| PrestacaoComprovanteForm | prestacao_contas/forms.py | PrestacaoConta | — | — | — | REVER | Import morto? |
| PrestacaoDBForm | prestacao_contas/forms.py | — | — | — | — | REVER | save JSON não referenciado |
| RelatorioTecnicoPrestacaoForm | prestacao_contas/forms.py | RelatorioTecnicoPrestacao | views.py | prestacoes_contas | idem | ADAPTAR | Catálogo atividades |
| TextoPadraoDocumentoForm | prestacao_contas/forms.py | TextoPadraoDocumento | views.py | prestacoes_contas | idem | ADAPTAR | |
| DiarioIdentificacaoForm | diario_bordo/forms.py | DiarioBordo | diario_bordo/views.py | diario_bordo | idem | ADAPTAR | |
| DiarioVeiculoResponsavelForm | diario_bordo/forms.py | DiarioBordo | views.py | diario_bordo | idem | ADAPTAR | |
| DiarioTrechoForm (+ FormSet) | diario_bordo/forms.py | DiarioBordoTrecho | views.py | diario_bordo | idem | ADAPTAR | Validação km/data |
| DiarioAssinadoForm | diario_bordo/forms.py | DiarioBordo | views.py | diario_bordo | idem | ADAPTAR | PDF |

---

## Regras para migração de forms

1. Form novo não deve inventar validação que já exista no legacy.
2. Validação funcional deve ser copiada/adaptada do legacy quando lá existir (`clean*`, `clean`, unicidade, formatos).
3. Máscaras visuais ficam em JS/componentes; attrs `data-mask` do legacy são referência, não destino final obrigatório.
4. Normalização final (CPF só dígitos, protocolo 9 dígitos, placa normalizada) permanece no **backend**.
5. Widgets devem usar classes do design system novo (equivalente a `form-control` / tokens globais).
6. Selects grandes (ofício, evento, viajantes) devem evoluir para pesquisável/autocomplete conforme já indicado no legacy (`data-searchable-*` removido no mixin).
7. Form Django não deve embutir HTML de página; apenas widgets.
8. Form Django não deve embutir CSS; apenas classes semânticas/tokens.
9. Regra complexa: form valida invariantes; **service** executa efeitos (geração, snapshots, PDF) — alinhado a `LEGACY_SERVICES_MAP.md`.
10. Testes pesados no fim do bloco funcional migrado.

---

## Próximo passo recomendado

Priorizar especificação dos forms **OficioStep1/2**, **PlanoTrabalhoForm** (decomposição) e **OrdemServicoForm** em paralelo aos models de `Oficio` / `PlanoTrabalho` / `OrdemServico`; limpar forms/views órfãos (`PrestacaoComprovanteForm`/`PrestacaoDBForm`, `PlanoTrabalhoStep*`, `EventoEtapa3Form`) com decisão explícita de remoção ou reuso.
