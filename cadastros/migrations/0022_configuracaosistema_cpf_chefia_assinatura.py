from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0021_config_pt_sede_chefia_coord"),
    ]

    operations = [
        migrations.AddField(
            model_name="configuracaosistema",
            name="cpf_chefia_assinatura",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Opcional: usado quando o pedido de assinatura do termo nao envia CPF manualmente.",
                max_length=14,
                verbose_name="CPF esperado da chefia (assinatura eletrónica)",
            ),
        ),
    ]
