# Central de Viagens 3

Base Django modular e document-centric para o novo sistema `central-viagens-3`.

`legacy/` e apenas referencia de consulta. O projeto novo nao deve importar codigo, templates, static ou settings da estrutura antiga.

## Arquitetura

O sistema e separado por apps de dominio: cadastros, roteiros, eventos, documentos, oficios, termos, justificativas, planos de trabalho, ordens de servico, prestacoes de contas, diario de bordo, assinaturas e integracoes.

Documentos sao o centro da arquitetura. Eventos podem agrupar documentos, mas nao sao obrigatorios para criar ou evoluir fluxos.

## Ambiente local

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
```

## Banco e validacao

```powershell
python manage.py migrate
python manage.py check
```

## Servidor local

```powershell
python manage.py runserver
```

Settings locais usam `config.settings.dev` por padrao em `manage.py`.
