def criar_unidade(form):
    return form.save()


def atualizar_unidade(instance, form):
    return form.save()


def excluir_unidade(instance):
    instance.ativa = False
    instance.save(update_fields=["ativa", "updated_at"])
    return instance


def criar_cidade(form):
    return form.save()


def atualizar_cidade(instance, form):
    return form.save()


def excluir_cidade(instance):
    instance.ativa = False
    instance.save(update_fields=["ativa", "updated_at"])
    return instance
