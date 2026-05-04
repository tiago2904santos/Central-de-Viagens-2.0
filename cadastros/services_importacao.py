import csv
import unicodedata
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal
from pathlib import Path

from django.db import transaction

from cadastros.models import Cidade
from cadastros.models import Estado

# Capitais por UF — comparação por nome normalizado (maiúsculas + acentos → NFKD).
CAPITAIS_POR_UF = {
    "AC": "RIO BRANCO",
    "AL": "MACEIÓ",
    "AP": "MACAPÁ",
    "AM": "MANAUS",
    "BA": "SALVADOR",
    "CE": "FORTALEZA",
    "DF": "BRASÍLIA",
    "ES": "VITÓRIA",
    "GO": "GOIÂNIA",
    "MA": "SÃO LUÍS",
    "MT": "CUIABÁ",
    "MS": "CAMPO GRANDE",
    "MG": "BELO HORIZONTE",
    "PA": "BELÉM",
    "PB": "JOÃO PESSOA",
    "PR": "CURITIBA",
    "PE": "RECIFE",
    "PI": "TERESINA",
    "RJ": "RIO DE JANEIRO",
    "RN": "NATAL",
    "RS": "PORTO ALEGRE",
    "RO": "PORTO VELHO",
    "RR": "BOA VISTA",
    "SC": "FLORIANÓPOLIS",
    "SP": "SÃO PAULO",
    "SE": "ARACAJU",
    "TO": "PALMAS",
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _normalize_whitespace_upper(text: str) -> str:
    return " ".join((text or "").strip().split()).upper()


def _norm_geo_compare(a: str, b: str) -> bool:
    return _strip_accents(_normalize_whitespace_upper(a)) == _strip_accents(_normalize_whitespace_upper(b))


def _sniff_delimiter(sample: str) -> str:
    first = sample.splitlines()[0] if sample else ""
    semi = first.count(";")
    comma = first.count(",")
    return ";" if semi > comma else ","


def _classify_column_cidade(header: str) -> str | None:
    raw = (header or "").strip()
    key = _strip_accents(raw.lower())
    if key in ("municipio", "cidade", "nome"):
        return "nome"
    if key == "uf":
        return "uf"
    return None


def _resolve_columns_cidade(fieldnames: list[str] | None) -> tuple[str | None, str | None]:
    if not fieldnames:
        return None, None
    col_nome = None
    col_uf = None
    for fn in fieldnames:
        kind = _classify_column_cidade(fn)
        if kind == "nome" and col_nome is None:
            col_nome = fn
        elif kind == "uf" and col_uf is None:
            col_uf = fn
    return col_nome, col_uf


def _classify_column_estado(header: str) -> str | None:
    raw = (header or "").strip()
    key = _strip_accents(raw.upper())
    if key == "COD":
        return "cod"
    if key == "NOME":
        return "nome"
    if key == "SIGLA":
        return "sigla"
    return None


def _resolve_columns_estado(fieldnames: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not fieldnames:
        return out
    for fn in fieldnames:
        kind = _classify_column_estado(fn)
        if kind and kind not in out:
            out[kind] = fn
    return out


def _parse_decimal(raw: str) -> Decimal | None:
    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        return Decimal(raw)
    except Exception:
        return None


def _parse_int(raw: str) -> int | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def capital_esperada_para_uf(sigla: str) -> str | None:
    return CAPITAIS_POR_UF.get((sigla or "").strip().upper()[:2])


def _marcar_capital(sigla_uf: str, nome_cidade: str) -> bool:
    esp = capital_esperada_para_uf(sigla_uf)
    if not esp:
        return False
    return _norm_geo_compare(nome_cidade, esp)


@dataclass
class ResultadoImportacaoEstados:
    total_linhas: int = 0
    criados: int = 0
    existentes: int = 0
    atualizados: int = 0
    ignorados: int = 0
    erros: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class ResultadoImportacaoCidades:
    total_linhas: int = 0
    criadas: int = 0
    existentes: int = 0
    atualizados: int = 0
    ignoradas: int = 0
    capitais_marcadas: int = 0
    erros: list[tuple[int, str]] = field(default_factory=list)


@dataclass
class ResultadoImportacaoGeografica:
    estados: ResultadoImportacaoEstados
    cidades: ResultadoImportacaoCidades


def importar_estados_csv(
    file_path: str | Path, *, dry_run: bool = False, encoding: str = "utf-8-sig"
) -> ResultadoImportacaoEstados:
    path = Path(file_path)
    resultado = ResultadoImportacaoEstados()

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

    delimiter = _sniff_delimiter(text[:8192])
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    cols = _resolve_columns_estado(reader.fieldnames)

    if not cols.get("sigla") or not cols.get("nome"):
        resultado.erros.append(
            (0, "Cabeçalho de estados deve incluir SIGLA e NOME (e opcionalmente COD)."),
        )
        return resultado

    line_no = 1
    col_cod = cols.get("cod")

    for row in reader:
        line_no += 1
        resultado.total_linhas += 1

        sigla_raw = (row.get(cols["sigla"]) or "").strip()
        nome_raw = (row.get(cols["nome"]) or "").strip()
        cod_raw = (row.get(col_cod) or "").strip() if col_cod else ""

        if not sigla_raw and not nome_raw:
            resultado.ignorados += 1
            continue

        sigla = _normalize_whitespace_upper(sigla_raw)
        if len(sigla) != 2:
            resultado.erros.append((line_no, f'Sigla de estado inválida "{sigla_raw}".'))
            continue

        nome = _normalize_whitespace_upper(nome_raw)
        if not nome:
            resultado.ignorados += 1
            continue

        cod_ibge = _parse_int(cod_raw) if cod_raw else None
        if cod_raw and cod_ibge is None:
            resultado.erros.append((line_no, f'COD IBGE inválido "{cod_raw}".'))
            continue

        try:
            estado_existente = Estado.objects.filter(sigla=sigla).first()
            if estado_existente:
                mudou = False
                if estado_existente.nome != nome:
                    mudou = True
                if cod_ibge is not None and estado_existente.codigo_ibge != cod_ibge:
                    mudou = True
                if mudou:
                    if dry_run:
                        resultado.atualizados += 1
                    else:
                        estado_existente.nome = nome
                        if cod_ibge is not None:
                            estado_existente.codigo_ibge = cod_ibge
                        estado_existente.save()
                        resultado.atualizados += 1
                else:
                    resultado.existentes += 1
            else:
                if dry_run:
                    resultado.criados += 1
                else:
                    Estado.objects.create(nome=nome, sigla=sigla, codigo_ibge=cod_ibge)
                    resultado.criados += 1
        except Exception as exc:
            resultado.erros.append((line_no, str(exc)))

    return resultado


def importar_cidades_csv(
    file_path: str | Path,
    *,
    dry_run: bool = False,
    encoding: str = "utf-8-sig",
    fonte_municipio_code: bool = False,
) -> ResultadoImportacaoCidades:
    """
    Importa cidades. Se fonte_municipio_code=True, espera colunas id_municipio;uf;municipio;longitude;latitude.
    Caso contrário, formato simples municipio/cidade/nome + uf.
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

    delimiter = _sniff_delimiter(text[:8192])
    lines = text.splitlines()
    reader = csv.DictReader(lines, delimiter=delimiter)
    fieldnames = reader.fieldnames or []

    if fonte_municipio_code or (
        any(_strip_accents(f.lower()) == "id_municipio" for f in fieldnames)
        and any(_strip_accents(f.lower()) == "municipio" for f in fieldnames)
    ):
        return _importar_cidades_municipio_code(reader, resultado, dry_run)

    col_nome, col_uf = _resolve_columns_cidade(reader.fieldnames)
    if not col_nome or not col_uf:
        resultado.erros.append(
            (
                0,
                "Cabeçalho deve identificar colunas de município (municipio/cidade/nome) e UF (uf). "
                "Importe estados antes ou use municipio_code.csv.",
            )
        )
        return resultado

    estados_por_sigla = {e.sigla: e for e in Estado.objects.all()}
    existing_keys = set(Cidade.objects.values_list("nome", "estado_id"))
    seen_in_file: set[tuple[str, int]] = set()
    to_create: list[Cidade] = []
    to_update: list[Cidade] = []
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
        sigla = _normalize_whitespace_upper(uf_raw)

        if not nome:
            resultado.ignoradas += 1
            continue

        if len(sigla) != 2:
            resultado.erros.append((line_no, f'UF inválida "{uf_raw}" (esperado 2 caracteres).'))
            continue

        estado = estados_por_sigla.get(sigla)
        if not estado:
            resultado.erros.append(
                (line_no, f'Estado "{sigla}" não cadastrado. Importe estados antes.'),
            )
            continue

        capital = _marcar_capital(sigla, nome)
        key = (nome, estado.id)

        if key in seen_in_file:
            resultado.ignoradas += 1
            continue

        if key in existing_keys:
            resultado.existentes += 1
            seen_in_file.add(key)
            if capital and not dry_run:
                cid = Cidade.objects.filter(nome=nome, estado=estado).first()
                if cid and not cid.capital:
                    cid.capital = True
                    to_update.append(cid)
                    resultado.capitais_marcadas += 1
            continue

        seen_in_file.add(key)
        if dry_run:
            resultado.criadas += 1
            if capital:
                resultado.capitais_marcadas += 1
            existing_keys.add(key)
            continue

        c = Cidade(
            estado=estado,
            nome=nome,
            uf=sigla,
            capital=capital,
            codigo_ibge=None,
            latitude=None,
            longitude=None,
        )
        to_create.append(c)
        if capital:
            resultado.capitais_marcadas += 1
        existing_keys.add(key)

    if not dry_run:
        if to_create:
            with transaction.atomic():
                Cidade.objects.bulk_create(to_create, batch_size=400)
            resultado.criadas = len(to_create)
        if to_update:
            Cidade.objects.bulk_update(to_update, ["capital"], batch_size=400)
            resultado.atualizados = len(to_update)

    return resultado


def _importar_cidades_municipio_code(reader, resultado: ResultadoImportacaoCidades, dry_run: bool):
    fieldnames = reader.fieldnames or []
    map_fn = {}
    for fn in fieldnames:
        k = _strip_accents(fn.lower().strip())
        if k == "id_municipio":
            map_fn["id"] = fn
        elif k == "uf":
            map_fn["uf"] = fn
        elif k == "municipio":
            map_fn["municipio"] = fn
        elif k == "longitude":
            map_fn["lon"] = fn
        elif k == "latitude":
            map_fn["lat"] = fn

    if not map_fn.get("id") or not map_fn.get("uf") or not map_fn.get("municipio"):
        resultado.erros.append(
            (0, "municipio_code.csv deve conter colunas id_municipio, uf e municipio."),
        )
        return resultado

    estados_por_sigla = {e.sigla: e for e in Estado.objects.all()}
    existing_by_cod = dict(Cidade.objects.exclude(codigo_ibge__isnull=True).values_list("codigo_ibge", "id"))
    existing_nome_estado = set(Cidade.objects.values_list("nome", "estado_id"))
    to_create: list[Cidade] = []
    to_update: list[Cidade] = []
    line_no = 1

    for row in reader:
        line_no += 1
        resultado.total_linhas += 1

        cod_ibge = _parse_int(row.get(map_fn["id"]) or "")
        uf_raw = (row.get(map_fn["uf"]) or "").strip()
        nome_raw = (row.get(map_fn["municipio"]) or "").strip()
        lat = _parse_decimal(row.get(map_fn["lat"]) or "") if map_fn.get("lat") else None
        lon = _parse_decimal(row.get(map_fn["lon"]) or "") if map_fn.get("lon") else None

        if not nome_raw and not uf_raw:
            resultado.ignoradas += 1
            continue

        nome = _normalize_whitespace_upper(nome_raw)
        sigla = _normalize_whitespace_upper(uf_raw)

        if not nome:
            resultado.ignoradas += 1
            continue

        if len(sigla) != 2:
            resultado.erros.append((line_no, f'UF inválida "{uf_raw}".'))
            continue

        estado = estados_por_sigla.get(sigla)
        if not estado:
            resultado.erros.append((line_no, f'Estado "{sigla}" não cadastrado. Importe estados antes.'))
            continue

        capital = _marcar_capital(sigla, nome)

        if cod_ibge is None:
            resultado.erros.append((line_no, "id_municipio inválido."))
            continue

        if cod_ibge in existing_by_cod:
            resultado.existentes += 1
            if not dry_run:
                cid = Cidade.objects.get(pk=existing_by_cod[cod_ibge])
                mud = False
                if capital and not cid.capital:
                    cid.capital = True
                    mud = True
                    resultado.capitais_marcadas += 1
                if lat is not None and cid.latitude != lat:
                    cid.latitude = lat
                    mud = True
                if lon is not None and cid.longitude != lon:
                    cid.longitude = lon
                    mud = True
                if mud:
                    to_update.append(cid)
            continue

        key_ne = (nome, estado.id)
        if key_ne in existing_nome_estado:
            resultado.existentes += 1
            continue

        if dry_run:
            resultado.criadas += 1
            if capital:
                resultado.capitais_marcadas += 1
            existing_nome_estado.add(key_ne)
            continue

        to_create.append(
            Cidade(
                estado=estado,
                nome=nome,
                uf=sigla,
                codigo_ibge=cod_ibge,
                capital=capital,
                latitude=lat,
                longitude=lon,
            )
        )
        if capital:
            resultado.capitais_marcadas += 1
        existing_nome_estado.add(key_ne)

    if not dry_run and to_create:
        with transaction.atomic():
            Cidade.objects.bulk_create(to_create, batch_size=400)
        resultado.criadas = len(to_create)
    elif dry_run:
        pass
    else:
        resultado.criadas = len(to_create)

    if not dry_run and to_update:
        Cidade.objects.bulk_update(to_update, ["capital", "latitude", "longitude"], batch_size=400)
        resultado.atualizados = len(to_update)

    return resultado


def importar_municipios_csv(
    file_path: str | Path, *, dry_run: bool = False, encoding: str = "utf-8-sig"
) -> ResultadoImportacaoCidades:
    """Formato municipios.csv: COD UF, COD, NOME — COD UF = código IBGE do estado."""
    path = Path(file_path)
    resultado = ResultadoImportacaoCidades()

    if not path.is_file():
        resultado.erros.append((0, f"Arquivo não encontrado: {path}"))
        return resultado

    try:
        text = path.read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError) as exc:
        resultado.erros.append((0, str(exc)))
        return resultado

    delimiter = _sniff_delimiter(text[:8192])
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    fn = reader.fieldnames or []

    def find_col(candidates: tuple[str, ...]) -> str | None:
        for h in fn:
            h_norm = _strip_accents(h.strip().upper().replace(" ", " "))
            for c in candidates:
                c_norm = _strip_accents(c.strip().upper().replace(" ", " "))
                if h_norm == c_norm:
                    return h
        return None

    col_cod_uf = find_col(("COD UF", "COD_UF"))
    col_cod = find_col(("COD",))
    col_nome = find_col(("NOME",))
    if not col_cod_uf or not col_cod or not col_nome:
        resultado.erros.append((0, "Esperado cabeçalho com COD UF, COD e NOME."))
        return resultado

    estados_por_cod = {e.codigo_ibge: e for e in Estado.objects.exclude(codigo_ibge__isnull=True)}
    existing_cod_cidade = set(Cidade.objects.exclude(codigo_ibge__isnull=True).values_list("codigo_ibge", flat=True))

    to_create: list[Cidade] = []
    line_no = 1

    for row in reader:
        line_no += 1
        resultado.total_linhas += 1

        cod_uf = _parse_int(row.get(col_cod_uf) or "")
        cod_mun = _parse_int(row.get(col_cod) or "")
        nome = _normalize_whitespace_upper((row.get(col_nome) or "").strip())

        if not nome:
            resultado.ignoradas += 1
            continue
        if cod_uf is None or cod_mun is None:
            resultado.erros.append((line_no, "COD UF ou COD inválido."))
            continue

        estado = estados_por_cod.get(cod_uf)
        if not estado:
            resultado.erros.append((line_no, f"Estado com código IBGE {cod_uf} não encontrado. Importe estados.csv antes."))
            continue

        if cod_mun in existing_cod_cidade:
            resultado.existentes += 1
            continue

        sigla = estado.sigla
        capital = _marcar_capital(sigla, nome)

        if dry_run:
            resultado.criadas += 1
            if capital:
                resultado.capitais_marcadas += 1
            existing_cod_cidade.add(cod_mun)
            continue

        to_create.append(
            Cidade(
                estado=estado,
                nome=nome,
                uf=sigla,
                codigo_ibge=cod_mun,
                capital=capital,
            )
        )
        if capital:
            resultado.capitais_marcadas += 1
        existing_cod_cidade.add(cod_mun)

    if not dry_run and to_create:
        with transaction.atomic():
            Cidade.objects.bulk_create(to_create, batch_size=400)
        resultado.criadas = len(to_create)

    return resultado


def importar_base_geografica(
    estados_path: str | Path,
    *,
    municipios_code_path: str | Path | None = None,
    municipios_ibge_path: str | Path | None = None,
    dry_run: bool = False,
    encoding: str = "utf-8-sig",
) -> ResultadoImportacaoGeografica:
    """
    Orquestra: 1) estados.csv 2) municipio_code OU municipios.csv (IBGE).
    """
    if dry_run:
        with transaction.atomic():
            resultado = importar_base_geografica(
                estados_path,
                municipios_code_path=municipios_code_path,
                municipios_ibge_path=municipios_ibge_path,
                dry_run=False,
                encoding=encoding,
            )
            transaction.set_rollback(True)
            return resultado

    re_estados = importar_estados_csv(estados_path, dry_run=dry_run, encoding=encoding)

    re_cidades = ResultadoImportacaoCidades()
    if re_estados.erros and any(ln == 0 for ln, _ in re_estados.erros):
        return ResultadoImportacaoGeografica(estados=re_estados, cidades=re_cidades)

    if municipios_code_path:
        p_code = Path(municipios_code_path)
        if not p_code.is_file():
            re_cidades.erros.append((0, f"Arquivo não encontrado: {p_code}"))
            return ResultadoImportacaoGeografica(estados=re_estados, cidades=re_cidades)
        re_cidades = importar_cidades_csv(
            p_code,
            dry_run=dry_run,
            encoding=encoding,
            fonte_municipio_code=True,
        )
    elif municipios_ibge_path:
        p_ibge = Path(municipios_ibge_path)
        if not p_ibge.is_file():
            re_cidades.erros.append((0, f"Arquivo não encontrado: {p_ibge}"))
            return ResultadoImportacaoGeografica(estados=re_estados, cidades=re_cidades)
        re_cidades = importar_municipios_csv(p_ibge, dry_run=dry_run, encoding=encoding)

    return ResultadoImportacaoGeografica(estados=re_estados, cidades=re_cidades)
