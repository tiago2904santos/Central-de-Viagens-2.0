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

## Cadastros

O app `cadastros` e a base de dados comum do sistema. Seus registros devem ser reutilizados por Oficios, Roteiros, Planos de Trabalho, Ordens de Servico, Prestacoes de Contas e Diario de Bordo.

- `Unidade`: representa uma unidade administrativa. Possui nome, sigla e status ativo/inativo.
- `Cidade`: representa uma cidade de referencia para destinos e documentos. Usa `PR` como UF padrao nesta base inicial.
- `Servidor`: representa uma pessoa vinculada a documentos de viagem. Possui nome, matricula, cargo, CPF textual e unidade opcional.
- `Motorista`: representa um servidor habilitado para conduzir veiculos. Aponta para `Servidor` e guarda CNH e categoria.
- `Viatura`: representa um veiculo da frota. Possui placa unica, modelo, marca, tipo, combustivel e unidade opcional.

Os models desta etapa sao uma base inicial e podem evoluir em etapas futuras. Views devem consultar dados por selectors, formatar exibicao por presenters e renderizar templates com components. CSS e JS por pagina continuam proibidos.
