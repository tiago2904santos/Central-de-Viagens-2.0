# Roteiros Arquitetura

## Auditoria antes da refatoracao

- View com regra funcional acoplada ao fluxo de step3 (validacao e persistencia).
- Consulta direta de cidades em endpoint de API fora de selector.
- Template de formulario com composicao misturada entre blocos de dominio e parciais de pagina.
- CSS extenso e especifico de Roteiros sem camada de dominio reutilizavel explicita.
- Componentes de dominio inexistentes em `templates/components/domain/`.

## Contrato de arquitetura

- Roteiro e avulso e reutilizavel; nao depende de Evento nem de Oficio.
- Trecho pertence a um roteiro, com ordem, origem e destino.
- Destinos, trechos, retorno e calculadora devem ser blocos de dominio reutilizaveis.
- Views ficam magras: orquestram form/selectors/services/presenters.
- Sem `href="#"`, sem CSS inline, sem JS inline, sem exibir "Atualizado em".

## Decisoes de refatoracao

- Extraida orquestracao de fluxo de criacao/edicao para `roteiros/services.py`.
- Centralizada consulta de cidades em `roteiros/selectors.py`.
- Mantida regra funcional existente via reutilizacao de `roteiro_logic`.
- Criada camada de componentes de dominio em `templates/components/domain/`.
