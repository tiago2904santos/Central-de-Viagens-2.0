# CreateModel CombustivelVeiculo

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0014_viajante_unidade_lotacao_fk'),
    ]

    operations = [
        migrations.CreateModel(
            name='CombustivelVeiculo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=60, unique=True, verbose_name='Nome')),
                ('is_padrao', models.BooleanField(default=False, verbose_name='Padrão')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Combustível (veículo)',
                'verbose_name_plural': 'Combustíveis (veículos)',
                'ordering': ['nome'],
            },
        ),
    ]
