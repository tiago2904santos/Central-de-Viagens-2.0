from django.contrib import admin

from .models import AssinaturaDocumento, ValidacaoAssinaturaDocumento


@admin.register(AssinaturaDocumento)
class AssinaturaDocumentoAdmin(admin.ModelAdmin):
    list_display = (
        'codigo_verificacao',
        'content_type',
        'object_id',
        'nome_assinante',
        'status',
        'data_hora_assinatura',
    )
    list_filter = ('status', 'metodo_autenticacao', 'content_type')
    search_fields = ('codigo_verificacao', 'nome_assinante', 'cpf_assinante', 'email_assinante')
    readonly_fields = (
        'id',
        'codigo_verificacao',
        'hash_pdf_original_sha256',
        'hash_pdf_assinado_sha256',
        'created_at',
        'updated_at',
    )


@admin.register(ValidacaoAssinaturaDocumento)
class ValidacaoAssinaturaDocumentoAdmin(admin.ModelAdmin):
    list_display = ('data_hora', 'assinatura', 'resultado', 'hash_pdf_enviado')
    list_filter = ('resultado',)
    search_fields = ('assinatura__codigo_verificacao', 'hash_pdf_enviado', 'observacao')
    readonly_fields = ('data_hora',)
