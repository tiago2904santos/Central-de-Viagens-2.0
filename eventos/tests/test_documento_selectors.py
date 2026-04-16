from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from eventos.models import Evento, Oficio, OrdemServico, PlanoTrabalho
from eventos.services.documento_selectors import (
    oficios_linkables,
    ordens_servico_base_queryset,
    planos_trabalho_base_queryset,
)


User = get_user_model()


class DocumentoSelectorsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='selector', password='selector123')
        self.client.login(username='selector', password='selector123')
        self.evento = Evento.objects.create(
            titulo='Evento Selectors',
            data_inicio=date(2026, 5, 10),
            data_fim=date(2026, 5, 12),
            status=Evento.STATUS_EM_ANDAMENTO,
        )
        self.oficio = Oficio.objects.create(
            evento=self.evento,
            protocolo='123123123',
            data_criacao=date(2026, 5, 1),
            status=Oficio.STATUS_RASCUNHO,
        )
        self.plano = PlanoTrabalho.objects.create(
            evento=self.evento,
            oficio=self.oficio,
            data_criacao=date(2026, 5, 2),
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        self.ordem = OrdemServico.objects.create(
            evento=self.evento,
            oficio=self.oficio,
            data_criacao=date(2026, 5, 2),
            data_deslocamento=date(2026, 5, 10),
            status=OrdemServico.STATUS_RASCUNHO,
        )

    def test_selectors_documentais_retorna_queryset_com_registros(self):
        self.assertTrue(planos_trabalho_base_queryset().filter(pk=self.plano.pk).exists())
        self.assertTrue(ordens_servico_base_queryset().filter(pk=self.ordem.pk).exists())
        self.assertTrue(any(of.pk == self.oficio.pk for of in oficios_linkables(limit=20)))

    def test_plano_contexto_vinculo_explicito(self):
        contexto = self.plano.get_contexto_vinculo()
        self.assertEqual(contexto['evento_canonico'].pk, self.evento.pk)
        self.assertIsNone(contexto['evento_herdado'])
        self.assertTrue(any(of.pk == self.oficio.pk for of in contexto['oficios_auxiliares']))
