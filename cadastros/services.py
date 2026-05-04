from django.db import transaction
from django.db.models import ProtectedError

from .models import Cargo
from .models import Combustivel


class CadastroVinculadoError(Exception):
    pass


@transaction.atomic
def definir_cargo_padrao(cargo: Cargo) -> Cargo:
    """Marca o cargo como padrão; o `save()` do modelo garante um único padrão."""
    cargo.is_padrao = True
    cargo.save()
    return cargo


@transaction.atomic
def definir_combustivel_padrao(combustivel: Combustivel) -> Combustivel:
    """Marca o combustível como padrão; o `save()` do modelo garante um único padrão."""
    combustivel.is_padrao = True
    combustivel.save()
    return combustivel


def criar_estado(form):
    return form.save()


def atualizar_estado(instance, form):
    return form.save()


def excluir_estado(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc


def criar_unidade(form):
    return form.save()


def atualizar_unidade(instance, form):
    return form.save()


def excluir_unidade(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc


def criar_cidade(form):
    return form.save()


def atualizar_cidade(instance, form):
    return form.save()


def excluir_cidade(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc


def criar_cargo(form):
    return form.save()


def atualizar_cargo(instance, form):
    return form.save()


def excluir_cargo(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc


def criar_combustivel(form):
    return form.save()


def atualizar_combustivel(instance, form):
    return form.save()


def excluir_combustivel(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc


def criar_servidor(form):
    return form.save()


def atualizar_servidor(instance, form):
    return form.save()


def excluir_servidor(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc


def criar_viatura(form):
    return form.save()


def atualizar_viatura(instance, form):
    return form.save()


def excluir_viatura(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise CadastroVinculadoError from exc
