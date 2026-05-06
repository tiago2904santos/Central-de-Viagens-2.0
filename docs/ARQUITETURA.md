# Arquitetura

## Visao geral

Central de Viagens 3 e um projeto Django por apps de dominio, com arquitetura document-centric e migracao controlada do legado.

A pasta `legacy/` existe apenas para consulta historica e nao pode ser dependencia de runtime.

O projeto novo pode consultar `legacy/` como referencia visual, mas nao pode importar ou depender tecnicamente de templates, CSS ou JS antigos.

## App cadastros

`cadastros` e o modulo de dados-base reutilizados, com CRUD publico para:

- `Unidade`
- `Cargo`
- `Combustivel`
- `Servidor`
- `Viatura`

e tela de **Configuracao do sistema** (`ConfiguracaoSistema` singleton + linhas `AssinaturaConfiguracao` por tipo de documento).

`Estado` e `Cidade` existem como **base geografica interna** (roteiros e FKs); nao fazem parte do hub publico de cadastros nem do submenu lateral nesta fase.

Regras estruturais aplicadas:

- nao existe cadastro de `Motorista`;
- `Servidor` nao possui matricula;
- `Servidor.nome` e unico e em maiusculo; CPF obrigatorio e validado; RG/telefone com regras de unicidade quando informados;
- `Servidor.cargo` referencia `Cargo` via `PROTECT` (nullable no model por compatibilidade; obrigatorio no form);
- `Cargo`/`Combustivel` podem ter `is_padrao` (um padrao ativo por vez);
- `Viatura` nao possui `marca` nem `unidade`;
- `Viatura.combustivel` referencia `Combustivel` via `PROTECT`;
- busca simples usa `q` nos selectors;
- exclusao e fisica e bloqueada quando houver vinculos;
- mascaras e normalizacoes centralizadas em `core/utils/masks.py`.

## App roteiros

`roteiros` guarda roteiros reutilizaveis e avulsos para deslocamentos. Nesta base inicial, o app possui:

- `Roteiro`: entidade principal, independente de Evento, Oficio, Plano de Trabalho, Ordem de Servico ou qualquer outro documento.
- `TrechoRoteiro`: trecho pertencente a um roteiro, removido em cascata quando o roteiro for excluido.

Origem e destino de `Roteiro` e `TrechoRoteiro` apontam para `cadastros.Cidade`; cada cidade pertence a um `Estado`. As relacoes com cidades usam `PROTECT`, porque uma cidade em uso nao deve ser removida.

O app segue a arquitetura ja validada em `cadastros`: views chamam selectors, presenters formatam dados para listagem, templates usam components globais e consultas nao ficam no template.

Padrao interno do app (**modulo referencia** para os demais):

- `views.py` apenas orquestra request/response e mensagens.
- `services/` concentra calculos legacy (`diarias`, estimativa, etc.) e `services/roteiro_editor.py` concentra persistencia e fluxo do editor avulso.
- `selectors.py` concentra consultas e querysets.
- `presenters.py` prepara dados de tela sem HTML.
- `templates/components/domain/` contem blocos de dominio reutilizaveis; ver `docs/COMPONENTES_DOMINIO.md` e `docs/ROTEIROS_ARQUITETURA.md`.

A interface publica em `/roteiros/` inclui listagem (busca `q`), criacao, edicao, detalhe, exclusao com confirmacao, wizard de trechos/destinos e endpoints de apoio (cidades, diarias, estimativa de trecho), sem alterar regras do legado ja portadas.

Regras transversais: sem `href="#"`, sem CSS/JS inline nos blocos de dominio, sem exibir "Atualizado em" como metadado de lista; JS de pagina em `static/js/` (ex.: `roteiros.js`) e tokens de dominio em `static/css/domain.css`.

## Padrao tecnico

Views orquestram `forms + selectors + services + presenters + messages`.
Templates usam apenas components globais. CSS/JS por pagina seguem proibidos.

## Configuracoes do sistema

A tela de configuracao segue o mesmo padrao arquitetural dos cadastros:

- view orquestra singleton, form, messages e redirect;
- `cadastros.services.salvar_configuracao_sistema()` persiste configuracao, resolve cidade sede e grava assinaturas por `update_or_create`;
- `cadastros.services.resolver_cidade_sede_por_endereco()` concentra a comparacao tolerante a acentos;
- `cadastros.selectors.build_configuracao_context()` prepara um contexto reutilizavel para documentos;
- API interna `/cadastros/api/cep/<cep>/` encapsula ViaCEP;
- JS da pagina fica em `static/js/pages/configuracoes.js`, enquanto mascaras globais permanecem em `static/js/components/masks.js`.

O app novo nao importa codigo do legacy em runtime; a tela apenas adapta as regras documentadas e auditadas do legacy.

## Navegacao lateral

A navegacao principal e declarada em `core/navigation.py` e suporta hierarquia. O grupo `Cadastros` organiza:

- `Servidores`
  - `Cargos`
- `Viaturas`
  - `Combustiveis`
- `Unidades`
- `Configuracoes`

O estado ativo/aberto e preparado antes da renderizacao e o comportamento de abrir/fechar fica em JS centralizado. `Motoristas` nao e cadastro independente e nao deve aparecer no menu lateral. Estados/Cidades **nao** aparecem no menu; permanecem como base interna e importacao conforme `docs/IMPORTACAO_BASE_GEOGRAFICA.md`.

## Autenticacao

Fluxo documentado em `docs/AUTENTICACAO.md`: login e logout em `/login/` e `/logout/` (`core:login`, `core:logout`), sessao padrao do Django, sem cadastro publico. Paginas internas sao protegidas por `LoginRequiredMiddleware`; usuarios sao criados pelo admin ate haver modulo proprio.
