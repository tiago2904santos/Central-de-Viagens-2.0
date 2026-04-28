from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from io import BytesIO

from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento


CODIGO_RE = re.compile(r'CV-\d{4}-[A-Z0-9]{6}-[A-Z0-9]{4}')
SISTEMA_ASSINATURA = 'Central de Viagens'


@dataclass(frozen=True)
class DadosCarimbo:
    nome_assinante: str
    cpf_mascarado: str
    data_hora_assinatura: timezone.datetime
    codigo_verificacao: str
    url_validacao: str


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
        'box_x': min(max(float(raw.get('box_x', raw.get('x_ratio', 0.53))), 0.01), 0.95),
        'box_y': min(max(float(raw.get('box_y', raw.get('y_ratio', 0.82))), 0.01), 0.95),
        'box_w': min(max(float(raw.get('box_w', 0.42)), 0.18), 0.95),
        'box_h': min(max(float(raw.get('box_h', 0.13)), 0.08), 0.35),
        'qr': bool(raw.get('qr', True)),
    }


def _draw_wrapped(c, text: str, x: float, y: float, max_width: float, *, font='Helvetica', size=7.2, leading=9):
    words = str(text or '').split()
    lines = []
    current = ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    c.setFont(font, size)
    for line in lines[:2]:
        c.drawString(x, y, line)
        y -= leading
    return y


def gerar_overlay_carimbo(page_width: float, page_height: float, dados_carimbo: DadosCarimbo, posicao: dict) -> bytes:
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=(page_width, page_height))

    box_w = page_width * posicao['box_w']
    box_h = page_height * posicao['box_h']
    left = page_width * posicao['box_x']
    bottom = page_height - (page_height * posicao['box_y']) - box_h
    left = min(max(left, 8), page_width - box_w - 8)
    bottom = min(max(bottom, 8), page_height - box_h - 8)

    c.setStrokeColor(HexColor('#64748b'))
    c.setFillColor(HexColor('#ffffff'))
    c.roundRect(left, bottom, box_w, box_h, 4, stroke=1, fill=1)

    padding = 8
    text_x = left + padding
    text_y = bottom + box_h - 13
    qr_size = min(46, box_h - 14)
    text_width = box_w - (padding * 2)
    if posicao.get('qr') and dados_carimbo.url_validacao:
        text_width -= qr_size + 8

    c.setFillColor(HexColor('#0f172a'))
    c.setFont('Helvetica-Bold', 7.8)
    c.drawString(text_x, text_y, 'ASSINADO ELETRONICAMENTE')
    text_y -= 10
    text_y = _draw_wrapped(c, f'por {dados_carimbo.nome_assinante}', text_x, text_y, text_width, size=7.1)
    c.setFont('Helvetica', 6.8)
    data_local = timezone.localtime(dados_carimbo.data_hora_assinatura).strftime('%d/%m/%Y %H:%M')
    linhas = [
        f'CPF: {dados_carimbo.cpf_mascarado}',
        f'Data/hora: {data_local}',
        f'Código: {dados_carimbo.codigo_verificacao}',
        f'Verifique em: {dados_carimbo.url_validacao}',
    ]
    for linha in linhas:
        if text_y < bottom + 7:
            break
        c.drawString(text_x, text_y, str(linha)[:92])
        text_y -= 8.2

    if posicao.get('qr') and dados_carimbo.url_validacao and qr_size > 22:
        qr_code = qr.QrCodeWidget(dados_carimbo.url_validacao)
        bounds = qr_code.getBounds()
        scale = qr_size / max(bounds[2] - bounds[0], bounds[3] - bounds[1])
        drawing = Drawing(qr_size, qr_size, transform=[scale, 0, 0, scale, 0, 0])
        drawing.add(qr_code)
        renderPDF.draw(drawing, c, left + box_w - qr_size - padding, bottom + box_h - qr_size - padding)

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
    pdf_assinado, posicao_final = aplicar_carimbo_pdf(pdf_original_bytes, dados, posicao)
    assinatura.hash_pdf_assinado_sha256 = calcular_sha256_bytes(pdf_assinado)
    assinatura.pagina_carimbo = posicao_final['page_number']
    assinatura.posicao_carimbo_json = posicao_final
    assinatura.metadata_json = {
        **assinatura.metadata_json,
        'assinatura_hash_pdf_assinado': assinatura.hash_pdf_assinado_sha256,
    }
    filename = f'{nome_documento.lower().replace(" ", "-")}-{documento.pk}-{assinatura.codigo_verificacao}.pdf'
    assinatura.arquivo_pdf_assinado.save(filename, ContentFile(pdf_assinado), save=False)
    assinatura.save(
        update_fields=[
            'hash_pdf_assinado_sha256',
            'pagina_carimbo',
            'posicao_carimbo_json',
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
        observacao=mensagem,
    )
    return {
        'assinatura': assinatura,
        'codigo': codigo,
        'hash_pdf_enviado': hash_pdf,
        'resultado': resultado,
        'valido': resultado == ValidacaoAssinaturaDocumento.RESULTADO_VALIDO,
        'mensagem': mensagem,
    }
