from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Cargo
from .models import Cidade
from .models import Combustivel
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


def listar_cargos(q=None):
    queryset = Cargo.objects.order_by("nome")
    if q:
        queryset = queryset.filter(Q(nome__icontains=q))
    return queryset


def get_cargo_by_id(pk):
    return get_object_or_404(Cargo, pk=pk)


def listar_combustiveis(q=None):
    queryset = Combustivel.objects.order_by("nome")
    if q:
        queryset = queryset.filter(Q(nome__icontains=q))
    return queryset


def get_combustivel_by_id(pk):
    return get_object_or_404(Combustivel, pk=pk)


def listar_servidores(q=None):
    queryset = Servidor.objects.select_related("cargo", "unidade").order_by("nome")
    if q:
        queryset = queryset.filter(
            Q(nome__icontains=q)
            | Q(cpf__icontains=q)
            | Q(rg__icontains=q)
            | Q(cargo__nome__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__sigla__icontains=q)
        )
    return queryset


def get_servidor_by_id(pk):
    return get_object_or_404(Servidor.objects.select_related("cargo", "unidade"), pk=pk)


def listar_viaturas(q=None):
    queryset = Viatura.objects.select_related("combustivel").order_by("placa")
    if q:
        queryset = queryset.filter(
            Q(placa__icontains=q)
            | Q(modelo__icontains=q)
            | Q(combustivel__nome__icontains=q)
            | Q(tipo__icontains=q)
        )
    return queryset


def get_viatura_by_id(pk):
    return get_object_or_404(Viatura.objects.select_related("combustivel"), pk=pk)
