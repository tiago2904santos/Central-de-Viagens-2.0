import csv
from io import StringIO

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from documentos.models import AssinaturaDocumento, ValidacaoAssinaturaDocumento
from documentos.services.assinaturas import calcular_sha256_bytes, mascarar_cpf_assinatura, validar_codigo, validar_pdf_por_upload
from eventos.models import OficioAssinaturaPedido


@login_required
@require_http_methods(['GET', 'POST'])
def assinatura_gestao(request):
    queryset = AssinaturaDocumento.objects.select_related('content_type', 'usuario_assinante').order_by('-data_hora_assinatura')
    if not request.user.is_staff and not request.user.is_superuser:
        queryset = queryset.filter(usuario_assinante=request.user)

    filtros = {
        'busca': (request.GET.get('q') or '').strip(),
        'status': (request.GET.get('status') or '').strip(),
        'tipo_documento': (request.GET.get('tipo_documento') or '').strip(),
        'assinante': (request.GET.get('assinante') or '').strip(),
        'token': (request.GET.get('token') or '').strip().upper(),
    }

    if filtros['busca']:
        queryset = queryset.filter(
            Q(nome_assinante__icontains=filtros['busca'])
            | Q(codigo_verificacao__icontains=filtros['busca'])
            | Q(metadata_json__nome_documento__icontains=filtros['busca'])
            | Q(object_id__icontains=filtros['busca'])
        )
    if filtros['status']:
        queryset = queryset.filter(status=filtros['status'])
    if filtros['tipo_documento']:
        queryset = queryset.filter(content_type__model=filtros['tipo_documento'])
    if filtros['assinante']:
        queryset = queryset.filter(nome_assinante__icontains=filtros['assinante'])
    if filtros['token']:
        queryset = queryset.filter(codigo_verificacao__icontains=filtros['token'])

    if request.GET.get('exportar') == 'csv':
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerow(
            [
                'tipo_documento',
                'numero_documento',
                'assinante',
                'cpf_mascarado',
                'status',
                'data_assinatura',
                'token',
                'url_validacao',
            ]
        )
        for assinatura in queryset:
            writer.writerow(
                [
                    assinatura.content_type.model,
                    assinatura.object_id,
                    assinatura.nome_assinante,
                    mascarar_cpf_assinatura(assinatura.cpf_assinante),
                    assinatura.get_status_display(),
                    assinatura.data_hora_assinatura.strftime('%d/%m/%Y %H:%M'),
                    assinatura.codigo_verificacao,
                    request.build_absolute_uri(
                        f"/assinaturas/verificar/{assinatura.codigo_verificacao}/"
                    ),
                ]
            )
        response = HttpResponse(stream.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="assinaturas.csv"'
        return response

    validacao_resultado = None
    validacao_erro = ''
    token_validacao = (request.POST.get('codigo_verificacao') or request.GET.get('token') or '').strip().upper()
    if token_validacao:
        assinatura_token = validar_codigo(token_validacao)
        if assinatura_token:
            validacao_resultado = _montar_contexto_validacao_assinatura(assinatura_token)
        elif request.method == 'POST' and request.POST.get('acao_validar') == 'token':
            validacao_erro = 'Código de validação não encontrado.'

    upload_resultado = None
    if request.method == 'POST' and request.POST.get('acao_validar') == 'upload':
        arquivo = request.FILES.get('arquivo_pdf')
        if not arquivo:
            validacao_erro = 'Envie um arquivo PDF para validação.'
        else:
            upload_resultado = validar_pdf_por_upload(
                arquivo,
                codigo_manual=request.POST.get('codigo_verificacao', ''),
                request=request,
            )

    indicadores = AssinaturaDocumento.objects.aggregate(
        total=Count('id'),
        validas=Count('id', filter=Q(status=AssinaturaDocumento.STATUS_VALIDA)),
        revogadas=Count('id', filter=Q(status=AssinaturaDocumento.STATUS_REVOGADA)),
        substituidas=Count('id', filter=Q(status=AssinaturaDocumento.STATUS_SUBSTITUIDA)),
    )
    pendentes = OficioAssinaturaPedido.objects.filter(status=OficioAssinaturaPedido.STATUS_PENDENTE).count()
    tipos_documento = AssinaturaDocumento.objects.values_list('content_type__model', flat=True).distinct().order_by('content_type__model')

    return render(
        request,
        'documentos/assinaturas/gestao.html',
        {
            'assinaturas': queryset[:200],
            'filtros': filtros,
            'tipos_documento': [tipo for tipo in tipos_documento if tipo],
            'status_choices': AssinaturaDocumento.STATUS_CHOICES,
            'indicadores': indicadores,
            'pendentes_total': pendentes,
            'validacao_resultado': validacao_resultado,
            'upload_resultado': upload_resultado,
            'validacao_erro': validacao_erro,
            'token_validacao': token_validacao,
        },
    )


@require_http_methods(['GET', 'POST'])
def assinatura_verificador(request):
    return redirect('documentos:assinatura-gestao')


def _montar_contexto_validacao_assinatura(assinatura):
    hash_atual_pdf_assinado = ''
    status_integridade_registro = False
    if assinatura.arquivo_pdf_assinado:
        assinatura.arquivo_pdf_assinado.open('rb')
        try:
            hash_atual_pdf_assinado = calcular_sha256_bytes(assinatura.arquivo_pdf_assinado.read())
        finally:
            assinatura.arquivo_pdf_assinado.close()
        status_integridade_registro = hash_atual_pdf_assinado == (assinatura.hash_pdf_assinado_sha256 or '')
    status_documento_valido = assinatura.status == AssinaturaDocumento.STATUS_VALIDA and status_integridade_registro
    return {
        'assinatura': assinatura,
        'status_valido': assinatura.status == AssinaturaDocumento.STATUS_VALIDA,
        'hash_atual_pdf_assinado': hash_atual_pdf_assinado,
        'status_integridade_registro': status_integridade_registro,
        'cpf_mascarado': mascarar_cpf_assinatura(assinatura.cpf_assinante),
        'status_documento_valido': status_documento_valido,
    }


@require_http_methods(['GET'])
def assinatura_verificar_codigo(request, codigo):
    assinatura = validar_codigo(codigo)
    if not assinatura:
        return HttpResponse('Código de verificação não encontrado.', status=404, content_type='text/plain; charset=utf-8')
    contexto = _montar_contexto_validacao_assinatura(assinatura)
    return render(
        request,
        'documentos/assinaturas/verificar_codigo.html',
        contexto,
    )


@require_http_methods(['GET', 'POST'])
def assinatura_verificar_upload(request):
    return redirect('documentos:assinatura-gestao')


@login_required
@require_http_methods(['GET'])
def assinatura_detalhe(request, assinatura_id):
    assinatura = get_object_or_404(AssinaturaDocumento.objects.select_related('content_type', 'usuario_assinante'), pk=assinatura_id)
    if not request.user.is_staff and not request.user.is_superuser and assinatura.usuario_assinante_id != request.user.id:
        return HttpResponse('Sem permissão para acessar esta assinatura.', status=403, content_type='text/plain; charset=utf-8')
    contexto = _montar_contexto_validacao_assinatura(assinatura)
    contexto['historico_validacoes'] = assinatura.validacoes.all()[:20]
    return render(request, 'documentos/assinaturas/detalhe.html', contexto)


@require_http_methods(['GET'])
def assinatura_verificar_publico(request, token):
    assinatura = validar_codigo(token)
    if not assinatura:
        return HttpResponse('Código de verificação não encontrado.', status=404, content_type='text/plain; charset=utf-8')
    ValidacaoAssinaturaDocumento.objects.create(
        assinatura=assinatura,
        ip=request.META.get('REMOTE_ADDR'),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:1000],
        resultado=ValidacaoAssinaturaDocumento.RESULTADO_VALIDO,
        observacao='Validação por token público.',
    )
    contexto = _montar_contexto_validacao_assinatura(assinatura)
    contexto['publico'] = True
    return render(request, 'documentos/assinaturas/verificar_codigo.html', contexto)
