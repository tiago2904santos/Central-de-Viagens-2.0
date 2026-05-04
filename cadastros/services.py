from django.db.models import ProtectedError


class CadastroVinculadoError(Exception):
    pass


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
