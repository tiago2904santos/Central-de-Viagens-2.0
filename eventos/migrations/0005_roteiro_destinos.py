# Roteiro: N destinos (RoteiroEventoDestino); remove destino_estado/cidade de RoteiroEvento

import django.db.models.deletion
from django.db import migrations, models


def migrar_destinos_para_tabela(apps, schema_editor):
    RoteiroEvento = apps.get_model('eventos', 'RoteiroEvento')
    RoteiroEventoDestino = apps.get_model('eventos', 'RoteiroEventoDestino')
    for r in RoteiroEvento.objects.filter(destino_estado_id__isnull=False, destino_cidade_id__isnull=False):
        RoteiroEventoDestino.objects.create(
            roteiro=r,
            estado_id=r.destino_estado_id,
            cidade_id=r.destino_cidade_id,
            ordem=0,
        )


def reverter_destinos(apps, schema_editor):
    RoteiroEvento = apps.get_model('eventos', 'RoteiroEvento')
    RoteiroEventoDestino = apps.get_model('eventos', 'RoteiroEventoDestino')
    for rd in RoteiroEventoDestino.objects.select_related('roteiro').order_by('roteiro', 'ordem'):
        roteiro = rd.roteiro
        if not roteiro.destino_estado_id:
            roteiro.destino_estado_id = rd.estado_id
            roteiro.destino_cidade_id = rd.cidade_id
            roteiro.save(update_fields=['destino_estado_id', 'destino_cidade_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0019_viajante_status_nome_rascunho'),
        ('eventos', '0004_populate_tipos_demanda'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoteiroEventoDestino',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(default=0, verbose_name='Ordem')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cidade', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='roteiro_destinos', to='cadastros.cidade', verbose_name='Cidade')),
                ('estado', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='roteiro_destinos', to='cadastros.estado', verbose_name='Estado')),
                ('roteiro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='destinos', to='eventos.roteiroevento', verbose_name='Roteiro')),
            ],
            options={
                'verbose_name': 'Destino do roteiro',
                'verbose_name_plural': 'Destinos do roteiro',
                'ordering': ['roteiro', 'ordem'],
            },
        ),
        migrations.RunPython(migrar_destinos_para_tabela, reverter_destinos),
        migrations.RemoveField(model_name='roteiroevento', name='destino_cidade'),
        migrations.RemoveField(model_name='roteiroevento', name='destino_estado'),
    ]
