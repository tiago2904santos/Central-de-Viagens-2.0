# Corrige banco dessincronizado: tabela cadastros_configuracaosistema criada/atualizada
# sem todas as colunas definidas em 0008 (ex.: restore parcial ou DDL manual).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0010_assinaturaconfiguracao_ativo"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE cadastros_configuracaosistema
                ADD COLUMN IF NOT EXISTS prazo_justificativa_dias integer NOT NULL DEFAULT 10,
                ADD COLUMN IF NOT EXISTS nome_orgao varchar(200) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS sigla_orgao varchar(20) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS sede varchar(200) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS nome_chefia varchar(120) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS cargo_chefia varchar(120) NOT NULL DEFAULT '',
                ADD COLUMN IF NOT EXISTS pt_ultimo_numero integer NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS pt_ano integer NOT NULL DEFAULT 0,
                ADD COLUMN IF NOT EXISTS coordenador_adm_plano_trabalho_id bigint NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
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
            END $$;
            CREATE INDEX IF NOT EXISTS cadastros_configuracaosist_coordenador_adm_plano_trab_a8f7b3a4
                ON cadastros_configuracaosistema (coordenador_adm_plano_trabalho_id);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
