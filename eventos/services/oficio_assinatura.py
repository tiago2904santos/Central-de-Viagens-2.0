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

from cadastros.models import AssinaturaConfiguracao, ConfiguracaoSistema
from core.utils.masks import format_masked_display
from eventos.models import Oficio, OficioAssinaturaPedido
from eventos.services.documentos import DocumentoFormato, DocumentoOficioTipo, render_document_bytes


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload or b'').hexdigest()


def _only_digits(value: str) -> str:
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


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
    'INVALIDADO': AssinaturaStatus('INVALIDADO', 'Invalidado', 'is-rascunho'),
}


def gerar_pdf_canonico_oficio(oficio: Oficio) -> bytes:
    return render_document_bytes(oficio, DocumentoOficioTipo.OFICIO, DocumentoFormato.PDF)


def criar_ou_obter_pedido_assinatura(oficio: Oficio) -> OficioAssinaturaPedido:
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
            hash_pdf_original=sha256_bytes(pdf_original),
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


def status_assinatura_oficio(oficio: Oficio) -> AssinaturaStatus:
    pedido = oficio.assinaturas_oficio.order_by('-created_at').first()
    if not pedido:
        return STATUS_META['SEM_ASSINATURA']
    if pedido.status == OficioAssinaturaPedido.STATUS_ASSINADO:
        if assinatura_foi_invalidada_por_alteracao(oficio, pedido):
            pedido.status = OficioAssinaturaPedido.STATUS_INVALIDADO
            pedido.save(update_fields=['status', 'updated_at'])
            return STATUS_META['INVALIDADO']
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
    atual = gerar_pdf_canonico_oficio(oficio)
    return sha256_bytes(atual) != pedido.hash_pdf_original


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
