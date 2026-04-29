from django.db import migrations


def sync_relatorio_campos_restantes(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return

    table_name = "prestacao_contas_relatoriotecnicoprestacao"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

    statements = []
    if "unidade_servidor" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN unidade_servidor varchar(160) NOT NULL DEFAULT ''")
    if "combustivel" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN combustivel varchar(80) NOT NULL DEFAULT 'Cartao Prime'")
    if "teve_translado" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN teve_translado bool NOT NULL DEFAULT 0")
    if "valor_translado" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN valor_translado decimal NULL")
    if "teve_passagem" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN teve_passagem bool NOT NULL DEFAULT 0")
    if "valor_passagem" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN valor_passagem decimal NULL")
    if "atividade_codigos" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN atividade_codigos varchar(500) NOT NULL DEFAULT ''")

    for statement in statements:
        schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("prestacao_contas", "0003_rt_campos_minimos"),
    ]

    operations = [
        migrations.RunPython(sync_relatorio_campos_restantes, migrations.RunPython.noop),
    ]
