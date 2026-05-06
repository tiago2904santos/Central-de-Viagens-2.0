from django.db.models import ProtectedError


DEFAULT_DELETE_BLOCKED_MESSAGE = (
    "Não foi possível excluir este cadastro porque ele está vinculado a outros registros."
)


class DelecaoProtegidaError(Exception):
    """Erro de domínio para padronizar exclusão bloqueada por vínculo."""


def excluir_com_protecao(instance):
    try:
        instance.delete()
    except ProtectedError as exc:
        raise DelecaoProtegidaError(DEFAULT_DELETE_BLOCKED_MESSAGE) from exc
