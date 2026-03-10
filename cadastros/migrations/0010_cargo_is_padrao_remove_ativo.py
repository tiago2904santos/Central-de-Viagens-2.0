# Cargo: remover ativo, adicionar is_padrao

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0009_rg_nao_possui_padrao'),
    ]

    operations = [
        migrations.AddField(
            model_name='cargo',
            name='is_padrao',
            field=models.BooleanField(default=False, verbose_name='Padrão'),
        ),
        migrations.RemoveField(
            model_name='cargo',
            name='ativo',
        ),
    ]
