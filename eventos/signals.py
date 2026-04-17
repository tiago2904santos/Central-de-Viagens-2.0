from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from eventos.models import Oficio, OrdemServico, PlanoTrabalho, RoteiroEvento, TermoAutorizacao
from eventos.services.evento_resgate import tentar_resgatar_documento


def _schedule_resgate(instance):
    if not instance.pk:
        return
    transaction.on_commit(lambda: tentar_resgatar_documento(instance))


@receiver(post_save, sender=Oficio)
def resgate_pos_save_oficio(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _schedule_resgate(instance)


@receiver(post_save, sender=RoteiroEvento)
def resgate_pos_save_roteiro(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _schedule_resgate(instance)


@receiver(post_save, sender=PlanoTrabalho)
def resgate_pos_save_plano(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _schedule_resgate(instance)


@receiver(post_save, sender=OrdemServico)
def resgate_pos_save_ordem(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _schedule_resgate(instance)


@receiver(post_save, sender=TermoAutorizacao)
def resgate_pos_save_termo(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _schedule_resgate(instance)
