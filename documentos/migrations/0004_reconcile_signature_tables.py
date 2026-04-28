from django.db import migrations


def reconcile_signature_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    assinatura_table = "documentos_assinaturadocumento"
    legacy_assinatura_table = "assinaturas_assinaturadocumento"
    validacao_table = "documentos_validacaoassinaturadocumento"

    if assinatura_table not in existing_tables:
        if legacy_assinatura_table in existing_tables:
            schema_editor.execute(
                f"ALTER TABLE {legacy_assinatura_table} RENAME TO {assinatura_table}"
            )
        else:
            AssinaturaDocumento = apps.get_model("documentos", "AssinaturaDocumento")
            schema_editor.create_model(AssinaturaDocumento)

        existing_tables = set(connection.introspection.table_names())

    if validacao_table not in existing_tables:
        ValidacaoAssinaturaDocumento = apps.get_model(
            "documentos",
            "ValidacaoAssinaturaDocumento",
        )
        schema_editor.create_model(ValidacaoAssinaturaDocumento)


class Migration(migrations.Migration):
    dependencies = [
        ("documentos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            reconcile_signature_tables,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
