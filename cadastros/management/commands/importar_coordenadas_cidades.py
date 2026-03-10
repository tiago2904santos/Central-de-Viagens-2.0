# -*- coding: utf-8 -*-
"""
Atualiza latitude e longitude das cidades já existentes no banco a partir de um CSV.
Não cria cidades novas. Match por UF + nome (comparação normalizada: caixa, acentos, espaços).
"""
import csv
import logging
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand

from cadastros.models import Estado, Cidade

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ('uf', 'municipio', 'latitude', 'longitude')
LIMITE_EXEMPLOS_NAO_ENCONTRADAS = 20


def normalizar_nome(texto):
    """
    Normaliza nome para comparação: strip, maiúsculas, remove acentos, colapsa espaços.
    """
    if texto is None or not isinstance(texto, str):
        return ''
    t = texto.strip()
    if not t:
        return ''
    t = t.upper()
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def _parse_coord(val):
    """Converte valor para Decimal válido para coordenada. Retorna None se inválido."""
    if val is None or (isinstance(val, str) and not val.strip()):
        return None
    s = str(val).strip().replace(',', '.')
    try:
        d = Decimal(s)
        if d < -180 or d > 180:
            return None
        return d
    except (InvalidOperation, ValueError):
        return None


class Command(BaseCommand):
    help = (
        'Atualiza latitude e longitude das cidades existentes a partir de um CSV. '
        'Formato: id_municipio;uf;municipio;longitude;latitude (delimiter ;). '
        'Não cria cidades novas; match por UF + nome (normalizado).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--arquivo',
            type=str,
            required=True,
            help='Caminho para o CSV (ex.: municipio_code.csv). Cabeçalho: id_municipio;uf;municipio;longitude;latitude',
        )

    def handle(self, *args, **options):
        path = Path(options['arquivo'])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Arquivo não encontrado: {path}'))
            return

        total_linhas = 0
        atualizadas = 0
        nao_encontradas = 0
        invalidas = 0
        exemplos_nao_encontradas = []

        try:
            with open(path, encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f, delimiter=';')
                if not reader.fieldnames:
                    self.stderr.write(self.style.ERROR('CSV vazio ou sem cabeçalho.'))
                    return
                fieldnames = [c.strip().lower() for c in reader.fieldnames]
                missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
                if missing:
                    self.stderr.write(self.style.ERROR(f'Colunas obrigatórias ausentes: {missing}. Cabeçalho esperado: id_municipio;uf;municipio;longitude;latitude'))
                    return

                def get_col(row, name):
                    for k, v in row.items():
                        if k and k.strip().lower() == name:
                            return v or ''
                    return ''

                for row in reader:
                    total_linhas += 1
                    uf = get_col(row, 'uf').strip().upper()
                    municipio = get_col(row, 'municipio').strip()
                    lat_raw = get_col(row, 'latitude')
                    lon_raw = get_col(row, 'longitude')

                    if not uf or not municipio:
                        invalidas += 1
                        if invalidas <= 5:
                            logger.warning('Linha %d: UF ou município vazio.', total_linhas)
                        continue

                    lat = _parse_coord(lat_raw)
                    lon = _parse_coord(lon_raw)
                    if lat is None or lon is None:
                        invalidas += 1
                        if invalidas <= 5:
                            logger.warning('Linha %d: latitude/longitude inválida (uf=%s, municipio=%s).', total_linhas, uf, municipio[:30])
                        continue

                    try:
                        estado = Estado.objects.get(sigla=uf)
                    except Estado.DoesNotExist:
                        invalidas += 1
                        if invalidas <= 5:
                            logger.warning('Linha %d: UF inexistente no banco: %s', total_linhas, uf)
                        continue

                    nome_norm = normalizar_nome(municipio)
                    if not nome_norm:
                        invalidas += 1
                        continue

                    cidades_no_estado = list(Cidade.objects.filter(estado=estado, ativo=True))
                    cidade = None
                    for c in cidades_no_estado:
                        if normalizar_nome(c.nome) == nome_norm:
                            cidade = c
                            break

                    if cidade is None:
                        nao_encontradas += 1
                        if len(exemplos_nao_encontradas) < LIMITE_EXEMPLOS_NAO_ENCONTRADAS:
                            exemplos_nao_encontradas.append(f'{municipio}/{uf}')
                        continue

                    cidade.latitude = lat
                    cidade.longitude = lon
                    cidade.save(update_fields=['latitude', 'longitude', 'updated_at'])
                    atualizadas += 1

        except csv.Error as e:
            self.stderr.write(self.style.ERROR(f'CSV malformado: {e}'))
            return

        self.stdout.write(self.style.SUCCESS('--- Resumo da importação de coordenadas ---'))
        self.stdout.write(f'Total de linhas lidas: {total_linhas}')
        self.stdout.write(f'Cidades atualizadas: {atualizadas}')
        self.stdout.write(f'Não encontradas (UF+nome): {nao_encontradas}')
        self.stdout.write(f'Linhas inválidas/ignoradas: {invalidas}')
        if exemplos_nao_encontradas:
            self.stdout.write('')
            self.stdout.write(f'Exemplos de não encontradas (máx. {LIMITE_EXEMPLOS_NAO_ENCONTRADAS}):')
            for ex in exemplos_nao_encontradas:
                self.stdout.write(f'  - {ex}')
