"""Testes da topologia documental: ofício N:N com evento, OS herdadas via evento, camada central de vínculos."""

from datetime import date

from django.test import TestCase

from eventos.models import Evento, Oficio, OrdemServico, RoteiroEvento
from eventos.models import PlanoTrabalho
from eventos.services.documento_vinculos import (
    resolver_vinculos_evento,
    resolver_vinculos_oficio,
    resolver_vinculos_ordem_servico,
)


class TopologiaDocumentalVinculosTest(TestCase):
    def setUp(self):
        self.ev1 = Evento.objects.create(
            titulo='Evento Alfa',
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 1, 3),
            status=Evento.STATUS_RASCUNHO,
        )
        self.ev2 = Evento.objects.create(
            titulo='Evento Beta',
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 2, 3),
            status=Evento.STATUS_RASCUNHO,
        )

    def test_oficio_pode_vincular_a_varios_eventos(self):
        oficio = Oficio.objects.create(status=Oficio.STATUS_RASCUNHO)
        oficio.eventos.add(self.ev1, self.ev2)
        self.assertEqual(
            set(oficio.eventos.values_list('pk', flat=True)),
            {self.ev1.pk, self.ev2.pk},
        )
        self.assertTrue(oficio.esta_vinculado_a_evento(self.ev1))
        self.assertTrue(oficio.esta_vinculado_a_evento(self.ev2))

    def test_evento_lista_oficios_roteiros_planos_ordens_via_resolver(self):
        oficio = Oficio.objects.create(evento=self.ev1, status=Oficio.STATUS_RASCUNHO)
        roteiro = RoteiroEvento.objects.create(
            evento=self.ev1,
            tipo=RoteiroEvento.TIPO_EVENTO,
            status=RoteiroEvento.STATUS_RASCUNHO,
        )
        plano = PlanoTrabalho.objects.create(evento=self.ev1, status=PlanoTrabalho.STATUS_RASCUNHO)
        ordem = OrdemServico.objects.create(evento=self.ev1, status=OrdemServico.STATUS_RASCUNHO)
        r = resolver_vinculos_evento(self.ev1)
        self.assertIn(oficio, r['oficios'])
        self.assertIn(roteiro, r['roteiros'])
        self.assertIn(plano, r['planos'])
        self.assertIn(ordem, r['ordens'])

    def test_os_vinculada_ao_evento_herda_todos_os_oficios(self):
        o1 = Oficio.objects.create(evento=self.ev1, status=Oficio.STATUS_RASCUNHO)
        o2 = Oficio.objects.create(evento=self.ev1, status=Oficio.STATUS_RASCUNHO)
        os_ev = OrdemServico.objects.create(evento=self.ev1, status=OrdemServico.STATUS_RASCUNHO)
        r = resolver_vinculos_ordem_servico(os_ev)
        herdados_ids = [v.id for v in r['herdados'] if v.tipo == 'oficio']
        self.assertCountEqual(herdados_ids, [o1.pk, o2.pk])

    def test_oficio_exibe_os_herdada_via_evento_no_resolver(self):
        oficio = Oficio.objects.create(evento=self.ev1, status=Oficio.STATUS_RASCUNHO)
        os_ev = OrdemServico.objects.create(evento=self.ev1, status=OrdemServico.STATUS_RASCUNHO)
        r = resolver_vinculos_oficio(oficio)
        herd_os = [v for v in r['herdados'] if v.tipo == 'ordem_servico']
        self.assertTrue(any(v.id == os_ev.pk for v in herd_os))

    def test_oficio_nao_duplica_os_que_ja_eh_vinculo_direto(self):
        oficio = Oficio.objects.create(evento=self.ev1, status=Oficio.STATUS_RASCUNHO)
        os_d = OrdemServico.objects.create(
            evento=self.ev1,
            oficio=oficio,
            status=OrdemServico.STATUS_RASCUNHO,
        )
        r = resolver_vinculos_oficio(oficio)
        herd_os_ids = [v.id for v in r['herdados'] if v.tipo == 'ordem_servico']
        self.assertNotIn(os_d.pk, herd_os_ids)
        direto_os_ids = [v.id for v in r['diretos'] if v.tipo == 'ordem_servico']
        self.assertIn(os_d.pk, direto_os_ids)
