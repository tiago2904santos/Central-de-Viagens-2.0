# Regras de Negocio

## Cadastros

O app `cadastros` centraliza dados-base reutilizados por documentos e fluxos futuros.

Entidades ativas do modulo:

- `Unidade`: nome e sigla.
- `Estado`: cadastro de UF (nome, sigla 2 caracteres, `codigo_ibge` opcional). Ver seção **Base geográfica** e `docs/IMPORTACAO_BASE_GEOGRAFICA.md`.
- `Cidade`: pertence a um `Estado`; combinação **nome + estado** é única; `uf` espelha a sigla do estado; pode ser **capital**; `codigo_ibge` e coordenadas opcionais. Carga em lote: `docs/IMPORTACAO_BASE_GEOGRAFICA.md` (comando `importar_base_geografica`). O guia `docs/IMPORTACAO_CIDADES.md` permanece como referência do fluxo somente cidades, quando aplicável.
- `Cargo`: nome unico e em maiusculo; opcionalmente um registro pode ser marcado como **padrao** (`is_padrao`), garantindo um unico padrao por vez no banco.
- `Combustivel`: nome unico e em maiusculo; opcionalmente um registro pode ser **combustivel padrao** (`is_padrao`), garantindo um unico padrao por vez.
- `Servidor`: nome unico e em maiusculo; cargo obrigatorio no form; **CPF obrigatorio**, validado por digitos verificadores, armazenado so digitos; **RG opcional** ou marcacao **sem RG** (valor canonico interno, espelhando o legacy); **telefone opcional** (10 ou 11 digitos); unicidade condicional de CPF, RG (exceto “nao possui”) e telefone quando preenchidos; unidade opcional.
- `Viatura`: placa unica (AAA1234 ou AAA1A23), modelo obrigatorio normalizado em maiusculo, combustivel FK e tipo (`CARACTERIZADA`/`DESCARACTERIZADA`); placa persistida sem hifen e em maiusculo; **motoristas** opcionais via relacionamento N:N com `Servidor` (sem entidade Motorista).
- `ConfiguracaoSistema`: **singleton** institucional (orgao, cabecalho, endereco, contato, chefia, prazo de justificativa, cidade sede padrao, coordenador administrativo de PT e numeracao auxiliar de PT); usada para documentos futuros.
- `AssinaturaConfiguracao`: assinante preferencial por **tipo de documento** (oficio, justificativa, plano de trabalho, ordem de servico, termo), apontando para `Servidor`, com ordem por tipo e `ativo` tecnico; nao e assinatura digital, apenas configuracao.

## Regras obrigatorias

- Nao existe cadastro de `Motorista`; motoristas de viatura sao apenas `Servidor` selecionados no relacionamento da viatura.
- `Servidor` nao possui matricula.
- `Viatura` nao possui marca nem unidade.
- Cadastros nao possuem ativo/inativo.
- Exclusao e fisica.
- Quando existir vinculo relevante, exclusao deve ser bloqueada com mensagem clara.

Mensagem padrao de bloqueio:

```text
Não foi possível excluir este cadastro porque ele está vinculado a outros registros.
```

## Mascaras visuais

- CPF: `000.000.000-00` (armazenado em digitos; banco limpo).
- RG: `00.000.000-0` ou exibicao de “nao possui” quando `sem_rg` (armazenado normalizado / valor canonico).
- Telefone: `(00) 00000-0000` na tela; armazenado em digitos.
- CEP: `00000-000` na configuracao; armazenado em digitos.
- Placa: `AAA-1234` ou `AAA1A23` na tela; armazenada sem hifen e em maiusculo.

Logica central em `core/utils/masks.py`; JS em `static/js/components/masks.js` via `data-mask` (sem JS inline).

## Configuracoes e documentos

- A tela `/cadastros/configuracao/` e a fonte funcional de dados institucionais para geradores documentais futuros.
- `cidade_sede_padrao` nao deve ser digitada como texto livre: e resolvida por UF + cidade do endereco contra a base geografica interna.
- A consulta de CEP passa pela API interna autenticada `/cadastros/api/cep/<cep>/`; o front nao chama ViaCEP diretamente.
- Assinaturas configuradas sao apenas politica de assinantes por tipo documental. Assinatura digital, token publico, hash e validacao ficam para etapa futura.

## Cadastros publicos vs base interna

- **Estados e Cidades** permanecem como **base interna** (importacao/admin quando aplicavel); **nao** ha CRUD publico nem entradas no menu lateral para esses cadastros.

## Roteiros

`Roteiro` e uma entidade reutilizavel e avulsa. Ele pode existir sozinho e nao depende de Evento, Oficio, Plano de Trabalho nem Ordem de Servico.

Regras da base:

- roteiros poderao ser reutilizados futuramente por documentos e fluxos;
- Evento, quando existir, sera apenas agrupador opcional;
- nao existe ativo/inativo;
- exclusao futura sera fisica;
- se houver vinculo futuro com documentos, a exclusao devera ser bloqueada;
- origem e destino usam `Cidade` do app `cadastros`;
- cada `Cidade` pertence a um `Estado`;
- trechos pertencem ao roteiro;
- nao ha calculo de distancia, tempo ou diarias nesta etapa.

## Base geografica

- `Estado` e um cadastro proprio (nao e apenas texto solto de UF).
- Toda `Cidade` referencia um `Estado` (exclusao de estado com cidades vinculadas e bloqueada).
- Uma cidade pode ser marcada como `capital` (usado em regras futuras; capitais sao identificadas na importacao por mapa UF -> nome, com comparacao normalizada de texto).
- Roteiros usarao `Cidade` para origem e destino.
- Nao existe ativo/inativo para estado nem cidade.
