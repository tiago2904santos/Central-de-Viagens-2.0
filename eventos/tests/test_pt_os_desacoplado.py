from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from eventos.models import Evento, Oficio, OrdemServico, PlanoTrabalho


User = get_user_model()


class PtOsDesacopladoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='ptos', password='ptos123')
        self.client.login(username='ptos', password='ptos123')

        self.evento = Evento.objects.create(
            titulo='Evento PT/OS',
            data_inicio=date(2026, 3, 10),
            data_fim=date(2026, 3, 12),
            status=Evento.STATUS_EM_ANDAMENTO,
        )
        self.oficio = Oficio.objects.create(
            evento=self.evento,
            protocolo='123456789',
            data_criacao=date(2026, 3, 1),
            status=Oficio.STATUS_RASCUNHO,
        )

    def test_criar_pt_sem_evento(self):
        response = self.client.post(
            reverse('eventos:documentos-planos-trabalho-novo'),
            data={
                'numero': '1',
                'ano': '2026',
                'data_criacao': '2026-03-10',
                'status': PlanoTrabalho.STATUS_RASCUNHO,
                'objetivo': 'PT sem evento',
                'return_to': reverse('eventos:documentos-planos-trabalho'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlanoTrabalho.objects.filter(objetivo='PT sem evento', evento__isnull=True).exists())

    def test_criar_pt_sem_oficio(self):
        response = self.client.post(
            reverse('eventos:documentos-planos-trabalho-novo'),
            data={
                'numero': '2',
                'ano': '2026',
                'data_criacao': '2026-03-10',
                'status': PlanoTrabalho.STATUS_RASCUNHO,
                'evento': self.evento.pk,
                'objetivo': 'PT sem oficio',
                'return_to': reverse('eventos:documentos-planos-trabalho'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PlanoTrabalho.objects.filter(
                objetivo='PT sem oficio',
                evento=self.evento,
                oficio__isnull=True,
            ).exists()
        )

    def test_criar_os_sem_evento(self):
        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'numero': '10',
                'ano': '2026',
                'data_criacao': '2026-03-10',
                'status': OrdemServico.STATUS_RASCUNHO,
                'finalidade': 'OS sem evento',
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OrdemServico.objects.filter(finalidade='OS sem evento', evento__isnull=True).exists())

    def test_criar_os_sem_oficio(self):
        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'numero': '11',
                'ano': '2026',
                'data_criacao': '2026-03-10',
                'status': OrdemServico.STATUS_RASCUNHO,
                'evento': self.evento.pk,
                'finalidade': 'OS sem oficio',
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            OrdemServico.objects.filter(
                finalidade='OS sem oficio',
                evento=self.evento,
                oficio__isnull=True,
            ).exists()
        )

    def test_preselected_event_id_pt(self):
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-novo'),
            {'preselected_event_id': self.evento.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('evento'), self.evento.pk)

    def test_preselected_event_id_os(self):
        response = self.client.get(
            reverse('eventos:documentos-ordens-servico-novo'),
            {'preselected_event_id': self.evento.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('evento'), self.evento.pk)

    def test_preselected_oficio_id_pt(self):
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-novo'),
            {'preselected_oficio_id': self.oficio.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('oficio'), self.oficio.pk)

    def test_preselected_oficio_id_os(self):
        response = self.client.get(
            reverse('eventos:documentos-ordens-servico-novo'),
            {'preselected_oficio_id': self.oficio.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('oficio'), self.oficio.pk)

    def test_etapa4_guiado_abre_cadastro_real_pt(self):
        response = self.client.get(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('eventos:documentos-planos-trabalho-novo'))

    def test_etapa4_guiado_abre_cadastro_real_os(self):
        response = self.client.get(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('eventos:documentos-ordens-servico-novo'))

    def test_download_pt_usa_model_quando_sem_oficio(self):
        pt = PlanoTrabalho.objects.create(objetivo='PT download', status=PlanoTrabalho.STATUS_RASCUNHO)
        with patch('eventos.views_global.render_plano_trabalho_model_docx', return_value=b'docx') as mock_model:
            with patch('eventos.views_global.render_plano_trabalho_docx', return_value=b'oficio-docx') as mock_oficio:
                response = self.client.get(
                    reverse('eventos:documentos-planos-trabalho-download', kwargs={'pk': pt.pk, 'formato': 'docx'})
                )
        self.assertEqual(response.status_code, 200)
        mock_model.assert_called_once()
        mock_oficio.assert_not_called()

    def test_download_os_usa_model_quando_sem_oficio(self):
        os_obj = OrdemServico.objects.create(finalidade='OS download', status=OrdemServico.STATUS_RASCUNHO)
        with patch('eventos.views_global.render_ordem_servico_model_docx', return_value=b'docx') as mock_model:
            with patch('eventos.views_global.render_ordem_servico_docx', return_value=b'oficio-docx') as mock_oficio:
                response = self.client.get(
                    reverse('eventos:documentos-ordens-servico-download', kwargs={'pk': os_obj.pk, 'formato': 'docx'})
                )
        self.assertEqual(response.status_code, 200)
        mock_model.assert_called_once()
        mock_oficio.assert_not_called()

    def test_model_legado_nao_existe_mais(self):
        import eventos.models as eventos_models

        legacy_name = 'Evento' + 'Fundamentacao'
        self.assertFalse(hasattr(eventos_models, legacy_name))
