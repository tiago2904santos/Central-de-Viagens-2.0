from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Roteiro
from .models import TrechoRoteiro


def listar_roteiros(q=None):
    queryset = (
        Roteiro.objects.select_related(
            "origem",
            "destino",
            "origem__estado",
            "destino__estado",
        )
        .annotate(trechos_count=Count("trechos"))
        .order_by("-updated_at", "nome")
    )
    if q:
        queryset = queryset.filter(
            Q(nome__icontains=q)
            | Q(descricao__icontains=q)
            | Q(origem__nome__icontains=q)
            | Q(origem__estado__nome__icontains=q)
            | Q(origem__estado__sigla__icontains=q)
            | Q(destino__nome__icontains=q)
            | Q(destino__estado__nome__icontains=q)
            | Q(destino__estado__sigla__icontains=q)
        )
    return queryset


def get_roteiro_by_id(pk):
    return get_object_or_404(
        Roteiro.objects.select_related(
            "origem",
            "destino",
            "origem__estado",
            "destino__estado",
        ),
        pk=pk,
    )


def listar_trechos_do_roteiro(roteiro):
    return (
        TrechoRoteiro.objects.filter(roteiro=roteiro)
        .select_related("origem", "destino", "origem__estado", "destino__estado")
        .order_by("ordem")
    )
