# Relatório — Configuração de variáveis de ambiente

## Arquivos alterados

- **`config/settings.py`** — Carregamento do `.env` com caminho explícito (`BASE_DIR / ".env"`) e aviso quando o arquivo não existir.
- **`README.md`** — Seção "Configure variáveis de ambiente" deixando explícito que `.env.example` é modelo e `.env` é o arquivo real carregado.

## Causa do problema

O projeto carrega variáveis a partir de **`.env`** na raiz. Se esse arquivo não existir (só houver `.env.example`), as variáveis ficam vazias (ex.: `POSTGRES_DB`). Além disso, sem documentação clara, fica ambíguo qual arquivo deve ser editado.

## Diferença entre `.env.example` e `.env`

| Arquivo        | Uso |
|----------------|-----|
| **`.env.example`** | Apenas **modelo/documentação**. Lista as variáveis esperadas, sem valores sensíveis. Pode ser versionado. O projeto **não** carrega este arquivo. |
| **`.env`**         | Arquivo **real** carregado pelo `settings.py` (`load_dotenv(BASE_DIR / ".env")`). Deve ser criado a partir do exemplo, preenchido com valores reais e **não** deve ser commitado. |

## Como o usuário deve proceder agora

1. Na raiz do projeto, criar o `.env`:  
   `copy .env.example .env` (Windows) ou `cp .env.example .env` (Linux/macOS).
2. Abrir **`.env`** e preencher as variáveis (ex.: PostgreSQL `POSTGRES_*`).
3. Não commitar o `.env` (já deve estar no `.gitignore`).

Se o `.env` não existir, ao rodar o Django (runserver, shell, testes) será exibido um **warning** lembrando de copiar `.env.example` para `.env`.

## Como validar no shell

```bash
python manage.py shell
```

```python
import os
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent  # raiz do projeto
load_dotenv(BASE_DIR / ".env")
print(os.getenv("POSTGRES_DB"))  # ou outra variável do .env
```

- Com `.env` e variável definida: exibe o valor.
- Sem `.env` ou variável ausente: exibe `None`.
