import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from eventos.models import Evento, PlanoTrabalho


User = get_user_model()


class PlanoTrabalhoAutosaveTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='autosave_user', password='autosave_pass123')
        self.client.login(username='autosave_user', password='autosave_pass123')
        self.url = reverse('eventos:documentos-planos-trabalho-autosave')

        self.evento = Evento.objects.create(
            titulo='Evento Autosave',
            data_inicio=date(2026, 3, 10),
            data_fim=date(2026, 3, 12),
        )
        self.plano = PlanoTrabalho.objects.create(
            status=PlanoTrabalho.STATUS_RASCUNHO,
            evento=self.evento,
            evento_data_inicio=date(2026, 3, 10),
            evento_data_fim=date(2026, 3, 12),
            quantidade_servidores=4,
            atividades_codigos='CIN,BO',
            destinos_json=[{'cidade': 'Curitiba', 'estado': 'PR'}],
            diarias_quantidade='2.5',
            diarias_valor_total='1234,56',
            diarias_valor_unitario='493,82',
            diarias_valor_extenso='mil duzentos e trinta e quatro reais e cinquenta e seis centavos',
        )

    def _post_json(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_autosave_formdata_success(self):
        response = self.client.post(
            self.url,
            data={
                'id': str(self.plano.pk),
                'evento_id': str(self.evento.pk),
                'evento_data_unica': '0',
                'evento_data_inicio': '2026-03-20',
                'evento_data_fim': '2026-03-22',
                'quantidade_servidores': '6',
                'destinos_payload': json.dumps([
                    {'cidade': 'Londrina', 'estado': 'PR'},
                    {'cidade': 'Maringa', 'estado': 'PR'},
                ]),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))

        self.plano.refresh_from_db()
        self.assertEqual(self.plano.evento_id, self.evento.pk)
        self.assertEqual(self.plano.evento_data_inicio, date(2026, 3, 20))
        self.assertEqual(self.plano.evento_data_fim, date(2026, 3, 22))
        self.assertEqual(self.plano.quantidade_servidores, 6)
        self.assertEqual(len(self.plano.destinos_json), 2)
        self.assertEqual(self.plano.destinos_json[0]['cidade'], 'Londrina')

    def test_autosave_json_legacy_success(self):
        response = self._post_json(
            {
                'id': self.plano.pk,
                'evento_id': self.evento.pk,
                'evento_data_unica': False,
                'evento_data_inicio': '2026-04-01',
                'evento_data_fim': '2026-04-03',
                'destinos_payload': [
                    {'cidade': 'Foz do Iguacu', 'estado': 'PR'},
                ],
                'diarias': {
                    'qtd': '3.5',
                    'valor_unitario': '150,00',
                    'total': '525,00',
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get('success'))
        self.assertEqual(body.get('id'), self.plano.pk)

        self.plano.refresh_from_db()
        self.assertEqual(self.plano.evento_data_inicio, date(2026, 4, 1))
        self.assertEqual(self.plano.evento_data_fim, date(2026, 4, 3))
        self.assertEqual(self.plano.destinos_json[0]['cidade'], 'Foz do Iguacu')
        self.assertEqual(self.plano.diarias_quantidade, '3.5')

    def test_autosave_partial_update(self):
        response = self.client.post(
            self.url,
            data={
                'id': str(self.plano.pk),
                'destinos_payload': json.dumps([
                    {'cidade': 'Ponta Grossa', 'estado': 'PR'},
                ]),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))

        self.plano.refresh_from_db()
        self.assertEqual(self.plano.destinos_json[0]['cidade'], 'Ponta Grossa')

    def test_autosave_does_not_override_existing_data(self):
        original_evento_id = self.plano.evento_id
        original_data_inicio = self.plano.evento_data_inicio
        original_data_fim = self.plano.evento_data_fim
        original_qtd_servidores = self.plano.quantidade_servidores
        original_atividades = self.plano.atividades_codigos
        original_diarias_total = self.plano.diarias_valor_total

        response = self.client.post(
            self.url,
            data={
                'id': str(self.plano.pk),
                'destinos_payload': json.dumps([
                    {'cidade': 'Cascavel', 'estado': 'PR'},
                ]),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.plano.refresh_from_db()
        self.assertEqual(self.plano.evento_id, original_evento_id)
        self.assertEqual(self.plano.evento_data_inicio, original_data_inicio)
        self.assertEqual(self.plano.evento_data_fim, original_data_fim)
        self.assertEqual(self.plano.quantidade_servidores, original_qtd_servidores)
        self.assertEqual(self.plano.atividades_codigos, original_atividades)
        self.assertEqual(self.plano.diarias_valor_total, original_diarias_total)

    def test_autosave_invalid_payload_safe(self):
        response = self.client.post(
            self.url,
            data={
                'id': str(self.plano.pk),
                'destinos_payload': '{invalid-json',
                'coordenadores_ids': 'not,a,number',
                'evento_data_inicio': '2026-99-99',
                'evento_data_fim': 'bad-date',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))

        self.plano.refresh_from_db()
        self.assertIsInstance(self.plano.destinos_json, list)

    def test_autosave_id_empresa_usuario_context_if_available(self):
        ownership_fields = ('criado_por_id', 'usuario_id', 'owner_id', 'empresa_id')
        if any(hasattr(self.plano, field) for field in ownership_fields):
            self.fail('PlanoTrabalho tem campo de ownership e este teste precisa de regra explícita de autorização.')

        self.client.logout()
        response = self.client.post(self.url, data={'id': str(self.plano.pk)})
        self.assertEqual(response.status_code, 302)
