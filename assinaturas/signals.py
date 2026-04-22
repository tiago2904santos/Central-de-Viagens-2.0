from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from assinaturas.services.documento_bloqueio import invalidar_assinaturas_por_alteracao
from eventos.models import Justificativa, Oficio, OficioTrecho, OrdemServico, PlanoTrabalho, TermoAutorizacao


def _sincronizar(documento_tipo: str, pk: int | None) -> None:
    invalidar_assinaturas_por_alteracao(documento_tipo, pk)


@receiver(post_save, sender=Oficio)
def _oficio_pos_save(sender, instance, **kwargs):
    _sincronizar("eventos.oficio", instance.pk)


@receiver(post_save, sender=OficioTrecho)
def _oficio_trecho_pos_save(sender, instance, **kwargs):
    _sincronizar("eventos.oficio", instance.oficio_id)


@receiver(post_delete, sender=OficioTrecho)
def _oficio_trecho_pos_delete(sender, instance, **kwargs):
    _sincronizar("eventos.oficio", instance.oficio_id)


@receiver(post_save, sender=Justificativa)
def _justificativa_pos_save(sender, instance, **kwargs):
    _sincronizar("eventos.justificativa", instance.pk)


@receiver(post_save, sender=PlanoTrabalho)
def _plano_pos_save(sender, instance, **kwargs):
    _sincronizar("eventos.planotrabalho", instance.pk)


@receiver(post_save, sender=OrdemServico)
def _os_pos_save(sender, instance, **kwargs):
    _sincronizar("eventos.ordemservico", instance.pk)


@receiver(post_save, sender=TermoAutorizacao)
def _termo_pos_save(sender, instance, **kwargs):
    _sincronizar("eventos.termoautorizacao", instance.pk)


@receiver(m2m_changed, sender=Oficio.viajantes.through)
def _oficio_viajantes_alterados(sender, instance, action, **kwargs):
    if action in {"post_add", "post_remove", "post_clear"}:
        _sincronizar("eventos.oficio", instance.pk)
