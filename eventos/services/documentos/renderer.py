from io import BytesIO
import importlib
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .backends import _load_docx_backend, _load_pdf_backend
from .types import (
    DocumentoFormato,
    DocumentoOficioTipo,
    DocumentFormatNotAvailable,
    DocumentRendererUnavailable,
    DocumentTemplateUnavailable,
    DocumentTypeNotImplemented,
    DocumentValidationError,
    get_document_type_meta,
)
from .validators import validate_oficio_for_document_generation


PLACEHOLDER_RE = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')
TEMPLATE_FILENAMES = {
    DocumentoOficioTipo.OFICIO: 'oficio_model.docx',
    DocumentoOficioTipo.JUSTIFICATIVA: 'modelo_justificativa.docx',
    DocumentoOficioTipo.PLANO_TRABALHO: 'modelo_plano_de_trabalho.docx',
    DocumentoOficioTipo.TERMO_AUTORIZACAO: 'termo_autorizacao.docx',
    DocumentoOficioTipo.ORDEM_SERVICO: 'modelo_ordem_servico.docx',
}
TERMO_AUTORIZACAO_TEMPLATE_VARIANTS = {
    'COMPLETO_COM_VIATURA': 'termo_autorizacao_automatico.docx',
    'COMPLETO_SEM_VIATURA': 'termo_autorizacao_automatico_sem_viatura.docx',
    'SEMIPREENCHIDO': 'termo_autorizacao.docx',
}


def _get_docx_symbols():
    docx_module, enum_text_module, shared_module = _load_docx_backend()
    return (
        docx_module.Document,
        enum_text_module.WD_ALIGN_PARAGRAPH,
        shared_module.Cm,
        shared_module.Pt,
    )


def create_base_document(title, subtitle=''):
    Document, WD_ALIGN_PARAGRAPH, Cm, Pt = _get_docx_symbols()
    document = Document()
    section = document.sections[0]
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.0)

    normal_style = document.styles['Normal']
    normal_style.font.name = 'Arial'
    normal_style.font.size = Pt(11)

    title_paragraph = document.add_paragraph()
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_paragraph.add_run(title)
    run.bold = True
    run.font.size = Pt(14)

    if subtitle:
        subtitle_paragraph = document.add_paragraph()
        subtitle_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        subtitle_run = subtitle_paragraph.add_run(subtitle)
        subtitle_run.font.size = Pt(11)

    return document


def add_section_heading(document, text):
    _, _, _, Pt = _get_docx_symbols()
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(11)


def add_label_value(document, label, value):
    paragraph = document.add_paragraph()
    label_run = paragraph.add_run(f'{label}: ')
    label_run.bold = True
    paragraph.add_run(value or '—')


def add_multiline_value(document, label, value):
    add_section_heading(document, label)
    document.add_paragraph(value or '—')


def add_simple_table(document, headers, rows):
    if not rows:
        return
    table = document.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    header_cells = table.rows[0].cells
    for idx, header in enumerate(headers):
        header_cells[idx].text = header
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            cells[idx].text = str(value or '—')


def add_bullet_list(document, title, items, empty_text='—'):
    add_section_heading(document, title)
    if not items:
        document.add_paragraph(empty_text)
        return
    for item in items:
        document.add_paragraph(item, style='List Bullet')


def add_signature_blocks(document, assinaturas):
    if not assinaturas:
        return
    _, WD_ALIGN_PARAGRAPH, _, _ = _get_docx_symbols()
    add_section_heading(document, 'Assinaturas')
    for assinatura in assinaturas:
        document.add_paragraph('')
        line = document.add_paragraph('_' * 55)
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        nome = document.add_paragraph(assinatura.get('nome') or '—')
        nome.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cargo = document.add_paragraph(assinatura.get('cargo') or '')
        cargo.alignment = WD_ALIGN_PARAGRAPH.CENTER


def document_to_bytes(document):
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _get_template_root():
    return Path(__file__).resolve().parents[2] / 'resources' / 'documentos'


def get_document_template_path(tipo_documento):
    meta = get_document_type_meta(tipo_documento)
    filename = TEMPLATE_FILENAMES.get(meta.tipo)
    if not filename:
        raise DocumentTemplateUnavailable(
            'Nenhum modelo DOCX versionado foi definido para este documento nesta fase.'
        )
    template_path = _get_template_root() / filename
    if not template_path.exists():
        raise DocumentTemplateUnavailable(
            f'Modelo DOCX não encontrado para {meta.label}: {template_path.name}.'
        )
    return template_path


def get_termo_autorizacao_template_path(variant):
    filename = TERMO_AUTORIZACAO_TEMPLATE_VARIANTS.get((variant or '').strip().upper())
    if not filename:
        raise DocumentTemplateUnavailable(
            f'Variante de template de termo inválida: {variant!r}.'
        )
    template_path = _get_template_root() / filename
    if not template_path.exists():
        raise DocumentTemplateUnavailable(
            f'Modelo DOCX não encontrado para Termo de autorização: {template_path.name}.'
        )
    return template_path


def get_termo_autorizacao_templates_availability():
    missing = []
    for variant in TERMO_AUTORIZACAO_TEMPLATE_VARIANTS:
        try:
            get_termo_autorizacao_template_path(variant)
        except DocumentTemplateUnavailable as exc:
            missing.append(str(exc))
    return {
        'available': len(missing) == 0,
        'errors': missing,
    }


def get_document_template_availability(tipo_documento):
    meta = get_document_type_meta(tipo_documento)
    if meta.tipo not in TEMPLATE_FILENAMES:
        return {
            'available': True,
            'message': '',
        }
    try:
        get_document_template_path(meta.tipo)
    except DocumentTemplateUnavailable as exc:
        return {
            'available': False,
            'message': str(exc),
        }
    return {
        'available': True,
        'message': '',
    }


def _sanitize_mapping_values(mapping):
    sanitized = {}
    for key, value in (mapping or {}).items():
        text = '' if value is None else str(value)
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        sanitized[str(key)] = text
    return sanitized


def replace_paragraph_text(paragraph, new_text):
    safe_text = (new_text or '').replace('\r\n', '\n').replace('\r', '\n')
    if not paragraph.runs:
        paragraph.add_run(safe_text)
        return
    paragraph.runs[0].text = safe_text
    for run in paragraph.runs[1:]:
        run.text = ''


def _iter_paragraphs_from_table(table):
    for row in table.rows:
        for cell in row.cells:
            yield from _iter_paragraphs_from_container(cell)


def _iter_paragraphs_from_container(container):
    for paragraph in getattr(container, 'paragraphs', []):
        yield paragraph
    for table in getattr(container, 'tables', []):
        yield from _iter_paragraphs_from_table(table)


def iter_all_paragraphs(document):
    yield from _iter_paragraphs_from_container(document)
    for section in getattr(document, 'sections', []):
        yield from _iter_paragraphs_from_container(section.header)
        yield from _iter_paragraphs_from_container(section.footer)


def extract_placeholders_from_doc(document):
    placeholders = set()
    for paragraph in iter_all_paragraphs(document):
        full_text = ''.join(run.text for run in paragraph.runs)
        if '{{' not in full_text:
            continue
        for match in PLACEHOLDER_RE.finditer(full_text):
            key = ' '.join((match.group(1) or '').split()).strip()
            if key:
                placeholders.add(key)
    return placeholders


def _replace_placeholders_across_runs(paragraph, mapping):
    full_text = ''.join(run.text for run in paragraph.runs)
    if '{{' not in full_text:
        return

    spans = []
    for match in PLACEHOLDER_RE.finditer(full_text):
        key = ' '.join((match.group(1) or '').split()).strip()
        spans.append((match.start(), match.end(), mapping.get(key, '')))
    if not spans:
        return

    run_bounds = []
    cursor = 0
    for run in paragraph.runs:
        start = cursor
        cursor += len(run.text)
        run_bounds.append((start, cursor))

    for start, end, value in reversed(spans):
        first_idx = None
        last_idx = None
        for idx, (run_start, run_end) in enumerate(run_bounds):
            if run_start <= start < run_end and first_idx is None:
                first_idx = idx
            if run_start < end <= run_end:
                last_idx = idx
                break
        if first_idx is None or last_idx is None:
            continue

        if first_idx == last_idx:
            run = paragraph.runs[first_idx]
            run_start, _ = run_bounds[first_idx]
            left = run.text[: start - run_start]
            right = run.text[end - run_start :]
            run.text = f'{left}{value}{right}'
            continue

        first_run = paragraph.runs[first_idx]
        first_run_start, _ = run_bounds[first_idx]
        prefix = first_run.text[: start - first_run_start]
        first_run.text = f'{prefix}{value}'

        for idx in range(first_idx + 1, last_idx):
            paragraph.runs[idx].text = ''

        last_run = paragraph.runs[last_idx]
        last_run_start, _ = run_bounds[last_idx]
        suffix = last_run.text[end - last_run_start :]
        last_run.text = suffix


def replace_placeholders_in_paragraph(paragraph, mapping):
    full_text = ''.join(run.text for run in paragraph.runs)
    if '{{' not in full_text:
        return

    changed = False
    for run in paragraph.runs:
        if '{{' not in run.text:
            continue
        new_text = PLACEHOLDER_RE.sub(
            lambda match: mapping.get(' '.join((match.group(1) or '').split()).strip(), ''),
            run.text,
        )
        if new_text != run.text:
            run.text = new_text
            changed = True

    if not changed or '{{' in ''.join(run.text for run in paragraph.runs):
        _replace_placeholders_across_runs(paragraph, mapping)


def safe_replace_placeholders(document, mapping):
    safe_mapping = _sanitize_mapping_values(mapping)
    for paragraph in iter_all_paragraphs(document):
        replace_placeholders_in_paragraph(paragraph, safe_mapping)


def render_docx_template_bytes(template_path, mapping, post_processor=None):
    Document, _, _, _ = _get_docx_symbols()
    document = Document(str(template_path))
    template_placeholders = extract_placeholders_from_doc(document)
    safe_mapping = {key: _sanitize_mapping_values(mapping).get(key, '') for key in template_placeholders}
    safe_replace_placeholders(document, safe_mapping)
    if post_processor is not None:
        post_processor(document)
    return document_to_bytes(document)


def _convert_via_word_com(docx_path, pdf_path):
    pythoncom = importlib.import_module('pythoncom')
    win32_client = importlib.import_module('win32com.client')
    word = None
    opened_doc = None
    pythoncom.CoInitialize()
    try:
        word = win32_client.gencache.EnsureDispatch('Word.Application')
        word.Visible = False
        if hasattr(word, 'DisplayAlerts'):
            word.DisplayAlerts = 0
        opened_doc = word.Documents.Open(str(docx_path))
        try:
            try:
                opened_doc.SaveAs(str(pdf_path), FileFormat=17)
            except Exception:
                opened_doc.SaveAs2(str(pdf_path), FileFormat=17)
        finally:
            opened_doc.Close(False)
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def convert_docx_bytes_to_pdf_bytes(docx_bytes):
    docx2pdf_module = _load_pdf_backend()
    with TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        docx_path = base_dir / 'documento.docx'
        pdf_path = base_dir / 'documento.pdf'
        docx_path.write_bytes(docx_bytes)
        try:
            docx2pdf_module.convert(str(docx_path), str(pdf_path))
        except Exception as docx2pdf_exc:
            if os.name != 'nt':
                raise DocumentRendererUnavailable(
                    f'Falha na conversão DOCX para PDF neste ambiente Windows: {docx2pdf_exc}'
                ) from docx2pdf_exc
            try:
                _convert_via_word_com(docx_path, pdf_path)
            except Exception as com_exc:
                raise DocumentRendererUnavailable(
                    'Falha na conversão DOCX para PDF neste ambiente Windows: '
                    f'{docx2pdf_exc} | fallback COM: {com_exc}'
                ) from com_exc
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise DocumentRendererUnavailable(
                'A conversão DOCX para PDF não gerou um arquivo PDF válido.'
            )
        return pdf_path.read_bytes()


def _render_document_docx_bytes(oficio, tipo_documento):
    meta = get_document_type_meta(tipo_documento)
    if meta.tipo == DocumentoOficioTipo.OFICIO:
        from .oficio import render_oficio_docx

        return render_oficio_docx(oficio)
    if meta.tipo == DocumentoOficioTipo.JUSTIFICATIVA:
        from .justificativa import render_justificativa_docx

        return render_justificativa_docx(oficio)
    if meta.tipo == DocumentoOficioTipo.TERMO_AUTORIZACAO:
        from .termo_autorizacao import render_termo_autorizacao_docx

        return render_termo_autorizacao_docx(oficio)
    if meta.tipo == DocumentoOficioTipo.PLANO_TRABALHO:
        from .plano_trabalho import render_plano_trabalho_docx

        return render_plano_trabalho_docx(oficio)
    if meta.tipo == DocumentoOficioTipo.ORDEM_SERVICO:
        from .ordem_servico import render_ordem_servico_docx

        return render_ordem_servico_docx(oficio)
    raise DocumentTypeNotImplemented('Tipo documental ainda não implementado nesta fase.')


def render_document_bytes(oficio, tipo_documento, formato):
    meta = get_document_type_meta(tipo_documento)
    formato = DocumentoFormato(formato)

    validation = validate_oficio_for_document_generation(oficio, meta.tipo)
    if not validation['ok']:
        raise DocumentValidationError(validation['errors'][0])

    if formato == DocumentoFormato.DOCX:
        return _render_document_docx_bytes(oficio, meta.tipo)
    if formato == DocumentoFormato.PDF:
        docx_bytes = _render_document_docx_bytes(oficio, meta.tipo)
        return convert_docx_bytes_to_pdf_bytes(docx_bytes)
    raise DocumentFormatNotAvailable(
        f'Formato {formato.value.upper()} ainda não está disponível nesta fase.'
    )
