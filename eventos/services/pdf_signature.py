from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFError, TTFont
from django.conf import settings
from django.utils import timezone
import requests

from documentos.services.assinaturas import DadosCarimbo, aplicar_carimbo_pdf

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
    if not reader.pages:
        return pdf_bytes, {
            'requested_font_key': font_key,
            'resolved_font_name': FALLBACK_FONT_NAME,
            'used_fallback': True,
            'font_detail': 'pdf sem páginas',
        }

    if strict_font:
        font_name, font_detail = assert_font_supports_signature(font_key)
        used_fallback = False
    else:
        font_name, used_fallback, font_detail = resolve_signature_font(font_key)

    payload = validation_payload or {}
    dados = DadosCarimbo(
        nome_assinante=payload.get('nome_assinante') or signer_name,
        cpf_mascarado=payload.get('cpf_mascarado') or '—',
        data_hora_assinatura=timezone.now(),
        codigo_verificacao=payload.get('codigo_validacao') or '',
        url_validacao=payload.get('url_verificacao') or '',
    )
    final_pdf_bytes, position_meta = aplicar_carimbo_pdf(pdf_bytes, dados, signature_position)

    return final_pdf_bytes, {
        'requested_font_key': font_key,
        'resolved_font_name': font_name,
        'used_fallback': used_fallback,
        'font_detail': font_detail,
        'has_validation_page': False,
        'signature_position': position_meta,
    }
