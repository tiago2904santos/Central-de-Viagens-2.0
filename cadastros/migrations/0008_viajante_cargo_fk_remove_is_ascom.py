# Generated manually — Viajante: cargo FK + remover is_ascom; migrar dados cargo texto -> Cargo

from django.db import migrations, models
import django.db.models.deletion


def migrar_cargo_texto_para_cargo_fk(apps, schema_editor):
    Viajante = apps.get_model('cadastros', 'Viajante')
    Cargo = apps.get_model('cadastros', 'Cargo')
    for v in Viajante.objects.all():
        nome_cargo = (getattr(v, 'cargo', None) or '').strip().upper()
        nome_cargo = ' '.join(nome_cargo.split()) if nome_cargo else 'SEM CARGO'
        cargo, _ = Cargo.objects.get_or_create(nome=nome_cargo, defaults={'ativo': True})
        v.cargo_fk = cargo
        v.save(update_fields=['cargo_fk'])


def reverse_migrar(apps, schema_editor):
    pass  # reverso não repopula cargo texto; usar noop para evitar complexidade


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0007_cargo'),
    ]

    operations = [
        migrations.AddField(
            model_name='viajante',
            name='cargo_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='cadastros.cargo',
                verbose_name='Cargo (temp)',
            ),
        ),
        migrations.RunPython(migrar_cargo_texto_para_cargo_fk, reverse_migrar),
        migrations.RemoveField(
            model_name='viajante',
            name='cargo',
        ),
        migrations.RenameField(
            model_name='viajante',
            old_name='cargo_fk',
            new_name='cargo',
        ),
        migrations.AlterField(
            model_name='viajante',
            name='cargo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='viajantes',
                to='cadastros.cargo',
                verbose_name='Cargo',
            ),
        ),
        migrations.RemoveField(
            model_name='viajante',
            name='is_ascom',
        ),
    ]
