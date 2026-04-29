from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from documentos.models import AssinaturaDocumento
from documentos.services.assinaturas import calcular_sha256_bytes, mascarar_cpf_assinatura, validar_codigo, validar_pdf_por_upload


@login_required
def placeholder_view(request):
    return render(request, 'core/placeholder.html', {'modulo': 'Documentos'})


@require_http_methods(['GET', 'POST'])
def assinatura_verificador(request):
    codigo = ''
    if request.method == 'POST':
        codigo = (request.POST.get('codigo_verificacao') or '').strip()
        if codigo:
            return redirect('documentos:assinatura-verificar-codigo', codigo=codigo)
    return render(request, 'documentos/assinaturas/verificador.html', {'codigo': codigo})


@require_http_methods(['GET'])
def assinatura_verificar_codigo(request, codigo):
    assinatura = validar_codigo(codigo)
    if not assinatura:
        return HttpResponse('Código de verificação não encontrado.', status=404, content_type='text/plain; charset=utf-8')
    hash_atual_pdf_assinado = ''
    status_integridade_registro = False
    if assinatura.arquivo_pdf_assinado:
        assinatura.arquivo_pdf_assinado.open('rb')
        try:
            hash_atual_pdf_assinado = calcular_sha256_bytes(assinatura.arquivo_pdf_assinado.read())
        finally:
            assinatura.arquivo_pdf_assinado.close()
        status_integridade_registro = hash_atual_pdf_assinado == (assinatura.hash_pdf_assinado_sha256 or '')
    return render(
        request,
        'documentos/assinaturas/verificar_codigo.html',
        {
            'assinatura': assinatura,
            'documento': assinatura.content_object,
            'status_valido': assinatura.status == AssinaturaDocumento.STATUS_VALIDA,
            'hash_atual_pdf_assinado': hash_atual_pdf_assinado,
            'status_integridade_registro': status_integridade_registro,
            'cpf_mascarado': mascarar_cpf_assinatura(assinatura.cpf_assinante),
            'status_documento_valido': assinatura.status == AssinaturaDocumento.STATUS_VALIDA and status_integridade_registro,
        },
    )


@require_http_methods(['GET', 'POST'])
def assinatura_verificar_upload(request):
    resultado = None
    erro = ''
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo_pdf')
        if not arquivo:
            erro = 'Envie um arquivo PDF para validação.'
        elif arquivo.content_type and arquivo.content_type != 'application/pdf':
            erro = 'O arquivo enviado deve ser um PDF.'
        else:
            resultado = validar_pdf_por_upload(
                arquivo,
                codigo_manual=request.POST.get('codigo_verificacao', ''),
                request=request,
            )
    return render(
        request,
        'documentos/assinaturas/verificar_upload.html',
        {'resultado': resultado, 'erro': erro},
    )
