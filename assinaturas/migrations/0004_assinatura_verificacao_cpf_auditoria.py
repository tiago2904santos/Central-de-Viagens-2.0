# Generated manually — evita tokens duplicados no SQLite ao adicionar UNIQUE.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def preencher_verificacao_token(apps, schema_editor):
    AssinaturaDocumento = apps.get_model("assinaturas", "AssinaturaDocumento")
    for row in AssinaturaDocumento.objects.all():
        if getattr(row, "verificacao_token", None):
            continue
        row.verificacao_token = uuid.uuid4()
        row.save(update_fields=["verificacao_token"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("assinaturas", "0003_assinatura_etapa_multassinatura"),
    ]

    operations = [
        migrations.AddField(
            model_name="assinaturadocumento",
            name="verificacao_token",
            field=models.UUIDField(
                null=True,
                blank=True,
                editable=False,
                db_index=True,
                verbose_name="Token publico de verificacao",
            ),
        ),
        migrations.RunPython(preencher_verificacao_token, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="assinaturadocumento",
            name="verificacao_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                unique=True,
                editable=False,
                db_index=True,
                verbose_name="Token publico de verificacao",
            ),
        ),
        migrations.AddField(
            model_name="assinaturadocumento",
            name="usuario_ultima_etapa",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assinaturas_documento_ultima_etapa",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Utilizador autenticado (ultima etapa)",
            ),
        ),
        migrations.AddField(
            model_name="assinaturaetapa",
            name="cpf_esperado_normalizado",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Vazio para etapas sem CPF conhecido no cadastro (assinatura recusada ate corrigir).",
                max_length=11,
                verbose_name="CPF esperado (11 digitos, auditoria)",
            ),
        ),
        migrations.AddField(
            model_name="assinaturaetapa",
            name="cpf_informado",
            field=models.CharField(
                blank=True,
                default="",
                max_length=20,
                verbose_name="CPF informado (mascarado)",
            ),
        ),
        migrations.AddField(
            model_name="assinaturaetapa",
            name="cpf_normalizado",
            field=models.CharField(blank=True, default="", max_length=11, verbose_name="CPF normalizado informado"),
        ),
        migrations.AddField(
            model_name="assinaturaetapa",
            name="cpf_confere",
            field=models.BooleanField(default=False, verbose_name="CPF confere com o esperado"),
        ),
        migrations.AddField(
            model_name="assinaturaetapa",
            name="usuario",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assinaturas_etapas_realizadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Utilizador autenticado na assinatura",
            ),
        ),
    ]
