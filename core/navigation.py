from django.urls import reverse


def _item(id_, label, icon, url_name=None, children=None, order=0, active_route_prefixes=None):
    return {
        'id': id_, 'label': label, 'icon': icon, 'url_name': url_name,
        'children': children, 'order': order, 'active_route_prefixes': active_route_prefixes or [],
    }


def get_sidebar_config():
    return [
        _item('central-documentos', 'Central de documentos', 'bi bi-folder2-open', 'documentos:hub', order=0, active_route_prefixes=['documentos:hub']),
        _item(
            'oficios', 'Ofícios', 'bi bi-file-earmark-text', 'documentos:oficios', order=1,
            active_route_prefixes=['documentos:oficio'],
        ),
        _item('roteiros', 'Roteiros', 'bi bi-signpost-2', 'documentos:roteiros', order=2, active_route_prefixes=['documentos:roteiro']),
        _item(
            'documentos', 'Documentos', 'bi bi-folder2-open', None, order=3,
            children=[
                _item('documentos-plano-trabalho', 'Planos de trabalho', 'bi bi-clipboard2-check', 'documentos:planos-trabalho', order=0),
                _item('documentos-ordem-servico', 'Ordens de serviço', 'bi bi-card-checklist', 'documentos:ordens-servico', order=1),
                _item('documentos-justificativas', 'Justificativas', 'bi bi-journal-text', 'documentos:justificativas', order=2),
                _item('documentos-termos', 'Termos', 'bi bi-file-check', 'documentos:termos', order=3),
            ],
            active_route_prefixes=['documentos:plano', 'documentos:ordem', 'documentos:justificativa', 'documentos:termo'],
        ),
        _item('eventos', 'Eventos', 'bi bi-calendar-event', 'documentos:eventos', order=4, active_route_prefixes=['documentos:evento']),
        _item('viajantes', 'Viajantes', 'bi bi-people', 'cadastros:viajante-lista', order=5, active_route_prefixes=['cadastros:viajante-']),
        _item('veiculos', 'Veículos', 'bi bi-truck', 'cadastros:veiculo-lista', order=6, active_route_prefixes=['cadastros:veiculo-']),
        _item('configuracoes', 'Configurações do sistema', 'bi bi-gear', 'cadastros:configuracoes', order=7, active_route_prefixes=['cadastros:configuracoes']),
    ]


def _resolve_url(request, url_name):
    if not url_name:
        return None
    try:
        return reverse(url_name)
    except Exception:
        return None


def _current_route_name(request):
    resolver = request.resolver_match
    if not resolver:
        return ''
    namespace = getattr(resolver, 'namespace', '') or ''
    url_name = getattr(resolver, 'url_name', '') or ''
    return f'{namespace}:{url_name}' if namespace else url_name


def _build_menu_item(request, item):
    current = _current_route_name(request)
    active = any(current.startswith(prefix) for prefix in item.get('active_route_prefixes') or [])
    children = item.get('children')
    built_children = None
    if children:
        built_children = []
        for child in sorted(children, key=lambda x: x.get('order', 0)):
            cactive = any(current.startswith(prefix) for prefix in child.get('active_route_prefixes') or []) or current == child.get('url_name')
            active = active or cactive
            built_children.append({'id': child['id'], 'label': child['label'], 'url': _resolve_url(request, child.get('url_name')), 'active': cactive})
    return {'id': item['id'], 'label': item['label'], 'icon': item['icon'], 'url': _resolve_url(request, item.get('url_name')), 'active': active or current == item.get('url_name'), 'has_children': bool(children), 'children': built_children}


def get_sidebar_menu(request):
    items = [_build_menu_item(request, i) for i in sorted(get_sidebar_config(), key=lambda x: x.get('order', 0))]
    return {'sidebar_menu': {'items': items}}
