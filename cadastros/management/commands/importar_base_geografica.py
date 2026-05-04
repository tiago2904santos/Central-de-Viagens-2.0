from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cadastros.services_importacao import importar_base_geografica


class Command(BaseCommand):
    help = "Importa estados e municípios (municipio_code.csv ou municipios.csv). Execute estados antes dos municípios."

    def add_arguments(self, parser):
        parser.add_argument("--estados", type=str, required=True, help="Arquivo estados.csv (COD, NOME, SIGLA).")
        parser.add_argument(
            "--municipios-code",
            type=str,
            dest="municipios_code",
            help="Arquivo municipio_code.csv (separador ;).",
        )
        parser.add_argument(
            "--municipios",
            type=str,
            dest="municipios_ibge",
            help="Arquivo municipios.csv (COD UF, COD, NOME) como alternativa ao municipio_code.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar.")
        parser.add_argument("--encoding", default="utf-8-sig", help="Encoding dos arquivos.")

    def handle(self, *args, **options):
        estados_path = Path(options["estados"]).expanduser()
        code_path = options["municipios_code"]
        ibge_path = options["municipios_ibge"]
        dry_run = options["dry_run"]
        encoding = options["encoding"]

        if not estados_path.is_file():
            raise CommandError(f"Arquivo de estados não encontrado: {estados_path}")

        if code_path and ibge_path:
            raise CommandError("Use apenas um entre --municipios-code e --municipios.")

        if not code_path and not ibge_path:
            raise CommandError("Informe --municipios-code ou --municipios.")

        if code_path:
            mp = Path(code_path).expanduser()
            if not mp.is_file():
                raise CommandError(f"Arquivo não encontrado (--municipios-code): {mp}")
        if ibge_path:
            mp = Path(ibge_path).expanduser()
            if not mp.is_file():
                raise CommandError(f"Arquivo não encontrado (--municipios): {mp}")

        resultado = importar_base_geografica(
            estados_path,
            municipios_code_path=Path(code_path).expanduser() if code_path else None,
            municipios_ibge_path=Path(ibge_path).expanduser() if ibge_path else None,
            dry_run=dry_run,
            encoding=encoding,
        )

        for ln, msg in resultado.estados.erros:
            if ln == 0:
                raise CommandError(msg)
        for ln, msg in resultado.cidades.erros:
            if ln == 0:
                raise CommandError(msg)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Estados"))
        self.stdout.write(f"  Linhas lidas:     {resultado.estados.total_linhas}")
        self.stdout.write(f"  Criados:          {resultado.estados.criados}")
        self.stdout.write(f"  Já existentes:    {resultado.estados.existentes}")
        self.stdout.write(f"  Atualizados:      {resultado.estados.atualizados}")
        self.stdout.write(f"  Ignorados:        {resultado.estados.ignorados}")
        err_e = [(ln, m) for ln, m in resultado.estados.erros if ln > 0]
        self.stdout.write(f"  Erros (linhas):   {len(err_e)}")
        if err_e:
            for ln, m in err_e[:30]:
                self.stdout.write(self.style.WARNING(f"    Linha {ln}: {m}"))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Cidades"))
        self.stdout.write(f"  Linhas lidas:       {resultado.cidades.total_linhas}")
        self.stdout.write(f"  Criadas:            {resultado.cidades.criadas}")
        self.stdout.write(f"  Já existentes:      {resultado.cidades.existentes}")
        self.stdout.write(f"  Atualizadas:        {resultado.cidades.atualizados}")
        self.stdout.write(f"  Ignoradas:          {resultado.cidades.ignoradas}")
        self.stdout.write(f"  Capitais marcadas:  {resultado.cidades.capitais_marcadas}")
        err_c = [(ln, m) for ln, m in resultado.cidades.erros if ln > 0]
        self.stdout.write(f"  Erros (linhas):     {len(err_c)}")
        if err_c:
            for ln, m in err_c[:40]:
                self.stdout.write(self.style.WARNING(f"    Linha {ln}: {m}"))
        self.stdout.write("")
