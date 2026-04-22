# Generated manually for multi-etapa assinatura

import uuid

import assinaturas.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _migrar_tokens_para_etapas(apps, schema_editor):
    AssinaturaDocumento = apps.get_model("assinaturas", "AssinaturaDocumento")
    AssinaturaEtapa = apps.get_model("assinaturas", "AssinaturaEtapa")
    for a in AssinaturaDocumento.objects.exclude(token__isnull=True):
        if AssinaturaEtapa.objects.filter(assinatura_id=a.pk).exists():
            continue
        tkn = a.token
        st = (a.status or "").lower()
        et_st = "assinado" if st == "assinado" else "pendente"
        AssinaturaEtapa.objects.create(
            assinatura_id=a.pk,
            ordem=1,
            token=tkn,
            tipo_assinante="interno_config",
            nome_previsto=(a.nome_assinante or "")[:200],
            expires_at=a.expires_at,
            status=et_st,
            nome_assinante=a.nome_assinante or "",
            nome_assinante_normalizado=getattr(a, "nome_assinante_normalizado", "") or "",
            signed_at=a.signed_at,
            ip=a.ip,
            user_agent=a.user_agent or "",
        )
        AssinaturaDocumento.objects.filter(pk=a.pk).update(token=None)


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("assinaturas", "0002_hardening_assinatura"),
        ("cadastros", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="assinaturadocumento",
            name="token",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                editable=False,
                help_text="Antes da multi-etapa; usar AssinaturaEtapa.token.",
                null=True,
                unique=True,
                verbose_name="Token legado do link",
            ),
        ),
        migrations.AlterField(
            model_name="assinaturadocumento",
            name="campo_arquivo",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Legado / opcional",
                max_length=80,
                verbose_name="Campo ficheiro no model (legado / opcional)",
            ),
        ),
        migrations.AlterField(
            model_name="assinaturadocumento",
            name="status",
            field=models.CharField(
                choices=[
                    ("pendente", "Pendente"),
                    ("parcial", "Parcialmente assinado"),
                    ("concluido", "Concluido"),
                ],
                db_index=True,
                default="pendente",
                max_length=20,
                verbose_name="Estado",
            ),
        ),
        migrations.CreateModel(
            name="AssinaturaEtapa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ordem", models.PositiveSmallIntegerField(db_index=True, verbose_name="Ordem")),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name="Token do link")),
                (
                    "tipo_assinante",
                    models.CharField(
                        choices=[
                            ("interno_config", "Servidor (configuracao do sistema)"),
                            ("termo_servidor", "Servidor do termo"),
                            ("externo_chefia", "Chefia (externa)"),
                        ],
                        max_length=24,
                        verbose_name="Tipo de assinante",
                    ),
                ),
                ("nome_previsto", models.CharField(blank=True, default="", max_length=200, verbose_name="Nome previsto (exibicao)")),
                ("email_previsto", models.CharField(blank=True, default="", max_length=254, verbose_name="E-mail previsto")),
                ("telefone_previsto", models.CharField(blank=True, default="", max_length=40, verbose_name="Telefone previsto")),
                ("status", models.CharField(choices=[("pendente", "Pendente"), ("assinado", "Assinado")], db_index=True, default="pendente", max_length=20, verbose_name="Estado")),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="Expira em")),
                ("nome_assinante", models.CharField(blank=True, default="", max_length=200, verbose_name="Nome declarado na assinatura")),
                ("nome_assinante_normalizado", models.CharField(blank=True, default="", max_length=220)),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("arquivo_sha256_apos_etapa", models.CharField(blank=True, default="", max_length=64)),
                (
                    "resultado_pdf",
                    models.FileField(
                        blank=True,
                        help_text="Saida PDF apos assinar nesta etapa (entrada da etapa seguinte).",
                        null=True,
                        upload_to=assinaturas.models._upload_etapa_resultado,
                        verbose_name="PDF apos esta etapa",
                    ),
                ),
                (
                    "assinatura",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="etapas",
                        to="assinaturas.assinaturadocumento",
                        verbose_name="Pedido",
                    ),
                ),
                (
                    "viajante",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assinaturas_etapas",
                        to="cadastros.viajante",
                        verbose_name="Viajante (interno)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Etapa de assinatura",
                "verbose_name_plural": "Etapas de assinatura",
                "ordering": ["assinatura_id", "ordem"],
            },
        ),
        migrations.AddConstraint(
            model_name="assinaturaetapa",
            constraint=models.UniqueConstraint(fields=("assinatura", "ordem"), name="uniq_assinatura_etapa_ordem"),
        ),
        migrations.RunPython(_migrar_tokens_para_etapas, _noop_reverse),
        migrations.RunSQL(
            "UPDATE assinaturas_assinaturadocumento SET status = 'concluido' WHERE status = 'assinado';",
            reverse_sql="UPDATE assinaturas_assinaturadocumento SET status = 'assinado' WHERE status = 'concluido';",
        ),
    ]
