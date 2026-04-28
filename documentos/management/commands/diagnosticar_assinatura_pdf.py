from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from documentos.services.assinaturas import diagnosticar_estrutura_assinatura_pdf


class Command(BaseCommand):
    help = "Diagnostica estrutura técnica de assinatura em um PDF."

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", type=str, help="Caminho do arquivo PDF")

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf_path"])
        if not pdf_path.exists():
            raise CommandError(f"Arquivo não encontrado: {pdf_path}")
        payload = pdf_path.read_bytes()
        diag = diagnosticar_estrutura_assinatura_pdf(payload)
        for key, value in diag.items():
            self.stdout.write(f"{key}: {value}")
