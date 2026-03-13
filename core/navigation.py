"""Configuracao central do menu lateral.

Estrutura obrigatoria: lista plana de itens. Apenas Documentos, Viajantes e
Veiculos possuem submenu. Demais itens sao links diretos.
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
    active_route_names=None,
    active_route_prefixes=None,
):
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
        'active_route_names': active_route_names or [],
        'active_route_prefixes': active_route_prefixes or [],
    }


def get_sidebar_config():
    """Retorna a lista plana de itens do menu, na ordem final.

    - Itens diretos: Central de documentos, Roteiros, Simulacao de diarias, Configuracoes.
    - Itens com submenu: Documentos, Viajantes, Veiculos.
    """
    return [
        # 1. Central de documentos (home)
        _item(
            'central-documentos',
            'Central de documentos',
            'bi bi-folder2-open',
            'eventos:documentos-hub',
            order=0,
            active_route_names=['eventos:documentos-hub'],
            active_route_prefixes=[],
        ),
        # 2. Roteiros
        _item(
            'roteiros',
            'Roteiros',
            'bi bi-signpost-2',
            'eventos:roteiros-global',
            order=2,
            active_route_names=['eventos:roteiros-global'],
            active_route_prefixes=['eventos:trecho-calcular-km', 'eventos:trechos-estimar', 'eventos:roteiro-avulso-'],
        ),
        # 3. Simulacao de diarias
        _item(
            'simulacao-diarias',
            'Simulacao de diarias',
            'bi bi-calculator',
            'eventos:simulacao-diarias',
            order=3,
            active_route_names=['eventos:simulacao-diarias'],
        ),
        # 4. Documentos (submenu)
        _item(
            'documentos',
            'Documentos',
            'bi bi-folder2-open',
            None,
            children=[
                _item(
                    'documentos-oficios',
                    'Ofícios',
                    'bi bi-file-earmark-text',
                    'eventos:oficios-global',
                    order=0,
                    active_route_names=['eventos:oficios-global'],
                    active_route_prefixes=['eventos:oficio-'],
                ),
                _item(
                    'documentos-plano-trabalho',
                    'Plano de trabalho',
                    'bi bi-clipboard2-check',
                    'eventos:documentos-planos-trabalho',
                    order=1,
                    active_route_names=['eventos:documentos-planos-trabalho'],
                ),
                _item(
                    'documentos-ordem-servico',
                    'Ordem de servico',
                    'bi bi-card-checklist',
                    'eventos:documentos-ordens-servico',
                    order=2,
                    active_route_names=['eventos:documentos-ordens-servico'],
                ),
                _item(
                    'documentos-justificativas',
                    'Justificativas',
                    'bi bi-journal-text',
                    'eventos:documentos-justificativas',
                    order=3,
                    active_route_names=['eventos:documentos-justificativas'],
                ),
                _item(
                    'documentos-termos',
                    'Termos',
                    'bi bi-file-check',
                    'eventos:documentos-termos',
                    order=4,
                    active_route_names=['eventos:documentos-termos'],
                ),
            ],
            order=4,
            active_route_prefixes=['eventos:documentos-', 'eventos:oficio-'],
        ),
        # 5. Viajantes (submenu)
        _item(
            'viajantes',
            'Viajantes',
            'bi bi-people',
            None,
            children=[
                _item(
                    'viajantes-lista',
                    'Lista de viajantes',
                    'bi bi-people',
                    'cadastros:viajante-lista',
                    order=0,
                    active_route_prefixes=['cadastros:viajante-'],
                ),
                _item(
                    'viajantes-cargos',
                    'Cargos',
                    'bi bi-person-badge',
                    'cadastros:cargo-lista',
                    order=1,
                    active_route_prefixes=['cadastros:cargo-'],
                ),
                _item(
                    'viajantes-unidades',
                    'Unidades',
                    'bi bi-buildings',
                    'cadastros:unidade-lotacao-lista',
                    order=2,
                    active_route_prefixes=['cadastros:unidade-lotacao-'],
                ),
            ],
            order=5,
            active_route_prefixes=['cadastros:viajante-', 'cadastros:cargo-', 'cadastros:unidade-lotacao-'],
        ),
        # 6. Veiculos (submenu)
        _item(
            'veiculos',
            'Veiculos',
            'bi bi-truck',
            None,
            children=[
                _item(
                    'veiculos-lista',
                    'Lista de veiculos',
                    'bi bi-truck',
                    'cadastros:veiculo-lista',
                    order=0,
                    active_route_prefixes=['cadastros:veiculo-'],
                ),
                _item(
                    'veiculos-gerenciamento',
                    'Gerenciamento de veiculos',
                    'bi bi-fuel-pump',
                    'cadastros:combustivel-lista',
                    order=1,
                    active_route_prefixes=['cadastros:combustivel-'],
                ),
            ],
            order=6,
            active_route_prefixes=['cadastros:veiculo-', 'cadastros:combustivel-'],
        ),
        # 7. Configuracoes do sistema
        _item(
            'configuracoes',
            'Configuracoes do sistema',
            'bi bi-gear',
            'cadastros:configuracoes',
            order=7,
            active_route_names=['cadastros:configuracoes'],
        ),
    ]


def _resolve_url(request, url_name, url_kwargs):
    if not url_name:
        return None
    try:
        return reverse(url_name, kwargs=url_kwargs)
    except Exception:
        return None


def _current_route_name(request):
    resolver = request.resolver_match
    if not resolver:
        return ''
    namespace = getattr(resolver, 'namespace', '') or ''
    url_name = getattr(resolver, 'url_name', '') or ''
    return f'{namespace}:{url_name}' if namespace else url_name


def _url_name_only(url_name):
    if not url_name:
        return ''
    return url_name.split(':')[-1] if ':' in url_name else url_name


def _is_active(request, item):
    resolver = request.resolver_match
    if not resolver:
        return False

    current_route_name = _current_route_name(request)
    active_route_names = item.get('active_route_names') or []
    active_route_prefixes = item.get('active_route_prefixes') or []

    if current_route_name in active_route_names:
        return True
    if any(current_route_name.startswith(prefix) for prefix in active_route_prefixes):
        return True

    if not item.get('enabled') or not item.get('url_name'):
        return False
    item_name = _url_name_only(item.get('url_name'))
    item_kwargs = item.get('url_kwargs') or {}
    return resolver.url_name == item_name and (resolver.kwargs or {}) == item_kwargs


def _build_menu_item(request, item):
    children = item.get('children')
    built_children = None
    if item.get('enabled') and children:
        built_children = []
        for child in sorted(children, key=lambda x: x.get('order', 0)):
            child_active = _is_active(request, child)
            built_children.append(
                {
                    'id': child.get('id'),
                    'label': child.get('label'),
                    'url': _resolve_url(request, child.get('url_name'), child.get('url_kwargs') or {}),
                    'active': child_active,
                    'enabled': child.get('enabled', True),
                    'visible': child.get('visible', True),
                    'badge': child.get('badge'),
                }
            )
    parent_url = _resolve_url(request, item.get('url_name'), item.get('url_kwargs') or {}) if item.get('enabled') and item.get('url_name') else None
    if built_children and not parent_url:
        parent_url = built_children[0].get('url') if built_children else None
    active = _is_active(request, item) or (bool(built_children) and any(c.get('active') for c in built_children))
    return {
        'id': item['id'],
        'label': item['label'],
        'icon': item.get('icon'),
        'url': parent_url,
        'active': active,
        'has_children': bool(built_children),
        'open': active,
        'enabled': item.get('enabled', True),
        'visible': item.get('visible', True),
        'badge': item.get('badge'),
        'children': built_children,
    }


def get_sidebar_menu(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'sidebar_menu': {'items': []}}

    items = []
    for item in sorted(get_sidebar_config(), key=lambda x: x.get('order', 0)):
        if not item.get('visible', True):
            continue
        items.append(_build_menu_item(request, item))
    return {'sidebar_menu': {'items': items}}
