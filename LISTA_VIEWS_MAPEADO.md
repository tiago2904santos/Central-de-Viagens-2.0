# Mapeamento Completo de List Views - Central de Viagens 2.0

## Resumo Executivo

Este documento mapeia todas as list views (vistas que renderizam listas) do sistema Django, seus padrões de URL, arquivos de visualização e templates correspondentes.

**Total de List Views Mapeadas: 21**

---

## 1. EVENTOS (Core Entity)

### 1.1 Eventos (Lista Principal)
| Campo | Valor |
|-------|-------|
| **Entidade** | Evento |
| **View Class** | `evento_lista` (function-based view) |
| **Localização** | [eventos/views.py](eventos/views.py#L695) |
| **URL Pattern** | `eventos:lista` |
| **URL Absoluta** | `/eventos/` |
| **Template** | [eventos/evento_lista.html](templates/eventos/evento_lista.html) |
| **Modelo Django** | `Evento` |
| **Filtros** | q (título), status, tipo_id |
| **Ordenação** | data_inicio, updated_at, titulo, status |

---

## 2. DOCUMENTOS GLOBAIS (Événement-scoped)

### 2.1 Ofícios (Global/Avulsos + Evento-linked)
| Campo | Valor |
|-------|-------|
| **Entidade** | Oficio |
| **View Class** | `oficio_global_lista` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L1481) |
| **URL Pattern** | `eventos:oficios-global` |
| **URL Absoluta** | `/eventos/oficios/` |
| **Template** | [eventos/global/oficios_lista.html](templates/eventos/global/oficios_lista.html) |
| **Modelo Django** | `Oficio` |
| **Filtros** | q, status (RASCUNHO/FINALIZADO/ENVIADO), contexto (EVENTO/AVULSO), viagem_status (FUTURA/PASSADA/HOJE), justificativa (sim/não), termo (sim/não), data_range |
| **Ordenação** | updated_at, created_at, numero, evento, status |
| **Paginação** | Sim (customizada) |

### 2.2 Roteiros (Global)
| Campo | Valor |
|-------|-------|
| **Entidade** | RoteiroEvento |
| **View Class** | `roteiro_global_lista` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L1561) |
| **URL Pattern** | `eventos:roteiros-global` |
| **URL Absoluta** | `/eventos/roteiros/` |
| **Template** | [eventos/global/roteiros_lista.html](templates/eventos/global/roteiros_lista.html) |
| **Modelo Django** | `RoteiroEvento` |
| **Filtros** | q (evento/cidade/estado), status, tipo (EVENTO/AVULSO), evento_id |
| **Ordenação** | updated_at, evento__titulo, status, created_at |
| **Paginação** | Sim |

### 2.3 Planos de Trabalho (Global)
| Campo | Valor |
|-------|-------|
| **Entidade** | PlanoTrabalho |
| **View Class** | `planos_trabalho_global` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L1932) |
| **URL Pattern** | `eventos:documentos-planos-trabalho` |
| **URL Absoluta** | `/eventos/documentos/planos-trabalho/` |
| **Template** | [eventos/documentos/planos_trabalho_lista.html](templates/eventos/documentos/planos_trabalho_lista.html) |
| **Modelo Django** | `PlanoTrabalho` |
| **Filtros** | q (recursos/observações/evento/motivo), evento_id, oficio_id, status |
| **Ordenação** | updated_at, created_at, status, evento__titulo |
| **Paginação** | Sim |

### 2.4 Ordens de Serviço (Global)
| Campo | Valor |
|-------|-------|
| **Entidade** | OrdemServico |
| **View Class** | `ordens_servico_global` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L2136) |
| **URL Pattern** | `eventos:documentos-ordens-servico` |
| **URL Absoluta** | `/eventos/documentos/ordens-servico/` |
| **Template** | [eventos/documentos/ordens_servico_lista.html](templates/eventos/documentos/ordens_servico_lista.html) |
| **Modelo Django** | `OrdemServico` |
| **Filtros** | q, evento_id, oficio_id, status |
| **Ordenação** | updated_at, created_at, status, evento__titulo |
| **Paginação** | Sim |

### 2.5 Justificativas (Global)
| Campo | Valor |
|-------|-------|
| **Entidade** | Justificativa |
| **View Class** | `justificativas_global` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L2287) |
| **URL Pattern** | `eventos:documentos-justificativas` |
| **URL Absoluta** | `/eventos/documentos/justificativas/` |
| **Template** | [eventos/documentos/justificativas_lista.html](templates/eventos/documentos/justificativas_lista.html) |
| **Modelo Django** | `Justificativa` |
| **Filtros** | q (texto/protocolo/motivo/evento), oficio_id |
| **Ordenação** | updated_at, created_at, oficio__numero, modelo__nome |
| **Paginação** | Sim |

### 2.6 Termos de Autorização (Global)
| Campo | Valor |
|-------|-------|
| **Entidade** | EventoTermoParticipante |
| **View Class** | `termos_global` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L2431) |
| **URL Pattern** | `eventos:documentos-termos` |
| **URL Absoluta** | `/eventos/documentos/termos/` |
| **Template** | [eventos/global/termos_lista.html](templates/eventos/global/termos_lista.html) |
| **Modelo Django** | `EventoTermoParticipante` |
| **Filtros** | q (evento/viajante/cargo), evento_id, status |
| **Ordenação** | updated_at, evento__titulo, viajante__nome |
| **Paginação** | Sim |

---

## 3. CONFIGURAÇÕES DE EVENTOS

### 3.1 Tipos de Demanda (Evento)
| Campo | Valor |
|-------|-------|
| **Entidade** | TipoDemandaEvento |
| **View Class** | `tipos_demanda_lista` |
| **Localização** | [eventos/views.py](eventos/views.py#L1283) |
| **URL Pattern** | `eventos:tipos-demanda-lista` |
| **URL Absoluta** | `/eventos/tipos-demanda/` |
| **Template** | [eventos/tipos_demanda/lista.html](templates/eventos/tipos_demanda/lista.html) |
| **Modelo Django** | `TipoDemandaEvento` |
| **Filtros** | (Nenhum - listar tudo) |
| **Ordenação** | ordem, nome |
| **Paginação** | Não |

### 3.2 Modelos de Motivo (Ofício Step 1)
| Campo | Valor |
|-------|-------|
| **Entidade** | ModeloMotivoViagem |
| **View Class** | `modelos_motivo_lista` |
| **Localização** | [eventos/views.py](eventos/views.py#L1373) |
| **URL Pattern** | `eventos:modelos-motivo-lista` |
| **URL Absoluta** | `/eventos/modelos-motivo/` |
| **Template** | [eventos/modelos_motivo/lista.html](templates/eventos/modelos_motivo/lista.html) |
| **Modelo Django** | `ModeloMotivoViagem` |
| **Filtros** | (Nenhum) |
| **Ordenação** | nome |
| **Paginação** | Não |

### 3.3 Modelos de Justificativa (Ofício)
| Campo | Valor |
|-------|-------|
| **Entidade** | ModeloJustificativa |
| **View Class** | `modelos_justificativa_lista` |
| **Localização** | [eventos/views.py](eventos/views.py#L1478) |
| **URL Pattern** | `eventos:modelos-justificativa-lista` |
| **URL Absoluta** | `/eventos/modelos-justificativa/` |
| **Template** | [eventos/modelos_justificativa/lista.html](templates/eventos/modelos_justificativa/lista.html) |
| **Modelo Django** | `ModeloJustificativa` |
| **Filtros** | (Nenhum - apenas ativo=True) |
| **Ordenação** | nome |
| **Paginação** | Não |

### 3.4 Simulação de Diárias (Global)
| Campo | Valor |
|-------|-------|
| **Entidade** | N/A (Calculado em tempo real) |
| **View Class** | `simulacao_diarias_global` |
| **Localização** | [eventos/views_global.py](eventos/views_global.py#L2581) |
| **URL Pattern** | `eventos:simulacao-diarias` |
| **URL Absoluta** | `/eventos/simulacao-diarias/` |
| **Template** | (Renderiza template de formulário + resultado) |
| **Modelo Django** | N/A - Ferramenta de cálculo |
| **Filtros** | Entrada de formulário |
| **Notas** | View interativa com form POST para simular cálculos de diárias |

---

## 4. CADASTROS (Master Data)

### 4.1 Cargos
| Campo | Valor |
|-------|-------|
| **Entidade** | Cargo |
| **View Class** | `cargo_lista` |
| **Localização** | [cadastros/views/cargos.py](cadastros/views/cargos.py#L15) |
| **URL Pattern** | `cadastros:cargo-lista` |
| **URL Absoluta** | `/cadastros/cargos/` |
| **Template** | [cadastros/cargos/lista.html](templates/cadastros/cargos/lista.html) |
| **Modelo Django** | `Cargo` |
| **Filtros** | q (nome) |
| **Ordenação** | nome, is_padrao, id |
| **Paginação** | Não |

### 4.2 Viajantes
| Campo | Valor |
|-------|-------|
| **Entidade** | Viajante |
| **View Class** | `viajante_lista` |
| **Localização** | [cadastros/views/viajantes.py](cadastros/views/viajantes.py#L109) |
| **URL Pattern** | `cadastros:viajante-lista` |
| **URL Absoluta** | `/cadastros/viajantes/` |
| **Template** | [cadastros/viajantes/lista.html](templates/cadastros/viajantes/lista.html) |
| **Modelo Django** | `Viajante` |
| **Filtros** | q (nome/cargo/rg/cpf/telefone/unidade/status) |
| **Ordenação** | updated_at, nome, cargo__nome, status |
| **Paginação** | Não |
| **Notas** | Draft records (RASCUNHO) listados primeiro |

### 4.3 Unidades de Lotação
| Campo | Valor |
|-------|-------|
| **Entidade** | UnidadeLotacao |
| **View Class** | `unidade_lotacao_lista` |
| **Localização** | [cadastros/views/unidades.py](cadastros/views/unidades.py#L14) |
| **URL Pattern** | `cadastros:unidade-lotacao-lista` |
| **URL Absoluta** | `/cadastros/unidades-lotacao/` |
| **Template** | [cadastros/unidades/lista.html](templates/cadastros/unidades/lista.html) |
| **Modelo Django** | `UnidadeLotacao` |
| **Filtros** | q (nome) |
| **Ordenação** | nome, id |
| **Paginação** | Não |

### 4.4 Veículos
| Campo | Valor |
|-------|-------|
| **Entidade** | Veiculo |
| **View Class** | `veiculo_lista` |
| **Localização** | [cadastros/views/veiculos.py](cadastros/views/veiculos.py#L48) |
| **URL Pattern** | `cadastros:veiculo-lista` |
| **URL Absoluta** | `/cadastros/veiculos/` |
| **Template** | [cadastros/veiculos/lista.html](templates/cadastros/veiculos/lista.html) |
| **Modelo Django** | `Veiculo` |
| **Filtros** | q (placa/modelo/combustível/tipo/status) |
| **Ordenação** | updated_at, placa, modelo, status |
| **Paginação** | Não |
| **Notas** | Ordenado por status DESC (FINALIZADO antes de RASCUNHO) |

### 4.5 Combustíveis (Veículos)
| Campo | Valor |
|-------|-------|
| **Entidade** | CombustivelVeiculo |
| **View Class** | `combustivel_lista` |
| **Localização** | [cadastros/views/veiculos.py](cadastros/views/veiculos.py#L192) |
| **URL Pattern** | `cadastros:combustivel-lista` |
| **URL Absoluta** | `/cadastros/veiculos/combustiveis/` |
| **Template** | [cadastros/veiculos/combustiveis_lista.html](templates/cadastros/veiculos/combustiveis_lista.html) |
| **Modelo Django** | `CombustivelVeiculo` |
| **Filtros** | q (nome) |
| **Ordenação** | nome, is_padrao, id |
| **Paginação** | Não |

---

## 5. GUIADO (Workflow)

### 5.1 Roteiros - Etapa 2 (Lista)
| Campo | Valor |
|-------|-------|
| **Entidade** | RoteiroEvento (within Evento context) |
| **View Class** | `guiado_etapa_2_lista` |
| **Localização** | [eventos/views.py](eventos/views.py#L4943) |
| **URL Pattern** | `eventos:guiado-etapa-2` |
| **URL Absoluta** | `/eventos/<evento_id>/guiado/etapa-2/` |
| **Template** | [eventos/guiado/etapa_2_lista.html](templates/eventos/guiado/etapa_2_lista.html) |
| **Modelo Django** | `RoteiroEvento` |
| **Context** | Evento específico (evento_id) |
| **Notas** | Workflow step 2 - Listar roteiros do evento |

---

## 6. ESTRUTURA DE TEMPLATES

### Template Hierarchy
```
templates/
├── base.html (Base template)
├── cadastros/
│   ├── cargos/
│   │   └── lista.html ✓ Mapped
│   ├── unidades/
│   │   └── lista.html ✓ Mapped
│   ├── veiculos/
│   │   ├── lista.html ✓ Mapped
│   │   └── combustiveis_lista.html ✓ Mapped
│   └── viajantes/
│       └── lista.html ✓ Mapped
├── eventos/
│   ├── evento_lista.html ✓ Mapped
│   ├── tipos_demanda/
│   │   └── lista.html ✓ Mapped
│   ├── modelos_motivo/
│   │   └── lista.html ✓ Mapped
│   ├── modelos_justificativa/
│   │   └── lista.html ✓ Mapped
│   ├── documentos/
│   │   ├── planos_trabalho_lista.html ✓ Mapped
│   │   ├── ordens_servico_lista.html ✓ Mapped
│   │   ├── justificativas_lista.html ✓ Mapped
│   │   └── (termos - em global/) ✓ Mapped
│   ├── global/
│   │   ├── oficios_lista.html ✓ Mapped
│   │   ├── roteiros_lista.html ✓ Mapped
│   │   └── termos_lista.html ✓ Mapped
│   └── guiado/
│       └── etapa_2_lista.html ✓ Mapped
└── core/
    └── placeholder.html
```

---

## 7. RESUMO POR APP

### eventos/
- **List Views**: 10
  - `evento_lista` - Eventos
  - `tipos_demanda_lista` - Tipos de Demanda
  - `modelos_motivo_lista` - Modelos de Motivo
  - `modelos_justificativa_lista` - Modelos de Justificativa
  - `oficio_global_lista` - Ofícios (Global)
  - `roteiro_global_lista` - Roteiros (Global)
  - `planos_trabalho_global` - Planos de Trabalho
  - `ordens_servico_global` - Ordens de Serviço
  - `justificativas_global` - Justificativas
  - `termos_global` - Termos de Autorização

### cadastros/
- **List Views**: 5
  - `cargo_lista` - Cargos
  - `viajante_lista` - Viajantes
  - `unidade_lotacao_lista` - Unidades
  - `veiculo_lista` - Veículos
  - `combustivel_lista` - Combustíveis

### guiado/
- **List Views**: 1
  - `guiado_etapa_2_lista` - Roteiros (Workflow)

### documentos/
- **List Views**: 0 (Placeholder app)

### core/
- **List Views**: 0 (Auth only)

---

## 8. PADRÕES IDENTIFICADOS

### URLs Pattern
```
/app/                           → Lista principal
/app/tipo/                      → Lista por tipo (ex: documentos/termos)
/eventos/<evento_id>/guiado/etapa-N/  → Lista contextualizada
```

### Template Pattern
```
templates/app/entity/
├── lista.html           → Standard list template
├── _lista.html          → Partial/reusable snippet
└── form.html            → Form para CRUD
```

### Context Variables (Comuns)
- `object_list` - Lista de objetos
- `page_obj` - Objeto de paginação
- `pagination_query` - Query params para paginação
- `form_filter` - Filtros aplicados
- `order_by_choices` - Opções de ordenação
- `order_dir_choices` - Opções de direção (asc/desc)
- `filters` - Dict com filtros contextualizados

### Filtros Comuns
- `q` - Search por texto (contains)
- `status` - Estado (RASCUNHO, FINALIZADO, etc)
- `<entity>_id` - Filter por entidade relacionada
- `order_by` - Campo de ordenação
- `order_dir` - Direção (asc/desc)

### Paginação
- **Com paginação**: oficio_global_lista, roteiro_global_lista, planos_trabalho_global, ordens_servico_global, justificativas_global, termos_global
- **Sem paginação**: cargo_lista, viajante_lista, unidade_lotacao_lista, veiculo_lista, combustivel_lista, tipos_demanda_lista, modelos_motivo_lista, modelos_justificativa_lista

---

## 9. ENTIDADES PRINCIPAIS MAPEADAS

| Entidade | Views | Templates | App |
|----------|-------|-----------|-----|
| Evento | evento_lista | evento_lista.html | eventos |
| Oficio | oficio_global_lista | oficios_lista.html | eventos |
| RoteiroEvento | roteiro_global_lista, guiado_etapa_2_lista | roteiros_lista.html, etapa_2_lista.html | eventos |
| PlanoTrabalho | planos_trabalho_global | planos_trabalho_lista.html | eventos |
| OrdemServico | ordens_servico_global | ordens_servico_lista.html | eventos |
| Justificativa | justificativas_global | justificativas_lista.html | eventos |
| EventoTermoParticipante | termos_global | termos_lista.html | eventos |
| TipoDemandaEvento | tipos_demanda_lista | lista.html | eventos |
| ModeloMotivoViagem | modelos_motivo_lista | lista.html | eventos |
| ModeloJustificativa | modelos_justificativa_lista | lista.html | eventos |
| Cargo | cargo_lista | lista.html | cadastros |
| Viajante | viajante_lista | lista.html | cadastros |
| UnidadeLotacao | unidade_lotacao_lista | lista.html | cadastros |
| Veiculo | veiculo_lista | lista.html | cadastros |
| CombustivelVeiculo | combustivel_lista | combustiveis_lista.html | cadastros |

---

## 10. NOTAS ARQUITECTURAIS

### Padrão MVC
- **Model**: Django ORM models em `app/models.py`
- **View**: Function-based views em `app/views.py` e `app/views_global.py`
- **Template**: HTM em `templates/app/entity/lista.html`

### Autenticação
- Todas as list views protegidas com `@login_required` ou `login_required()` decorator

### Relacionamentos Típicos
```
Evento → [Oficios, Roteiros, Termos]
Oficio → [Justificativa, Termos, Trechos]
RoteiroEvento → [Destinos, Trechos, Oficios]
Viajante → [Cargo, UnidadeLotacao]
Veiculo → [CombustivelVeiculo, Motorista]
```

### Search & Filter
- Implementação custom em cada view
- Queries com `Q()` objects para OR conditions
- Select related / Prefetch related para otimização

---

## Última Atualização
- **Data**: 2026-03-23
- **Total Views**: 21
- **Total Templates**: 18
- **Total Entidades**: 15
