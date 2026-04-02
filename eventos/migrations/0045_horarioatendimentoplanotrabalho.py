from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0044_alter_atividadeplanotrabalho_codigo_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='HorarioAtendimentoPlanoTrabalho',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descricao', models.CharField(max_length=120, verbose_name='Descrição')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('ordem', models.PositiveIntegerField(default=100, verbose_name='Ordem')),
                ('is_padrao', models.BooleanField(default=False, verbose_name='Padrão')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Horário de atendimento (Plano de Trabalho)',
                'verbose_name_plural': 'Horários de atendimento (Plano de Trabalho)',
                'ordering': ['ordem', 'descricao'],
            },
        ),
    ]
