import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.text import slugify


def assinatura_documento_upload_to(instance, filename):
    base = Path(filename or '').name.strip() or 'documento-assinado.pdf'
    safe_name = slugify(Path(base).stem) or 'documento-assinado'
    ext = Path(base).suffix.lower() or '.pdf'
    app_label = instance.content_type.app_label if instance.content_type_id else 'documento'
    model = instance.content_type.model if instance.content_type_id else 'generico'
    return f'assinaturas/{app_label}/{model}/{instance.object_id}/{safe_name}-{uuid.uuid4().hex[:10]}{ext}'


class AssinaturaDocumento(models.Model):
    STATUS_VALIDA = 'valida'
    STATUS_REVOGADA = 'revogada'
    STATUS_SUBSTITUIDA = 'substituida'
    STATUS_CHOICES = [
        (STATUS_VALIDA, 'Válida'),
        (STATUS_REVOGADA, 'Revogada'),
        (STATUS_SUBSTITUIDA, 'Substituída'),
    ]

    METODO_USUARIO_SISTEMA = 'usuario_sistema'
    METODO_CONTA_GOOGLE = 'conta_google'
    METODO_LOGIN_INTERNO = 'login_interno'
    METODO_VALIDACAO_CPF = 'validacao_cpf'
    METODO_CHOICES = [
        (METODO_USUARIO_SISTEMA, 'Usuário do sistema'),
        (METODO_CONTA_GOOGLE, 'Conta Google'),
        (METODO_LOGIN_INTERNO, 'Login interno'),
        (METODO_VALIDACAO_CPF, 'Validação por CPF'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name='assinaturas_documentos')
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    usuario_assinante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assinaturas_documentos',
    )
    nome_assinante = models.CharField(max_length=160)
    cpf_assinante = models.CharField(max_length=14, blank=True, default='')
    email_assinante = models.EmailField(blank=True, default='')
    metodo_autenticacao = models.CharField(
        max_length=40,
        choices=METODO_CHOICES,
        default=METODO_USUARIO_SISTEMA,
    )
    ip_assinatura = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    data_hora_assinatura = models.DateTimeField()
    codigo_verificacao = models.CharField(max_length=32, unique=True, db_index=True)
    hash_pdf_original_sha256 = models.CharField(max_length=64)
    hash_pdf_assinado_sha256 = models.CharField(max_length=64, blank=True, default='')
    arquivo_pdf_assinado = models.FileField(upload_to=assinatura_documento_upload_to, blank=True, null=True)
    pagina_carimbo = models.PositiveIntegerField(default=1)
    posicao_carimbo_json = models.JSONField(blank=True, default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_VALIDA, db_index=True)
    motivo_revogacao = models.TextField(blank=True, default='')
    metadata_json = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_hora_assinatura', '-created_at']
        verbose_name = 'Assinatura de documento'
        verbose_name_plural = 'Assinaturas de documentos'
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'status']),
        ]

    def __str__(self):
        return f'{self.codigo_verificacao} - {self.nome_assinante}'


class ValidacaoAssinaturaDocumento(models.Model):
    RESULTADO_VALIDO = 'valido'
    RESULTADO_INVALIDO = 'invalido'
    RESULTADO_CODIGO_NAO_ENCONTRADO = 'codigo_nao_encontrado'
    RESULTADO_ARQUIVO_SEM_CODIGO = 'arquivo_sem_codigo'
    RESULTADO_CHOICES = [
        (RESULTADO_VALIDO, 'Válido'),
        (RESULTADO_INVALIDO, 'Inválido'),
        (RESULTADO_CODIGO_NAO_ENCONTRADO, 'Código não encontrado'),
        (RESULTADO_ARQUIVO_SEM_CODIGO, 'Arquivo sem código'),
    ]

    assinatura = models.ForeignKey(
        AssinaturaDocumento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validacoes',
    )
    data_hora = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    hash_pdf_enviado = models.CharField(max_length=64, blank=True, default='')
    resultado = models.CharField(max_length=40, choices=RESULTADO_CHOICES)
    observacao = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-data_hora', '-pk']
        verbose_name = 'Validação de assinatura'
        verbose_name_plural = 'Validações de assinatura'

    def __str__(self):
        return f'{self.get_resultado_display()} em {self.data_hora:%d/%m/%Y %H:%M}'
