"""Sobreposicao de imagem de assinatura no PDF (reportlab + pypdf)."""
from __future__ import annotations

import base64
import re
from io import BytesIO

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

from assinaturas.services.assinatura_layout import AssinaturaLayoutRect, resolver_layout_assinatura


def _decode_png_data_url(data_url: str) -> bytes:
    raw = (data_url or "").strip()
    if not raw:
        raise ValueError("Assinatura vazia.")
    m = re.match(r"^data:image/png;base64,(.+)$", raw, re.DOTALL | re.IGNORECASE)
    if not m:
        raise ValueError("Formato de assinatura invalido (esperado PNG base64).")
    try:
        raw = base64.b64decode(m.group(1), validate=True)
    except Exception as exc:
        raise ValueError("Base64 da assinatura invalido.") from exc
    return _normalizar_png_assinatura(raw)


def _normalizar_png_assinatura(png_bytes: bytes) -> bytes:
    """
    Garante PNG válido e com traço visível.
    Evita registrar assinatura "vazia" que resultaria em PDF aparentemente em branco.
    """
    try:
        img = Image.open(BytesIO(png_bytes))
    except Exception as exc:
        raise ValueError("Imagem de assinatura inválida.") from exc
    img = img.convert("RGBA")

    alpha_bbox = img.getchannel("A").getbbox()
    if not alpha_bbox:
        raise ValueError("Assinatura vazia (sem traço visível).")

    # Rejeita assinaturas semanticamente vazias (ex.: canvas sem traço útil).
    rgba = img.getdata()
    has_ink = any(a > 0 and (r < 245 or g < 245 or b < 245) for r, g, b, a in rgba)
    if not has_ink:
        raise ValueError("Assinatura vazia (desenhe no quadro antes de enviar).")

    # Recorta para a área útil para evitar imagem praticamente vazia no overlay.
    left, top, right, bottom = alpha_bbox
    img = img.crop((left, top, right, bottom))

    # Recria com fundo transparente e traço opaco, reduzindo risco de "assinatura invisível".
    stroke = img.convert("RGBA")
    pixels = []
    for r, g, b, a in stroke.getdata():
        if a == 0:
            pixels.append((255, 255, 255, 0))
        else:
            pixels.append((r, g, b, 255))
    stroke.putdata(pixels)

    # Preserva transparência com traço visível e evita artefatos de canvas.
    out = BytesIO()
    stroke.save(out, format="PNG")
    return out.getvalue()


def aplicar_assinatura_png(
    pdf_bytes: bytes,
    png_bytes: bytes,
    layout: AssinaturaLayoutRect | None = None,
) -> bytes:
    """
    Aplica a imagem da assinatura na pagina alvo (por defeito: ultima pagina, canto inferior direito).
    """
    layout = layout or AssinaturaLayoutRect(page_index=-1, margin=36.0, height_ratio=0.15, aspect=3.0)
    reader = PdfReader(BytesIO(pdf_bytes))
    if not reader.pages:
        raise ValueError("PDF sem paginas.")

    n = len(reader.pages)
    if layout.page_index < 0:
        page_idx = n - 1
    else:
        page_idx = min(max(0, layout.page_index), n - 1)

    target = reader.pages[page_idx]
    try:
        target.transfer_rotation_to_content()
    except Exception:
        pass
    box = target.mediabox
    page_w = float(box.width)
    page_h = float(box.height)

    margin = layout.margin
    sig_h = max(48.0, min(120.0, page_h * layout.height_ratio))
    aspect = layout.aspect
    sig_w = sig_h * aspect
    if sig_w > page_w - 2 * margin:
        sig_w = page_w - 2 * margin
        sig_h = sig_w / aspect

    buf = BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_w, page_h))
    img = ImageReader(BytesIO(png_bytes))
    x = page_w - margin - sig_w
    y = margin
    c.drawImage(img, x, y, width=sig_w, height=sig_h, mask="auto")
    c.save()
    buf.seek(0)

    overlay_reader = PdfReader(buf)
    overlay_page = overlay_reader.pages[0]

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i == page_idx:
            page.merge_page(overlay_page)
        writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def aplicar_assinatura_data_url(
    pdf_bytes: bytes,
    signature_data_url: str,
    *,
    documento_tipo: str = "",
) -> bytes:
    png = _decode_png_data_url(signature_data_url)
    layout = resolver_layout_assinatura(documento_tipo)
    return aplicar_assinatura_png(pdf_bytes, png, layout)
