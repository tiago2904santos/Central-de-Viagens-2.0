from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class EmBreveViewTests(TestCase):
    """Página única 'Em breve' para módulos não implementados."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_em_breve_requires_login(self):
        response = self.client.get(reverse('core:em-breve'))
        self.assertRedirects(response, f"{reverse('core:login')}?next={reverse('core:em-breve')}")

    def test_em_breve_accessible_when_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('core:em-breve'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Em breve')
