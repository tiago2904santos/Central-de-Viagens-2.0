# Data migration: padronizar rg "NÃO POSSUI RG" -> "NAO POSSUI RG"

from django.db import migrations


def atualizar_nao_possui_rg(apps, schema_editor):
    Viajante = apps.get_model('cadastros', 'Viajante')
    Viajante.objects.filter(rg='NÃO POSSUI RG').update(rg='NAO POSSUI RG')


def reverter(apps, schema_editor):
    Viajante = apps.get_model('cadastros', 'Viajante')
    Viajante.objects.filter(rg='NAO POSSUI RG').update(rg='NÃO POSSUI RG')


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0008_viajante_cargo_fk_remove_is_ascom'),
    ]

    operations = [
        migrations.RunPython(atualizar_nao_possui_rg, reverter),
    ]
