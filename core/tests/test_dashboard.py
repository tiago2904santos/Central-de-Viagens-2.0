from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('core:dashboard'))
        self.assertRedirects(response, f"{reverse('core:login')}?next={reverse('core:dashboard')}")

    def test_dashboard_renders_when_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Painel')
        self.assertContains(response, 'Eventos')
        self.assertContains(response, 'Ofícios')
        self.assertContains(response, 'Termos')
        self.assertContains(response, 'Pendências')
