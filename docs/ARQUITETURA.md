# Arquitetura

## Visao geral

Central de Viagens 3 e um projeto Django por apps de dominio, com arquitetura document-centric e migracao controlada do legado.

A pasta `legacy/` existe apenas para consulta historica e nao pode ser dependencia de runtime.

O projeto novo pode consultar `legacy/` como referencia visual, mas nao pode importar ou depender tecnicamente de templates, CSS ou JS antigos.

## App cadastros

`cadastros` e o primeiro modulo fechado da arquitetura nova, com CRUD fisico para:

- `Unidade`
- `Cidade`
- `Cargo`
- `Combustivel`
- `Servidor`
- `Viatura`

Regras estruturais aplicadas:

- nao existe cadastro de `Motorista`;
- `Servidor` nao possui matricula;
- `Servidor.nome` e unico e em maiusculo;
- `Servidor.cargo` referencia `Cargo` via `PROTECT`;
- `Viatura` nao possui `marca` nem `unidade`;
- `Viatura.combustivel` referencia `Combustivel` via `PROTECT`;
- busca simples usa `q` nos selectors;
- exclusao e fisica e bloqueada quando houver vinculos.

## App roteiros

`roteiros` guarda roteiros reutilizaveis e avulsos para deslocamentos. Nesta base inicial, o app possui:

- `Roteiro`: entidade principal, independente de Evento, Oficio, Plano de Trabalho, Ordem de Servico ou qualquer outro documento.
- `TrechoRoteiro`: trecho pertencente a um roteiro, removido em cascata quando o roteiro for excluido.

Origem e destino de `Roteiro` e `TrechoRoteiro` apontam para `cadastros.Cidade`; cada cidade pertence a um `Estado`. As relacoes com cidades usam `PROTECT`, porque uma cidade em uso nao deve ser removida.

O app segue a arquitetura ja validada em `cadastros`: views chamam selectors, presenters formatam dados para listagem, templates usam components globais e consultas nao ficam no template.

## Padrao tecnico

Views orquestram `forms + selectors + services + presenters + messages`.
Templates usam apenas components globais. CSS/JS por pagina seguem proibidos.

## Navegacao lateral

A navegacao principal e declarada em `core/navigation.py` e suporta hierarquia. O grupo `Cadastros` organiza:

- `Servidores`
  - `Cargos`
- `Viaturas`
  - `Combustiveis`
- `Unidades`
- `Cidades`

O estado ativo/aberto e preparado antes da renderizacao e o comportamento de abrir/fechar fica em JS centralizado. `Motoristas` nao e cadastro independente e nao deve aparecer no menu lateral. `Cidades` permanece como cadastro de banco, com importacao CSV prevista para etapa futura.
