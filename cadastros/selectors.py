from .models import Cidade
from .models import Motorista
from .models import Servidor
from .models import Unidade
from .models import Viatura


def listar_unidades():
    return Unidade.objects.order_by("nome")


def listar_cidades():
    return Cidade.objects.order_by("uf", "nome")


def listar_servidores():
    return Servidor.objects.select_related("unidade").order_by("nome")


def listar_motoristas():
    return Motorista.objects.select_related("servidor", "servidor__unidade").order_by(
        "servidor__nome"
    )


def listar_viaturas():
    return Viatura.objects.select_related("unidade").order_by("placa")
