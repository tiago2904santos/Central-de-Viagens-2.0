"""
Importação idempotente de Unidades de Lotação a partir de CSV.

Formato esperado (UTF-8):
  NOME
  Ex.: DEFENSORIA PÚBLICA DO ESTADO

- Chave de idempotência: nome normalizado (update_or_create por nome).
- Nome é normalizado: strip, colapsar espaços, UPPER.
- Relatório: criados, atualizados, ignorados (linhas vazias).
"""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from cadastros.models import UnidadeLotacao


def _normalizar(val):
    if val is None:
        return ''
    return ' '.join(str(val).strip().upper().split())


class Command(BaseCommand):
    help = 'Importa unidades de lotação a partir de CSV (coluna: NOME). Idempotente por nome.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            nargs='?',
            type=str,
            default='data/lotacao/unidades.csv',
            help='Caminho para o CSV (default: data/lotacao/unidades.csv)',
        )

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Arquivo não encontrado: {path}'))
            return

        created = updated = ignored = 0
        with open(path, encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or 'NOME' not in reader.fieldnames:
                self.stderr.write(
                    self.style.ERROR('CSV deve ter coluna exatamente: NOME.')
                )
                return
            for row in reader:
                nome = _normalizar(row.get('NOME', ''))
                if not nome:
                    ignored += 1
                    continue
                obj, was_created = UnidadeLotacao.objects.update_or_create(
                    nome=nome,
                    defaults={'nome': nome},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Unidades de lotação: {created} criadas, {updated} atualizadas, {ignored} ignoradas.'
            )
        )
