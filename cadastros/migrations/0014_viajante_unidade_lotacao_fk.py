# Viajante: unidade_lotacao CharField -> FK UnidadeLotacao (com migração de dados)

import logging

from django.db import migrations, models


def _normalizar(val):
    if not val or not str(val).strip():
        return ''
    return ' '.join(str(val).strip().upper().split())


def migrar_unidade_lotacao(apps, schema_editor):
    Viajante = apps.get_model('cadastros', 'Viajante')
    UnidadeLotacao = apps.get_model('cadastros', 'UnidadeLotacao')
    logger = logging.getLogger(__name__)
    sem_match = 0
    for v in Viajante.objects.all():
        texto = getattr(v, 'unidade_lotacao', '') or ''
        texto_norm = _normalizar(texto)
        if not texto_norm:
            v.unidade_lotacao_fk_id = None
            v.save(update_fields=['unidade_lotacao_fk_id'])
            continue
        unidade = UnidadeLotacao.objects.filter(sigla=texto_norm).first()
        if not unidade:
            unidade = UnidadeLotacao.objects.filter(nome=texto_norm).first()
        if unidade:
            v.unidade_lotacao_fk_id = unidade.pk
            v.save(update_fields=['unidade_lotacao_fk_id'])
        else:
            v.unidade_lotacao_fk_id = None
            v.save(update_fields=['unidade_lotacao_fk_id'])
            sem_match += 1
            logger.warning('Viajante pk=%s: unidade_lotacao "%s" não encontrada; definido como NULL.', v.pk, texto[:80])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0013_unidade_lotacao_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='viajante',
            name='unidade_lotacao_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='viajantes',
                to='cadastros.unidadelotacao',
                verbose_name='Unidade de lotação',
            ),
        ),
        migrations.RunPython(migrar_unidade_lotacao, noop),
        migrations.RemoveField(
            model_name='viajante',
            name='unidade_lotacao',
        ),
        migrations.RenameField(
            model_name='viajante',
            old_name='unidade_lotacao_fk',
            new_name='unidade_lotacao',
        ),
    ]
