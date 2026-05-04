# Importação de cidades por CSV

## Fonte principal recomendada

Arquivo **`municipio_code.csv`** (estrutura típica do IBGE / bases geográficas), com separador **`;`**.

### Formato esperado (colunas)

```
id_municipio;uf;municipio;longitude;latitude
```

### Colunas utilizadas nesta etapa

- `uf`
- `município` (ou `municipio` — o importador reconhece variações; ver `cadastros/services_importacao.py`)

### Colunas ignoradas por enquanto

- `id_municipio`
- `longitude`
- `latitude`

## Comandos

Simulação (não grava no banco):

```bash
python manage.py importar_cidades dados/municipio_code.csv --dry-run
```

Importação real:

```bash
python manage.py importar_cidades dados/municipio_code.csv
```

Encoding (quando necessário, padrão é `utf-8-sig`):

```bash
python manage.py importar_cidades dados/municipio_code.csv --encoding utf-8-sig
```

## Regras de normalização

- Nome do município: armazenado em **MAIÚSCULO**, com espaços internos colapsados.
- UF: **2 caracteres**, em **MAIÚSCULO**.

## Duplicidade

- Não é permitida a repetição da combinação **nome + UF** (constraint `unique_cidade_nome_uf` no model `Cidade`).
- Linhas que coincidam com cidades já cadastradas são contadas como **já existentes** e não são recriadas.

## Arquivos grandes

Os CSVs completos (`municipio_code.csv`, `municipios.csv`, `estados.csv`) podem ficar apenas na sua máquina em `dados/`. O repositório mantém um exemplo pequeno em `dados/exemplos/cidades_exemplo.csv`.

## Uso futuro

As cidades importadas servirão como base para **Roteiros** (origem/destino) e demais módulos que referenciem municípios.
