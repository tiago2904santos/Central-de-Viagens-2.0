from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0045_horarioatendimentoplanotrabalho'),
    ]

    operations = [
        migrations.AlterField(
            model_name='justificativa',
            name='oficio',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='justificativa',
                to='eventos.oficio',
                verbose_name='Ofício',
            ),
        ),
    ]
