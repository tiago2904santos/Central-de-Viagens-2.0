from __future__ import annotations

import hashlib
import os
import re
import secrets
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pypdf import PdfReader, PdfWriter
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, validation
from pyhanko.stamp import StaticStampStyle
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento


CODIGO_RE = re.compile(r'CV-\d{4}-[A-Z0-9]{6}-[A-Z0-9]{4}')
SISTEMA_ASSINATURA = 'Central de Viagens'
STATUS_PDF_INTEGRA = 'assinatura_pdf_integra'
STATUS_PDF_INVALIDA = 'assinatura_pdf_invalida'
STATUS_PDF_AUSENTE = 'assinatura_pdf_ausente'
STATUS_PDF_CERT_NAO_CONFIAVEL = 'certificado_nao_confiavel'
SIGNATURE_LABEL_WIDTH_PT = 205
SIGNATURE_LABEL_HEIGHT_PT = 70
SIGNATURE_LABEL_QR_PT = 54
SIGNATURE_LABEL_WATERMARK_ALPHA = 0.20
SIGNATURE_LABEL_MIN_BOTTOM_PT = 72


@dataclass(frozen=True)
class DadosCarimbo:
    nome_assinante: str
    cpf_mascarado: str
    data_hora_assinatura: timezone.datetime
    codigo_verificacao: str
    url_validacao: str


@dataclass(frozen=True)
class SignatureStampData:
    titulo: str
    linha_nome_1: str
    linha_nome_2: str
    fonte_nome: float
    cpf_linha: str
    data_hora_linha: str
    codigo_linha: str
    url_linha: str


@dataclass(frozen=True)
class AparenciaAssinaturaLayout:
    width: float
    height: float
    padding: float
    logo_box: tuple[float, float, float, float]
    text_box: tuple[float, float, float, float]
    qr_box: tuple[float, float, float, float]


PARTICULAS_NOME = {'de', 'da', 'do', 'dos', 'das', 'e'}


def calcular_sha256_bytes(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes or b'').hexdigest()


def calcular_sha256_arquivo(path_or_file) -> str:
    sha = hashlib.sha256()
    close_after = False
    if isinstance(path_or_file, (str, bytes)):
        arquivo = open(path_or_file, 'rb')
        close_after = True
    else:
        arquivo = path_or_file
    try:
        if hasattr(arquivo, 'seek'):
            arquivo.seek(0)
        for chunk in iter(lambda: arquivo.read(1024 * 1024), b''):
            sha.update(chunk)
        if hasattr(arquivo, 'seek'):
            arquivo.seek(0)
        return sha.hexdigest()
    finally:
        if close_after:
            arquivo.close()


def _only_digits(value: str) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def mascarar_cpf(cpf: str) -> str:
    digits = _only_digits(cpf)
    if len(digits) != 11:
        return 'â€”' if not digits else digits
    return f'***.{digits[3:6]}.{digits[6:9]}-**'


def mascarar_cpf_assinatura(cpf: str) -> str:
    return mascarar_cpf(cpf)


def gerar_codigo_verificacao() -> str:
    ano = timezone.localdate().year
    while True:
        codigo = f'CV-{ano}-{secrets.token_hex(3).upper()}-{secrets.token_hex(2).upper()}'
        if not AssinaturaDocumento.objects.filter(codigo_verificacao=codigo).exists():
            return codigo


def gerar_url_validacao(assinatura, request=None) -> str:
    url = reverse('documentos:assinatura-verificar-codigo', kwargs={'codigo': assinatura.codigo_verificacao})
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def montar_dados_assinatura(assinatura, request=None) -> DadosCarimbo:
    return DadosCarimbo(
        nome_assinante=assinatura.nome_assinante,
        cpf_mascarado=mascarar_cpf_assinatura(assinatura.cpf_assinante),
        data_hora_assinatura=assinatura.data_hora_assinatura,
        codigo_verificacao=assinatura.codigo_verificacao,
        url_validacao=gerar_url_validacao(assinatura, request=request),
    )


def _normalizar_posicao(posicao: dict | None, total_paginas: int) -> dict:
    raw = posicao or {}
    page_index = int(raw.get('page_index', raw.get('pagina', total_paginas - 1)) or 0)
    if page_index < 0:
        page_index = total_paginas - 1
    page_index = min(max(page_index, 0), max(total_paginas - 1, 0))
    box_w = min(max(float(raw.get('box_w', 0.5)), 0.40), 0.50)
    default_box_x = (1 - box_w) / 2
    return {
        'page_index': page_index,
        'box_x': min(max(float(raw.get('box_x', raw.get('x_ratio', default_box_x))), 0.01), 0.95),
        'box_y': min(max(float(raw.get('box_y', raw.get('y_ratio', 0.80))), 0.01), 0.95),
        'box_w': box_w,
        'box_h': min(max(float(raw.get('box_h', 0.11)), 0.09), 0.18),
        'qr': bool(raw.get('qr', True)),
    }


def _short_url(raw_url: str) -> str:
    parsed = urlparse(str(raw_url or '').strip())
    if not parsed.netloc:
        return str(raw_url or '')[:70]
    path = parsed.path or '/'
    if len(path) > 36:
        path = f'{path[:33]}...'
    return f'{parsed.netloc}{path}'


def fit_text_single_or_two_lines(text: str, max_width: float, font_name: str) -> tuple[float, str, str]:
    clean = re.sub(r'\s+', ' ', str(text or '').strip()) or 'Assinante'
    words = clean.split(' ')
    for font_size in (11.8, 11.2, 10.6, 10.0, 9.4, 8.8):
        if pdfmetrics.stringWidth(clean, font_name, font_size) <= max_width:
            return font_size, clean, ''
    for font_size in (9.8, 9.2, 8.6, 8.0):
        candidates = []
        for idx in range(2, len(words) - 1):
            left_words = words[:idx]
            right_words = words[idx:]
            if left_words[-1].lower() in PARTICULAS_NOME or right_words[0].lower() in PARTICULAS_NOME:
                continue
            left = ' '.join(left_words)
            right = ' '.join(right_words)
            left_w = pdfmetrics.stringWidth(left, font_name, font_size)
            right_w = pdfmetrics.stringWidth(right, font_name, font_size)
            if left_w <= max_width and right_w <= max_width:
                balance = abs(left_w - right_w)
                # Avoid awkward first lines that are too short for institutional names.
                short_penalty = 1000 if len(left_words) < 2 or len(right_words) < 2 else 0
                candidates.append((short_penalty + balance, left, right))
        if candidates:
            _score, left, right = sorted(candidates, key=lambda item: item[0])[0]
            return font_size, left, right
    clipped = clean[:64].rstrip()
    return 7.6, clipped, ''


def ajustar_quebra_nome_assinante(text: str, max_width: float, font_name: str = 'Helvetica-Bold') -> tuple[float, str, str]:
    return fit_text_single_or_two_lines(text, max_width=max_width, font_name=font_name)


def build_signature_stamp_data(dados_carimbo: DadosCarimbo, text_width: float) -> SignatureStampData:
    fonte_nome, linha_nome_1, linha_nome_2 = fit_text_single_or_two_lines(
        dados_carimbo.nome_assinante,
        text_width,
        'Helvetica-Bold',
    )
    dt = timezone.localtime(dados_carimbo.data_hora_assinatura).strftime('%d/%m/%Y Ã s %H:%M')
    return SignatureStampData(
        titulo='ASSINADO ELETRONICAMENTE',
        linha_nome_1=linha_nome_1,
        linha_nome_2=linha_nome_2,
        fonte_nome=fonte_nome,
        cpf_linha=f'CPF: {dados_carimbo.cpf_mascarado}',
        data_hora_linha=f'Assinado em {dt}',
        codigo_linha=f'CÃ³digo verificador: {dados_carimbo.codigo_verificacao}',
        url_linha=f'Verifique em: {_short_url(dados_carimbo.url_validacao)}',
    )


def _resolve_logo_path() -> Path | None:
    custom = (os.getenv('ASSINATURA_LOGO_PATH') or getattr(settings, 'ASSINATURA_LOGO_PATH', '') or '').strip()
    if custom:
        path = Path(custom)
        if path.exists():
            return path
    fallback = Path(settings.BASE_DIR) / 'static' / 'favicon.svg'
    return fallback if fallback.exists() else None


def _resolve_cv_watermark_path() -> Path | None:
    path = Path(settings.BASE_DIR) / 'static' / 'img' / 'assinatura' / 'cv-watermark.png'
    return path if path.exists() else None


def _draw_fallback_logo(c: canvas.Canvas, left: float, bottom: float, width: float, height: float):
    size = min(width, height)
    cx = left + width / 2
    cy = bottom + height / 2
    c.saveState()
    c.setFillColor(HexColor('#0f4c81'))
    c.circle(cx, cy, size / 2, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', max(8, size * 0.28))
    c.drawCentredString(cx, cy + size * 0.03, 'CV')
    c.setFont('Helvetica-Bold', max(3.8, size * 0.075))
    c.drawCentredString(cx, cy - size * 0.22, 'ASSINATURA')
    c.restoreState()


def _draw_logo_profissional(c: canvas.Canvas, left: float, bottom: float, width: float, height: float):
    logo_path = _resolve_logo_path()
    if logo_path and logo_path.suffix.lower() not in {'.svg', '.svgz'}:
        try:
            c.drawImage(
                ImageReader(str(logo_path)),
                left,
                bottom,
                width=width,
                height=height,
                preserveAspectRatio=True,
                anchor='c',
                mask='auto',
            )
            return
        except Exception:
            pass
    _draw_fallback_logo(c, left, bottom, width, height)


def _calcular_layout_aparencia(width: float, height: float) -> AparenciaAssinaturaLayout:
    width, height = _coerce_signature_label_size(width, height)
    padding = 8
    qr_size = min(SIGNATURE_LABEL_QR_PT, height - padding * 2)
    qr_box = (padding, (height - qr_size) / 2, qr_size, qr_size)
    text_left = qr_box[0] + qr_size + 8
    text_right = width - 5
    text_box = (text_left, padding, max(1, text_right - text_left), height - padding * 2)
    return AparenciaAssinaturaLayout(
        width=width,
        height=height,
        padding=padding,
        logo_box=(0, 0, 0, 0),
        text_box=text_box,
        qr_box=qr_box,
    )


def calcular_layout_aparencia_assinatura(width: float, height: float) -> AparenciaAssinaturaLayout:
    return _calcular_layout_aparencia(width, height)


def _draw_qrcode_profissional(c: canvas.Canvas, box: tuple[float, float, float, float], url_validacao: str):
    left, bottom, width, height = box
    qr_size = min(width, height)
    c.saveState()
    qr_code = qr.QrCodeWidget(url_validacao or 'assinatura')
    qr_code.barBorder = 1
    qr_code.barFillColor = white
    qr_code.barStrokeColor = white
    bounds = qr_code.getBounds()
    scale = qr_size / max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    drawing = Drawing(qr_size, qr_size, transform=[scale, 0, 0, scale, 0, 0])
    drawing.add(qr_code)
    renderPDF.draw(drawing, c, left, bottom)
    c.restoreState()


def _font_size_to_fit(text: str, font_name: str, max_width: float, candidates: tuple[float, ...]) -> float:
    for font_size in candidates:
        if pdfmetrics.stringWidth(str(text or ''), font_name, font_size) <= max_width:
            return font_size
    return candidates[-1]


def _wrap_text_by_width(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    words = re.sub(r'\s+', ' ', str(text or '').strip()).split()
    if not words:
        return ['']
    lines: list[str] = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if not current or pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def _coerce_signature_label_size(width: float, height: float) -> tuple[float, float]:
    return SIGNATURE_LABEL_WIDTH_PT, SIGNATURE_LABEL_HEIGHT_PT


def _display_validation_url(raw_url: str) -> str:
    raw_url = str(raw_url or '').strip()
    parsed = urlparse(raw_url)
    display = parsed.path or raw_url
    if parsed.query:
        display = f'{display}?{parsed.query}'
    return display or raw_url


def _wrap_url_line(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return [text]
    prefix = ''
    rest = text
    if text.startswith('verifique em '):
        prefix = 'verifique em '
        rest = text[len(prefix):]
    pieces = re.findall(r'/[^/]*|[^/]+', rest)
    lines: list[str] = []
    current = prefix
    for piece in pieces:
        candidate = f'{current}{piece}'
        if not current.strip() or pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        lines.append(current.rstrip())
        current = piece
    if current.strip():
        lines.append(current)
    return lines


def _draw_cv_watermark(c: canvas.Canvas, text_left: float, width: float, height: float, padding: float):
    wm_size = 155
    wm_left = max(text_left + 8, 82)
    wm_bottom = -42
    c.saveState()
    clip = c.beginPath()
    clip.rect(0, 0, width, height)
    c.clipPath(clip, stroke=0, fill=0)
    try:
        c.setFillAlpha(SIGNATURE_LABEL_WATERMARK_ALPHA)
        c.setStrokeAlpha(SIGNATURE_LABEL_WATERMARK_ALPHA)
    except AttributeError:
        pass
    wm_path = _resolve_cv_watermark_path()
    if wm_path:
        try:
            c.drawImage(
                ImageReader(str(wm_path)),
                wm_left,
                wm_bottom,
                width=wm_size,
                height=wm_size,
                preserveAspectRatio=True,
                anchor='c',
                mask='auto',
            )
            c.restoreState()
            return
        except Exception:
            pass
    c.restoreState()


def _draw_signature_stamp_content(c: canvas.Canvas, dados_carimbo: DadosCarimbo, width: float, height: float, *, with_qr: bool = True):
    width, height = _coerce_signature_label_size(width, height)
    layout = _calcular_layout_aparencia(width, height)
    padding = layout.padding

    c.setFillColor(HexColor('#08172a'))
    c.roundRect(0, 0, width, height, 6, stroke=0, fill=1)

    text_left, _text_bottom, text_width, _text_height = layout.text_box
    _draw_cv_watermark(c, text_left, width, height, padding)

    if with_qr and dados_carimbo.url_validacao:
        _draw_qrcode_profissional(c, layout.qr_box, dados_carimbo.url_validacao)

    data_formatada = timezone.localtime(dados_carimbo.data_hora_assinatura).strftime('%d/%m/%Y %H:%M:%S%z')
    if not data_formatada.endswith(('-0300', '-0200', '-0400')):
        data_formatada = f'{data_formatada or timezone.localtime(dados_carimbo.data_hora_assinatura).strftime("%d/%m/%Y %H:%M:%S")}-0300'

    title = 'Documento assinado eletronicamente'
    title_size = _font_size_to_fit(title, 'Times-Bold', text_width, (8.2, 8.0, 7.8, 7.5))
    y = height - 18
    c.setFillColor(HexColor('#f8fafc'))
    c.setFont('Times-Bold', title_size)
    c.drawString(text_left, y, title)
    y -= 16

    name_size = _font_size_to_fit(dados_carimbo.nome_assinante, 'Times-Roman', text_width, (7.2, 7.0, 6.8, 6.5))
    for line, font_size in (
        (dados_carimbo.nome_assinante, name_size),
        (f'CPF: {dados_carimbo.cpf_mascarado}', 6.8),
        (f'Data: {data_formatada}', 6.6),
    ):
        c.setFont('Times-Roman', font_size)
        c.drawString(text_left, y, line)
        y -= 10.2

    link_linha = f'verifique em {_display_validation_url(dados_carimbo.url_validacao)}'
    link_size = _font_size_to_fit(link_linha, 'Times-Roman', text_width, (5.8, 5.6, 5.3, 5.0))
    c.setFont('Times-Roman', link_size)
    for line in _wrap_url_line(link_linha, 'Times-Roman', link_size, text_width)[:2]:
        c.drawString(text_left, y, line)
        y -= 5.8


def renderizar_aparencia_assinatura(dados_carimbo: DadosCarimbo, width: float, height: float) -> bytes:
    width, height = _coerce_signature_label_size(width, height)
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(width, height), pageCompression=1)
    _draw_signature_stamp_content(c, dados_carimbo, width, height, with_qr=True)
    c.save()
    return stream.getvalue()


def renderizar_aparencia_assinatura_legado(dados_carimbo: DadosCarimbo, width: float, height: float) -> bytes:
    return renderizar_aparencia_assinatura(dados_carimbo, width, height)

def draw_signature_logo(c: canvas.Canvas, left: float, bottom: float, logo_size: float) -> float:
    logo_path = _resolve_logo_path()
    if not logo_path:
        return left
    try:
        c.drawImage(ImageReader(str(logo_path)), left, bottom, width=logo_size, height=logo_size, preserveAspectRatio=True, anchor='sw', mask='auto')
    except Exception:
        c.setFillColor(HexColor('#334155'))
        c.setFont('Helvetica-Bold', 9)
        c.drawString(left, bottom + (logo_size / 2), 'CV')
    return left + logo_size + 8


def draw_signature_qrcode(c: canvas.Canvas, right: float, bottom: float, qr_size: float, url_validacao: str) -> float:
    qr_left = right - qr_size
    qr_code = qr.QrCodeWidget(url_validacao)
    bounds = qr_code.getBounds()
    scale = qr_size / max(bounds[2] - bounds[0], bounds[3] - bounds[1])
    drawing = Drawing(qr_size, qr_size, transform=[scale, 0, 0, scale, 0, 0])
    drawing.add(qr_code)
    renderPDF.draw(drawing, c, qr_left, bottom)
    return qr_left - 8


def draw_signature_text(c: canvas.Canvas, x: float, y_top: float, stamp: SignatureStampData):
    c.setFillColor(HexColor('#1f2933'))
    c.setFont('Helvetica-Bold', 8.2)
    c.drawString(x, y_top, stamp.titulo)
    y = y_top - 10
    c.setFont('Helvetica-Bold', stamp.fonte_nome)
    c.drawString(x, y, stamp.linha_nome_1)
    if stamp.linha_nome_2:
        y -= 8.3
        c.drawString(x, y, stamp.linha_nome_2)
    y -= 8.6
    c.setFont('Helvetica', 6.7)
    c.setFillColor(HexColor('#4b5563'))
    c.drawString(x, y, stamp.cpf_linha)
    y -= 7.8
    c.drawString(x, y, stamp.data_hora_linha)
    y -= 7.8
    c.drawString(x, y, stamp.codigo_linha)
    y -= 7.8
    c.drawString(x, y, stamp.url_linha[:88])


def calculate_signature_stamp_box(page_width: float, page_height: float, posicao: dict) -> tuple[float, float, float, float]:
    box_w = SIGNATURE_LABEL_WIDTH_PT
    box_h = SIGNATURE_LABEL_HEIGHT_PT
    left = (page_width - box_w) / 2
    bottom = page_height - (page_height * posicao['box_y']) - box_h
    left = min(max(left, 8), page_width - box_w - 8)
    bottom = min(max(bottom, SIGNATURE_LABEL_MIN_BOTTOM_PT), page_height - box_h - 8)
    return left, bottom, box_w, box_h


def get_signature_stamp_position(page_width: float, page_height: float, posicao: dict) -> dict:
    left, bottom, box_w, box_h = calculate_signature_stamp_box(page_width, page_height, posicao)
    return {'left': left, 'bottom': bottom, 'box_w': box_w, 'box_h': box_h}


def draw_signature_stamp(c: canvas.Canvas, dados_carimbo: DadosCarimbo, stamp_pos: dict, with_qr: bool):
    left = stamp_pos['left']
    bottom = stamp_pos['bottom']
    box_w = stamp_pos['box_w']
    box_h = stamp_pos['box_h']
    c.saveState()
    c.translate(left, bottom)
    _draw_signature_stamp_content(c, dados_carimbo, box_w, box_h, with_qr=with_qr)
    c.restoreState()


def gerar_overlay_carimbo(page_width: float, page_height: float, dados_carimbo: DadosCarimbo, posicao: dict) -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(page_width, page_height))
    stamp_pos = get_signature_stamp_position(page_width, page_height, posicao)
    draw_signature_stamp(c, dados_carimbo, stamp_pos, with_qr=bool(posicao.get('qr')))
    c.save()
    return stream.getvalue()


def aplicar_carimbo_pdf(pdf_original: bytes, dados_carimbo: DadosCarimbo, posicao: dict | None = None) -> tuple[bytes, dict]:
    reader = PdfReader(BytesIO(pdf_original))
    writer = PdfWriter()
    if not reader.pages:
        raise ValueError('PDF sem pÃ¡ginas para aplicaÃ§Ã£o do carimbo.')

    posicao_final = _normalizar_posicao(posicao, len(reader.pages))
    target_index = posicao_final['page_index']
    target_page = reader.pages[target_index]
    width = float(target_page.mediabox.width)
    height = float(target_page.mediabox.height)
    overlay_bytes = gerar_overlay_carimbo(width, height, dados_carimbo, posicao_final)
    overlay_page = PdfReader(BytesIO(overlay_bytes)).pages[0]

    for index, page in enumerate(reader.pages):
        if index == target_index:
            page.merge_page(overlay_page)
        writer.add_page(page)

    writer.add_metadata(
        {
            '/assinatura_codigo': dados_carimbo.codigo_verificacao,
            '/assinatura_sistema': SISTEMA_ASSINATURA,
            '/assinatura_data_hora': dados_carimbo.data_hora_assinatura.isoformat(),
            '/assinatura_hash_pdf_assinado': 'calculado_apos_gravacao',
        }
    )
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), {
        **posicao_final,
        'page_number': target_index + 1,
        'label_width_pt': SIGNATURE_LABEL_WIDTH_PT,
        'label_height_pt': SIGNATURE_LABEL_HEIGHT_PT,
        'qr_size_pt': SIGNATURE_LABEL_QR_PT,
    }


def _read_bytes(pdf_original) -> bytes:
    if isinstance(pdf_original, bytes):
        return pdf_original
    if hasattr(pdf_original, 'read'):
        if hasattr(pdf_original, 'seek'):
            pdf_original.seek(0)
        data = pdf_original.read()
        if hasattr(pdf_original, 'seek'):
            pdf_original.seek(0)
        return data
    raise TypeError('PDF original deve ser bytes ou arquivo.')


def _cert_env_path() -> Path | None:
    cert_path = (os.getenv('PDF_SIGNING_CERT_PATH') or '').strip()
    return Path(cert_path) if cert_path else None


def _ensure_dev_pkcs12_certificate() -> tuple[Path, bytes]:
    cert_path = _cert_env_path()
    password = (os.getenv('PDF_SIGNING_CERT_PASSWORD') or 'dev-signature').encode('utf-8')
    if cert_path and cert_path.exists():
        return cert_path, password

    target = Path('media') / 'assinaturas' / 'certs'
    target.mkdir(parents=True, exist_ok=True)
    cert_file = target / 'assinatura-eletronica-interna-dev.p12'
    if cert_file.exists():
        return cert_file, password

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, 'BR'),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'Central de Viagens'),
            x509.NameAttribute(NameOID.COMMON_NAME, 'Assinatura eletrÃ´nica interna'),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )
    pfx = pkcs12.serialize_key_and_certificates(
        name=b'assinatura-eletronica-interna',
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )
    cert_file.write_bytes(pfx)
    return cert_file, password


def diagnosticar_estrutura_assinatura_pdf(pdf_bytes: bytes) -> dict:
    raw = pdf_bytes or b''
    has_byterange = b'/ByteRange' in raw
    has_sig = b'/Sig' in raw
    has_ft_sig = b'/FT /Sig' in raw or b'/FT/Sig' in raw
    has_contents = b'/Contents' in raw
    has_acroform = b'/AcroForm' in raw
    has_appearance = b'/AP' in raw
    try:
        reader = PdfFileReader(BytesIO(raw))
        embedded_count = len(reader.embedded_signatures)
    except Exception:
        embedded_count = 0
    try:
        pypdf_reader = PdfReader(BytesIO(raw))
        page_count = len(pypdf_reader.pages)
        page_text = '\n'.join((page.extract_text() or '') for page in pypdf_reader.pages)
        metadata = pypdf_reader.metadata or {}
        codigo_metadata = metadata.get('/assinatura_codigo') or metadata.get('assinatura_codigo') or ''
    except Exception:
        page_count = 0
        page_text = ''
        codigo_metadata = ''
    return {
        'has_byterange': has_byterange,
        'has_sig': has_sig,
        'has_ft_sig': has_ft_sig,
        'has_contents': has_contents,
        'has_acroform': has_acroform,
        'has_appearance': has_appearance,
        'embedded_signatures_count': embedded_count,
        'page_count': page_count,
        'codigo_metadata': codigo_metadata,
        'page_text_has_signature_visual': 'ASSINADO ELETRONICAMENTE' in page_text.upper(),
        'apenas_carimbo_visual': not (has_byterange and has_sig and has_acroform and has_contents),
    }


def _preparar_pdf_base_assinatura(pdf_original: bytes, dados_carimbo: DadosCarimbo) -> bytes:
    reader = PdfReader(BytesIO(pdf_original))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    existing_metadata = dict(reader.metadata or {})
    existing_metadata.update(
        {
            '/assinatura_codigo': dados_carimbo.codigo_verificacao,
            '/assinatura_sistema': SISTEMA_ASSINATURA,
            '/assinatura_data_hora': dados_carimbo.data_hora_assinatura.isoformat(),
            '/assinatura_tipo': 'assinatura_pdf_real_com_aparencia_de_campo',
        }
    )
    writer.add_metadata(existing_metadata)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def calcular_posicao_assinatura(page_width: float, page_height: float, posicao: dict) -> tuple[int, int, int, int]:
    left, bottom, box_w, box_h = calculate_signature_stamp_box(page_width, page_height, posicao)
    return int(left), int(bottom), int(left + box_w), int(bottom + box_h)


def _criar_arquivo_aparencia_temporario(dados_carimbo: DadosCarimbo, width: float, height: float) -> str:
    appearance_pdf = renderizar_aparencia_assinatura(dados_carimbo, width=width, height=height)
    temp = tempfile.NamedTemporaryFile(prefix='assinatura-aparencia-', suffix='.pdf', delete=False)
    try:
        temp.write(appearance_pdf)
        return temp.name
    finally:
        temp.close()


def aplicar_assinatura_pdf_real(pdf_base: bytes, dados_carimbo: DadosCarimbo, posicao: dict) -> tuple[bytes, dict]:
    cert_file, password = _ensure_dev_pkcs12_certificate()
    signer = signers.SimpleSigner.load_pkcs12(cert_file, passphrase=password)
    reader = PdfReader(BytesIO(pdf_base))
    page = reader.pages[posicao['page_index']]
    sig_box = calcular_posicao_assinatura(float(page.mediabox.width), float(page.mediabox.height), posicao)
    appearance_path = _criar_arquivo_aparencia_temporario(
        dados_carimbo,
        width=sig_box[2] - sig_box[0],
        height=sig_box[3] - sig_box[1],
    )
    meta = signers.PdfSignatureMetadata(
        field_name=f'Signature_{dados_carimbo.codigo_verificacao}',
        md_algorithm='sha256',
        reason=(os.getenv('PDF_SIGNING_REASON') or 'Assinatura eletronica interna').strip(),
        location=(os.getenv('PDF_SIGNING_LOCATION') or 'Central de Viagens').strip(),
    )
    writer = IncrementalPdfFileWriter(BytesIO(pdf_base))
    out = BytesIO()
    stamp_style = StaticStampStyle.from_pdf_file(appearance_path, border_width=0, background_opacity=1)
    pdf_signer = signers.PdfSigner(
        meta,
        signer=signer,
        stamp_style=stamp_style,
        new_field_spec=fields.SigFieldSpec(
            sig_field_name=meta.field_name,
            on_page=posicao['page_index'],
            box=sig_box,
        ),
    )
    try:
        pdf_signer.sign_pdf(writer, output=out)
    finally:
        try:
            os.unlink(appearance_path)
        except OSError:
            pass
    cert = signer.signing_cert
    return out.getvalue(), {
        'assinatura_pdf_tecnica_status': STATUS_PDF_INTEGRA,
        'certificado_subject': cert.subject.human_friendly,
        'certificado_issuer': cert.issuer.human_friendly,
        'certificado_serial': hex(cert.serial_number),
        'signature_field_name': meta.field_name,
        'signature_position': {**posicao, 'box_pdf': sig_box},
        'label_width_pt': SIGNATURE_LABEL_WIDTH_PT,
        'label_height_pt': SIGNATURE_LABEL_HEIGHT_PT,
        'qr_size_pt': SIGNATURE_LABEL_QR_PT,
        'appearance_bound_to_signature_field': True,
    }


def _assinar_pdf_real(pdf_carimbado: bytes, posicao: dict, codigo_verificacao: str) -> tuple[bytes, dict]:
    cert_file, password = _ensure_dev_pkcs12_certificate()
    signer = signers.SimpleSigner.load_pkcs12(cert_file, passphrase=password)
    reader = PdfReader(BytesIO(pdf_carimbado))
    page = reader.pages[posicao['page_index']]
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)
    box_w = SIGNATURE_LABEL_WIDTH_PT
    box_h = SIGNATURE_LABEL_HEIGHT_PT
    left = (page_width - box_w) / 2
    bottom = page_height - (page_height * posicao['box_y']) - box_h
    left = min(max(left, 8), page_width - box_w - 8)
    bottom = min(max(bottom, SIGNATURE_LABEL_MIN_BOTTOM_PT), page_height - box_h - 8)
    sig_box = (int(left), int(bottom), int(left + box_w), int(bottom + box_h))

    meta = signers.PdfSignatureMetadata(
        field_name=f'Signature_{codigo_verificacao}',
        md_algorithm='sha256',
        reason=(os.getenv('PDF_SIGNING_REASON') or 'Assinatura eletrÃ´nica interna').strip(),
        location=(os.getenv('PDF_SIGNING_LOCATION') or 'Central de Viagens').strip(),
    )
    out = BytesIO()
    writer = IncrementalPdfFileWriter(BytesIO(pdf_carimbado))
    signers.sign_pdf(
        writer,
        signature_meta=meta,
        signer=signer,
        new_field_spec=fields.SigFieldSpec(
            sig_field_name=meta.field_name,
            on_page=posicao['page_index'],
            box=sig_box,
        ),
        output=out,
    )
    cert = signer.signing_cert
    return out.getvalue(), {
        'assinatura_pdf_tecnica_status': STATUS_PDF_INTEGRA,
        'certificado_subject': cert.subject.human_friendly,
        'certificado_issuer': cert.issuer.human_friendly,
        'certificado_serial': hex(cert.serial_number),
    }


def _validar_assinatura_pdf_tecnica(pdf_bytes: bytes) -> tuple[str, str]:
    try:
        reader = PdfFileReader(BytesIO(pdf_bytes))
        if not reader.embedded_signatures:
            return STATUS_PDF_AUSENTE, 'PDF sem assinatura digital incorporada.'
        emb = reader.embedded_signatures[0]
        status = validation.validate_pdf_signature(emb)
        if status.intact and status.valid:
            if getattr(status, 'trusted', False):
                return STATUS_PDF_INTEGRA, 'Assinatura PDF Ã­ntegra e cadeia confiÃ¡vel.'
            return STATUS_PDF_CERT_NAO_CONFIAVEL, 'Assinatura PDF Ã­ntegra; certificado nÃ£o confiÃ¡vel no ambiente.'
        return STATUS_PDF_INVALIDA, 'Assinatura PDF invÃ¡lida ou documento alterado.'
    except Exception:
        return STATUS_PDF_AUSENTE, 'NÃ£o foi possÃ­vel validar tecnicamente a assinatura PDF.'


def validar_assinatura_pdf(pdf_bytes: bytes) -> tuple[str, str]:
    return _validar_assinatura_pdf_tecnica(pdf_bytes)


def validar_hash_assinatura(pdf_bytes: bytes, assinatura: AssinaturaDocumento) -> bool:
    return calcular_sha256_bytes(pdf_bytes) == (assinatura.hash_pdf_assinado_sha256 or '')


def otimizar_pdf_assinado(pdf_bytes: bytes) -> bytes:
    # A assinatura cobre os bytes do documento; qualquer otimizacao posterior invalidaria o ByteRange.
    return pdf_bytes


@transaction.atomic
def assinar_documento_pdf(
    documento,
    usuario=None,
    metodo_autenticacao=AssinaturaDocumento.METODO_USUARIO_SISTEMA,
    *,
    pdf_original,
    nome_documento='Documento',
    nome_assinante='',
    cpf_assinante='',
    email_assinante='',
    request=None,
    posicao=None,
    metadata=None,
) -> AssinaturaDocumento:
    pdf_original_bytes = _read_bytes(pdf_original)
    now = timezone.now()
    content_type = ContentType.objects.get_for_model(documento, for_concrete_model=False)
    usuario_assinante = usuario if getattr(usuario, 'is_authenticated', False) else None
    assinatura = AssinaturaDocumento.objects.create(
        content_type=content_type,
        object_id=documento.pk,
        usuario_assinante=usuario_assinante,
        nome_assinante=(nome_assinante or getattr(usuario, 'get_full_name', lambda: '')() or str(usuario or '')).strip(),
        cpf_assinante=_only_digits(cpf_assinante),
        email_assinante=email_assinante or getattr(usuario, 'email', ''),
        metodo_autenticacao=metodo_autenticacao,
        ip_assinatura=request.META.get('REMOTE_ADDR') if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:1000] if request else '',
        data_hora_assinatura=now,
        codigo_verificacao=gerar_codigo_verificacao(),
        hash_pdf_original_sha256=calcular_sha256_bytes(pdf_original_bytes),
        metadata_json={'nome_documento': nome_documento, **(metadata or {})},
    )
    dados = montar_dados_assinatura(assinatura, request=request)
    reader_original = PdfReader(BytesIO(pdf_original_bytes))
    if not reader_original.pages:
        raise ValueError('PDF sem pÃ¡ginas para assinatura.')
    posicao_final = _normalizar_posicao(posicao, len(reader_original.pages))
    pdf_base = _preparar_pdf_base_assinatura(pdf_original_bytes, dados)
    pdf_assinado, cert_meta = aplicar_assinatura_pdf_real(pdf_base, dados, posicao_final)
    pdf_assinado = otimizar_pdf_assinado(pdf_assinado)
    diagnostico = diagnosticar_estrutura_assinatura_pdf(pdf_assinado)
    assinatura.hash_pdf_assinado_sha256 = calcular_sha256_bytes(pdf_assinado)
    assinatura.pagina_carimbo = posicao_final['page_index'] + 1
    assinatura.posicao_carimbo_json = cert_meta.get('signature_position') or {**posicao_final, 'page_number': posicao_final['page_index'] + 1}
    assinatura.assinatura_pdf_tecnica_status = cert_meta['assinatura_pdf_tecnica_status']
    assinatura.certificado_subject = cert_meta['certificado_subject'][:255]
    assinatura.certificado_issuer = cert_meta['certificado_issuer'][:255]
    assinatura.certificado_serial = cert_meta['certificado_serial'][:128]
    assinatura.metadata_json = {
        **assinatura.metadata_json,
        'assinatura_hash_pdf_assinado': assinatura.hash_pdf_assinado_sha256,
        'assinatura_tipo': 'assinatura_pdf_real_com_aparencia_de_campo',
        'assinatura_visual': {
            'layout': 'etiqueta_compacta_horizontal',
            'largura_pt': SIGNATURE_LABEL_WIDTH_PT,
            'altura_pt': SIGNATURE_LABEL_HEIGHT_PT,
            'qr_tamanho_pt': SIGNATURE_LABEL_QR_PT,
            'marca_dagua': 'static/img/assinatura/cv-watermark.png',
            'marca_dagua_opacidade': SIGNATURE_LABEL_WATERMARK_ALPHA,
            'qr_code': True,
            'aparencia_vinculada_ao_campo_pdf': True,
            'sem_overlay_na_pagina': not diagnostico.get('page_text_has_signature_visual'),
        },
        'diagnostico_pdf': diagnostico,
    }
    filename = f'{nome_documento.lower().replace(" ", "-")}-{documento.pk}-{assinatura.codigo_verificacao}.pdf'
    assinatura.arquivo_pdf_assinado.save(filename, ContentFile(pdf_assinado), save=False)
    assinatura.save(
        update_fields=[
            'hash_pdf_assinado_sha256',
            'pagina_carimbo',
            'posicao_carimbo_json',
            'assinatura_pdf_tecnica_status',
            'certificado_subject',
            'certificado_issuer',
            'certificado_serial',
            'metadata_json',
            'arquivo_pdf_assinado',
            'updated_at',
        ]
    )
    return assinatura


def extrair_codigo_pdf(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        metadata = reader.metadata or {}
        for key in ('/assinatura_codigo', 'assinatura_codigo'):
            value = metadata.get(key)
            if value and CODIGO_RE.search(str(value)):
                return CODIGO_RE.search(str(value)).group(0)
        for page in reader.pages:
            text = page.extract_text() or ''
            match = CODIGO_RE.search(text)
            if match:
                return match.group(0)
    except Exception:
        return ''
    return ''


def validar_codigo(codigo: str):
    clean = str(codigo or '').strip().upper()
    if not clean:
        return None
    return AssinaturaDocumento.objects.filter(codigo_verificacao=clean).select_related('content_type', 'usuario_assinante').first()


def validar_pdf_por_upload(arquivo_pdf, *, codigo_manual='', request=None) -> dict:
    pdf_bytes = _read_bytes(arquivo_pdf)
    hash_pdf = calcular_sha256_bytes(pdf_bytes)
    codigo = (codigo_manual or '').strip().upper() or extrair_codigo_pdf(pdf_bytes)
    assinatura = validar_codigo(codigo) if codigo else None
    status_assinatura_pdf = STATUS_PDF_AUSENTE
    msg_assinatura_pdf = 'Sem anÃ¡lise tÃ©cnica de assinatura PDF.'
    if assinatura is not None:
        status_assinatura_pdf, msg_assinatura_pdf = _validar_assinatura_pdf_tecnica(pdf_bytes)

    if not codigo:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_ARQUIVO_SEM_CODIGO
        mensagem = 'NÃ£o foi possÃ­vel identificar um cÃ³digo de verificaÃ§Ã£o no PDF enviado.'
    elif assinatura is None:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_CODIGO_NAO_ENCONTRADO
        mensagem = 'CÃ³digo de verificaÃ§Ã£o nÃ£o encontrado.'
    elif assinatura.status != AssinaturaDocumento.STATUS_VALIDA:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_INVALIDO
        mensagem = 'A assinatura registrada nÃ£o estÃ¡ ativa.'
    elif validar_hash_assinatura(pdf_bytes, assinatura) and status_assinatura_pdf in {STATUS_PDF_INTEGRA, STATUS_PDF_CERT_NAO_CONFIAVEL}:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_VALIDO
        mensagem = 'O arquivo enviado corresponde exatamente ao PDF assinado originalmente.'
    else:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_INVALIDO
        mensagem = 'O arquivo enviado foi alterado apÃ³s a assinatura, reexportado, editado ou nÃ£o corresponde ao arquivo originalmente assinado.'

    ValidacaoAssinaturaDocumento.objects.create(
        assinatura=assinatura,
        ip=request.META.get('REMOTE_ADDR') if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:1000] if request else '',
        hash_pdf_enviado=hash_pdf,
        resultado=resultado,
        status_assinatura_pdf=status_assinatura_pdf,
        observacao=f'{mensagem} | {msg_assinatura_pdf}',
    )
    return {
        'assinatura': assinatura,
        'codigo': codigo,
        'hash_pdf_enviado': hash_pdf,
        'resultado': resultado,
        'status_assinatura_pdf': status_assinatura_pdf,
        'valido': resultado == ValidacaoAssinaturaDocumento.RESULTADO_VALIDO,
        'mensagem': f'{mensagem} {msg_assinatura_pdf}',
    }
