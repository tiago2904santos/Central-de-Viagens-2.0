from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0042_atividadeplanotrabalho'),
    ]

    operations = [
        migrations.AddField(
            model_name='planotrabalho',
            name='data_chegada_sede',
            field=models.DateField(blank=True, null=True, verbose_name='Chegada na sede (data)'),
        ),
        migrations.AddField(
            model_name='planotrabalho',
            name='data_saida_sede',
            field=models.DateField(blank=True, null=True, verbose_name='Saída da sede (data)'),
        ),
        migrations.AddField(
            model_name='planotrabalho',
            name='hora_chegada_sede',
            field=models.TimeField(blank=True, null=True, verbose_name='Chegada na sede (hora)'),
        ),
        migrations.AddField(
            model_name='planotrabalho',
            name='hora_saida_sede',
            field=models.TimeField(blank=True, null=True, verbose_name='Saída da sede (hora)'),
        ),
    ]
