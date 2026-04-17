"""Resgate documento → evento e pacote documental agregado."""
from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone as dj_tz

from cadastros.models import Cargo, Cidade, CombustivelVeiculo, Estado, UnidadeLotacao, Veiculo, Viajante
from eventos.models import (
    Evento,
    EventoDestino,
    EventoDocumentoSugestao,
    EventoParticipante,
    EventoResgateAuditoria,
    Oficio,
    OficioTrecho,
    OrdemServico,
    PlanoTrabalho,
    RoteiroEvento,
    RoteiroEventoDestino,
    TermoAutorizacao,
)
from eventos.services.evento_pacote import build_evento_document_pacote
from eventos.services.evento_resgate import (
    auto_attach_document_to_event_if_safe,
    list_candidate_events_for_document,
    resgatar_documentos_orfaos_para_evento,
)


class EventoResgateTest(TestCase):
    def setUp(self):
        self.estado_pr = Estado.objects.create(nome='Paraná', sigla='PR')
        self.cidade_maringa = Cidade.objects.create(nome='Maringá', estado=self.estado_pr)
        self.cidade_londrina = Cidade.objects.create(nome='Londrina', estado=self.estado_pr)
        self.cargo = Cargo.objects.create(nome='Agente')
        self.unidade = UnidadeLotacao.objects.create(nome='DPC')
        self.v1 = Viajante.objects.create(
            nome='ANA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            sem_rg=True,
            cpf='11111111111',
            telefone='44999990001',
            unidade_lotacao=self.unidade,
        )
        self.v2 = Viajante.objects.create(
            nome='BRUNO',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            sem_rg=True,
            cpf='22222222222',
            telefone='44999990002',
            unidade_lotacao=self.unidade,
        )
        comb = CombustivelVeiculo.objects.create(nome='Gasolina', is_padrao=True)
        self.veiculo = Veiculo.objects.create(
            placa='ABC1D23',
            modelo='Sedan',
            combustivel=comb,
            tipo=Veiculo.TIPO_DESCARACTERIZADO,
            status=Veiculo.STATUS_FINALIZADO,
        )

    def _criar_evento_maringa_16(self, titulo='Maringá 16'):
        ev = Evento.objects.create(
            titulo=titulo,
            data_inicio=date(2026, 4, 16),
            data_fim=date(2026, 4, 16),
            data_unica=True,
            status=Evento.STATUS_RASCUNHO,
        )
        EventoDestino.objects.create(evento=ev, estado=self.estado_pr, cidade=self.cidade_maringa, ordem=0)
        EventoParticipante.objects.create(evento=ev, viajante=self.v1, ordem=0)
        ev.veiculo = self.veiculo
        ev.save(update_fields=['veiculo'])
        return ev

    def test_resgate_automatico_oficio_avulso(self):
        ev = self._criar_evento_maringa_16()
        oficio = Oficio.objects.create(
            protocolo='123456789',
            data_criacao=date(2026, 4, 10),
            motivo='Motivo',
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_AVULSO,
            veiculo=self.veiculo,
        )
        oficio.viajantes.add(self.v1)
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            destino_cidade=self.cidade_maringa,
            destino_estado=self.estado_pr,
            saida_data=date(2026, 4, 16),
            saida_hora=time(8, 0),
            chegada_data=date(2026, 4, 16),
            chegada_hora=time(10, 0),
        )
        r = auto_attach_document_to_event_if_safe(oficio)
        self.assertTrue(r.get('attached'))
        oficio.refresh_from_db()
        self.assertTrue(oficio.esta_vinculado_a_evento(ev))
        self.assertTrue(
            EventoResgateAuditoria.objects.filter(
                object_id=oficio.pk,
                acao=EventoResgateAuditoria.ACAO_AUTO_ANEXOU,
                evento=ev,
            ).exists()
        )

    def test_resgate_roteiro_e_termo_compativel(self):
        ev = self._criar_evento_maringa_16()
        roteiro = RoteiroEvento.objects.create(
            tipo=RoteiroEvento.TIPO_AVULSO,
            status=RoteiroEvento.STATUS_RASCUNHO,
        )
        RoteiroEventoDestino.objects.create(
            roteiro=roteiro, cidade=self.cidade_maringa, estado=self.estado_pr, ordem=0
        )
        roteiro.saida_dt = dj_tz.make_aware(datetime.combine(date(2026, 4, 16), time(7, 0)))
        roteiro.chegada_dt = dj_tz.make_aware(datetime.combine(date(2026, 4, 16), time(18, 0)))
        roteiro.save(update_fields=['saida_dt', 'chegada_dt'])

        r1 = auto_attach_document_to_event_if_safe(roteiro)
        self.assertTrue(r1.get('attached'))
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.evento_id, ev.pk)

        termo = TermoAutorizacao.objects.create(
            destino='Maringá/PR',
            data_evento=date(2026, 4, 16),
            viajante=self.v1,
            veiculo=self.veiculo,
        )
        r2 = auto_attach_document_to_event_if_safe(termo)
        self.assertTrue(r2.get('attached'))
        termo.refresh_from_db()
        self.assertEqual(termo.evento_id, ev.pk)

    def test_ambiguidade_nao_anexa_automaticamente(self):
        ev1 = self._criar_evento_maringa_16('A')
        ev2 = self._criar_evento_maringa_16('B')
        oficio = Oficio.objects.create(
            protocolo='987654321',
            data_criacao=date(2026, 4, 10),
            motivo='Motivo',
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_AVULSO,
        )
        oficio.viajantes.add(self.v1, self.v2)
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            destino_cidade=self.cidade_maringa,
            destino_estado=self.estado_pr,
            saida_data=date(2026, 4, 16),
            saida_hora=time(8, 0),
            chegada_data=date(2026, 4, 16),
            chegada_hora=time(10, 0),
        )
        cands = list_candidate_events_for_document(oficio)
        self.assertGreaterEqual(len(cands), 2)
        r = auto_attach_document_to_event_if_safe(oficio)
        self.assertTrue(r.get('suggestion') or r.get('noop'))
        oficio.refresh_from_db()
        self.assertFalse(oficio.vinculos_evento.exists())
        self.assertTrue(EventoDocumentoSugestao.objects.filter(object_id=oficio.pk).exists())

    def test_conflito_periodo_nao_anexa(self):
        ev = Evento.objects.create(
            titulo='Semana 1',
            data_inicio=date(2026, 5, 1),
            data_fim=date(2026, 5, 5),
            status=Evento.STATUS_RASCUNHO,
        )
        EventoDestino.objects.create(evento=ev, estado=self.estado_pr, cidade=self.cidade_maringa, ordem=0)
        oficio = Oficio.objects.create(
            protocolo='555555555',
            data_criacao=date(2026, 4, 10),
            motivo='Motivo',
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_AVULSO,
        )
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            destino_cidade=self.cidade_maringa,
            destino_estado=self.estado_pr,
            saida_data=date(2026, 4, 16),
            saida_hora=time(8, 0),
            chegada_data=date(2026, 4, 16),
            chegada_hora=time(10, 0),
        )
        r = auto_attach_document_to_event_if_safe(oficio)
        self.assertFalse(r.get('attached'))
        self.assertFalse(oficio.vinculos_evento.exists())

    def test_pacote_evento_reune_oficio_plano_ordem_termo_roteiro(self):
        ev = self._criar_evento_maringa_16()
        oficio = Oficio.objects.create(
            protocolo='111111111',
            data_criacao=date(2026, 4, 10),
            motivo='Motivo',
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_EVENTO,
        )
        oficio.eventos.add(ev)
        roteiro = RoteiroEvento.objects.create(
            evento=ev,
            tipo=RoteiroEvento.TIPO_EVENTO,
            status=RoteiroEvento.STATUS_RASCUNHO,
        )
        plano = PlanoTrabalho.objects.create(
            evento=ev,
            oficio=oficio,
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        ordem = OrdemServico.objects.create(
            evento=ev,
            oficio=oficio,
            status=OrdemServico.STATUS_RASCUNHO,
        )
        termo = TermoAutorizacao.objects.create(
            evento=ev,
            oficio=oficio,
            destino='Maringá',
            data_evento=date(2026, 4, 16),
        )
        pacote = build_evento_document_pacote(ev)
        keys = {s['key'] for s in pacote['sections']}
        self.assertTrue({'oficios', 'roteiros', 'planos', 'ordens', 'termos'} <= keys)

    def test_documento_avulso_sem_evento_permanece_valido(self):
        os_doc = OrdemServico.objects.create(
            data_deslocamento=date(2027, 1, 1),
            finalidade='Avulso',
            status=OrdemServico.STATUS_RASCUNHO,
        )
        self.assertIsNone(os_doc.evento_id)
        r = auto_attach_document_to_event_if_safe(os_doc)
        self.assertFalse(r.get('attached'))
        os_doc.refresh_from_db()
        self.assertIsNone(os_doc.evento_id)

    def test_pos_save_evento_dispara_resgate(self):
        ev = self._criar_evento_maringa_16()
        oficio = Oficio.objects.create(
            protocolo='333333333',
            data_criacao=date(2026, 4, 10),
            motivo='Motivo',
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_AVULSO,
        )
        oficio.viajantes.add(self.v1)
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            destino_cidade=self.cidade_maringa,
            destino_estado=self.estado_pr,
            saida_data=date(2026, 4, 16),
            saida_hora=time(8, 0),
            chegada_data=date(2026, 4, 16),
            chegada_hora=time(10, 0),
        )
        stats = resgatar_documentos_orfaos_para_evento(ev)
        oficio.refresh_from_db()
        self.assertTrue(oficio.esta_vinculado_a_evento(ev))
        self.assertGreaterEqual(stats['auto'], 1)
