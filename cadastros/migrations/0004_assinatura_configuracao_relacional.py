# Generated manually for refatoração assinaturas

from django.db import migrations, models
import django.db.models.deletion


def migrate_assinaturas_para_novo_modelo(apps, schema_editor):
    """Migra dados dos campos antigos de assinatura para AssinaturaConfiguracao."""
    ConfiguracaoSistema = apps.get_model('cadastros', 'ConfiguracaoSistema')
    AssinaturaConfiguracao = apps.get_model('cadastros', 'AssinaturaConfiguracao')

    for config in ConfiguracaoSistema.objects.all():
        mapeamento = [
            ('assinatura_oficio_1', 'OFICIO', 1),
            ('assinatura_oficio_2', 'OFICIO', 2),
            ('assinatura_justificativas', 'JUSTIFICATIVA', 1),
            ('assinatura_planos_trabalho', 'PLANO_TRABALHO', 1),
            ('assinatura_ordens_servico', 'ORDEM_SERVICO', 1),
        ]
        for attr, tipo, ordem in mapeamento:
            viajante = getattr(config, attr, None)
            if viajante is not None:
                AssinaturaConfiguracao.objects.update_or_create(
                    configuracao=config,
                    tipo=tipo,
                    ordem=ordem,
                    defaults={'viajante': viajante, 'ativo': True},
                )


def reverse_migrate_assinaturas(apps, schema_editor):
    """Reversão: não repopula campos antigos (já removidos na mesma migration)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0003_expand_configuracao_sistema'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssinaturaConfiguracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('OFICIO', 'Ofício'), ('JUSTIFICATIVA', 'Justificativa'), ('PLANO_TRABALHO', 'Plano de Trabalho'), ('ORDEM_SERVICO', 'Ordem de Serviço')], max_length=20, verbose_name='Tipo')),
                ('ordem', models.PositiveSmallIntegerField(default=1, verbose_name='Ordem')),
                ('ativo', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('configuracao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assinaturas', to='cadastros.configuracaosistema', verbose_name='Configuração')),
                ('viajante', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='cadastros.viajante', verbose_name='Viajante')),
            ],
            options={
                'verbose_name': 'Assinatura (configuração)',
                'verbose_name_plural': 'Assinaturas (configuração)',
            },
        ),
        migrations.AddConstraint(
            model_name='assinaturaconfiguracao',
            constraint=models.UniqueConstraint(fields=('configuracao', 'tipo', 'ordem'), name='uniq_assinatura_por_tipo_ordem'),
        ),
        migrations.RunPython(migrate_assinaturas_para_novo_modelo, reverse_migrate_assinaturas),
        migrations.RemoveField(
            model_name='configuracaosistema',
            name='assinatura_oficio_1',
        ),
        migrations.RemoveField(
            model_name='configuracaosistema',
            name='assinatura_oficio_2',
        ),
        migrations.RemoveField(
            model_name='configuracaosistema',
            name='assinatura_justificativas',
        ),
        migrations.RemoveField(
            model_name='configuracaosistema',
            name='assinatura_planos_trabalho',
        ),
        migrations.RemoveField(
            model_name='configuracaosistema',
            name='assinatura_ordens_servico',
        ),
    ]
