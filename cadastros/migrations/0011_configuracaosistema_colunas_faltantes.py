# Corrige banco dessincronizado: tabela cadastros_configuracaosistema criada/atualizada
# sem todas as colunas definidas em 0008 (ex.: restore parcial ou DDL manual).
# Executa apenas em PostgreSQL (SQLite/testes usam o schema gerado pelas migrações normais).

from django.db import connection
from django.db import migrations


def aplicar_colunas_faltantes_postgres(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute(
            """
            ALTER TABLE cadastros_configuracaosistema
                ADD COLUMN IF NOT EXISTS prazo_justificativa_dias integer NOT NULL DEFAULT 10,
                ADD COLUMN IF NOT EXISTS nome_orgao varchar(200) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS sigla_orgao varchar(20) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS sede varchar(200) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS nome_chefia varchar(120) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS cargo_chefia varchar(120) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS pt_ultimo_numero integer NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS pt_ano integer NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS coordenador_adm_plano_trabalho_id bigint NULL
            """
        )
        cursor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'cadastros_configurac_coordenador_adm_plan_a8f7b3a4_fk_cadastros'
                ) THEN
                    ALTER TABLE cadastros_configuracaosistema
                        ADD CONSTRAINT cadastros_configurac_coordenador_adm_plan_a8f7b3a4_fk_cadastros
                        FOREIGN KEY (coordenador_adm_plano_trabalho_id)
                        REFERENCES cadastros_servidor(id)
                        DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS cadastros_configuracaosist_coordenador_adm_plano_trab_a8f7b3a4
                ON cadastros_configuracaosistema (coordenador_adm_plano_trabalho_id)
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0010_assinaturaconfiguracao_ativo"),
    ]

    operations = [
        migrations.RunPython(aplicar_colunas_faltantes_postgres, noop_reverse),
    ]
