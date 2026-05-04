# Arquitetura

## Visao geral

Central de Viagens 3 e um projeto Django organizado por apps de dominio, com uma arquitetura document-centric. O sistema deve permitir criar, editar, relacionar e gerar documentos de viagem sem transformar um evento em fluxo obrigatorio.

O projeto novo fica na raiz. A pasta `legacy/` existe apenas para consulta historica durante a migracao gradual.

## Regra sobre legacy

`legacy/` nao deve ser importado por nenhum modulo novo. Tambem nao deve ser usado como dependencia em settings, templates, static, URLs ou services. Qualquer regra aproveitada do sistema antigo deve ser entendida, redesenhada e migrada para o app correto.

## Apps

- `core`: dashboard, navegacao principal e helpers globais.
- `usuarios`: base futura para usuarios, perfis e permissoes.
- `cadastros`: dados-base reutilizaveis como servidores, motoristas, viaturas, cidades e unidades.
- `roteiros`: roteiros reutilizaveis, destinos, trechos e calculos futuros de distancia, tempo e diarias.
- `eventos`: agrupador opcional de documentos. Nao e o centro obrigatorio do fluxo.
- `documentos`: infraestrutura generica para registry, renderizacao, placeholders, validacao, downloads e templates de documentos.
- `oficios`: documento principal, fluxo proprio e vinculos opcionais com roteiro e evento.
- `termos`: termos de autorizacao, geracao por servidor e vinculo com oficios quando aplicavel.
- `justificativas`: CRUD proprio para justificativas e vinculos documentais.
- `planos_trabalho`: planos, etapas e calculos futuros de diarias.
- `ordens_servico`: ordens de servico.
- `prestacoes_contas`: fluxo futuro de despacho, RT, DB, comprovantes e resumo copiavel.
- `diario_bordo`: geracao futura baseada em modelo XLSX.
- `assinaturas`: assinatura eletronica, carimbo visual e validacao de hash.
- `integracoes.google_drive`: OAuth e persistencia futura de documentos no Google Drive.

## Separacao conceitual

Cadastros guardam dados reutilizaveis. Roteiros descrevem deslocamentos reaproveitaveis. Documentos centralizam geracao e validacao. Eventos agrupam quando houver ganho de organizacao, mas documentos tambem podem existir sem evento. Integracoes ficam isoladas para evitar acoplamento de dominio com APIs externas.

## Banco de desenvolvimento

O ambiente de desenvolvimento usa PostgreSQL local no Windows, configurado por `.env`. O settings `config.settings.dev` nao deve usar SQLite como fallback silencioso. SQLite fica restrito a `config.settings.test`, para testes automatizados.
