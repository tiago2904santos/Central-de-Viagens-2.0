# Veiculo: combustivel CharField -> FK, remove prefixo/ativo, add tipo, modelo 120

from django.db import migrations, models


def _norm_nome(val):
    if not val or not str(val).strip():
        return ''
    return ' '.join(str(val).strip().upper().split())


def migrar_combustivel(apps, schema_editor):
    Veiculo = apps.get_model('cadastros', 'Veiculo')
    CombustivelVeiculo = apps.get_model('cadastros', 'CombustivelVeiculo')
    for v in Veiculo.objects.all():
        texto = getattr(v, 'combustivel', '') or ''
        nome_norm = _norm_nome(texto)
        if nome_norm:
            comb, _ = CombustivelVeiculo.objects.get_or_create(
                nome=nome_norm,
                defaults={'is_padrao': False},
            )
            v.combustivel_fk_id = comb.pk
        else:
            v.combustivel_fk_id = None
        v.save(update_fields=['combustivel_fk_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0015_combustivel_veiculo'),
    ]

    operations = [
        migrations.AddField(
            model_name='veiculo',
            name='combustivel_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='veiculos',
                to='cadastros.combustivelveiculo',
                verbose_name='Combustível',
            ),
        ),
        migrations.RunPython(migrar_combustivel, noop),
        migrations.RemoveField(model_name='veiculo', name='combustivel'),
        migrations.RenameField(
            model_name='veiculo',
            old_name='combustivel_fk',
            new_name='combustivel',
        ),
        migrations.RemoveField(model_name='veiculo', name='prefixo'),
        migrations.RemoveField(model_name='veiculo', name='ativo'),
        migrations.AddField(
            model_name='veiculo',
            name='tipo',
            field=models.CharField(
                choices=[('CARACTERIZADO', 'Caracterizado'), ('DESCARACTERIZADO', 'Descaracterizado')],
                default='CARACTERIZADO',
                max_length=20,
                verbose_name='Tipo',
            ),
        ),
        migrations.AlterField(
            model_name='veiculo',
            name='modelo',
            field=models.CharField(max_length=120, verbose_name='Modelo'),
        ),
    ]
