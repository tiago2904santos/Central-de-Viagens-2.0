from django.db import migrations


def sync_prestacao_columns(apps, schema_editor):
    if schema_editor.connection.vendor != "sqlite":
        return

    table_name = "prestacao_contas_prestacaoconta"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}

    statements = []
    if "status_rt" not in existing_columns:
        statements.append(
            f"ALTER TABLE {table_name} ADD COLUMN status_rt varchar(20) NOT NULL DEFAULT 'pendente'"
        )
    if "rt_atualizado_em" not in existing_columns:
        statements.append(f"ALTER TABLE {table_name} ADD COLUMN rt_atualizado_em datetime NULL")

    for statement in statements:
        schema_editor.execute(statement)


class Migration(migrations.Migration):
    dependencies = [
        ("prestacao_contas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sync_prestacao_columns, migrations.RunPython.noop),
    ]
