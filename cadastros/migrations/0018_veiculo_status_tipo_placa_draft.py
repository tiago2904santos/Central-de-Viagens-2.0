# Veiculo: status RASCUNHO/FINALIZADO; tipo default DESCARACTERIZADO; placa/modelo opcionais para rascunho

from django.db import migrations, models
from django.db.models import Q


def set_existentes_finalizado(apps, schema_editor):
    Veiculo = apps.get_model('cadastros', 'Veiculo')
    Veiculo.objects.all().update(status='FINALIZADO')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0017_unidade_lotacao_somente_nome'),
    ]

    operations = [
        migrations.AddField(
            model_name='veiculo',
            name='status',
            field=models.CharField(
                choices=[('RASCUNHO', 'Rascunho'), ('FINALIZADO', 'Finalizado')],
                default='RASCUNHO',
                max_length=20,
                verbose_name='Status',
            ),
        ),
        migrations.RunPython(set_existentes_finalizado, noop),
        migrations.AlterField(
            model_name='veiculo',
            name='placa',
            field=models.CharField(blank=True, default='', max_length=10, unique=False, verbose_name='Placa'),
        ),
        migrations.AlterField(
            model_name='veiculo',
            name='modelo',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Modelo'),
        ),
        migrations.AlterField(
            model_name='veiculo',
            name='tipo',
            field=models.CharField(
                choices=[('CARACTERIZADO', 'Caracterizado'), ('DESCARACTERIZADO', 'Descaracterizado')],
                default='DESCARACTERIZADO',
                max_length=20,
                verbose_name='Tipo',
            ),
        ),
        migrations.AddConstraint(
            model_name='veiculo',
            constraint=models.UniqueConstraint(
                condition=Q(placa__gt=''),
                fields=('placa',),
                name='cadastros_veiculo_placa_unique_preenchida',
            ),
        ),
        migrations.AlterModelOptions(
            name='veiculo',
            options={'ordering': ['-updated_at'], 'verbose_name': 'Veículo', 'verbose_name_plural': 'Veículos'},
        ),
    ]
