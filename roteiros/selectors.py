from django.db.models import Count
from django.db.models import Q
from django.shortcuts import get_object_or_404

from cadastros.models import Cidade, Estado

from .models import Roteiro
from .models import RoteiroTrecho


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


def get_trecho_by_id(pk):
    return get_object_or_404(
        RoteiroTrecho.objects.select_related(
            "roteiro",
            "origem_estado",
            "origem_cidade",
            "destino_estado",
            "destino_cidade",
        ),
        pk=pk,
    )


def listar_estados_para_select():
    return Estado.objects.order_by("nome")


def listar_cidades_para_select(estado_id=None, q=None):
    if not estado_id:
        return Cidade.objects.none()
    qs = Cidade.objects.filter(estado_id=estado_id).select_related("estado").order_by("nome")
    if q and str(q).strip():
        qs = qs.filter(nome__icontains=q.strip())
    return qs


def queryset_roteiros_avulsos_para_mapa_rotas(limit=50):
    """Roteiros avulsos com relacionamentos para duplicar estado no editor (mesmo limite do legacy)."""
    return (
        Roteiro.objects.filter(tipo=Roteiro.TIPO_AVULSO)
        .select_related("origem_cidade", "origem_estado")
        .prefetch_related(
            "destinos",
            "destinos__estado",
            "destinos__cidade",
            "trechos",
            "trechos__origem_estado",
            "trechos__origem_cidade",
            "trechos__destino_estado",
            "trechos__destino_cidade",
        )
        .order_by("-pk")[:limit]
    )


def obter_cidades_origem_destino_estimativa(origem_id, destino_id):
    origem = Cidade.objects.filter(pk=origem_id).select_related("estado").first()
    destino = Cidade.objects.filter(pk=destino_id).select_related("estado").first()
    return origem, destino
