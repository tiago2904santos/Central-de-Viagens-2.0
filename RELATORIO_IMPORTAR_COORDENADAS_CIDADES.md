# Relatório — Importação de coordenadas (municipio_code.csv)

## 1) Arquivos alterados / criados

| Arquivo | Alteração |
|---------|-----------|
| **cadastros/management/commands/importar_coordenadas_cidades.py** | **Criado.** Comando que lê CSV com `;`, normaliza nome (strip, maiúsculas, sem acentos, espaços colapsados), faz match por UF + nome e atualiza apenas `latitude` e `longitude` em cidades existentes. |
| **eventos/views.py** | Antes de chamar a estimativa local, verifica se origem/destino têm coordenadas; em caso negativo retorna mensagem específica: "Cidade de origem sem coordenadas: NOME/UF" ou "Cidade de destino sem coordenadas: NOME/UF". |
| **cadastros/tests/test_cadastros.py** | Nova classe **ImportCoordenadasCidadesTest** com 6 testes: atualiza cidade existente, não cria cidade nova, match ignora acento/caixa, linha inválida não quebra, arquivo inexistente, leitura com delimiter `;`. |

**Model Cidade:** Os campos `latitude` e `longitude` já existiam (DecimalField 9,6); nenhuma alteração de model nem nova migration.

---

## 2) Migration criada

**Nenhuma.** Os campos `latitude` e `longitude` já constam do model `Cidade` (migration `cadastros.0020_cidade_latitude_longitude`). Nenhuma migration nova foi criada nesta tarefa.

---

## 3) Nome do comando

**`importar_coordenadas_cidades`**

Uso:

```bash
python manage.py importar_coordenadas_cidades --arquivo municipio_code.csv
```

---

## 4) Formato esperado do CSV

- **Nome do arquivo:** qualquer (ex.: `municipio_code.csv`)
- **Separador:** `;` (ponto e vírgula)
- **Encoding:** UTF-8
- **Cabeçalho (primeira linha):**
  - `id_municipio`
  - `uf`
  - `municipio`
  - `longitude`
  - `latitude`

Exemplo:

```text
id_municipio;uf;municipio;longitude;latitude
3550308;SP;São Paulo;-46.633308;-23.550520
4106902;PR;Curitiba;-49.2733;-25.4284
```

- **UF:** sigla do estado (ex.: SP, PR). Deve existir em `Estado` (sigla).
- **municipio:** nome do município. A comparação com o banco é feita após normalização (maiúsculas, sem acentos, espaços simples).
- **latitude / longitude:** números no intervalo [-180, 180]. Aceita vírgula ou ponto como separador decimal.

---

## 5) Como rodar o comando

Na raiz do projeto, com o ambiente ativado:

```bash
python manage.py importar_coordenadas_cidades --arquivo municipio_code.csv
```

Se o CSV estiver em outro diretório, use o caminho completo, por exemplo:

```bash
python manage.py importar_coordenadas_cidades --arquivo data/geografia/municipio_code.csv
```

Ao final o comando imprime um resumo: total de linhas lidas, cidades atualizadas, não encontradas, inválidas e até 20 exemplos de “não encontradas”.

---

## 6) Como validar no shell se as cidades foram atualizadas

```bash
python manage.py shell
```

```python
from cadastros.models import Cidade

# Cidades com coordenadas preenchidas
com_coords = Cidade.objects.exclude(latitude=None).exclude(longitude=None)
print(com_coords.count())
for c in com_coords[:5]:
    print(c.nome, c.estado.sigla, c.latitude, c.longitude)

# Exemplo para uma cidade específica
c = Cidade.objects.filter(nome__icontains='Curitiba').first()
if c:
    print('Curitiba:', c.latitude, c.longitude)
```

---

## 7) Checklist de aceite

| Item | Status |
|------|--------|
| Model Cidade com latitude/longitude (já existente) | OK |
| Comando `importar_coordenadas_cidades` criado | OK |
| Uso: `--arquivo municipio_code.csv` | OK |
| CSV com delimiter `;` e cabeçalho id_municipio;uf;municipio;longitude;latitude | OK |
| Match por UF + nome (normalizado: caixa, acentos, espaços) | OK |
| Apenas atualiza cidades existentes; não cria novas | OK |
| Relatório: total linhas, atualizadas, não encontradas, inválidas, exemplos (máx. 20) | OK |
| Tratamento: arquivo inexistente, CSV malformado, lat/lon inválidas, UF inexistente, cidade não encontrada | OK |
| Linha inválida não interrompe a importação | OK |
| Testes: sucesso, atualiza existente, não cria nova, acento/caixa, linha inválida, delimiter `;`, arquivo inexistente | OK |
| Mensagens de erro da estimativa local: "Cidade de origem/destino sem coordenadas: NOME/UF" | OK |
