# Generated manually for estimativa local (km/tempo entre cidades)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0019_viajante_status_nome_rascunho'),
    ]

    operations = [
        migrations.AddField(
            model_name='cidade',
            name='latitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text='Coordenada para estimativa local de distância/tempo entre cidades.',
                max_digits=9,
                null=True,
                verbose_name='Latitude',
            ),
        ),
        migrations.AddField(
            model_name='cidade',
            name='longitude',
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text='Coordenada para estimativa local de distância/tempo entre cidades.',
                max_digits=9,
                null=True,
                verbose_name='Longitude',
            ),
        ),
    ]
