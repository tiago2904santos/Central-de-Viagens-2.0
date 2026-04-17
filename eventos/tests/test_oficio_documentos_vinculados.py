"""Fluxo do wizard do ofício após remoção do vínculo lateral documento↔documento."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from cadastros.models import Cargo, Cidade, Estado, UnidadeLotacao, Viajante
from eventos.models import Evento, Justificativa, Oficio, OficioTrecho

User = get_user_model()


class OficioWizardContextoEventoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='oficio-wizard', password='oficio-wizard')
        self.client.login(username='oficio-wizard', password='oficio-wizard')

        self.estado_pr = Estado.objects.create(nome='Paraná', sigla='PR')
        self.cidade_maringa = Cidade.objects.create(nome='Maringá', estado=self.estado_pr)
        self.cargo = Cargo.objects.create(nome='Agente')
        self.unidade = UnidadeLotacao.objects.create(nome='DPC')
        self.viajante = Viajante.objects.create(
            nome='ANA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            sem_rg=True,
            cpf='11111111111',
            telefone='44999990001',
            unidade_lotacao=self.unidade,
        )

        self.evento = Evento.objects.create(
            titulo='Op Maringá',
            data_inicio=date(2026, 4, 16),
            data_fim=date(2026, 4, 16),
            data_unica=True,
            status=Evento.STATUS_RASCUNHO,
        )

    def test_step1_exibe_bloco_pertencimento_evento(self):
        oficio = Oficio.objects.create(
            protocolo='123456789',
            data_criacao=date(2026, 4, 10),
            motivo='Motivo',
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_EVENTO,
        )
        oficio.eventos.add(self.evento)
        Justificativa.objects.create(oficio=oficio, texto='x')

        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertIn('oficio_evento_context_block', response.context)
        block = response.context['oficio_evento_context_block']
        self.assertFalse(block['sem_evento'])
        self.assertContains(response, 'Pertencimento ao evento')
