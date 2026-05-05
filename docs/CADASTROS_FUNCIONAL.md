# Cadastros funcionais (alinhamento ao legacy)

Este documento registra o que foi copiado, adaptado ou descartado ao alinhar o modulo `cadastros` ao comportamento util do legado (`legacy/central de viagens 2.0`), mantendo as decisoes do projeto 3.0.

Fontes de verdade usadas: `docs/LEGACY_*_MAP.md` e arquivos em `legacy/.../cadastros` e `legacy/.../core/utils/masks.py`.

## Mascaras e normalizacao

| Legacy | Novo |
|--------|------|
| `masks.py` (CPF, RG, telefone, CEP, placa, protocolo) | `core/utils/masks.py` + exibicao via propriedades/helpers nos models |

- **Regra**: dados persistidos sem caracteres de mascara; formularios e listagens formatam na saida; edicao reabre com mascara via `data-mask` e `initial` nos forms.
- **JS**: `static/js/components/masks.js` (sem JS inline).

## Cargo e Combustivel

| Aspecto | Decisao |
|---------|---------|
| Nome unico, maiusculo | Mantido (form + save). |
| `is_padrao` (legacy) | **Implementado**: um unico cargo/combustivel padrao por vez (`save` desmarca os demais). Util para default em `ServidorForm` / `ViaturaForm`. |
| Ativo/inativo | **Descartado** (decisao 3.0). |

## Servidor vs Viajante (legacy)

| Legacy (Viajante) | Novo (Servidor) |
|-------------------|-----------------|
| Nome maiusculo, unicidade | Igual. |
| CPF/RG com formatacao | CPF obrigatorio + digitos verificadores; RG opcional ou `sem_rg`. |
| Telefone | **Copiado** como opcional com unicidade quando preenchido. |
| Status RASCUNHO/FINALIZADO | **Nao implementado** nesta fase (CRUD completo via form; sem rascunho). |
| `esta_completo` | **Adaptado** como metodo utilitario; nao bloqueia operacoes basicas. |
| Matricula | **Nao existe** (decisao 3.0). |

## Viatura vs Veiculo (legacy)

| Legacy | Novo |
|--------|------|
| Placa normalizada, Mercosul/antiga | Validacao regex `AAA1234` / `AAA1A23`; persistencia sem hifen. |
| Modelo maiusculo | `ViaturaForm.clean_modelo` normaliza. |
| Combustivel FK + tipo | Mantido; default de combustivel padrao no form quando existir. |
| `placa_formatada`, `_placa_valida`, `esta_completo` | Propriedades/helpers no model. |
| Status RASCUNHO/FINALIZADO | **Nao implementado** (mesma decisao que Servidor). |
| Marca / unidade na viatura | **Nao existe** (decisao 3.0). |

## Unidade vs UnidadeLotacao

- Nome e sigla em maiusculo; CRUD publico; exclusao fisica com bloqueio por vinculo.
- **Nao** foi convertida em “base interna” oculta: continua cadastro de dominio.

## Configuracao do sistema

- **Implementado**: modelo `ConfiguracaoSistema` (singleton `get_singleton()`), campos institucionais (orgao, endereco, chefia, prazo justificativa, cidade sede padrao, numeracao PT auxiliar quando aplicavel).
- **Local**: `cadastros/models.py` (coerente com demais cadastros e FKs para `Cidade` / `Servidor`).
- A tela foi refinada como central institucional: identificacao, sede/chefia, endereco dos documentos, contato, prazos/numeracao e assinaturas documentais.
- CEP e telefone sao normalizados no backend e mascarados via `static/js/components/masks.js`.
- A consulta de CEP usa a API interna autenticada `/cadastros/api/cep/<cep>/`, que chama ViaCEP com timeout curto.
- `cidade_sede_padrao` e resolvida automaticamente por UF + cidade do endereco, com comparacao tolerante a acentos.
- Detalhes em `docs/CONFIGURACOES_SISTEMA.md`.

## AssinaturaConfiguracao

- **Implementado** como base de configuracao: por tipo de documento (oficio, justificativa, plano de trabalho, ordem de servico, termo), referencia `Servidor`, ordem por tipo e `ativo` tecnico.
- A UI permite Ofício com assinatura 1 e 2; os demais tipos usam ordem 1.
- **Nao** e assinatura digital; apenas preparacao para geracao de documentos futura.

## Forms, services, views

- Forms atualizados: `CargoForm`, `CombustivelForm`, `ServidorForm`, `ViaturaForm`, `UnidadeForm`, `ConfiguracaoSistemaForm`.
- Padrao mantido: views orquestram; selectors consultam; services persistem; presenters formatam listagens.

## UI e card-toggles (alinhamento ao legacy)

- Checkboxes booleanos em Cadastros usam o componente global **card-toggle** (`templates/components/forms/card_toggle.html`, `static/css/forms.css`, `static/js/components/card-toggle.js`), inspirado no botao **Data unica** do Plano de Trabalho no legacy (`visually-hidden` + card clicavel + estado `LIGADA` / `DESLIGADA`), sem copiar CSS legado.
- Checkbox cru do navegador nao deve aparecer na interface final; BooleanFields futuros renderizados manualmente devem usar o card-toggle.
- **Servidor**: ao lado de Cargo e Unidade ha botoes para listas de gerenciamento (`input_with_action`); **Nao possui RG** trava o campo RG (JS centralizado); telefone com mascara via `data-mask="telefone"`.
- **Cargo / Combustivel**: acoes POST **Definir como padrao** na lista (`cadastros:cargo_set_default`, `cadastros:combustivel_set_default`); badge **Padrao** quando `is_padrao`; services `definir_cargo_padrao` / `definir_combustivel_padrao`.
- **Viatura**: titulo de lista `MODELO — PLACA`; meta com combustivel, tipo e motoristas; relacionamento **motoristas** e M2M com `Servidor` (sem cadastro Motorista).

## Menu e hub

- Estados/Cidades e Motoristas **nao** aparecem no hub publico nem no submenu lateral.
- Entrada **Configuracao** no menu e hub.

## Proximas revisoes (REVER)

- Fluxos que exijam **rascunho/finalizacao** explicita em Servidor/Viatura (se documentos exigirem bloqueio por incompleto).
- Campos institucionais adicionais na configuracao se novos modelos de documento precisarem.
