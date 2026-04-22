from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assinaturas", "0004_assinatura_verificacao_cpf_auditoria"),
    ]

    operations = [
        migrations.AddField(
            model_name="assinaturadocumento",
            name="invalidado_em",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Invalidado em",
            ),
        ),
        migrations.AddField(
            model_name="assinaturadocumento",
            name="invalidado_motivo",
            field=models.CharField(
                blank=True,
                default="",
                max_length=280,
                verbose_name="Motivo da invalidacao",
            ),
        ),
    ]
