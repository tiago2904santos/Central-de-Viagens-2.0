from django.db import migrations


def rebuild_assinatura_schema_if_legacy(apps, schema_editor):
    connection = schema_editor.connection
    cursor = connection.cursor()

    assinatura_table = "documentos_assinaturadocumento"
    backup_table = "documentos_assinaturadocumento_legacy_backup"

    existing_tables = set(connection.introspection.table_names())
    if assinatura_table not in existing_tables:
        return

    columns = {
        col.name
        for col in connection.introspection.get_table_description(cursor, assinatura_table)
    }
    if "codigo_verificacao" in columns:
        return

    if backup_table in existing_tables:
        schema_editor.execute(f"DROP TABLE {backup_table}")

    schema_editor.execute(f"ALTER TABLE {assinatura_table} RENAME TO {backup_table}")

    AssinaturaDocumento = apps.get_model("documentos", "AssinaturaDocumento")
    schema_editor.create_model(AssinaturaDocumento)


class Migration(migrations.Migration):
    dependencies = [
        ("documentos", "0004_reconcile_signature_tables"),
    ]

    operations = [
        migrations.RunPython(
            rebuild_assinatura_schema_if_legacy,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
