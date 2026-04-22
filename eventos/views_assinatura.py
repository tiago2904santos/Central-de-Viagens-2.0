from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt

from eventos.models import Oficio, OficioAssinaturaPedido
from eventos.services.oficio_assinatura import (
    criar_ou_obter_pedido_assinatura,
    formatar_nome_assinatura,
    sha256_bytes,
    status_assinatura_oficio,
    url_publica_assinatura,
    validar_prefixo_cpf,
    confirmar_telefone,
)
from eventos.services.pdf_signature import apply_text_signature_on_pdf


SIGN_SESSION_KEY = 'oficio_assinatura_confirmada'
logger = logging.getLogger(__name__)


def _status_page(request, pedido, titulo, mensagem):
    return render(
        request,
        'eventos/assinatura/oficio_status_publico.html',
        {'pedido': pedido, 'titulo': titulo, 'mensagem': mensagem},
    )


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_gerar_link_assinatura(request, pk):
    oficio = get_object_or_404(Oficio, pk=pk)
    try:
        pedido = criar_ou_obter_pedido_assinatura(oficio)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('eventos:oficios-global')
    link = url_publica_assinatura(request, pedido)
    messages.success(request, f'Link de assinatura gerado: {link}')
    return redirect('eventos:oficios-global')


@require_http_methods(['GET', 'POST'])
def assinatura_oficio_identidade(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    if pedido.status == OficioAssinaturaPedido.STATUS_ASSINADO:
        return _status_page(request, pedido, 'Documento já assinado', 'Este link já foi utilizado.')
    if pedido.status in {OficioAssinaturaPedido.STATUS_INVALIDADO, OficioAssinaturaPedido.STATUS_EXPIRADO}:
        return _status_page(request, pedido, 'Link inválido', 'Este pedido de assinatura não está mais válido.')
    if pedido.expira_em and pedido.expira_em < timezone.now():
        pedido.status = OficioAssinaturaPedido.STATUS_EXPIRADO
        pedido.save(update_fields=['status', 'updated_at'])
        return _status_page(request, pedido, 'Link expirado', 'Este pedido de assinatura expirou.')

    session_data = request.session.get(SIGN_SESSION_KEY, {})
    if session_data.get(token):
        return redirect('eventos:assinatura-oficio-assinar', token=token)

    etapa = 'cpf' if not pedido.cpf_confirmado_em else 'telefone'
    erro = ''
    if request.method == 'POST':
        if request.POST.get('etapa') == 'cpf':
            if validar_prefixo_cpf(pedido, request.POST.get('cpf_prefixo', '')):
                etapa = 'telefone'
            else:
                erro = 'Os 5 primeiros dígitos do CPF não conferem.'
        elif request.POST.get('etapa') == 'telefone':
            confirmar = request.POST.get('confirmar_telefone') == '1'
            if confirmar:
                confirmar_telefone(pedido)
                session_data[token] = True
                request.session[SIGN_SESSION_KEY] = session_data
                request.session.modified = True
                return redirect('eventos:assinatura-oficio-assinar', token=token)
            erro = 'É necessário confirmar o telefone para continuar.'

    return render(
        request,
        'eventos/assinatura/oficio_confirmacao_publica.html',
        {'pedido': pedido, 'etapa': etapa, 'erro': erro},
    )


@require_http_methods(['GET', 'POST'])
def assinatura_oficio_assinar(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    if pedido.status != OficioAssinaturaPedido.STATUS_PENDENTE:
        return _status_page(request, pedido, 'Assinatura indisponível', 'Este pedido não está pendente.')
    session_data = request.session.get(SIGN_SESSION_KEY, {})
    if not session_data.get(token):
        return redirect('eventos:assinatura-oficio-identidade', token=token)

    erro = ''
    if request.method == 'POST':
        fonte = request.POST.get('fonte_escolhida', '')
        fontes_validas = {item[0] for item in OficioAssinaturaPedido.FONTE_CHOICES}
        if fonte not in fontes_validas:
            erro = 'Selecione uma fonte válida.'
        elif not pedido.pdf_original_congelado:
            erro = 'PDF original não encontrado para assinatura.'
        else:
            nome_assinatura = formatar_nome_assinatura(pedido.nome_assinante_esperado)
            original_bytes = pedido.pdf_original_congelado.read()
            assinado_bytes, assinatura_meta = apply_text_signature_on_pdf(
                original_bytes,
                signer_name=nome_assinatura,
                font_key=fonte,
            )
            pedido.fonte_escolhida = fonte
            pedido.hash_pdf_assinado = sha256_bytes(assinado_bytes)
            pedido.assinado_em = timezone.now()
            pedido.status = OficioAssinaturaPedido.STATUS_ASSINADO
            pedido.assinado_ip = request.META.get('REMOTE_ADDR')
            pedido.assinado_user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:1000]
            pedido.auditoria = {
                **(pedido.auditoria or {}),
                'nome_assinatura_formatado': nome_assinatura,
                'cpf_prefixo_confirmado': pedido.cpf_prefixo_confirmado,
                'telefone_mascarado_exibido': pedido.telefone_mascarado_exibido,
                'hash_pdf_original': pedido.hash_pdf_original,
                'hash_pdf_assinado': pedido.hash_pdf_assinado,
                'fonte_escolhida': fonte,
                'fonte_pdf_resolvida': assinatura_meta.get('resolved_font_name'),
                'fonte_pdf_fallback': bool(assinatura_meta.get('used_fallback')),
                'fonte_pdf_detalhe': assinatura_meta.get('font_detail'),
                'assinado_em': pedido.assinado_em.isoformat(),
                'status': pedido.status,
            }
            pedido.pdf_assinado_final.save(
                f'oficio-{pedido.oficio_id}-assinado.pdf',
                ContentFile(assinado_bytes),
                save=False,
            )
            pedido.save()
            session_data.pop(token, None)
            request.session[SIGN_SESSION_KEY] = session_data
            request.session.modified = True
            return redirect('eventos:assinatura-oficio-verificacao', token=token)

    return render(
        request,
        'eventos/assinatura/oficio_assinar_publico.html',
        {
            'pedido': pedido,
            'erro': erro,
            'fontes': OficioAssinaturaPedido.FONTE_CHOICES,
            'status_oficio': status_assinatura_oficio(pedido.oficio),
            'nome_assinatura': formatar_nome_assinatura(pedido.nome_assinante_esperado),
        },
    )


@require_http_methods(['GET'])
def assinatura_oficio_verificacao(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    return render(
        request,
        'eventos/assinatura/oficio_verificacao_publica.html',
        {
            'pedido': pedido,
            'nome_assinatura': formatar_nome_assinatura(pedido.nome_assinante_esperado),
        },
    )


@require_http_methods(['GET'])
@xframe_options_exempt
def assinatura_oficio_pdf_assinado(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    arquivo = pedido.pdf_assinado_final or pedido.pdf_original_congelado
    if not arquivo or not getattr(arquivo, 'name', ''):
        logger.warning('Preview de assinatura sem arquivo disponível para pedido %s', pedido.pk)
        return HttpResponse('PDF de preview indisponível para este pedido.', status=404, content_type='text/plain; charset=utf-8')
    try:
        response = FileResponse(arquivo.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="oficio-preview.pdf"'
        return response
    except FileNotFoundError:
        logger.warning('Arquivo de preview ausente no storage para pedido %s', pedido.pk)
        return HttpResponse('Arquivo do PDF de preview não foi encontrado.', status=404, content_type='text/plain; charset=utf-8')
