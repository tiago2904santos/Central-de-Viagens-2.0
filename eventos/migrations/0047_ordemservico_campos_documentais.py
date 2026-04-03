import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0021_config_pt_sede_chefia_coord'),
        ('eventos', '0046_alter_justificativa_oficio_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordemservico',
            name='data_deslocamento',
            field=models.DateField(blank=True, db_index=True, null=True, verbose_name='Data do deslocamento'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='destinos_json',
            field=models.JSONField(blank=True, default=list, verbose_name='Destinos estruturados'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='modelo_motivo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ordens_servico', to='eventos.modelomotivoviagem', verbose_name='Modelo de motivo'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='motivo_texto',
            field=models.TextField(blank=True, default='', verbose_name='Motivo'),
        ),
        migrations.AddField(
            model_name='ordemservico',
            name='viajantes',
            field=models.ManyToManyField(blank=True, related_name='ordens_servico', to='cadastros.viajante', verbose_name='Servidores'),
        ),
    ]