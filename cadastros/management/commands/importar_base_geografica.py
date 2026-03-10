"""
Importação idempotente da base geográfica (Estados e Cidades) a partir de CSVs.

Formato esperado:

  estados.csv (UTF-8):
    COD,NOME,SIGLA
    Ex.: 35,São Paulo,SP

  municipios.csv (UTF-8):
    COD UF,COD,NOME[,LAT,LON]
    Ex.: 35,3550308,São Paulo,-23.550520,-46.633308

  - COD do estado vira Estado.codigo_ibge
  - COD do município vira Cidade.codigo_ibge
  - COD UF do município é usado para relacionar com Estado.codigo_ibge
  - Opcional: colunas LAT e LON (ou LATITUDE e LONGITUDE) preenchem Cidade.latitude e Cidade.longitude
    para estimativa local de distância/tempo entre cidades.
  - Valores textuais recebem strip()
"""
import csv
import logging
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand

from cadastros.models import Estado, Cidade

logger = logging.getLogger(__name__)


def _strip(val):
    if val is None:
        return ''
    return str(val).strip()


class Command(BaseCommand):
    help = 'Importa estados e cidades a partir de CSVs (idempotente; use codigo_ibge como chave).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--estados',
            type=str,
            help='Caminho para o CSV de estados (colunas: COD, NOME, SIGLA)',
        )
        parser.add_argument(
            '--cidades',
            type=str,
            help='Caminho para o CSV de municípios (colunas: COD UF, COD, NOME)',
        )

    def handle(self, *args, **options):
        estados_path = options.get('estados')
        cidades_path = options.get('cidades')

        if not estados_path and not cidades_path:
            self.stdout.write(self.style.WARNING('Informe pelo menos --estados ou --cidades.'))
            return

        if estados_path:
            self._importar_estados(Path(estados_path))
        if cidades_path:
            self._importar_cidades(Path(cidades_path))

    def _importar_estados(self, path: Path):
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Arquivo não encontrado: {path}'))
            return
        created = updated = 0
        with open(path, encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cod = _strip(row.get('COD', ''))
                nome = _strip(row.get('NOME', ''))
                sigla = _strip(row.get('SIGLA', ''))
                if not cod:
                    continue
                obj, was_created = Estado.objects.update_or_create(
                    codigo_ibge=cod,
                    defaults={'nome': nome, 'sigla': sigla, 'ativo': True},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f'Estados: {created} criados, {updated} atualizados.'))

    def _importar_cidades(self, path: Path):
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Arquivo não encontrado: {path}'))
            return
        created = updated = skipped = 0
        with open(path, encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cod_uf = _strip(row.get('COD UF', row.get('COD_UF', '')))
                cod = _strip(row.get('COD', ''))
                nome = _strip(row.get('NOME', ''))
                if not cod:
                    continue
                try:
                    estado = Estado.objects.get(codigo_ibge=cod_uf)
                except Estado.DoesNotExist:
                    logger.warning('Estado com codigo_ibge=%s não encontrado; cidade %s (%s) ignorada.', cod_uf, nome, cod)
                    self.stdout.write(
                        self.style.WARNING(f'Estado codigo_ibge={cod_uf!r} inexistente; cidade {nome!r} ({cod}) ignorada.')
                    )
                    skipped += 1
                    continue
                defaults = {'nome': nome, 'estado': estado, 'ativo': True}
                lat_raw = _strip(row.get('LAT', row.get('LATITUDE', '')))
                lon_raw = _strip(row.get('LON', row.get('LONGITUDE', '')))
                if lat_raw and lon_raw:
                    try:
                        defaults['latitude'] = Decimal(lat_raw.replace(',', '.'))
                        defaults['longitude'] = Decimal(lon_raw.replace(',', '.'))
                    except Exception:
                        pass
                obj, was_created = Cidade.objects.update_or_create(
                    codigo_ibge=cod,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f'Cidades: {created} criados, {updated} atualizados, {skipped} ignoradas (estado inexistente).'))
