from django.db import migrations


def adicionar_campos_rt_sqlite(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return

    table_name = "prestacao_contas_relatoriotecnicoprestacao"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

    statements = []
    if "cpf_servidor" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN cpf_servidor varchar(14) NOT NULL DEFAULT ''")
    if "cargo_servidor" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN cargo_servidor varchar(120) NOT NULL DEFAULT ''")
    if "diaria" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN diaria varchar(80) NOT NULL DEFAULT ''")
    if "translado" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN translado varchar(80) NOT NULL DEFAULT ''")
    if "passagem" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN passagem varchar(80) NOT NULL DEFAULT ''")
    if "motivo" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN motivo text NOT NULL DEFAULT ''")

    for statement in statements:
        schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("prestacao_contas", "0002_sync_sqlite_status_rt_columns"),
    ]

    operations = [
        migrations.RunPython(adicionar_campos_rt_sqlite, migrations.RunPython.noop),
    ]
