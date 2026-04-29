from django.db import migrations


def seed_textos(apps, schema_editor):
    TextoPadrao = apps.get_model("prestacao_contas", "TextoPadraoDocumento")
    seeds = [
        ("relatorio_tecnico_conclusao", "Conclusao padrao 1", "Todas as atividades foram desenvolvidas.", 1, True),
        (
            "relatorio_tecnico_conclusao",
            "Conclusao padrao 2",
            "As atividades previstas foram cumpridas conforme programacao.",
            2,
            False,
        ),
        (
            "relatorio_tecnico_conclusao",
            "Conclusao padrao 3",
            "A participacao ocorreu conforme planejamento, sem intercorrencias relevantes.",
            3,
            False,
        ),
        ("relatorio_tecnico_medidas", "Medidas padrao 1", "Nada a acrescentar.", 1, True),
        (
            "relatorio_tecnico_medidas",
            "Medidas padrao 2",
            "Foram produzidas imagens para producao de materia jornalistica para o site da PCPR.",
            2,
            False,
        ),
        (
            "relatorio_tecnico_medidas",
            "Medidas padrao 3",
            "As informacoes coletadas serao encaminhadas a unidade responsavel.",
            3,
            False,
        ),
        (
            "relatorio_tecnico_medidas",
            "Medidas padrao 4",
            "Nao ha medidas adicionais a serem adotadas.",
            4,
            False,
        ),
        ("relatorio_tecnico_informacoes_complementares", "Info padrao 1", "Nada a acrescentar.", 1, True),
        ("relatorio_tecnico_informacoes_complementares", "Info padrao 2", "Sem informacoes complementares.", 2, False),
        (
            "relatorio_tecnico_informacoes_complementares",
            "Info padrao 3",
            "Nao houve intercorrencias durante o deslocamento.",
            3,
            False,
        ),
        (
            "relatorio_tecnico_informacoes_complementares",
            "Info padrao 4",
            "Houve alteracao de viatura, conforme informado neste relatorio.",
            4,
            False,
        ),
    ]
    for categoria, titulo, texto, ordem, is_padrao in seeds:
        obj, _ = TextoPadrao.objects.get_or_create(
            categoria=categoria,
            titulo=titulo,
            defaults={"texto": texto, "ordem": ordem, "is_padrao": is_padrao, "ativo": True},
        )
        if is_padrao:
            TextoPadrao.objects.filter(categoria=categoria).exclude(pk=obj.pk).update(is_padrao=False)


class Migration(migrations.Migration):
    dependencies = [
        ("prestacao_contas", "0005_relatoriotecnicoprestacao_atividade_codigos_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_textos, migrations.RunPython.noop),
    ]
