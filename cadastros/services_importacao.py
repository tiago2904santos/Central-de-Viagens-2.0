import csv
import unicodedata
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from django.db import transaction

from cadastros.models import Cidade


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_whitespace_upper(text: str) -> str:
    return " ".join((text or "").strip().split()).upper()


def _sniff_delimiter(sample: str) -> str:
    first = sample.splitlines()[0] if sample else ""
    semi = first.count(";")
    comma = first.count(",")
    return ";" if semi > comma else ","


def _classify_column(header: str) -> str | None:
    raw = (header or "").strip()
    key = _strip_accents(raw.lower())
    if key in ("municipio", "cidade", "nome"):
        return "nome"
    if key == "uf":
        return "uf"
    return None


def _resolve_columns(fieldnames: list[str] | None) -> tuple[str | None, str | None]:
    if not fieldnames:
        return None, None
    col_nome = None
    col_uf = None
    for fn in fieldnames:
        kind = _classify_column(fn)
        if kind == "nome" and col_nome is None:
            col_nome = fn
        elif kind == "uf" and col_uf is None:
            col_uf = fn
    return col_nome, col_uf


@dataclass
class ResultadoImportacaoCidades:
    total_linhas: int = 0
    criadas: int = 0
    existentes: int = 0
    ignoradas: int = 0
    erros: list[tuple[int, str]] = field(default_factory=list)


def importar_cidades_csv(file_path: str | Path, *, dry_run: bool = False, encoding: str = "utf-8-sig") -> ResultadoImportacaoCidades:
    """
    Importa cidades a partir de CSV. Colunas de nome aceitas: municipio, município, cidade, nome.
    Coluna UF: uf. Separador `;` ou `,` inferido pela primeira linha.
    """
    path = Path(file_path)
    resultado = ResultadoImportacaoCidades()

    if not path.is_file():
        resultado.erros.append((0, f"Arquivo não encontrado: {path}"))
        return resultado

    try:
        text = path.read_text(encoding=encoding)
    except OSError as exc:
        resultado.erros.append((0, f"Não foi possível ler o arquivo: {exc}"))
        return resultado
    except UnicodeDecodeError as exc:
        resultado.erros.append((0, f"Encoding inválido ({encoding}): {exc}"))
        return resultado

    if not text.strip():
        resultado.erros.append((0, "Arquivo vazio."))
        return resultado

    sample = text[:8192]
    delimiter = _sniff_delimiter(sample)
    lines = text.splitlines()
    reader = csv.DictReader(lines, delimiter=delimiter)
    col_nome, col_uf = _resolve_columns(reader.fieldnames)

    if not col_nome or not col_uf:
        resultado.erros.append(
            (
                0,
                "Cabeçalho deve identificar colunas de município (municipio/cidade/nome) e UF (uf).",
            )
        )
        return resultado

    existing = set(Cidade.objects.values_list("nome", "uf"))
    seen_in_file: set[tuple[str, str]] = set()
    to_create: list[Cidade] = []
    line_no = 1

    for row in reader:
        line_no += 1
        resultado.total_linhas += 1

        nome_raw = (row.get(col_nome) or "").strip()
        uf_raw = (row.get(col_uf) or "").strip()

        if not nome_raw and not uf_raw:
            resultado.ignoradas += 1
            continue

        nome = _normalize_whitespace_upper(nome_raw)
        uf = _normalize_whitespace_upper(uf_raw)

        if not nome:
            resultado.ignoradas += 1
            continue

        if len(uf) != 2:
            resultado.erros.append((line_no, f'UF inválida "{uf_raw}" (esperado 2 caracteres).'))
            continue

        key = (nome, uf)

        if key in seen_in_file:
            resultado.ignoradas += 1
            continue

        if key in existing:
            resultado.existentes += 1
            seen_in_file.add(key)
            continue

        seen_in_file.add(key)
        if dry_run:
            resultado.criadas += 1
            existing.add(key)
            continue

        to_create.append(Cidade(nome=nome, uf=uf))

    if not dry_run and to_create:
        with transaction.atomic():
            Cidade.objects.bulk_create(to_create, batch_size=400)
        resultado.criadas = len(to_create)
    elif dry_run:
        pass
    else:
        resultado.criadas = 0

    return resultado
