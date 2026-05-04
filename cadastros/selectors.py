from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Cidade
from .models import Motorista
from .models import Servidor
from .models import Unidade
from .models import Viatura


def listar_unidades(q=None):
    queryset = Unidade.objects.order_by("nome")
    if q:
        queryset = queryset.filter(Q(nome__icontains=q) | Q(sigla__icontains=q))
    return queryset


def listar_cidades(q=None):
    queryset = Cidade.objects.order_by("uf", "nome")
    if q:
        queryset = queryset.filter(Q(nome__icontains=q) | Q(uf__icontains=q))
    return queryset


def get_unidade_by_id(pk):
    return get_object_or_404(Unidade, pk=pk)


def get_cidade_by_id(pk):
    return get_object_or_404(Cidade, pk=pk)


def listar_servidores():
    return Servidor.objects.select_related("unidade").order_by("nome")


def listar_motoristas():
    return Motorista.objects.select_related("servidor", "servidor__unidade").order_by(
        "servidor__nome"
    )


def listar_viaturas():
    return Viatura.objects.select_related("unidade").order_by("placa")
