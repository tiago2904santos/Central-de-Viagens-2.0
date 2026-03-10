# Generated manually — Remove campo ativo do Viajante (exclusão real em vez de toggle)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0005_viajante_sem_rg_ajustes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='viajante',
            name='ativo',
        ),
    ]
