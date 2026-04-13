"""
Management command: excluir_rascunhos
Exclui todos os registros em rascunho do sistema.

Uso:
    python manage.py excluir_rascunhos             # modo interativo (pede confirmação)
    python manage.py excluir_rascunhos --dry-run   # só mostra contagens, não exclui
    python manage.py excluir_rascunhos --force     # exclui sem pedir confirmação
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from cadastros.models import Veiculo, Viajante
from eventos.models import (
    Evento,
    Oficio,
    PlanoTrabalho,
    RoteiroEvento,
)


class Command(BaseCommand):
    help = 'Exclui todos os registros em status RASCUNHO do sistema.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas conta os registros que seriam excluídos, sem excluir.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Executa a exclusão sem pedir confirmação interativa.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        # ------------------------------------------------------------------ #
        # Contagens de rascunhos por modelo                                   #
        # Ordem importa: Evento cascateia Oficio e RoteiroEvento vinculados.  #
        # ------------------------------------------------------------------ #

        eventos_qs = Evento.objects.filter(status=Evento.STATUS_RASCUNHO)
        # Todos os ofícios em rascunho, com ou sem evento vinculado.
        oficios_qs = Oficio.objects.filter(status=Oficio.STATUS_RASCUNHO)
        # Todos os roteiros em rascunho, com ou sem evento vinculado.
        roteiros_qs = RoteiroEvento.objects.filter(status=RoteiroEvento.STATUS_RASCUNHO)
        # PlanoTrabalho usa SET_NULL no FK evento, portanto não é cascateado.
        planos_qs = PlanoTrabalho.objects.filter(status=PlanoTrabalho.STATUS_RASCUNHO)

        viajantes_qs = Viajante.objects.filter(status=Viajante.STATUS_RASCUNHO)
        veiculos_qs = Veiculo.objects.filter(status=Veiculo.STATUS_RASCUNHO)

        counts = {
            'Eventos (RASCUNHO)': eventos_qs.count(),
            'Ofícios (RASCUNHO)': oficios_qs.count(),
            'Roteiros (RASCUNHO)': roteiros_qs.count(),
            'Planos de Trabalho (RASCUNHO)': planos_qs.count(),
            'Viajantes (RASCUNHO)': viajantes_qs.count(),
            'Veículos (RASCUNHO)': veiculos_qs.count(),
        }

        self.stdout.write(self.style.WARNING('\n=== Rascunhos encontrados ==='))
        total_direto = 0
        for label, count in counts.items():
            cor = self.style.ERROR if count > 0 else self.style.SUCCESS
            self.stdout.write(f'  {label}: {cor(str(count))}')
            total_direto += count
        self.stdout.write('')

        if total_direto == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum rascunho encontrado. Nada a fazer.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('[DRY-RUN] Nenhum registro foi excluído.'))
            return

        if not force:
            confirmacao = input(
                'Tem certeza que deseja EXCLUIR permanentemente esses registros? '
                'Digite "sim" para confirmar: '
            )
            if confirmacao.strip().lower() != 'sim':
                self.stdout.write(self.style.WARNING('Operação cancelada.'))
                return

        # ------------------------------------------------------------------ #
        # Exclusão dentro de uma transação atômica                           #
        # ------------------------------------------------------------------ #
        with transaction.atomic():
            # Excluir ofícios e roteiros antes dos eventos para evitar
            # conflito com a CASCADE do evento (que excluiria os mesmos registros).
            n_oficios, _ = oficios_qs.delete()
            n_roteiros, _ = roteiros_qs.delete()
            n_eventos, _ = eventos_qs.delete()
            n_planos, _ = planos_qs.delete()
            n_viajantes, _ = viajantes_qs.delete()
            n_veiculos, _ = veiculos_qs.delete()

        self.stdout.write(self.style.SUCCESS('\n=== Exclusão concluída ==='))
        self.stdout.write(f'  Ofícios excluídos: {n_oficios}')
        self.stdout.write(f'  Roteiros excluídos: {n_roteiros}')
        self.stdout.write(f'  Eventos excluídos: {n_eventos}')
        self.stdout.write(f'  Planos de Trabalho excluídos: {n_planos}')
        self.stdout.write(f'  Viajantes excluídos: {n_viajantes}')
        self.stdout.write(f'  Veículos excluídos: {n_veiculos}')
        self.stdout.write('')
