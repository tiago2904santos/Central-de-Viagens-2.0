# Central de Viagens

Sistema Django para gestão autônoma de documentos institucionais e cadastros de apoio.

## Módulos ativos

- Ofícios
- Roteiros
- Planos de trabalho
- Ordens de serviço
- Justificativas
- Termos
- Cadastros de viajantes, veículos, cargos, unidades e configurações

## Execução local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Qualidade

```bash
python manage.py check
python manage.py test
```
