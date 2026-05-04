# Regras de Negocio

Este documento registra apenas as regras conceituais da base inicial. A migracao funcional sera feita em etapas futuras.

- Oficio e o documento principal do sistema.
- Documentos podem ser criados de forma avulsa quando o fluxo permitir.
- Evento e opcional e funciona como agrupador, nao como fluxo obrigatorio.
- Roteiro e reutilizavel e pode ser vinculado a documentos quando fizer sentido.
- Termo, justificativa, plano de trabalho, ordem de servico, prestacao de contas e diario de bordo devem ter CRUD proprio.
- Documentos podem se vincular entre si quando houver relacao real de negocio.
- Geracao DOCX/PDF deve ser tratada pelo app `documentos`.
- Integracoes externas, como Google Drive, devem ficar isoladas em `integracoes/`.
