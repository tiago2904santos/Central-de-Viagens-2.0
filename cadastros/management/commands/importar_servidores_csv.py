import csv
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand

from cadastros.models import Cargo, UnidadeLotacao, Viajante


HEADER_NAME_KEYS = {
    'nome',
    'nomes',
    'servidor',
    'servidores',
    'servidor nome completo',
    'nome completo',
}


def _strip_bom(value):
    return (value or '').replace('\ufeff', '')


def _normalize_spaces(value):
    return ' '.join((value or '').strip().split())


def _normalize_upper(value):
    return _normalize_spaces(value).upper()


def _to_ascii_key(value):
    if not value:
        return ''
    text = unicodedata.normalize('NFKD', value)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = _normalize_spaces(text).casefold()
    return text


def _header_token(value):
    token = _to_ascii_key(_strip_bom(value))
    token = re.sub(r'[^a-z0-9]+', ' ', token)
    return _normalize_spaces(token)


def _clean_digits(value):
    return re.sub(r'\D', '', value or '')


def _normalize_rg(value):
    text = _normalize_upper(value)
    text = text.replace('–', '-').replace('—', '-')
    if not text:
        return ''
    if 'NAO POSSUI' in _to_ascii_key(text):
        return ''
    if 'MESMA NUMERACAO' in _to_ascii_key(text):
        return ''
    return text


def _detect_delimiter(text):
    sample = '\n'.join(text.splitlines()[:20]).strip()
    if not sample:
        return ','
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        return dialect.delimiter
    except csv.Error:
        semicolons = sample.count(';')
        commas = sample.count(',')
        tabs = sample.count('\t')
        if semicolons >= commas and semicolons >= tabs:
            return ';'
        if tabs > commas:
            return '\t'
        return ','


def _read_text_with_fallback(path):
    raw = path.read_bytes()
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', errors='replace'), 'latin-1-replace'


def _is_header_row(first_row):
    if not first_row:
        return False
    tokens = [_header_token(c) for c in first_row]
    known = {
        'lotacao',
        'servidor nome completo',
        'nome',
        'nomes',
        'rg',
        'cpf',
        'cargo',
        'telefone',
        'servidor',
        'servidores',
    }
    matches = sum(1 for t in tokens if t in known or 'nome' in t or 'servidor' in t)
    return matches >= 2


def _find_column_indexes(headers):
    idx = {
        'nome': None,
        'lotacao': None,
        'rg': None,
        'cpf': None,
        'cargo': None,
        'telefone': None,
    }
    for i, raw in enumerate(headers):
        token = _header_token(raw)
        if idx['nome'] is None and (
            token in HEADER_NAME_KEYS
            or token.startswith('nome')
            or token.startswith('servidor')
            or 'nome completo' in token
        ):
            idx['nome'] = i
            continue
        if idx['lotacao'] is None and 'lotacao' in token:
            idx['lotacao'] = i
            continue
        if idx['rg'] is None and token == 'rg':
            idx['rg'] = i
            continue
        if idx['cpf'] is None and token == 'cpf':
            idx['cpf'] = i
            continue
        if idx['cargo'] is None and 'cargo' in token:
            idx['cargo'] = i
            continue
        if idx['telefone'] is None and 'telefone' in token:
            idx['telefone'] = i
            continue
    return idx


def _guess_name_column(rows):
    if not rows:
        return 0
    width = max(len(r) for r in rows)
    if width <= 1:
        return 0

    sample = rows[:25]
    best_idx = 0
    best_score = -1
    for col in range(width):
        score = 0
        for row in sample:
            cell = row[col] if col < len(row) else ''
            text = _normalize_spaces(cell)
            if not text:
                continue
            key = _to_ascii_key(text)
            if any(tag in key for tag in ('cpf', 'rg', 'telefone', 'cargo', 'lotacao')):
                score -= 2
                continue
            words = text.split()
            if len(words) >= 2 and not _clean_digits(text):
                score += 2
            elif re.search(r'[A-Za-zÀ-ÿ]', text):
                score += 1
        if score > best_score:
            best_score = score
            best_idx = col
    return best_idx


def _get_col(row, idx):
    if idx is None or idx < 0 or idx >= len(row):
        return ''
    return row[idx]


class Command(BaseCommand):
    help = 'Importa servidores (Viajante) a partir de CSV, com deduplicação e normalização.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Caminho do arquivo CSV.')

    def handle(self, *args, **options):
        path = Path(options['csv_path'])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'Arquivo não encontrado: {path}'))
            return

        text, encoding_used = _read_text_with_fallback(path)
        delimiter = _detect_delimiter(text)
        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        rows = [row for row in reader]

        if not rows:
            self.stdout.write(self.style.WARNING('Arquivo CSV vazio. Nada a importar.'))
            return

        has_header = _is_header_row(rows[0])
        if has_header:
            header = rows[0]
            data_rows = rows[1:]
            indexes = _find_column_indexes(header)
            if indexes['nome'] is None:
                indexes['nome'] = _guess_name_column(data_rows)
        else:
            header = []
            data_rows = rows
            indexes = {
                'nome': _guess_name_column(data_rows),
                'lotacao': 0 if _guess_name_column(data_rows) != 0 else None,
                'rg': None,
                'cpf': None,
                'cargo': None,
                'telefone': None,
            }

        existing = Viajante.objects.select_related('cargo', 'unidade_lotacao').all()
        by_cpf = {}
        by_rg = {}
        by_nome_key = {}

        for obj in existing:
            if obj.cpf:
                by_cpf[obj.cpf] = obj
            if obj.rg and obj.rg != 'NAO POSSUI RG':
                by_rg[_to_ascii_key(obj.rg)] = obj
            nome_key = _to_ascii_key(obj.nome)
            if nome_key:
                by_nome_key[nome_key] = obj

        total_lidas = len(data_rows)
        importados = 0
        atualizados = 0
        ignorados_vazio = 0
        ignorados_duplicidade = 0
        erros = []

        seen_keys = set()

        for line_offset, row in enumerate(data_rows, start=2 if has_header else 1):
            if not any(_normalize_spaces(col) for col in row):
                ignorados_vazio += 1
                continue

            nome_raw = _get_col(row, indexes['nome'])
            nome = _normalize_upper(nome_raw)
            if not nome:
                ignorados_vazio += 1
                continue

            cpf = _clean_digits(_get_col(row, indexes['cpf']))
            if len(cpf) != 11:
                cpf = ''

            rg = _normalize_rg(_get_col(row, indexes['rg']))
            rg_key = _to_ascii_key(rg) if rg else ''

            telefone = _clean_digits(_get_col(row, indexes['telefone']))
            if len(telefone) not in (10, 11):
                telefone = ''

            cargo_nome = _normalize_upper(_get_col(row, indexes['cargo']))
            lotacao_nome = _normalize_upper(_get_col(row, indexes['lotacao']))

            nome_key = _to_ascii_key(nome)
            identity_key = f'cpf:{cpf}' if cpf else (f'rg:{rg_key}' if rg_key else f'nome:{nome_key}')
            if identity_key in seen_keys or (nome_key and f'nome:{nome_key}' in seen_keys):
                ignorados_duplicidade += 1
                continue

            target = None
            if cpf and cpf in by_cpf:
                target = by_cpf[cpf]
            elif rg_key and rg_key in by_rg:
                target = by_rg[rg_key]
            elif nome_key and nome_key in by_nome_key:
                target = by_nome_key[nome_key]

            try:
                cargo = None
                if cargo_nome:
                    cargo, _ = Cargo.objects.get_or_create(nome=cargo_nome)

                unidade = None
                if lotacao_nome:
                    unidade, _ = UnidadeLotacao.objects.get_or_create(nome=lotacao_nome)

                if target is None:
                    target = Viajante(nome=nome)
                    created = True
                else:
                    created = False

                target.nome = nome
                target.cpf = cpf
                target.rg = rg
                target.sem_rg = not bool(rg)
                target.telefone = telefone
                target.cargo = cargo
                target.unidade_lotacao = unidade
                target.status = (
                    Viajante.STATUS_FINALIZADO if target.esta_completo() else Viajante.STATUS_RASCUNHO
                )
                target.save()

                if created:
                    importados += 1
                else:
                    atualizados += 1

                if cpf:
                    by_cpf[cpf] = target
                if rg_key:
                    by_rg[rg_key] = target
                if nome_key:
                    by_nome_key[nome_key] = target

                seen_keys.add(identity_key)
                if nome_key:
                    seen_keys.add(f'nome:{nome_key}')
            except Exception as exc:
                if len(erros) < 20:
                    erros.append(f'Linha {line_offset}: {exc}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Importação de servidores finalizada.'))
        self.stdout.write(f'Arquivo: {path}')
        self.stdout.write(f'Encoding detectado: {encoding_used}')
        self.stdout.write(f'Delimitador detectado: {repr(delimiter)}')
        self.stdout.write(f'Cabeçalho detectado: {"sim" if has_header else "não"}')
        if has_header:
            self.stdout.write(f'Colunas no cabeçalho: {header}')
        self.stdout.write('')
        self.stdout.write(f'Total de linhas lidas: {total_lidas}')
        self.stdout.write(f'Total importado (novos): {importados}')
        self.stdout.write(f'Total atualizado: {atualizados}')
        self.stdout.write(f'Total ignorado por vazio: {ignorados_vazio}')
        self.stdout.write(f'Total ignorado por duplicidade: {ignorados_duplicidade}')
        self.stdout.write(f'Total com erro: {len(erros)}')

        if erros:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('Exemplos de erros de linha:'))
            for err in erros[:10]:
                self.stdout.write(f'- {err}')
