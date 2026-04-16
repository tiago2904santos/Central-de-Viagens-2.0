from django.db import migrations


def forwards(apps, schema_editor):
    TermoAutorizacao = apps.get_model('eventos', 'TermoAutorizacao')
    through = TermoAutorizacao.oficios.through

    for termo in TermoAutorizacao.objects.all().iterator():
        legado_ids = list(
            through.objects.filter(termoautorizacao_id=termo.pk)
            .order_by('oficio_id')
            .values_list('oficio_id', flat=True)
        )
        canonical_id = termo.oficio_id or (legado_ids[0] if legado_ids else None)
        if canonical_id and termo.oficio_id != canonical_id:
            termo.oficio_id = canonical_id
            termo.save(update_fields=['oficio', 'updated_at'])
        if canonical_id:
            through.objects.filter(termoautorizacao_id=termo.pk).exclude(oficio_id=canonical_id).delete()
            if not through.objects.filter(termoautorizacao_id=termo.pk, oficio_id=canonical_id).exists():
                through.objects.create(termoautorizacao_id=termo.pk, oficio_id=canonical_id)


class Migration(migrations.Migration):
    dependencies = [
        ('eventos', '0051_ordemservico_data_unica_remocao_complementos'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
