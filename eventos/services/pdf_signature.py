from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from reportlab.pdfgen import canvas
from django.conf import settings
import requests

logger = logging.getLogger(__name__)

FONT_CATALOG = {
    'great_vibes': {
        'reportlab_name': 'SignGreatVibes',
        'filename': 'GreatVibes-Regular.ttf',
        'download_url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/greatvibes/GreatVibes-Regular.ttf',
    },
    'alex_brush': {
        'reportlab_name': 'SignAlexBrush',
        'filename': 'AlexBrush-Regular.ttf',
        'download_url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/alexbrush/AlexBrush-Regular.ttf',
    },
    'pinyon_script': {
        'reportlab_name': 'SignPinyonScript',
        'filename': 'PinyonScript-Regular.ttf',
        'download_url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/pinyonscript/PinyonScript-Regular.ttf',
    },
    'allura': {
        'reportlab_name': 'SignAllura',
        'filename': 'Allura-Regular.ttf',
        'download_url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/allura/Allura-Regular.ttf',
    },
    'arizonia': {
        'reportlab_name': 'SignArizonia',
        'filename': 'Arizonia-Regular.ttf',
        'download_url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/arizonia/Arizonia-Regular.ttf',
    },
    'monsieur_la_doulaise': {
        'reportlab_name': 'SignMonsieurLaDoulaise',
        'filename': 'MonsieurLaDoulaise-Regular.ttf',
        'download_url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/monsieurladoulaise/MonsieurLaDoulaise-Regular.ttf',
    },
}

FALLBACK_FONT_NAME = 'Helvetica-Oblique'


def _signature_fonts_dir() -> Path:
    return Path(settings.BASE_DIR) / 'eventos' / 'resources' / 'assinatura_fonts'


def _ensure_font_file(font_key: str, filename: str, download_url: str) -> Path:
    fonts_dir = _signature_fonts_dir()
    fonts_dir.mkdir(parents=True, exist_ok=True)
    font_path = fonts_dir / filename
    if font_path.exists() and font_path.stat().st_size > 0:
        return font_path
    response = requests.get(download_url, timeout=20)
    response.raise_for_status()
    font_path.write_bytes(response.content)
    return font_path


def resolve_signature_font(font_key: str) -> tuple[str, bool, str]:
    """Resolve e registra a fonte real para assinatura.

    Retorna (nome_reportlab, usou_fallback, detalhe).
    """
    spec = FONT_CATALOG.get(font_key)
    if not spec:
        detail = f'fonte desconhecida "{font_key}"'
        logger.warning('Assinatura PDF em fallback: %s', detail)
        return FALLBACK_FONT_NAME, True, detail
    reportlab_name = spec['reportlab_name']
    if reportlab_name in pdfmetrics.getRegisteredFontNames():
        return reportlab_name, False, 'fonte já registrada'
    try:
        font_path = _ensure_font_file(font_key, spec['filename'], spec['download_url'])
        pdfmetrics.registerFont(TTFont(reportlab_name, str(font_path)))
        return reportlab_name, False, f'fonte registrada de {font_path.name}'
    except (requests.RequestException, OSError, TTFError) as exc:
        detail = f'erro ao registrar {font_key}: {exc}'
        logger.warning('Assinatura PDF em fallback: %s', detail)
        return FALLBACK_FONT_NAME, True, detail


def assert_font_supports_signature(font_key: str) -> tuple[str, str]:
    font_name, used_fallback, detail = resolve_signature_font(font_key)
    if used_fallback:
        raise ValueError(f'Não foi possível carregar a fonte "{font_key}": {detail}')
    return font_name, detail


def _append_pdf(target_writer: PdfWriter, pdf_bytes: bytes):
    reader = PdfReader(BytesIO(pdf_bytes))
    for page in reader.pages:
        target_writer.add_page(page)


def build_validation_page_pdf(payload: dict) -> bytes:
    width, height = A4
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=A4)
    c.setTitle('Validação de assinatura eletrônica')
    c.setStrokeColor(HexColor('#334155'))
    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(34, 34, width - 68, height - 68, 8, stroke=1, fill=1)
    c.setFillColor(HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 14)
    c.drawString(52, height - 70, 'Validação de assinatura eletrônica')
    c.setFont('Helvetica', 9)
    c.drawString(52, height - 88, 'Página anexa de autenticidade do documento assinado')

    labels = [
        ('Documento', payload.get('nome_documento', 'Ofício')),
        ('Identificador', payload.get('identificador_oficio', 'Não informado')),
        ('Protocolo', payload.get('protocolo', 'Não informado')),
        ('Assinante', payload.get('nome_assinante', 'Não informado')),
        ('CPF mascarado', payload.get('cpf_mascarado', 'Não informado')),
        ('Assinado em', payload.get('assinado_em', 'Não informado')),
        ('Local', payload.get('local_assinatura', 'Não informado')),
        ('Confirmação', payload.get('confirmacao_identidade', 'Não informado')),
        ('Inserido por', payload.get('criado_por_nome', 'Não informado')),
        ('Pedido criado em', payload.get('pedido_criado_em', 'Não informado')),
        ('Hash do documento', payload.get('hash_documento', '')),
        ('Código de validação', payload.get('codigo_validacao', '')),
        ('URL de verificação', payload.get('url_verificacao', '')),
    ]
    y = height - 122
    c.setFont('Helvetica-Bold', 9)
    for label, value in labels:
        c.drawString(52, y, f'{label}:')
        c.setFont('Helvetica', 9)
        c.drawString(170, y, str(value or 'Não informado')[:110])
        c.setFont('Helvetica-Bold', 9)
        y -= 20

    qr_value = payload.get('url_verificacao', '')
    if qr_value:
        qr_code = qr.QrCodeWidget(qr_value)
        bounds = qr_code.getBounds()
        size = 105
        x = width - 175
        y_qr = 95
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = size / max(w, h)
        drawing = Drawing(size, size, transform=[d, 0, 0, d, 0, 0])
        drawing.add(qr_code)
        renderPDF.draw(drawing, c, x, y_qr)
        c.setFont('Helvetica', 8)
        c.drawString(width - 178, 82, 'Escaneie para validar')

    c.setFont('Helvetica-Oblique', 9)
    c.drawString(52, 58, payload.get('texto_assinatura', 'Documento assinado eletronicamente.'))
    c.drawString(52, 44, 'A autenticidade deste documento pode ser validada no endereço informado acima.')
    c.showPage()
    c.save()
    return stream.getvalue()


def apply_text_signature_on_pdf(
    pdf_bytes: bytes,
    *,
    signer_name: str,
    font_key: str,
    validation_payload: dict | None = None,
    signature_position: dict | None = None,
    strict_font: bool = False,
) -> tuple[bytes, dict]:
    reader = PdfReader(BytesIO(pdf_bytes))
    writer = PdfWriter()
    if not reader.pages:
        return pdf_bytes, {
            'requested_font_key': font_key,
            'resolved_font_name': FALLBACK_FONT_NAME,
            'used_fallback': True,
            'font_detail': 'pdf sem páginas',
        }

    overlay_stream = BytesIO()
    target_page_index = len(reader.pages) - 1
    if isinstance(signature_position, dict):
        raw_idx = signature_position.get('page_index', -1)
        try:
            requested_idx = int(raw_idx)
        except (TypeError, ValueError):
            requested_idx = -1
        if requested_idx < 0:
            target_page_index = len(reader.pages) - 1
        else:
            target_page_index = min(max(requested_idx, 0), len(reader.pages) - 1)
    target_page = reader.pages[target_page_index]
    width = float(target_page.mediabox.width)
    height = float(target_page.mediabox.height)
    if strict_font:
        font_name, font_detail = assert_font_supports_signature(font_key)
        used_fallback = False
    else:
        font_name, used_fallback, font_detail = resolve_signature_font(font_key)

    # Caixa de assinatura em frações da página (origem superior esquerda, como no canvas PDF.js):
    # box_x, box_y: canto superior esquerdo (0–1 da largura/altura).
    # box_w, box_h: largura e altura da caixa (0–1 da página).
    box_x = 0.28
    box_y = 0.82
    box_w = 0.38
    box_h = 0.08
    if isinstance(signature_position, dict):
        try:
            box_x = float(signature_position.get('box_x', signature_position.get('x_ratio', box_x)))
            box_y = float(signature_position.get('box_y', signature_position.get('y_ratio', box_y)))
            box_w = float(signature_position.get('box_w', box_w))
            box_h = float(signature_position.get('box_h', box_h))
        except (TypeError, ValueError):
            pass
    box_w = min(max(box_w, 0.04), 0.95)
    box_h = min(max(box_h, 0.02), 0.4)
    box_x = min(max(box_x, 0.01), 0.99 - box_w)
    box_y = min(max(box_y, 0.01), 0.99 - box_h)

    left = width * box_x
    right = left + width * box_w
    bottom_rl = height - (box_y + box_h) * height
    top_rl = height - box_y * height
    box_h_pt = max(top_rl - bottom_rl, 12.0)

    font_size = min(40.0, max(9.0, box_h_pt * 0.62))
    while font_size > 7.0 and pdfmetrics.stringWidth(signer_name, font_name, font_size) > (right - left) - 6.0:
        font_size -= 0.5
    text_width = pdfmetrics.stringWidth(signer_name, font_name, font_size)
    x_center = left + (right - left) / 2.0
    x = x_center - text_width / 2.0
    margin = 6.0
    x = max(left + margin, min(x, right - text_width - margin))
    baseline_rl = bottom_rl + max(font_size * 0.28, box_h_pt * 0.18)
    baseline_rl = max(margin, min(baseline_rl, top_rl - font_size * 0.05))

    overlay = canvas.Canvas(overlay_stream, pagesize=(width, height))
    overlay.setFillColor(HexColor('#1f2937'))
    overlay.setFont(font_name, font_size)
    overlay.drawString(x, baseline_rl, signer_name)
    overlay.setFont('Helvetica', 9)
    overlay.drawString(x, max(18.0, baseline_rl - 16.0), 'Assinatura eletrônica')
    overlay.save()

    overlay_pdf = PdfReader(BytesIO(overlay_stream.getvalue()))
    overlay_page = overlay_pdf.pages[0]

    for index, page in enumerate(reader.pages):
        if index == target_page_index:
            page.merge_page(overlay_page)
        writer.add_page(page)

    signed_stream = BytesIO()
    writer.write(signed_stream)
    signed_pdf_bytes = signed_stream.getvalue()

    final_pdf_bytes = signed_pdf_bytes
    if validation_payload:
        validation_page_bytes = build_validation_page_pdf(validation_payload)
        merged_writer = PdfWriter()
        _append_pdf(merged_writer, signed_pdf_bytes)
        _append_pdf(merged_writer, validation_page_bytes)
        merged_stream = BytesIO()
        merged_writer.write(merged_stream)
        final_pdf_bytes = merged_stream.getvalue()

    return final_pdf_bytes, {
        'requested_font_key': font_key,
        'resolved_font_name': font_name,
        'used_fallback': used_fallback,
        'font_detail': font_detail,
        'has_validation_page': bool(validation_payload),
        'signature_position': {
            'box_x': box_x,
            'box_y': box_y,
            'box_w': box_w,
            'box_h': box_h,
            'page_index': target_page_index,
        },
    }
