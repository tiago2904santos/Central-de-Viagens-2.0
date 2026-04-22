from django.contrib import admin

from assinaturas.models import AssinaturaDocumento, AssinaturaEtapa


class AssinaturaEtapaInline(admin.TabularInline):
    model = AssinaturaEtapa
    extra = 0
    readonly_fields = (
        "token",
        "signed_at",
        "arquivo_sha256_apos_etapa",
        "cpf_esperado_normalizado",
        "cpf_informado",
        "cpf_normalizado",
        "cpf_confere",
    )
    raw_id_fields = ("viajante",)


@admin.register(AssinaturaDocumento)
class AssinaturaDocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "documento_tipo",
        "documento_id",
        "status",
        "expires_at",
        "nome_assinante",
        "signed_at",
    )
    list_filter = ("status", "documento_tipo")
    inlines = [AssinaturaEtapaInline]
    readonly_fields = (
        "token",
        "verificacao_token",
        "created_at",
        "signed_at",
        "ip",
        "user_agent",
        "arquivo_original_sha256",
        "arquivo_assinado_sha256",
        "nome_assinante_normalizado",
        "drive_sync_error",
    )
    search_fields = ("nome_assinante", "documento_id", "arquivo_original_sha256")


@admin.register(AssinaturaEtapa)
class AssinaturaEtapaAdmin(admin.ModelAdmin):
    list_display = ("id", "assinatura", "ordem", "status", "nome_previsto", "signed_at")
    list_filter = ("status", "tipo_assinante")
    search_fields = ("nome_assinante", "nome_previsto")
    raw_id_fields = ("assinatura", "viajante")
