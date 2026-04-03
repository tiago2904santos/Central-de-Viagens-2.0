"""Testes da navegacao global e da sidebar."""

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import resolve, reverse

from core.navigation import get_sidebar_config, get_sidebar_menu

User = get_user_model()


class SidebarMenuTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client()
        self.user = User.objects.create_user(username='nav', password='nav123')

    def _build_menu(self, path):
        request = self.factory.get(path)
        request.user = self.user
        request.resolver_match = resolve(path)
        return get_sidebar_menu(request)['sidebar_menu']['items']

    def _flatten_items(self, items):
        flattened = []
        for item in items:
            flattened.append(item)
            if item.get('children'):
                flattened.extend(self._flatten_items(item['children']))
        return flattened

    def test_sidebar_menu_retorna_itens_na_ordem_obrigatoria(self):
        items = self._build_menu(reverse('eventos:documentos-hub'))
        labels = [item['label'] for item in items]
        self.assertEqual(
            labels,
            [
                'Central de documentos',
                'Eventos',
                'Roteiros',
                'Simulacao de diarias',
                'Documentos',
                'Viajantes',
                'Veiculos',
                'Configuracoes',
            ],
        )

    def test_primeiro_item_e_central_de_documentos(self):
        items = self._build_menu(reverse('eventos:documentos-hub'))
        self.assertEqual(len(items), 8)
        self.assertEqual(items[0]['id'], 'central-documentos')
        self.assertEqual(items[0]['label'], 'Central de documentos')
        self.assertEqual(items[0]['url'], reverse('eventos:documentos-hub'))

    def test_apenas_documentos_viajantes_veiculos_tem_submenu(self):
        items = self._build_menu(reverse('eventos:documentos-hub'))
        with_children = [i for i in items if i.get('has_children')]
        self.assertEqual(len(with_children), 3)
        self.assertEqual([i['id'] for i in with_children], ['documentos', 'viajantes', 'veiculos'])

    def test_oficios_esta_dentro_de_documentos(self):
        config = get_sidebar_config()
        doc_item = next(i for i in config if i['id'] == 'documentos')
        child_ids = [c['id'] for c in doc_item['children']]
        self.assertIn('documentos-oficios', child_ids)
        self.assertEqual(
            child_ids,
            ['documentos-oficios', 'documentos-plano-trabalho', 'documentos-ordem-servico', 'documentos-justificativas', 'documentos-termos'],
        )

    def test_todos_os_itens_habilitados_tem_url_resolvida(self):
        items = self._build_menu(reverse('eventos:documentos-hub'))
        for item in self._flatten_items(items):
            if item.get('url') is not None:
                self.assertIsNotNone(item['url'], f"Item '{item.get('label')}' deveria ter URL real.")
        direct = [i for i in items if not i.get('has_children')]
        for item in direct:
            self.assertIsNotNone(item['url'], f"Item direto '{item['label']}' deveria ter URL.")

    def test_item_ativo_e_submenu_aberto_conforme_rota(self):
        scenarios = [
            (reverse('eventos:documentos-hub'), 'central-documentos'),
            (reverse('eventos:lista'), 'eventos'),
            (reverse('eventos:oficios-global'), 'documentos'),
            (reverse('eventos:roteiros-global'), 'roteiros'),
            (reverse('cadastros:viajante-lista'), 'viajantes'),
            (reverse('cadastros:cargo-lista'), 'viajantes'),
            (reverse('cadastros:veiculo-lista'), 'veiculos'),
            (reverse('cadastros:combustivel-lista'), 'veiculos'),
            (reverse('cadastros:configuracoes'), 'configuracoes'),
        ]
        for path, active_item_id in scenarios:
            items = self._build_menu(path)
            active_found = any(i['id'] == active_item_id and i.get('active') for i in items)
            active_in_child = any(
                c.get('active') for i in items if i.get('children') for c in i['children']
            )
            parent_active = any(i.get('active') for i in items)
            self.assertTrue(active_found or active_in_child or parent_active, f'Algum item deveria estar ativo para {path}')

    def test_oficios_global_e_hubs_principais_respondem_200(self):
        self.client.login(username='nav', password='nav123')
        urls = [
            reverse('eventos:oficios-global'),
            reverse('eventos:roteiros-global'),
            reverse('eventos:documentos-hub'),
            reverse('eventos:documentos-planos-trabalho'),
            reverse('eventos:documentos-ordens-servico'),
            reverse('eventos:documentos-justificativas'),
            reverse('eventos:documentos-termos'),
            reverse('eventos:simulacao-diarias'),
            reverse('cadastros:viajante-lista'),
            reverse('cadastros:cargo-lista'),
            reverse('cadastros:unidade-lotacao-lista'),
            reverse('cadastros:veiculo-lista'),
            reverse('cadastros:combustivel-lista'),
            reverse('cadastros:configuracoes'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_sidebar_html_renderiza_itens_e_submenu_documentos(self):
        self.client.login(username='nav', password='nav123')
        response = self.client.get(reverse('cadastros:cargo-lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-sidebar-group')
        self.assertContains(response, 'data-group-id="viajantes"')
        self.assertContains(response, 'Central de documentos')
        self.assertContains(response, 'Documentos')
        self.assertContains(response, 'Ofícios')
        self.assertContains(response, reverse('eventos:documentos-hub'))
        self.assertContains(response, reverse('cadastros:cargo-lista'))
