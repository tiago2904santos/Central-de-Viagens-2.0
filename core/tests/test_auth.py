from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_login_page_renders(self):
        response = self.client.get(reverse('core:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Central de Viagens')
        self.assertContains(response, 'Usuário')
        self.assertContains(response, 'Senha')

    def test_login_redirects_authenticated_user_to_dashboard(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('core:login'))
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(reverse('core:login'), {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertRedirects(response, reverse('core:dashboard'))

    def test_login_invalid_credentials_shows_form(self):
        response = self.client.post(reverse('core:login'), {
            'username': 'testuser',
            'password': 'wrong',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário')
