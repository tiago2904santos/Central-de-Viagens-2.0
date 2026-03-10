"""
Constantes e helpers centralizados para status RASCUNHO/FINALIZADO.
Usado em Viajante e Veiculo (e futuros módulos com o mesmo fluxo).
"""

# Valores armazenados no banco (não alterar sem migração)
RASCUNHO = 'RASCUNHO'
FINALIZADO = 'FINALIZADO'

# Labels para exibição
LABELS = {
    RASCUNHO: 'Rascunho',
    FINALIZADO: 'Finalizado',
}

# Classes CSS para badge (Bootstrap 5)
BADGE_CLASSES = {
    RASCUNHO: 'badge bg-warning text-dark',
    FINALIZADO: 'badge bg-success',
}


def get_status_label(status):
    """Retorna o label de exibição do status ou o próprio valor se desconhecido."""
    if status is None:
        return ''
    return LABELS.get(status, status)


def get_status_badge_class(status):
    """Retorna as classes CSS para o badge do status (Bootstrap)."""
    if status is None:
        return 'badge bg-secondary'
    return BADGE_CLASSES.get(status, 'badge bg-secondary')
