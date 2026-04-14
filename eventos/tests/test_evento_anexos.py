from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from cadastros.models import Cidade, Estado
from eventos.models import Evento, EventoAnexoSolicitante, TipoDemandaEvento


User = get_user_model()


class EventoAnexosSolicitanteTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')

        self.tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        if self.tipo is None:
            self.tipo = TipoDemandaEvento.objects.create(nome='TESTE', ativo=True, ordem=1)
        self.estado = Estado.objects.create(nome='Parana', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')

        self.evento = Evento.objects.create(
            titulo='',
            data_inicio=date(2026, 1, 10),
            data_fim=date(2026, 1, 10),
            status=Evento.STATUS_RASCUNHO,
        )

    def _payload_base(self):
        return {
            'tipos_demanda': [self.tipo.pk],
            'data_unica': 'on',
            'data_inicio': '2026-01-10',
            'data_fim': '2026-01-10',
            'descricao': '',
            'tem_convite_ou_oficio_evento': 'on',
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade.pk,
        }

    def test_etapa4_salva_multiplos_anexos_pdf(self):
        arquivo_1 = SimpleUploadedFile('convite-1.pdf', b'%PDF-1.4 arquivo um', content_type='application/pdf')
        arquivo_2 = SimpleUploadedFile('oficio-2.pdf', b'%PDF-1.4 arquivo dois', content_type='application/pdf')
        payload = {
            'tem_convite_ou_oficio_evento': 'on',
            'convite_documentos': [arquivo_1, arquivo_2],
        }

        response = self.client.post(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}), payload)

        self.assertEqual(response.status_code, 302)
        self.evento.refresh_from_db()
        self.assertTrue(self.evento.tem_convite_ou_oficio_evento)
        self.assertEqual(self.evento.anexos_solicitante.count(), 2)

    def test_etapa4_nao_duplica_o_mesmo_pdf_em_reenvio(self):
        arquivo_1 = SimpleUploadedFile('convite-1.pdf', b'%PDF-1.4 arquivo repetido', content_type='application/pdf')
        payload_1 = {
            'tem_convite_ou_oficio_evento': 'on',
            'convite_documentos': [arquivo_1],
        }
        arquivo_2 = SimpleUploadedFile('convite-1.pdf', b'%PDF-1.4 arquivo repetido', content_type='application/pdf')
        payload_2 = {
            'tem_convite_ou_oficio_evento': 'on',
            'convite_documentos': [arquivo_2],
        }

        response_1 = self.client.post(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}), payload_1)
        response_2 = self.client.post(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}), payload_2)

        self.assertEqual(response_1.status_code, 302)
        self.assertEqual(response_2.status_code, 302)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.anexos_solicitante.count(), 1)

    def test_etapa4_permite_desmarcar_convite_mesmo_com_anexo_existente(self):
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-a.pdf',
            arquivo=SimpleUploadedFile('convite-a.pdf', b'%PDF-1.4 a', content_type='application/pdf'),
            ordem=0,
        )
        self.evento.tem_convite_ou_oficio_evento = True
        self.evento.save(update_fields=['tem_convite_ou_oficio_evento'])

        response = self.client.post(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}), {})

        self.assertEqual(response.status_code, 302)
        self.evento.refresh_from_db()
        self.assertFalse(self.evento.tem_convite_ou_oficio_evento)
        self.assertEqual(self.evento.anexos_solicitante.count(), 1)

    def test_etapa4_remove_todos_os_anexos_quando_convite_e_desmarcado(self):
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-a.pdf',
            arquivo=SimpleUploadedFile('convite-a.pdf', b'%PDF-1.4 a', content_type='application/pdf'),
            ordem=0,
        )
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-b.pdf',
            arquivo=SimpleUploadedFile('convite-b.pdf', b'%PDF-1.4 b', content_type='application/pdf'),
            ordem=1,
        )
        self.evento.tem_convite_ou_oficio_evento = True
        self.evento.save(update_fields=['tem_convite_ou_oficio_evento'])

        response = self.client.post(
            reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}),
            {'remover_todos_anexos_convite': '1'},
        )

        self.assertEqual(response.status_code, 302)
        self.evento.refresh_from_db()
        self.assertFalse(self.evento.tem_convite_ou_oficio_evento)
        self.assertEqual(self.evento.anexos_solicitante.count(), 0)

    def test_etapa4_ajax_remove_todos_os_anexos(self):
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-a.pdf',
            arquivo=SimpleUploadedFile('convite-a.pdf', b'%PDF-1.4 a', content_type='application/pdf'),
            ordem=0,
        )
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-b.pdf',
            arquivo=SimpleUploadedFile('convite-b.pdf', b'%PDF-1.4 b', content_type='application/pdf'),
            ordem=1,
        )
        self.evento.tem_convite_ou_oficio_evento = True
        self.evento.save(update_fields=['tem_convite_ou_oficio_evento'])

        response = self.client.post(
            reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}),
            {'remover_todos_anexos_convite': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertIn('evento-section-convite', payload.get('html', ''))
        self.evento.refresh_from_db()
        self.assertFalse(self.evento.tem_convite_ou_oficio_evento)
        self.assertEqual(self.evento.anexos_solicitante.count(), 0)

    def test_etapa4_get_deduplica_anexos_existentes(self):
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-a.pdf',
            arquivo=SimpleUploadedFile('convite-a.pdf', b'%PDF-1.4 a', content_type='application/pdf'),
            ordem=0,
        )
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-a.pdf',
            arquivo=SimpleUploadedFile('convite-a.pdf', b'%PDF-1.4 a', content_type='application/pdf'),
            ordem=1,
        )

        response = self.client.get(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}))

        self.assertEqual(response.status_code, 200)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.anexos_solicitante.count(), 1)

    def test_etapa4_ajax_atualiza_sem_redirect(self):
        response = self.client.post(
            reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}),
            {'tem_convite_ou_oficio_evento': 'on', 'remover_todos_anexos_convite': '0'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'application/json')
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertIn('evento-section-convite', payload.get('html', ''))

    def test_etapa4_rejeita_anexo_nao_pdf(self):
        arquivo_invalido = SimpleUploadedFile('convite.txt', b'teste', content_type='text/plain')
        payload = {
            'tem_convite_ou_oficio_evento': 'on',
            'convite_documentos': [arquivo_invalido],
        }

        response = self.client.post(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}), payload, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PDF')
        self.assertEqual(EventoAnexoSolicitante.objects.count(), 0)

    def test_remove_anexo_individual(self):
        anexo_1 = EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-a.pdf',
            arquivo=SimpleUploadedFile('convite-a.pdf', b'%PDF-1.4 a', content_type='application/pdf'),
            ordem=0,
        )
        EventoAnexoSolicitante.objects.create(
            evento=self.evento,
            nome_original='convite-b.pdf',
            arquivo=SimpleUploadedFile('convite-b.pdf', b'%PDF-1.4 b', content_type='application/pdf'),
            ordem=1,
        )
        self.evento.tem_convite_ou_oficio_evento = True
        self.evento.save(update_fields=['tem_convite_ou_oficio_evento'])

        response = self.client.post(
            reverse('eventos:evento-anexo-remover', kwargs={'anexo_id': anexo_1.pk}),
            {'next': reverse('eventos:guiado-etapa-1', kwargs={'pk': self.evento.pk})},
        )

        self.assertEqual(response.status_code, 302)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.anexos_solicitante.count(), 1)
        self.assertTrue(self.evento.tem_convite_ou_oficio_evento)
