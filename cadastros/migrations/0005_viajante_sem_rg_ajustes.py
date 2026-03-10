# Generated manually — Viajante: sem_rg, ajustes de campos, remoção email, constraint CPF

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0004_assinatura_configuracao_relacional'),
    ]

    operations = [
        migrations.AddField(
            model_name='viajante',
            name='sem_rg',
            field=models.BooleanField(default=False, verbose_name='Não possui RG'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='nome',
            field=models.CharField(max_length=160, verbose_name='Nome'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='cargo',
            field=models.CharField(max_length=120, verbose_name='Cargo'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='rg',
            field=models.CharField(blank=True, default='', max_length=30, verbose_name='RG'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='cpf',
            field=models.CharField(blank=True, default='', max_length=14, verbose_name='CPF'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='telefone',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Telefone'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='unidade_lotacao',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Unidade de lotação'),
        ),
        migrations.AlterField(
            model_name='viajante',
            name='is_ascom',
            field=models.BooleanField(default=True, verbose_name='ASCOM'),
        ),
        migrations.RemoveField(
            model_name='viajante',
            name='email',
        ),
        migrations.AddConstraint(
            model_name='viajante',
            constraint=models.UniqueConstraint(
                condition=Q(cpf__gt=''),
                fields=('cpf',),
                name='cadastros_viajante_cpf_unique',
            ),
        ),
    ]
