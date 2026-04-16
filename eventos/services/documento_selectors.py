from django.db.models import Prefetch

from cadastros.models import Viajante
from eventos.models import Oficio, OrdemServico, PlanoTrabalho


def planos_trabalho_base_queryset():
    return (
        PlanoTrabalho.objects.select_related('evento', 'oficio', 'solicitante', 'roteiro')
        .prefetch_related('oficios', 'oficios__eventos')
        .all()
    )


def ordens_servico_base_queryset():
    return (
        OrdemServico.objects.select_related('evento', 'oficio').prefetch_related(
            Prefetch('viajantes', queryset=Viajante.objects.select_related('cargo', 'unidade_lotacao')),
            Prefetch('oficio__viajantes', queryset=Viajante.objects.select_related('cargo', 'unidade_lotacao')),
        ).all()
    )


def oficios_linkables(limit=12):
    return list(Oficio.objects.prefetch_related('eventos').order_by('-updated_at')[:limit])
