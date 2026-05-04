from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cadastros.services_importacao import importar_cidades_csv


class Command(BaseCommand):
    help = "Importa cidades a partir de um arquivo CSV (ex.: municipio_code.csv com separador ;)."

    def add_arguments(self, parser):
        parser.add_argument(
            "arquivo",
            type=str,
            help="Caminho para o arquivo CSV (relativo ou absoluto).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula a importação sem gravar no banco.",
        )
        parser.add_argument(
            "--encoding",
            default="utf-8-sig",
            help="Encoding do arquivo (padrão: utf-8-sig).",
        )

    def handle(self, *args, **options):
        path = Path(options["arquivo"]).expanduser()
        dry_run = options["dry_run"]
        encoding = options["encoding"]

        if not path.is_file():
            raise CommandError(f"Arquivo não encontrado: {path}")

        resultado = importar_cidades_csv(path, dry_run=dry_run, encoding=encoding)

        for ln, msg in resultado.erros:
            if ln == 0:
                raise CommandError(msg)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Resumo da importação de cidades"))
        self.stdout.write(f"  Arquivo: {path.resolve()}")
        self.stdout.write(f"  Modo: {'simulação (dry-run)' if dry_run else 'gravação'}")
        self.stdout.write(f"  Encoding: {encoding}")
        self.stdout.write("")
        self.stdout.write(f"  Linhas de dados lidas: {resultado.total_linhas}")
        self.stdout.write(f"  Cidades criadas:       {resultado.criadas}")
        self.stdout.write(f"  Já existentes (SKIP):  {resultado.existentes}")
        self.stdout.write(f"  Linhas ignoradas:      {resultado.ignoradas}")
        err_lines = [(ln, m) for ln, m in resultado.erros if ln > 0]
        self.stdout.write(f"  Erros em linhas:       {len(err_lines)}")
        self.stdout.write("")

        if err_lines:
            self.stdout.write(self.style.WARNING("Detalhes dos erros (linha / mensagem):"))
            for ln, msg in err_lines[:50]:
                self.stdout.write(f"  Linha {ln}: {msg}")
            if len(err_lines) > 50:
                self.stdout.write(self.style.WARNING(f"  ... e mais {len(err_lines) - 50} erro(s)."))
