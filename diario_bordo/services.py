from __future__ import annotations

import copy
import shutil
import subprocess
import sys
import tempfile
import re
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import DiarioBordo, DiarioBordoTrecho

XLSX_TEMPLATE_PATH = Path(settings.BASE_DIR) / "documentos" / "templates_xlsx" / "diario_bordo" / "modelo_diario_bordo.xlsx"
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS = {"x": SHEET_NS}
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")
ET.register_namespace("", SHEET_NS)


def ET_fromstring(payload):
    return ET.fromstring(payload)


def ET_tostring(root):
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def abastecimento_display(value):
    return "(X) Sim ( ) Não" if value else "( ) Sim (X) Não"


def _format_date(value):
    return value.strftime("%d/%m/%Y") if value else ""


def _format_time(value):
    return value.strftime("%H:%M") if value else ""


def _format_int(value):
    return "" if value is None else str(value)


def _cell_column(ref):
    return re.sub(r"\d+", "", ref or "")


def _set_cell_ref(cell, row_number):
    column = _cell_column(cell.attrib.get("r", "A"))
    if column:
        cell.set("r", f"{column}{row_number}")


def _replace_row_number_in_formula(value, old_row, new_row):
    return re.sub(rf"(?<=[A-Z]){old_row}\b", str(new_row), value or "")


def _shift_cell_ref(ref, after_row, delta):
    def repl(match):
        col, row_text = match.groups()
        row = int(row_text)
        if row > after_row:
            row += delta
        return f"{col}{row}"

    return re.sub(r"([A-Z]+)(\d+)", repl, ref)


def _shared_strings(root):
    values = []
    for si in root.findall("x:si", NS):
        values.append("".join(t.text or "" for t in si.findall(".//x:t", NS)))
    return values


def _cell_text(cell, shared):
    value = cell.find("x:v", NS)
    if value is None:
        inline = cell.find(".//x:t", NS)
        return inline.text if inline is not None else ""
    if cell.attrib.get("t") == "s":
        try:
            return shared[int(value.text or "0")]
        except (ValueError, IndexError):
            return ""
    return value.text or ""


def _set_inline_string(cell, text):
    for child in list(cell):
        cell.remove(child)
    cell.set("t", "inlineStr")
    is_el = cell.makeelement(f"{{{SHEET_NS}}}is", {})
    t_el = cell.makeelement(f"{{{SHEET_NS}}}t", {})
    t_el.text = str(text)
    is_el.append(t_el)
    cell.append(is_el)


def _replace_fixed_placeholders_in_shared_strings(root, mapping):
    for si in root.findall("x:si", NS):
        texts = si.findall(".//x:t", NS)
        if not texts:
            continue
        combined = "".join(t.text or "" for t in texts)
        replaced = combined
        for key, value in mapping.items():
            replaced = replaced.replace("{{" + key + "}}", str(value or ""))
        if replaced != combined:
            texts[0].text = replaced
            for text_node in texts[1:]:
                text_node.text = ""


def _clear_dynamic_placeholders_in_shared_strings(root):
    dynamic = set(_empty_trecho_mapping().keys())
    for si in root.findall("x:si", NS):
        texts = si.findall(".//x:t", NS)
        if not texts:
            continue
        combined = "".join(t.text or "" for t in texts)
        replaced = combined
        for placeholder in dynamic:
            replaced = replaced.replace(placeholder, "")
        if replaced != combined:
            texts[0].text = replaced
            for text_node in texts[1:]:
                text_node.text = ""


def _trecho_mapping(trecho):
    return {
        "{{trecho_data_saida}}": _format_date(trecho.data_saida),
        "{{trecho.data_saida}}": _format_date(trecho.data_saida),
        "{{trecho_hora_saida}}": _format_time(trecho.hora_saida),
        "{{trecho.hora_saida}}": _format_time(trecho.hora_saida),
        "{{trecho_km_inicial}}": _format_int(trecho.km_inicial),
        "{{trecho.km_inicial}}": _format_int(trecho.km_inicial),
        "{{trecho_data_chegada}}": _format_date(trecho.data_chegada),
        "{{trecho.data_chegada}}": _format_date(trecho.data_chegada),
        "{{trecho_hora_chegada}}": _format_time(trecho.hora_chegada),
        "{{trecho.hora_chegada}}": _format_time(trecho.hora_chegada),
        "{{trecho_km_final}}": _format_int(trecho.km_final),
        "{{trecho.km_final}}": _format_int(trecho.km_final),
        "{{trecho_origem}}": (trecho.origem or "").upper(),
        "{{trecho.origem}}": (trecho.origem or "").upper(),
        "{{trecho_destino}}": (trecho.destino or "").upper(),
        "{{trecho.destino}}": (trecho.destino or "").upper(),
        "{{trecho_abastecimento}}": abastecimento_display(trecho.necessidade_abastecimento),
        "{{trecho.abastecimento}}": abastecimento_display(trecho.necessidade_abastecimento),
    }


def _empty_trecho_mapping():
    data = {
        key: ""
        for key in [
            "{{trecho_data_saida}}",
            "{{trecho.data_saida}}",
            "{{trecho_hora_saida}}",
            "{{trecho.hora_saida}}",
            "{{trecho_km_inicial}}",
            "{{trecho.km_inicial}}",
            "{{trecho_data_chegada}}",
            "{{trecho.data_chegada}}",
            "{{trecho_hora_chegada}}",
            "{{trecho.hora_chegada}}",
            "{{trecho_km_final}}",
            "{{trecho.km_final}}",
            "{{trecho_origem}}",
            "{{trecho.origem}}",
            "{{trecho_destino}}",
            "{{trecho.destino}}",
            "{{trecho_abastecimento}}",
            "{{trecho.abastecimento}}",
        ]
    }
    data["{{trecho_origem}}"] = "SEM TRECHOS CADASTRADOS"
    data["{{trecho.origem}}"] = "SEM TRECHOS CADASTRADOS"
    return data


def _populate_row_from_mapping(row, shared, mapping):
    for cell in row.findall("x:c", NS):
        text = _cell_text(cell, shared)
        if "{{" not in text:
            continue
        replaced = text
        for placeholder, value in mapping.items():
            replaced = replaced.replace(placeholder, value)
        _set_inline_string(cell, replaced)


def _parse_merge_ref(ref):
    cells = ref.split(":")
    if len(cells) == 1:
        cells = [cells[0], cells[0]]
    rows = [int(re.search(r"\d+", cell).group(0)) for cell in cells]
    return cells, rows


def _row_ref_from_template(ref, template_row, new_row):
    return re.sub(rf"(?<=[A-Z]){template_row}\b", str(new_row), ref)


def _update_merge_cells(sheet_root, template_row, generated_rows, delta):
    merge_cells = sheet_root.find("x:mergeCells", NS)
    if merge_cells is None:
        return
    original = list(merge_cells.findall("x:mergeCell", NS))
    for merge in original:
        ref = merge.attrib.get("ref", "")
        _cells, rows = _parse_merge_ref(ref)
        if rows[0] == template_row and rows[1] == template_row:
            merge_cells.remove(merge)
            for row_number in generated_rows:
                new_merge = copy.deepcopy(merge)
                new_merge.set("ref", _row_ref_from_template(ref, template_row, row_number))
                merge_cells.append(new_merge)
        else:
            merge.set("ref", _shift_cell_ref(ref, template_row, delta))
    merge_cells.set("count", str(len(merge_cells.findall("x:mergeCell", NS))))


def _configure_print_settings(sheet_root):
    sheet_pr = sheet_root.find("x:sheetPr", NS)
    if sheet_pr is None:
        sheet_pr = ET.Element(f"{{{SHEET_NS}}}sheetPr")
        sheet_root.insert(0, sheet_pr)
    page_setup_pr = sheet_pr.find("x:pageSetUpPr", NS)
    if page_setup_pr is None:
        page_setup_pr = ET.SubElement(sheet_pr, f"{{{SHEET_NS}}}pageSetUpPr")
    page_setup_pr.set("fitToPage", "1")

    page_setup = sheet_root.find("x:pageSetup", NS)
    if page_setup is None:
        page_setup = ET.SubElement(sheet_root, f"{{{SHEET_NS}}}pageSetup")
    page_setup.set("fitToWidth", "1")
    page_setup.set("fitToHeight", "0")


def limpar_bordas_indevidas_diario_bordo(sheet_root):
    """
    Remove apenas gridlines de visualizacao/impressao.
    Nao aplica bordas novas e preserva as bordas do template oficial.
    """
    sheet_views = sheet_root.find("x:sheetViews", NS)
    if sheet_views is not None:
        for sheet_view in sheet_views.findall("x:sheetView", NS):
            sheet_view.set("showGridLines", "0")

    print_options = sheet_root.find("x:printOptions", NS)
    if print_options is None:
        print_options = ET.SubElement(sheet_root, f"{{{SHEET_NS}}}printOptions")
    print_options.set("gridLines", "0")
    print_options.set("gridLinesSet", "0")


def render_trechos_diario_bordo(sheet_root, shared_strings, diario):
    sheet_data = sheet_root.find("x:sheetData", NS)
    if sheet_data is None:
        raise ValidationError("Tabela de trechos do Diário de Bordo não encontrada.")
    rows = list(sheet_data.findall("x:row", NS))
    template_row = None
    for row in rows:
        row_text = " ".join(_cell_text(cell, shared_strings) for cell in row.findall("x:c", NS))
        if "{{trecho_data_saida}}" in row_text or "{{trecho.data_saida}}" in row_text:
            template_row = row
            break
    if template_row is None:
        raise ValidationError("Linha modelo dos trechos não encontrada no Diário de Bordo.")

    template_index = list(sheet_data).index(template_row)
    template_number = int(template_row.attrib.get("r", "0"))
    trechos = list(diario.trechos.order_by("ordem", "id"))
    mappings = [_trecho_mapping(trecho) for trecho in trechos] or [_empty_trecho_mapping()]
    generated_rows = []
    delta = len(mappings) - 1

    for row in rows:
        row_number = int(row.attrib.get("r", "0"))
        if row_number > template_number:
            row.set("r", str(row_number + delta))
            for cell in row.findall("x:c", NS):
                old_ref = cell.attrib.get("r", "")
                cell.set("r", _shift_cell_ref(old_ref, template_number, delta))
                formula = cell.find("x:f", NS)
                if formula is not None and formula.text:
                    formula.text = _replace_row_number_in_formula(formula.text, row_number, row_number + delta)

    for offset, mapping in enumerate(mappings):
        new_row = copy.deepcopy(template_row)
        row_number = template_number + offset
        new_row.set("r", str(row_number))
        for cell in new_row.findall("x:c", NS):
            _set_cell_ref(cell, row_number)
        _populate_row_from_mapping(new_row, shared_strings, mapping)
        generated_rows.append(new_row)

    sheet_data.remove(template_row)
    for offset, row in enumerate(generated_rows):
        sheet_data.insert(template_index + offset, row)

    _update_merge_cells(sheet_root, template_number, [int(row.attrib["r"]) for row in generated_rows], delta)


def _fixed_mapping(diario):
    oficio = diario.numero_oficio or ""
    numero, ano = (oficio.split("/", 1) + [""])[:2] if "/" in oficio else (oficio, "")
    return {
        "divisao": diario.divisao or "",
        "unidade_cabecalho": diario.unidade_cabecalho or "",
        "oficio_motorista": numero,
        "ano": ano,
        "protocolo_motorista": diario.e_protocolo or "",
        "viatura": diario.tipo_veiculo or "",
        "combustivel": diario.combustivel or "",
        "placa": diario.placa_oficial or "",
        "placa_reservada": diario.placa_reservada or "",
        "motorista": diario.nome_responsavel or "",
        "rg_motorista": diario.rg_responsavel or "",
    }


def _validate_no_placeholders(xlsx_bytes):
    leftovers = set()
    with ZipFile(BytesIO(xlsx_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            text = zf.read(name).decode("utf-8", errors="ignore")
            leftovers.update(PLACEHOLDER_RE.findall(text))
    if leftovers:
        raise ValidationError("Placeholders não substituídos no Diário de Bordo: " + ", ".join(sorted(leftovers)))


def render_xlsx_diario_bordo(diario: DiarioBordo):
    if not XLSX_TEMPLATE_PATH.exists():
        raise ValidationError(f"Template XLSX do Diário de Bordo não encontrado: {XLSX_TEMPLATE_PATH}")
    output = BytesIO()
    with ZipFile(XLSX_TEMPLATE_PATH, "r") as zin, ZipFile(output, "w", ZIP_DEFLATED) as zout:
        shared_root = ET_fromstring(zin.read("xl/sharedStrings.xml"))
        _replace_fixed_placeholders_in_shared_strings(shared_root, _fixed_mapping(diario))
        shared = _shared_strings(shared_root)
        sheet_names = [name for name in zin.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
        target_sheet = sheet_names[0]
        sheet_root = ET_fromstring(zin.read(target_sheet))
        render_trechos_diario_bordo(sheet_root, shared, diario)
        _configure_print_settings(sheet_root)
        limpar_bordas_indevidas_diario_bordo(sheet_root)
        _clear_dynamic_placeholders_in_shared_strings(shared_root)
        for item in zin.infolist():
            if item.filename == "xl/sharedStrings.xml":
                zout.writestr(item, ET_tostring(shared_root))
            elif item.filename == target_sheet:
                zout.writestr(item, ET_tostring(sheet_root))
            else:
                zout.writestr(item, zin.read(item.filename))
    xlsx_bytes = output.getvalue()
    _validate_no_placeholders(xlsx_bytes)
    return xlsx_bytes


def _nome_base_arquivo(diario: DiarioBordo):
    referencia = diario.numero_oficio or str(diario.pk or "avulso")
    referencia = referencia.replace("/", "_").replace("\\", "_")
    referencia = re.sub(r"[^A-Za-z0-9_-]+", "_", referencia).strip("_").lower()
    return f"diario_bordo_oficio_{referencia or diario.pk or 'avulso'}"


def gerar_diario_bordo_xlsx(diario: DiarioBordo):
    if not diario.trechos.exists():
        raise ValidationError("Nenhum trecho cadastrado. Preencha o Step 3 antes de gerar o XLSX/PDF.")
    xlsx_bytes = render_xlsx_diario_bordo(diario)
    filename = f"{_nome_base_arquivo(diario)}_{timezone.localdate():%Y%m%d}.xlsx"
    diario.arquivo_xlsx.save(filename, ContentFile(xlsx_bytes), save=False)
    diario.status = DiarioBordo.STATUS_GERADO
    diario.save(update_fields=["arquivo_xlsx", "status", "atualizado_em"])
    return xlsx_bytes, filename



def _converter_xlsx_com_excel(xlsx_path: Path, pdf_path: Path):
    if not sys.platform.startswith("win"):
        return False
    try:
        import win32com.client  # type: ignore
        import pythoncom  # type: ignore
    except ImportError:
        return False

    excel = None
    workbook = None
    com_initialized = False
    try:
        # Django pode executar requests em threads; COM precisa ser inicializado por thread.
        pythoncom.CoInitialize()
        com_initialized = True
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(xlsx_path))
        for worksheet in workbook.Worksheets:
            worksheet.PageSetup.PrintGridlines = False
        workbook.ExportAsFixedFormat(0, str(pdf_path))
        return pdf_path.exists()
    finally:
        if workbook is not None:
            workbook.Close(False)
        if excel is not None:
            excel.Quit()
        if com_initialized:
            pythoncom.CoUninitialize()


def _converter_xlsx_com_libreoffice(xlsx_path: Path, pdf_path: Path):
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        return False
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            executable,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(pdf_path.parent),
            str(xlsx_path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    generated = pdf_path.parent / f"{xlsx_path.stem}.pdf"
    if generated.exists() and generated != pdf_path:
        generated.replace(pdf_path)
    return pdf_path.exists()


def converter_xlsx_para_pdf(xlsx_path, pdf_path):
    xlsx_path = Path(xlsx_path)
    pdf_path = Path(pdf_path)
    if not xlsx_path.exists():
        raise ValidationError("XLSX preenchido do Diario de Bordo nao encontrado para conversao em PDF.")

    errors = []
    for converter in (_converter_xlsx_com_excel, _converter_xlsx_com_libreoffice):
        try:
            if converter(xlsx_path, pdf_path):
                return pdf_path
        except Exception as exc:
            errors.append(f"{converter.__name__}: {exc}")
            continue
    details = " | ".join(errors) if errors else "nenhum backend retornou sucesso"
    raise ValidationError(
        "Nao foi possivel converter o XLSX do Diario de Bordo para PDF. "
        f"Detalhes: {details}. Verifique se Excel/LibreOffice esta disponivel."
    )


def gerar_diario_bordo_pdf(diario: DiarioBordo):
    xlsx_bytes, _xlsx_filename = gerar_diario_bordo_xlsx(diario)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        xlsx_path = temp_dir / f"{_nome_base_arquivo(diario)}.xlsx"
        pdf_path = temp_dir / f"{_nome_base_arquivo(diario)}.pdf"
        xlsx_path.write_bytes(xlsx_bytes)
        converter_xlsx_para_pdf(xlsx_path, pdf_path)
        pdf_bytes = pdf_path.read_bytes()

    filename = f"{_nome_base_arquivo(diario)}_{timezone.localdate():%Y%m%d}.pdf"
    diario.arquivo_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    diario.status = DiarioBordo.STATUS_GERADO
    diario.save(update_fields=["arquivo_pdf", "status", "atualizado_em"])
    return pdf_bytes, filename


gerar_xlsx_diario = gerar_diario_bordo_xlsx
gerar_pdf_diario = gerar_diario_bordo_pdf


def _cidade_label(cidade=None, estado=None):
    if cidade:
        uf = getattr(getattr(cidade, "estado", None), "sigla", "") or getattr(estado, "sigla", "")
        return f"{cidade.nome}/{uf}" if uf else cidade.nome
    if estado:
        return getattr(estado, "sigla", "") or str(estado)
    return ""


def _build_trecho_payload(
    *,
    ordem,
    data_saida=None,
    hora_saida=None,
    data_chegada=None,
    hora_chegada=None,
    km_inicial=None,
    km_final=None,
    origem="",
    destino="",
    necessidade_abastecimento=False,
):
    return {
        "ordem": ordem,
        "data_saida": data_saida,
        "hora_saida": hora_saida,
        "km_inicial": km_inicial,
        "data_chegada": data_chegada,
        "hora_chegada": hora_chegada,
        "km_final": km_final,
        "origem": (origem or "").strip() or "Origem",
        "destino": (destino or "").strip() or "Destino",
        "necessidade_abastecimento": bool(necessidade_abastecimento),
    }


def _fallback_payloads_from_roteiro(roteiro):
    origem_base = _cidade_label(getattr(roteiro, "origem_cidade", None), getattr(roteiro, "origem_estado", None))
    destinos = list(roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "id"))
    destino_labels = [_cidade_label(destino.cidade, destino.estado) for destino in destinos if _cidade_label(destino.cidade, destino.estado)]
    if not origem_base or not destino_labels:
        return []

    payloads = []
    saida_dt = getattr(roteiro, "saida_dt", None)
    chegada_dt = getattr(roteiro, "chegada_dt", None)
    retorno_saida_dt = getattr(roteiro, "retorno_saida_dt", None)
    retorno_chegada_dt = getattr(roteiro, "retorno_chegada_dt", None)

    atual = origem_base
    for ordem, destino_label in enumerate(destino_labels):
        payloads.append(
            _build_trecho_payload(
                ordem=ordem,
                data_saida=saida_dt.date() if ordem == 0 and saida_dt else None,
                hora_saida=saida_dt.time() if ordem == 0 and saida_dt else None,
                data_chegada=chegada_dt.date() if ordem == len(destino_labels) - 1 and chegada_dt else None,
                hora_chegada=chegada_dt.time() if ordem == len(destino_labels) - 1 and chegada_dt else None,
                origem=atual,
                destino=destino_label,
            )
        )
        atual = destino_label

    payloads.append(
        _build_trecho_payload(
            ordem=len(payloads),
            data_saida=retorno_saida_dt.date() if retorno_saida_dt else (chegada_dt.date() if chegada_dt else None),
            hora_saida=retorno_saida_dt.time() if retorno_saida_dt else None,
            data_chegada=retorno_chegada_dt.date() if retorno_chegada_dt else None,
            hora_chegada=retorno_chegada_dt.time() if retorno_chegada_dt else None,
            origem=atual,
            destino=origem_base,
        )
    )
    return payloads


def _payloads_from_roteiro_trechos(roteiro):
    trechos = list(roteiro.trechos.select_related("origem_cidade", "origem_estado", "destino_cidade", "destino_estado").order_by("ordem", "id"))
    payloads = []
    for idx, trecho in enumerate(trechos):
        saida_dt = getattr(trecho, "saida_dt", None)
        chegada_dt = getattr(trecho, "chegada_dt", None)
        payloads.append(
            _build_trecho_payload(
                ordem=idx,
                data_saida=saida_dt.date() if saida_dt else None,
                hora_saida=saida_dt.time() if saida_dt else None,
                data_chegada=chegada_dt.date() if chegada_dt else None,
                hora_chegada=chegada_dt.time() if chegada_dt else None,
                km_inicial=int(trecho.distancia_km) if getattr(trecho, "distancia_km", None) and idx == 0 else None,
                origem=_cidade_label(trecho.origem_cidade, trecho.origem_estado),
                destino=_cidade_label(trecho.destino_cidade, trecho.destino_estado),
            )
        )
    return payloads


def _payloads_from_oficio_trechos(oficio):
    trechos = list(oficio.trechos.select_related("origem_cidade", "origem_estado", "destino_cidade", "destino_estado").order_by("ordem", "id"))
    payloads = []
    for idx, trecho in enumerate(trechos):
        payloads.append(
            _build_trecho_payload(
                ordem=idx,
                data_saida=trecho.saida_data,
                hora_saida=trecho.saida_hora,
                data_chegada=trecho.chegada_data,
                hora_chegada=trecho.chegada_hora,
                origem=_cidade_label(trecho.origem_cidade, trecho.origem_estado),
                destino=_cidade_label(trecho.destino_cidade, trecho.destino_estado),
            )
        )
    if payloads:
        return payloads

    origem = _cidade_label(getattr(oficio, "cidade_sede", None), getattr(oficio, "estado_sede", None))
    destino = (getattr(oficio, "destinos_formatados_display", "") or "").split(",")[0].strip()
    if origem and destino and (oficio.retorno_chegada_data or oficio.retorno_saida_data):
        ida = _build_trecho_payload(
            ordem=0,
            data_saida=oficio.data_criacao,
            origem=origem,
            destino=destino,
        )
        volta = _build_trecho_payload(
            ordem=1,
            data_saida=oficio.retorno_saida_data or oficio.retorno_chegada_data,
            hora_saida=oficio.retorno_saida_hora,
            data_chegada=oficio.retorno_chegada_data,
            hora_chegada=oficio.retorno_chegada_hora,
            origem=destino,
            destino=origem,
        )
        return [ida, volta]
    return []


def _descobrir_payloads_trechos(diario):
    if diario.roteiro_id:
        payloads = _payloads_from_roteiro_trechos(diario.roteiro)
        if payloads:
            return payloads
        payloads = _fallback_payloads_from_roteiro(diario.roteiro)
        if payloads:
            return payloads

    oficio = diario.oficio
    if oficio is None and diario.prestacao_id and diario.prestacao and diario.prestacao.oficio_id:
        oficio = diario.prestacao.oficio

    if oficio and getattr(oficio, "roteiro_evento_id", None):
        payloads = _payloads_from_roteiro_trechos(oficio.roteiro_evento)
        if payloads:
            return payloads
        payloads = _fallback_payloads_from_roteiro(oficio.roteiro_evento)
        if payloads:
            return payloads

    if oficio:
        payloads = _payloads_from_oficio_trechos(oficio)
        if payloads:
            return payloads

    return []


@transaction.atomic
def inicializar_trechos_diario_bordo(diario, force=False):
    existentes = diario.trechos.order_by("ordem", "id")
    if existentes.exists() and not force:
        return list(existentes), False
    if force:
        diario.trechos.all().delete()

    payloads = _descobrir_payloads_trechos(diario)
    criados = []
    for idx, data in enumerate(payloads):
        criados.append(
            DiarioBordoTrecho.objects.create(
                diario=diario,
                ordem=idx,
                data_saida=data.get("data_saida"),
                hora_saida=data.get("hora_saida"),
                km_inicial=data.get("km_inicial"),
                data_chegada=data.get("data_chegada"),
                hora_chegada=data.get("hora_chegada"),
                km_final=data.get("km_final"),
                origem=data.get("origem") or "Origem",
                destino=data.get("destino") or "Destino",
                necessidade_abastecimento=data.get("necessidade_abastecimento", False),
            )
        )
    return criados, bool(criados)
