"""
Configuração central da sidebar (menu lateral).
Menu honesto: apenas itens implementados têm link; demais desabilitados com "Em breve".
"""
from django.urls import reverse


def _item(
    id_,
    label,
    icon,
    url_name=None,
    url_kwargs=None,
    children=None,
    order=0,
    enabled=True,
    visible=True,
    badge=None,
):
    """Helper para definir um item de menu."""
    return {
        'id': id_,
        'label': label,
        'icon': icon,
        'url_name': url_name,
        'url_kwargs': url_kwargs or {},
        'children': children,
        'order': order,
        'enabled': enabled,
        'visible': visible,
        'badge': badge,
    }


def get_sidebar_config():
    """
    Retorna a estrutura bruta do menu.
    Apenas Painel e Configurações estão habilitados com URL; demais enabled=False e badge "Em breve".
    Submenus não são exibidos para itens não implementados.
    """
    return [
        {
            'id': 'main',
            'items': [
                _item('dashboard', 'Painel', 'bi bi-grid-1x2-fill', 'core:dashboard', order=0, enabled=True),
                _item('simulacao-diarias', 'Simulação de Diárias', 'bi bi-calculator', order=1, enabled=False, badge='Em breve'),
                _item('eventos', 'Eventos', 'bi bi-calendar-event', 'eventos:lista', order=2, enabled=True),
                _item('roteiros', 'Roteiros', 'bi bi-signpost-2', order=3, enabled=False, badge='Em breve'),
                _item('oficios', 'Ofícios', 'bi bi-file-earmark-text', order=4, enabled=False, badge='Em breve'),
                _item('planos-trabalho', 'Planos de Trabalho', 'bi bi-clipboard2-check', order=5, enabled=False, badge='Em breve'),
                _item('ordens-servico', 'Ordens de Serviço', 'bi bi-card-checklist', order=6, enabled=False, badge='Em breve'),
                _item('justificativas', 'Justificativas', 'bi bi-journal-text', order=7, enabled=False, badge='Em breve'),
                _item('termos', 'Termos de Autorização', 'bi bi-file-check', order=8, enabled=False, badge='Em breve'),
            ],
        },
        {
            'id': 'cadastros',
            'items': [
                _item(
                    'viajantes', 'Viajantes', 'bi bi-people', 'cadastros:viajante-lista', order=0, enabled=True,
                    children=[
                        _item('viajante-lista', 'Lista', 'bi bi-list-ul', 'cadastros:viajante-lista', order=0),
                        _item('viajante-cadastrar', 'Cadastrar', 'bi bi-plus-lg', 'cadastros:viajante-cadastrar', order=1),
                    ],
                ),
                _item(
                    'veiculos', 'Veículos', 'bi bi-truck', 'cadastros:veiculo-lista', order=2, enabled=True,
                    children=[
                        _item('veiculo-lista', 'Lista', 'bi bi-list-ul', 'cadastros:veiculo-lista', order=0),
                        _item('veiculo-cadastrar', 'Cadastrar', 'bi bi-plus-lg', 'cadastros:veiculo-cadastrar', order=1),
                    ],
                ),
                _item('configuracoes', 'Configurações', 'bi bi-gear', 'cadastros:configuracoes', order=3, enabled=True),
            ],
        },
    ]


def _resolve_url(request, url_name, url_kwargs):
    if not url_name:
        return None
    try:
        return reverse(url_name, kwargs=url_kwargs)
    except Exception:
        return None


def _url_name_only(url_name):
    if not url_name:
        return ''
    return url_name.split(':')[-1] if ':' in url_name else url_name


def _is_active(request, item):
    if not item.get('enabled') or not item.get('url_name'):
        return False
    resolver = request.resolver_match
    if not resolver:
        return False
    item_name = _url_name_only(item.get('url_name'))
    item_kwargs = item.get('url_kwargs') or {}
    return resolver.url_name == item_name and (resolver.kwargs or {}) == item_kwargs


def _build_menu_item(request, item):
    """Constrói item para o template: url, active, enabled, badge. Se enabled e tem children, monta children com url/active."""
    children = item.get('children')
    built_children = None
    if item.get('enabled') and children:
        built_children = []
        for ch in sorted(children, key=lambda x: x.get('order', 0)):
            built_children.append({
                'id': ch.get('id'),
                'label': ch.get('label'),
                'url': _resolve_url(request, ch.get('url_name'), ch.get('url_kwargs') or {}),
                'active': _is_active(request, ch),
            })
    parent_url = _resolve_url(request, item.get('url_name'), item.get('url_kwargs') or {}) if item.get('enabled') else None
    if built_children and not parent_url:
        parent_url = built_children[0].get('url')
    active = _is_active(request, item) or (bool(built_children) and any(c.get('active') for c in built_children))
    built = {
        'id': item['id'],
        'label': item['label'],
        'icon': item.get('icon'),
        'url': parent_url,
        'active': active,
        'enabled': item.get('enabled', True),
        'visible': item.get('visible', True),
        'badge': item.get('badge'),
        'children': built_children,
    }
    return built


def get_sidebar_menu(request):
    """Retorna o menu para o template. Itens desabilitados não têm URL nem submenus."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'sidebar_menu': {'groups': []}}

    config = get_sidebar_config()
    groups = []
    for group in config:
        items = []
        for item in sorted(group['items'], key=lambda x: x.get('order', 0)):
            if not item.get('visible', True):
                continue
            items.append(_build_menu_item(request, item))
        groups.append({'id': group['id'], 'items': items})
    return {'sidebar_menu': {'groups': groups}}
