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


def listar_servidores(q=None):
    queryset = Servidor.objects.select_related("unidade").order_by("nome")
    if q:
        queryset = queryset.filter(
            Q(nome__icontains=q)
            | Q(matricula__icontains=q)
            | Q(cargo__icontains=q)
            | Q(cpf__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__sigla__icontains=q)
        )
    return queryset


def listar_motoristas(q=None):
    queryset = Motorista.objects.select_related("servidor", "servidor__unidade").order_by(
        "servidor__nome"
    )
    if q:
        queryset = queryset.filter(
            Q(servidor__nome__icontains=q)
            | Q(servidor__matricula__icontains=q)
            | Q(cnh__icontains=q)
            | Q(categoria_cnh__icontains=q)
        )
    return queryset


def listar_viaturas(q=None):
    queryset = Viatura.objects.select_related("unidade").order_by("placa")
    if q:
        queryset = queryset.filter(
            Q(placa__icontains=q)
            | Q(modelo__icontains=q)
            | Q(marca__icontains=q)
            | Q(tipo__icontains=q)
            | Q(combustivel__icontains=q)
            | Q(unidade__nome__icontains=q)
            | Q(unidade__sigla__icontains=q)
        )
    return queryset


def get_servidor_by_id(pk):
    return get_object_or_404(Servidor.objects.select_related("unidade"), pk=pk)


def get_motorista_by_id(pk):
    return get_object_or_404(
        Motorista.objects.select_related("servidor", "servidor__unidade"), pk=pk
    )


def get_viatura_by_id(pk):
    return get_object_or_404(Viatura.objects.select_related("unidade"), pk=pk)
