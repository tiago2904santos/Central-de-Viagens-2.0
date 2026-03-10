# Data migration: cria tipos de demanda a partir de TIPO_CHOICES e associa eventos existentes

from django.db import migrations


TIPO_CHOICES_MAP = [
    ('PCPR_NA_COMUNIDADE', 'PCPR NA COMUNIDADE', 10),
    ('OPERACAO_POLICIAL', 'OPERAÇÃO POLICIAL', 20),
    ('PARANA_EM_ACAO', 'PARANÁ EM AÇÃO', 30),
    ('OUTRO', 'OUTROS', 100),  # is_outros=True
]


def criar_tipos_e_associar(apps, schema_editor):
    Evento = apps.get_model('eventos', 'Evento')
    TipoDemandaEvento = apps.get_model('eventos', 'TipoDemandaEvento')
    tipo_by_valor = {}
    for valor, nome, ordem in TIPO_CHOICES_MAP:
        tipo, _ = TipoDemandaEvento.objects.get_or_create(
            nome=nome,
            defaults={'ordem': ordem, 'ativo': True, 'is_outros': (valor == 'OUTRO')}
        )
        tipo_by_valor[valor] = tipo
    for ev in Evento.objects.all():
        if ev.tipo_demanda and ev.tipo_demanda in tipo_by_valor:
            ev.tipos_demanda.add(tipo_by_valor[ev.tipo_demanda])


def reverter(apps, schema_editor):
    # Não desfazemos associações M2M; tipos podem permanecer
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0003_etapa1_tipos_demanda_destinos'),
    ]

    operations = [
        migrations.RunPython(criar_tipos_e_associar, reverter),
    ]
