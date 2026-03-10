# UnidadeLotacao: remover sigla; preservar nome; mesclar duplicados por nome normalizado

import logging

from django.db import migrations


def _normalizar(val):
    if not val or not str(val).strip():
        return ''
    return ' '.join(str(val).strip().upper().split())


def mesclar_duplicados_e_remover_sigla(apps, schema_editor):
    UnidadeLotacao = apps.get_model('cadastros', 'UnidadeLotacao')
    Viajante = apps.get_model('cadastros', 'Viajante')
    logger = logging.getLogger(__name__)
    # Normalizar todos os nomes
    for u in UnidadeLotacao.objects.all():
        n = _normalizar(u.nome)
        if n and u.nome != n:
            u.nome = n
            u.save(update_fields=['nome'])
    # Agrupar por nome (duplicados)
    from collections import defaultdict
    por_nome = defaultdict(list)
    for u in UnidadeLotacao.objects.all():
        por_nome[u.nome].append(u)
    # Para cada nome com mais de um registro: manter o de menor pk, reassign viajantes, apagar os demais
    for nome, unidades in por_nome.items():
        if len(unidades) <= 1:
            continue
        unidades.sort(key=lambda x: x.pk)
        manter = unidades[0]
        for u in unidades[1:]:
            count = Viajante.objects.filter(unidade_lotacao_id=u.pk).update(unidade_lotacao_id=manter.pk)
            if count:
                logger.info('UnidadeLotacao pk=%s ("%s") mesclada em pk=%s; %s viajante(s) reassignados.', u.pk, u.nome, manter.pk, count)
            u.delete()
    # Remoção do campo sigla é feita na operação RemoveField abaixo


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0016_veiculo_combustivel_fk_refactor'),
    ]

    operations = [
        migrations.RunPython(mesclar_duplicados_e_remover_sigla, noop),
        migrations.RemoveField(
            model_name='unidadelotacao',
            name='sigla',
        ),
        migrations.AlterModelOptions(
            name='unidadelotacao',
            options={'ordering': ['nome'], 'verbose_name': 'Unidade de lotação', 'verbose_name_plural': 'Unidades de lotação'},
        ),
    ]
