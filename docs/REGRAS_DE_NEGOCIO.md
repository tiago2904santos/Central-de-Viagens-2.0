# Regras de Negocio

## Cadastros

O app `cadastros` centraliza dados-base reutilizados por documentos e fluxos futuros.

Entidades ativas do modulo:

- `Unidade`: nome e sigla.
- `Estado`: cadastro de UF (nome, sigla 2 caracteres, `codigo_ibge` opcional). Ver seção **Base geográfica** e `docs/IMPORTACAO_BASE_GEOGRAFICA.md`.
- `Cidade`: pertence a um `Estado`; combinação **nome + estado** é única; `uf` espelha a sigla do estado; pode ser **capital**; `codigo_ibge` e coordenadas opcionais. Carga em lote: `docs/IMPORTACAO_BASE_GEOGRAFICA.md` (comando `importar_base_geografica`). O guia `docs/IMPORTACAO_CIDADES.md` permanece como referência do fluxo somente cidades, quando aplicável.
- `Cargo`: nome unico e em maiusculo.
- `Combustivel`: nome unico e em maiusculo.
- `Servidor`: nome unico e em maiusculo, cargo, CPF, RG opcional e unidade opcional.
- `Viatura`: placa unica (AAA1234 ou AAA1A23), modelo, combustivel e tipo (`CARACTERIZADA`/`DESCARACTERIZADA`).

## Regras obrigatorias

- Nao existe cadastro de `Motorista`.
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

- CPF: `000.000.000-00` (armazenado em digitos).
- RG: `00.000.000-0` (armazenado normalizado).
- Placa: `AAA-1234` ou `AAA1A23` na tela; armazenada sem hifen e em maiusculo.

## Roteiros

`Roteiro` e uma entidade reutilizavel e avulsa. Ele pode existir sozinho e nao depende de Evento, Oficio, Plano de Trabalho, Ordem de Servico ou Evento.

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
