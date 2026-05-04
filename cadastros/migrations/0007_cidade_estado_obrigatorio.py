# Generated manually for Cidade.estado NOT NULL

import django.db.models.deletion
from django.db import migrations, models


def _fix_cidades_sem_estado(apps, schema_editor):
    Estado = apps.get_model("cadastros", "Estado")
    Cidade = apps.get_model("cadastros", "Cidade")
    if not Cidade.objects.filter(estado__isnull=True).exists():
        return
    fallback, _ = Estado.objects.get_or_create(
        sigla="PR",
        defaults={"nome": "PARANÁ", "codigo_ibge": 41},
    )
    for c in Cidade.objects.filter(estado__isnull=True).iterator():
        c.estado_id = fallback.pk
        c.save(update_fields=["estado_id"])


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0006_estado_e_cidade_geografica"),
    ]

    operations = [
        migrations.RunPython(_fix_cidades_sem_estado, _noop),
        migrations.AlterField(
            model_name="cidade",
            name="estado",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cidades",
                to="cadastros.estado",
            ),
        ),
    ]
