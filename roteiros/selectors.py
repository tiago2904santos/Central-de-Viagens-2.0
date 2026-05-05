from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Roteiro


def listar_roteiros(q=None):
    queryset = (
        Roteiro.objects.select_related("origem_estado", "origem_cidade", "origem_cidade__estado")
        .prefetch_related("destinos__cidade", "destinos__estado")
        .annotate(trechos_count=Count("trechos", distinct=True))
        .order_by("-updated_at")
    )
    if q:
        queryset = queryset.filter(
            Q(origem_cidade__nome__icontains=q)
            | Q(origem_estado__sigla__icontains=q)
            | Q(origem_estado__nome__icontains=q)
            | Q(destinos__cidade__nome__icontains=q)
            | Q(destinos__estado__sigla__icontains=q)
            | Q(observacoes__icontains=q)
            | Q(quantidade_diarias__icontains=q)
        ).distinct()
    return queryset


def get_roteiro_by_id(pk):
    return get_object_or_404(
        Roteiro.objects.select_related(
            "origem_estado",
            "origem_cidade",
            "origem_cidade__estado",
        ).prefetch_related(
            "destinos__cidade",
            "destinos__estado",
            "trechos__origem_estado",
            "trechos__origem_cidade",
            "trechos__destino_estado",
            "trechos__destino_cidade",
        ),
        pk=pk,
    )


def listar_trechos_do_roteiro(roteiro):
    return (
        roteiro.trechos.select_related(
            "origem_estado",
            "origem_cidade",
            "destino_estado",
            "destino_cidade",
        )
        .order_by("ordem", "pk")
    )
