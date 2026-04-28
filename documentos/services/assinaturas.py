from __future__ import annotations

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

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
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
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
        return '—' if not digits else digits
    return f'***.{digits[3:6]}.{digits[6:9]}-**'


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


def _normalizar_posicao(posicao: dict | None, total_paginas: int) -> dict:
    raw = posicao or {}
    page_index = int(raw.get('page_index', raw.get('pagina', total_paginas - 1)) or 0)
    if page_index < 0:
        page_index = total_paginas - 1
    page_index = min(max(page_index, 0), max(total_paginas - 1, 0))
    return {
        'page_index': page_index,
        'box_x': min(max(float(raw.get('box_x', raw.get('x_ratio', 0.15))), 0.01), 0.95),
        'box_y': min(max(float(raw.get('box_y', raw.get('y_ratio', 0.78))), 0.01), 0.95),
        'box_w': min(max(float(raw.get('box_w', 0.42)), 0.18), 0.95),
        'box_h': min(max(float(raw.get('box_h', 0.14)), 0.10), 0.35),
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
    for font_size in (8.8, 8.4, 8.0, 7.6):
        if pdfmetrics.stringWidth(clean, font_name, font_size) <= max_width:
            return font_size, clean, ''
    for font_size in (8.0, 7.6, 7.2):
        for idx in range(1, len(words)):
            left_words = words[:idx]
            right_words = words[idx:]
            if left_words[-1].lower() in PARTICULAS_NOME or right_words[0].lower() in PARTICULAS_NOME:
                continue
            left = ' '.join(left_words)
            right = ' '.join(right_words)
            if (
                pdfmetrics.stringWidth(left, font_name, font_size) <= max_width
                and pdfmetrics.stringWidth(right, font_name, font_size) <= max_width
            ):
                return font_size, left, right
    clipped = clean[:54].rstrip()
    return 7.0, clipped, ''


def build_signature_stamp_data(dados_carimbo: DadosCarimbo, text_width: float) -> SignatureStampData:
    fonte_nome, linha_nome_1, linha_nome_2 = fit_text_single_or_two_lines(
        dados_carimbo.nome_assinante,
        text_width,
        'Helvetica-Bold',
    )
    dt = timezone.localtime(dados_carimbo.data_hora_assinatura).strftime('%d/%m/%Y às %H:%M')
    return SignatureStampData(
        titulo='ASSINADO ELETRONICAMENTE',
        linha_nome_1=linha_nome_1,
        linha_nome_2=linha_nome_2,
        fonte_nome=fonte_nome,
        cpf_linha=f'CPF: {dados_carimbo.cpf_mascarado}',
        data_hora_linha=f'Assinado em {dt}',
        codigo_linha=f'Código verificador: {dados_carimbo.codigo_verificacao}',
        url_linha=f'Verifique em: {_short_url(dados_carimbo.url_validacao)}',
    )


def _resolve_logo_path() -> Path | None:
    custom = (os.getenv('ASSINATURA_LOGO_PATH') or '').strip()
    if custom:
        path = Path(custom)
        if path.exists():
            return path
    fallback = Path('static') / 'favicon.svg'
    return fallback if fallback.exists() else None


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
    box_w = page_width * posicao['box_w']
    box_h = page_height * posicao['box_h']
    left = page_width * posicao['box_x']
    bottom = page_height - (page_height * posicao['box_y']) - box_h
    left = min(max(left, 8), page_width - box_w - 8)
    bottom = min(max(bottom, 8), page_height - box_h - 8)
    return left, bottom, box_w, box_h


def get_signature_stamp_position(page_width: float, page_height: float, posicao: dict) -> dict:
    left, bottom, box_w, box_h = calculate_signature_stamp_box(page_width, page_height, posicao)
    return {'left': left, 'bottom': bottom, 'box_w': box_w, 'box_h': box_h}


def draw_signature_stamp(c: canvas.Canvas, dados_carimbo: DadosCarimbo, stamp_pos: dict, with_qr: bool):
    left = stamp_pos['left']
    bottom = stamp_pos['bottom']
    box_w = stamp_pos['box_w']
    box_h = stamp_pos['box_h']
    padding = 8
    logo_size = min(34, box_h - 14)
    qr_size = min(44, box_h - 14)

    c.setStrokeColor(HexColor('#cbd5e1'))
    c.setFillColor(HexColor('#f8fafc'))
    c.roundRect(left, bottom, box_w, box_h, 4, stroke=1, fill=1)

    text_left = draw_signature_logo(c, left + padding, bottom + (box_h - logo_size) / 2, logo_size)
    text_right = left + box_w - padding
    if with_qr and dados_carimbo.url_validacao:
        text_right = draw_signature_qrcode(c, text_right, bottom + (box_h - qr_size) / 2, qr_size, dados_carimbo.url_validacao)
    text_width = max(70, text_right - text_left)
    stamp = build_signature_stamp_data(dados_carimbo, text_width)
    draw_signature_text(c, text_left, bottom + box_h - 11, stamp)


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
        raise ValueError('PDF sem páginas para aplicação do carimbo.')

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
    return output.getvalue(), {**posicao_final, 'page_number': target_index + 1}


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
            x509.NameAttribute(NameOID.COMMON_NAME, 'Assinatura eletrônica interna'),
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
    try:
        reader = PdfFileReader(BytesIO(raw))
        embedded_count = len(reader.embedded_signatures)
    except Exception:
        embedded_count = 0
    return {
        'has_byterange': has_byterange,
        'has_sig': has_sig,
        'has_ft_sig': has_ft_sig,
        'has_contents': has_contents,
        'has_acroform': has_acroform,
        'embedded_signatures_count': embedded_count,
        'apenas_carimbo_visual': not (has_byterange and has_sig and has_acroform and has_contents),
    }


def _assinar_pdf_real(pdf_carimbado: bytes, posicao: dict, codigo_verificacao: str) -> tuple[bytes, dict]:
    cert_file, password = _ensure_dev_pkcs12_certificate()
    signer = signers.SimpleSigner.load_pkcs12(cert_file, passphrase=password)
    reader = PdfReader(BytesIO(pdf_carimbado))
    page = reader.pages[posicao['page_index']]
    page_width = float(page.mediabox.width)
    page_height = float(page.mediabox.height)
    box_w = page_width * posicao['box_w']
    box_h = page_height * posicao['box_h']
    left = page_width * posicao['box_x']
    bottom = page_height - (page_height * posicao['box_y']) - box_h
    left = min(max(left, 8), page_width - box_w - 8)
    bottom = min(max(bottom, 8), page_height - box_h - 8)
    sig_box = (int(left), int(bottom), int(left + box_w), int(bottom + box_h))

    meta = signers.PdfSignatureMetadata(
        field_name=f'Signature_{codigo_verificacao}',
        md_algorithm='sha256',
        reason=(os.getenv('PDF_SIGNING_REASON') or 'Assinatura eletrônica interna').strip(),
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
                return STATUS_PDF_INTEGRA, 'Assinatura PDF íntegra e cadeia confiável.'
            return STATUS_PDF_CERT_NAO_CONFIAVEL, 'Assinatura PDF íntegra; certificado não confiável no ambiente.'
        return STATUS_PDF_INVALIDA, 'Assinatura PDF inválida ou documento alterado.'
    except Exception:
        return STATUS_PDF_AUSENTE, 'Não foi possível validar tecnicamente a assinatura PDF.'


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
    dados = DadosCarimbo(
        nome_assinante=assinatura.nome_assinante,
        cpf_mascarado=mascarar_cpf(assinatura.cpf_assinante),
        data_hora_assinatura=assinatura.data_hora_assinatura,
        codigo_verificacao=assinatura.codigo_verificacao,
        url_validacao=gerar_url_validacao(assinatura, request=request),
    )
    pdf_carimbado, posicao_final = aplicar_carimbo_pdf(pdf_original_bytes, dados, posicao)
    pdf_assinado, cert_meta = _assinar_pdf_real(pdf_carimbado, posicao_final, assinatura.codigo_verificacao)
    diagnostico = diagnosticar_estrutura_assinatura_pdf(pdf_assinado)
    assinatura.hash_pdf_assinado_sha256 = calcular_sha256_bytes(pdf_assinado)
    assinatura.pagina_carimbo = posicao_final['page_number']
    assinatura.posicao_carimbo_json = posicao_final
    assinatura.assinatura_pdf_tecnica_status = cert_meta['assinatura_pdf_tecnica_status']
    assinatura.certificado_subject = cert_meta['certificado_subject'][:255]
    assinatura.certificado_issuer = cert_meta['certificado_issuer'][:255]
    assinatura.certificado_serial = cert_meta['certificado_serial'][:128]
    assinatura.metadata_json = {
        **assinatura.metadata_json,
        'assinatura_hash_pdf_assinado': assinatura.hash_pdf_assinado_sha256,
        'assinatura_tipo': 'assinatura_eletronica_interna',
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
    msg_assinatura_pdf = 'Sem análise técnica de assinatura PDF.'
    if assinatura is not None:
        status_assinatura_pdf, msg_assinatura_pdf = _validar_assinatura_pdf_tecnica(pdf_bytes)

    if not codigo:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_ARQUIVO_SEM_CODIGO
        mensagem = 'Não foi possível identificar um código de verificação no PDF enviado.'
    elif assinatura is None:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_CODIGO_NAO_ENCONTRADO
        mensagem = 'Código de verificação não encontrado.'
    elif assinatura.status != AssinaturaDocumento.STATUS_VALIDA:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_INVALIDO
        mensagem = 'A assinatura registrada não está ativa.'
    elif hash_pdf == assinatura.hash_pdf_assinado_sha256:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_VALIDO
        mensagem = 'O arquivo enviado corresponde exatamente ao PDF assinado originalmente.'
    else:
        resultado = ValidacaoAssinaturaDocumento.RESULTADO_INVALIDO
        mensagem = 'O arquivo enviado foi alterado após a assinatura, reexportado, editado ou não corresponde ao arquivo originalmente assinado.'

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
