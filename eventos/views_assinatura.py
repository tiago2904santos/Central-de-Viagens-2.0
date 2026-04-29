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

from documentos.models import AssinaturaDocumento
from documentos.services.assinaturas import assinar_documento_pdf
from eventos.models import Oficio, OficioAssinaturaPedido
from eventos.services.oficio_assinatura import (
    TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO,
    codigo_validacao_assinatura,
    criar_ou_obter_pedido_assinatura,
    formatar_cpf_exibicao_auditoria,
    formatar_nome_assinatura,
    invalidar_pedidos_pendentes_oficio,
    local_assinatura_oficio,
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


def _resolve_pedido_por_codigo(codigo: str):
    clean = ''.join(ch for ch in str(codigo or '') if ch.isalnum()).upper()
    if not clean:
        return None
    for pedido in OficioAssinaturaPedido.objects.select_related('oficio').order_by('-created_at')[:500]:
        codigo_documento = str((pedido.auditoria or {}).get('assinatura_documento_codigo') or '')
        if codigo_documento and codigo_documento.replace('-', '').upper() == clean:
            return pedido
        codigo_pedido = codigo_validacao_assinatura(pedido.token).replace('-', '').upper()
        if codigo_pedido == clean:
            return pedido
    return None


def _build_public_doc_context(request, pedido: OficioAssinaturaPedido):
    codigo_validacao = (pedido.auditoria or {}).get('assinatura_documento_codigo') or codigo_validacao_assinatura(pedido.token)
    if (pedido.auditoria or {}).get('assinatura_documento_codigo'):
        url_verificacao = request.build_absolute_uri(
            reverse('documentos:assinatura-verificar-codigo', kwargs={'codigo': codigo_validacao})
        )
    else:
        url_verificacao = request.build_absolute_uri(
            reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token})
        )
    cpf_mascarado = formatar_cpf_exibicao_auditoria(pedido.cpf_esperado)
    return {
        'pedido': pedido,
        'nome_assinatura': formatar_nome_assinatura(pedido.nome_assinante_esperado),
        'codigo_validacao': codigo_validacao,
        'url_verificacao': url_verificacao,
        'cpf_mascarado': cpf_mascarado,
        'local_assinatura': local_assinatura_oficio(pedido.oficio),
        'confirmacao_identidade': TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO,
        'identificador_oficio': pedido.oficio.numero_formatado or f'#{pedido.oficio_id}',
        'protocolo_oficio': (pedido.oficio.protocolo_formatado or '').strip() or 'Não informado',
        'inserido_por': pedido.criado_por_nome or 'Não informado',
        'pedido_criado_em': pedido.created_at,
    }


def _serve_pdf_file(arquivo, filename: str):
    if not arquivo or not getattr(arquivo, 'name', ''):
        return HttpResponse('PDF indisponível para este pedido.', status=404, content_type='text/plain; charset=utf-8')
    try:
        response = FileResponse(arquivo.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    except FileNotFoundError:
        return HttpResponse('Arquivo PDF não encontrado.', status=404, content_type='text/plain; charset=utf-8')


@login_required
@require_http_methods(['GET'])
def oficio_assinatura_gestao(request, pk):
    oficio = get_object_or_404(Oficio, pk=pk)
    pedido = oficio.assinaturas_oficio.order_by('-created_at').first()
    status = status_assinatura_oficio(oficio)
    codigo_validacao = ''
    if pedido and pedido.status == OficioAssinaturaPedido.STATUS_ASSINADO:
        codigo_validacao = (pedido.auditoria or {}).get('assinatura_documento_codigo') or codigo_validacao_assinatura(pedido.token)
    context = {
        'oficio': oficio,
        'pedido': pedido,
        'status_assinatura': status,
        'url_publica': url_publica_assinatura(request, pedido) if pedido else '',
        'codigo_validacao': codigo_validacao,
        'cpf_esperado_mascarado': formatar_cpf_exibicao_auditoria(pedido.cpf_esperado) if pedido else '',
    }
    return render(request, 'eventos/assinatura/oficio_assinatura_gestao.html', context)


def _build_validation_block_payload(request, pedido: OficioAssinaturaPedido, nome_assinatura: str, assinado_em_dt):
    codigo_validacao = (pedido.auditoria or {}).get('assinatura_documento_codigo') or codigo_validacao_assinatura(pedido.token)
    if (pedido.auditoria or {}).get('assinatura_documento_codigo'):
        validacao_url = request.build_absolute_uri(
            reverse('documentos:assinatura-verificar-codigo', kwargs={'codigo': codigo_validacao})
        )
    else:
        validacao_url = request.build_absolute_uri(
            reverse('eventos:assinatura-oficio-verificacao', kwargs={'token': pedido.token})
        )
    cpf_mascarado = formatar_cpf_exibicao_auditoria(pedido.cpf_esperado)
    return {
        'nome_documento': 'Ofício',
        'identificador_oficio': pedido.oficio.numero_formatado or f'#{pedido.oficio_id}',
        'protocolo': (pedido.oficio.protocolo_formatado or '').strip() or 'Não informado',
        'nome_assinante': nome_assinatura,
        'cpf_mascarado': cpf_mascarado,
        'assinado_em': timezone.localtime(assinado_em_dt).strftime('%d/%m/%Y %H:%M:%S'),
        'local_assinatura': local_assinatura_oficio(pedido.oficio),
        'confirmacao_identidade': TEXTO_CONFIRMACAO_IDENTIDADE_ASSINATURA_OFICIO,
        'criado_por_nome': (pedido.criado_por_nome or 'Não informado'),
        'pedido_criado_em': timezone.localtime(pedido.created_at).strftime('%d/%m/%Y %H:%M:%S'),
        'hash_documento': pedido.hash_pdf_original,
        'codigo_validacao': codigo_validacao,
        'url_verificacao': validacao_url,
        'texto_assinatura': 'Documento assinado eletronicamente no fluxo interno do sistema.',
    }


def _extract_signature_position(request):
    def _parse_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _parse_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    page_index = _parse_int(request.POST.get('sig_page', request.GET.get('sig_page')), -1)
    box_x = _parse_float(request.POST.get('sig_x', request.GET.get('sig_x')), 0.25)
    box_y = _parse_float(request.POST.get('sig_y', request.GET.get('sig_y')), 0.77)
    box_w = _parse_float(request.POST.get('sig_w', request.GET.get('sig_w')), 0.50)
    box_h = _parse_float(request.POST.get('sig_h', request.GET.get('sig_h')), 0.11)
    return {
        'page_index': page_index,
        'box_x': box_x,
        'box_y': box_y,
        'box_w': box_w,
        'box_h': box_h,
    }


def _render_signed_pdf_bytes(request, pedido: OficioAssinaturaPedido, fonte: str):
    nome_assinatura = formatar_nome_assinatura(pedido.nome_assinante_esperado)
    original_bytes = pedido.pdf_original_congelado.read()
    bloco_validacao = _build_validation_block_payload(
        request,
        pedido,
        nome_assinatura=nome_assinatura,
        assinado_em_dt=timezone.now(),
    )
    assinado_bytes, assinatura_meta = apply_text_signature_on_pdf(
        original_bytes,
        signer_name=nome_assinatura,
        font_key=fonte,
        validation_payload=bloco_validacao,
        signature_position=_extract_signature_position(request),
        strict_font=True,
    )
    return assinado_bytes, assinatura_meta, nome_assinatura, bloco_validacao


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_gerar_link_assinatura(request, pk):
    oficio = get_object_or_404(Oficio, pk=pk)
    forcar_novo = request.GET.get('novo') in {'1', 'true', 'True'}
    next_url = request.GET.get('next') or ''
    try:
        if forcar_novo:
            invalidar_pedidos_pendentes_oficio(oficio)
        pedido = criar_ou_obter_pedido_assinatura(oficio, criado_por=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('eventos:oficios-global')
    link = url_publica_assinatura(request, pedido)
    if forcar_novo:
        messages.success(request, f'Novo link de assinatura gerado: {link}')
    else:
        messages.success(request, f'Link de assinatura gerado: {link}')
    if next_url:
        return redirect(next_url)
    return redirect('eventos:oficios-global')


@require_http_methods(['GET', 'POST'])
def assinatura_oficio_identidade(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    if pedido.status == OficioAssinaturaPedido.STATUS_ASSINADO:
        return redirect('eventos:assinatura-oficio-verificacao', token=token)
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
            try:
                nome_assinatura = formatar_nome_assinatura(pedido.nome_assinante_esperado)
                assinatura_documento = assinar_documento_pdf(
                    pedido.oficio,
                    usuario=None,
                    metodo_autenticacao=AssinaturaDocumento.METODO_VALIDACAO_CPF,
                    pdf_original=pedido.pdf_original_congelado,
                    nome_documento='Ofício',
                    nome_assinante=nome_assinatura,
                    cpf_assinante=pedido.cpf_esperado,
                    request=request,
                    posicao=_extract_signature_position(request),
                    metadata={
                        'pedido_oficio_assinatura_id': pedido.pk,
                        'oficio_id': pedido.oficio_id,
                        'protocolo': (pedido.oficio.protocolo_formatado or '').strip(),
                    },
                )
                assinatura_documento.arquivo_pdf_assinado.open('rb')
                try:
                    assinado_bytes = assinatura_documento.arquivo_pdf_assinado.read()
                finally:
                    assinatura_documento.arquivo_pdf_assinado.close()
                assinatura_meta = {
                    'resolved_font_name': 'Helvetica',
                    'used_fallback': False,
                    'font_detail': 'carimbo institucional',
                    'signature_position': assinatura_documento.posicao_carimbo_json,
                }
                bloco_validacao = {
                    'codigo_validacao': assinatura_documento.codigo_verificacao,
                    'url_verificacao': request.build_absolute_uri(
                        reverse(
                            'documentos:assinatura-verificar-codigo',
                            kwargs={'codigo': assinatura_documento.codigo_verificacao},
                        )
                    ),
                }
            except ValueError as exc:
                logger.error('Falha ao aplicar fonte real no PDF do pedido %s: %s', pedido.pk, exc)
                erro = str(exc)
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
                'assinatura_posicao': assinatura_meta.get('signature_position'),
                'codigo_validacao': bloco_validacao.get('codigo_validacao'),
                'url_verificacao': bloco_validacao.get('url_verificacao'),
                'assinatura_documento_id': str(assinatura_documento.pk),
                'assinatura_documento_codigo': assinatura_documento.codigo_verificacao,
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
    context = _build_public_doc_context(request, pedido)
    return render(
        request,
        'eventos/assinatura/oficio_verificacao_publica.html',
        context,
    )


@require_http_methods(['GET'])
def assinatura_oficio_verificacao_por_codigo(request, codigo):
    pedido = _resolve_pedido_por_codigo(codigo)
    if not pedido:
        return HttpResponse('Código de validação não encontrado.', status=404, content_type='text/plain; charset=utf-8')
    return redirect('eventos:assinatura-oficio-verificacao', token=pedido.token)


@require_http_methods(['GET'])
def assinatura_oficio_documento_assinado(request, token):
    """Compatibilidade: URL antiga redireciona para a página única de consulta/verificação."""
    return redirect('eventos:assinatura-oficio-verificacao', token=token)


@require_http_methods(['GET'])
@xframe_options_exempt
def assinatura_oficio_pdf_original(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    return _serve_pdf_file(pedido.pdf_original_congelado, 'oficio-original.pdf')


@require_http_methods(['GET'])
@xframe_options_exempt
def assinatura_oficio_pdf_final(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    return _serve_pdf_file(pedido.pdf_assinado_final, 'oficio-assinado.pdf')


@require_http_methods(['GET'])
@xframe_options_exempt
def assinatura_oficio_pdf_assinado(request, token):
    pedido = get_object_or_404(OficioAssinaturaPedido, token=token)
    preview_font = (request.GET.get('preview_font') or '').strip()
    if pedido.status == OficioAssinaturaPedido.STATUS_PENDENTE and preview_font:
        try:
            preview_bytes, assinatura_meta, _nome, _bloco = _render_signed_pdf_bytes(request, pedido, preview_font)
            response = HttpResponse(preview_bytes, content_type='application/pdf')
            response['Content-Disposition'] = 'inline; filename="oficio-preview-assinado.pdf"'
            response['X-Assinatura-Fonte'] = assinatura_meta.get('resolved_font_name', '')
            response['X-Assinatura-Fallback'] = str(bool(assinatura_meta.get('used_fallback'))).lower()
            return response
        except ValueError as exc:
            logger.error('Preview de assinatura falhou para pedido %s: %s', pedido.pk, exc)
            return HttpResponse(str(exc), status=422, content_type='text/plain; charset=utf-8')
        except Exception as exc:  # noqa: BLE001
            logger.exception('Erro inesperado no preview de assinatura do pedido %s: %s', pedido.pk, exc)
            return HttpResponse('Falha ao gerar preview do PDF assinado.', status=500, content_type='text/plain; charset=utf-8')

    arquivo = pedido.pdf_assinado_final or pedido.pdf_original_congelado
    if not arquivo or not getattr(arquivo, 'name', ''):
        logger.warning('Preview de assinatura sem arquivo disponível para pedido %s', pedido.pk)
        return HttpResponse('PDF de preview indisponível para este pedido.', status=404, content_type='text/plain; charset=utf-8')
    return _serve_pdf_file(arquivo, 'oficio-preview.pdf')
