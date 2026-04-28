from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
import re

from django.core.files.base import ContentFile
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader
from io import BytesIO

from cadastros.models import AssinaturaConfiguracao, ConfiguracaoSistema
from core.utils.masks import format_masked_display
from documentos.models import AssinaturaDocumento
from eventos.models import Oficio, OficioAssinaturaPedido
from eventos.services.documentos import DocumentoFormato, DocumentoOficioTipo, render_document_bytes
from eventos.services.documentos.backends import get_pdf_backend_availability
from eventos.services.documentos.types import DocumentRendererUnavailable


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload or b'').hexdigest()


def hash_conteudo_pdf_bytes(pdf_bytes: bytes) -> str:
    """Hash canônico do conteúdo textual do PDF (ignora metadados binários voláteis)."""
    if not pdf_bytes:
        return sha256_bytes(b'')
    if not bytes(pdf_bytes[:5]).startswith(b'%PDF-'):
        return sha256_bytes(pdf_bytes)
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        partes = []
        for page in reader.pages:
            texto = page.extract_text() or ''
            texto_norm = re.sub(r'\s+', ' ', texto).strip()
            if texto_norm:
                partes.append(texto_norm)
        if partes:
            payload = '\n'.join(partes).encode('utf-8')
            return sha256_bytes(payload)
    except Exception:
        # fallback seguro para não quebrar fluxo em PDFs não textuais
        pass
    return sha256_bytes(pdf_bytes)


def _only_digits(value: str) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO = (
    'Confirmação de identidade por CPF (5 dígitos) e telefone.'
)


def formatar_cpf_exibicao_auditoria(cpf: str) -> str:
    """Máscara de privacidade para CPF em telas de assinatura e consulta pública."""
    digits = _only_digits(cpf)
    if len(digits) != 11:
        return '—' if not digits else digits
    return f'***.{digits[3:6]}.{digits[6:9]}-**'


def _resolve_assinante_oficio():
    config = ConfiguracaoSistema.get_singleton()
    return (
        AssinaturaConfiguracao.objects.filter(
            configuracao=config,
            tipo=AssinaturaConfiguracao.TIPO_OFICIO,
            ordem=1,
            ativo=True,
            viajante__isnull=False,
        )
        .select_related('viajante')
        .first()
    )


def _mask_phone(phone_digits: str) -> str:
    return format_masked_display('telefone', phone_digits, empty='Telefone não informado')


def _public_link(request, pedido: OficioAssinaturaPedido) -> str:
    return request.build_absolute_uri(
        reverse('eventos:assinatura-oficio-identidade', kwargs={'token': pedido.token})
    )


PARTICULAS_MINUSCULAS_ASSINATURA = {'de', 'da', 'do', 'das', 'dos', 'e'}


def formatar_nome_assinatura(nome: str) -> str:
    """Formata nome para exibição de assinatura sem caixa alta bruta.

    Observação: não tenta inferir acentos que não existam no dado de origem.
    """
    bruto = re.sub(r'\s+', ' ', str(nome or '').strip())
    if not bruto:
        return ''
    partes = bruto.split(' ')
    resultado = []
    for idx, parte in enumerate(partes):
        lower = parte.lower()
        if idx > 0 and lower in PARTICULAS_MINUSCULAS_ASSINATURA:
            resultado.append(lower)
            continue
        if "'" in parte:
            subpartes = [p.capitalize() for p in parte.lower().split("'")]
            resultado.append("'".join(subpartes))
            continue
        if '-' in parte:
            subpartes = [p.capitalize() for p in parte.lower().split('-')]
            resultado.append('-'.join(subpartes))
            continue
        resultado.append(parte.lower().capitalize())
    return ' '.join(resultado)


@dataclass
class AssinaturaStatus:
    key: str
    label: str
    css_class: str


STATUS_META = {
    'SEM_ASSINATURA': AssinaturaStatus('SEM_ASSINATURA', 'Sem assinatura', 'is-muted'),
    'PENDENTE': AssinaturaStatus('PENDENTE', 'Pendente', 'is-warning'),
    'ASSINADO': AssinaturaStatus('ASSINADO', 'Assinado', 'is-finalizado'),
    'DESATUALIZADA': AssinaturaStatus('DESATUALIZADA', 'Assinatura desatualizada', 'is-warning'),
    'INVALIDADO': AssinaturaStatus('INVALIDADO', 'Invalidado', 'is-rascunho'),
}


def gerar_pdf_canonico_oficio(oficio: Oficio) -> bytes:
    return render_document_bytes(oficio, DocumentoOficioTipo.OFICIO, DocumentoFormato.PDF)


def criar_ou_obter_pedido_assinatura(oficio: Oficio, *, criado_por=None) -> OficioAssinaturaPedido:
    existente = (
        oficio.assinaturas_oficio.filter(status=OficioAssinaturaPedido.STATUS_PENDENTE)
        .order_by('-created_at')
        .first()
    )
    if existente:
        return existente

    assinatura_cfg = _resolve_assinante_oficio()
    viajante = assinatura_cfg.viajante if assinatura_cfg else None
    if not viajante:
        raise ValueError('Assinante de Ofício não configurado em Configurações do Sistema.')

    pdf_original = gerar_pdf_canonico_oficio(oficio)
    cpf = _only_digits(viajante.cpf)
    telefone = _only_digits(viajante.telefone)
    now = timezone.now()
    token = secrets.token_urlsafe(24)

    with transaction.atomic():
        pedido = OficioAssinaturaPedido.objects.create(
            oficio=oficio,
            token=token,
            assinante_esperado=viajante,
            nome_assinante_esperado=(viajante.nome or '').strip(),
            cpf_esperado=cpf,
            telefone_esperado=telefone,
            telefone_mascarado_exibido=_mask_phone(telefone),
            criado_por_usuario=criado_por if getattr(criado_por, 'is_authenticated', False) else None,
            criado_por_nome=(
                (criado_por.get_full_name() or criado_por.get_username() or '').strip()
                if getattr(criado_por, 'is_authenticated', False)
                else ''
            ),
            hash_pdf_original=hash_conteudo_pdf_bytes(pdf_original),
            expira_em=now + timedelta(days=7),
            auditoria={
                'nome_assinante_esperado': (viajante.nome or '').strip(),
                'cpf_esperado': cpf,
            },
        )
        pedido.pdf_original_congelado.save(
            f'oficio-{oficio.pk}-original.pdf',
            ContentFile(pdf_original),
            save=False,
        )
        pedido.save(update_fields=['pdf_original_congelado', 'updated_at'])
    return pedido


def invalidar_pedidos_pendentes_oficio(oficio: Oficio):
    oficio.assinaturas_oficio.filter(status=OficioAssinaturaPedido.STATUS_PENDENTE).update(
        status=OficioAssinaturaPedido.STATUS_INVALIDADO,
        updated_at=timezone.now(),
    )


def status_assinatura_oficio(oficio: Oficio) -> AssinaturaStatus:
    pedido = _latest_pedido_assinatura(oficio)
    if not pedido:
        return STATUS_META['SEM_ASSINATURA']
    if pedido.status == OficioAssinaturaPedido.STATUS_ASSINADO:
        if assinatura_foi_invalidada_por_alteracao(oficio, pedido):
            assinatura_id = (pedido.auditoria or {}).get('assinatura_documento_id')
            if assinatura_id:
                AssinaturaDocumento.objects.filter(pk=assinatura_id, status=AssinaturaDocumento.STATUS_VALIDA).update(
                    status=AssinaturaDocumento.STATUS_SUBSTITUIDA,
                    motivo_revogacao='Documento fonte alterado após a assinatura.',
                    updated_at=timezone.now(),
                )
            return STATUS_META['DESATUALIZADA']
        return STATUS_META['ASSINADO']
    if pedido.status == OficioAssinaturaPedido.STATUS_PENDENTE:
        if pedido.expira_em and pedido.expira_em < timezone.now():
            pedido.status = OficioAssinaturaPedido.STATUS_EXPIRADO
            pedido.save(update_fields=['status', 'updated_at'])
            return STATUS_META['INVALIDADO']
        return STATUS_META['PENDENTE']
    return STATUS_META['INVALIDADO']


def assinatura_foi_invalidada_por_alteracao(oficio: Oficio, pedido: OficioAssinaturaPedido) -> bool:
    if not pedido.hash_pdf_original:
        return False
    if not get_pdf_backend_availability().get('available'):
        return False
    if pedido.assinado_em and getattr(oficio, 'updated_at', None) and oficio.updated_at <= pedido.assinado_em:
        return False
    try:
        atual = gerar_pdf_canonico_oficio(oficio)
    except DocumentRendererUnavailable:
        # Sem backend DOCX->PDF disponível, não é possível revalidar neste ambiente.
        # Falha segura: preserva status atual sem quebrar a listagem.
        return False
    return hash_conteudo_pdf_bytes(atual) != pedido.hash_pdf_original


def _latest_pedido_assinatura(oficio: Oficio):
    prefetched = getattr(oficio, '_prefetched_objects_cache', {}).get('assinaturas_oficio')
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    return oficio.assinaturas_oficio.order_by('-created_at').first()


def validar_prefixo_cpf(pedido: OficioAssinaturaPedido, prefixo: str) -> bool:
    clean = _only_digits(prefixo)[:5]
    esperado = _only_digits(pedido.cpf_esperado)[:5]
    if not clean or clean != esperado:
        return False
    pedido.cpf_prefixo_confirmado = clean
    pedido.cpf_confirmado_em = timezone.now()
    pedido.save(update_fields=['cpf_prefixo_confirmado', 'cpf_confirmado_em', 'updated_at'])
    return True


def confirmar_telefone(pedido: OficioAssinaturaPedido):
    pedido.telefone_confirmado_em = timezone.now()
    pedido.save(update_fields=['telefone_confirmado_em', 'updated_at'])


def url_publica_assinatura(request, pedido: OficioAssinaturaPedido) -> str:
    return _public_link(request, pedido)


def codigo_validacao_assinatura(token: str) -> str:
    raw = (token or '').replace('-', '').replace('_', '').upper()
    if not raw:
        return ''
    base = raw[:20]
    grupos = [base[i : i + 4] for i in range(0, len(base), 4)]
    return '-'.join([g for g in grupos if g])


def local_assinatura_oficio(oficio: Oficio) -> str:
    cidade = getattr(getattr(oficio, 'cidade_sede', None), 'nome', '') or ''
    estado = getattr(getattr(oficio, 'estado_sede', None), 'sigla', '') or ''
    if cidade and estado:
        return f'{cidade}/{estado}'
    return cidade or estado or 'Não informado'
