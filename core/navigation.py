from copy import deepcopy

from django.urls import NoReverseMatch
from django.urls import reverse


NAVIGATION_ITEMS = [
    {"id": "dashboard", "label": "Dashboard", "url_name": "core:dashboard", "icon": "DG"},
    {
        "id": "cadastros",
        "label": "Cadastros",
        "url_name": "cadastros:index",
        "icon": "CD",
        "active_when": ["cadastros:"],
        "children": [
            {
                "id": "cadastros-servidores",
                "label": "Servidores",
                "url_name": "cadastros:servidores_index",
                "active_when": ["cadastros:servidor_", "cadastros:servidores_index"],
            },
            {
                "id": "cadastros-cargos",
                "label": "Cargos",
                "url_name": "cadastros:cargos_index",
                "active_when": ["cadastros:cargo_", "cadastros:cargos_index"],
            },
            {
                "id": "cadastros-viaturas",
                "label": "Viaturas",
                "url_name": "cadastros:viaturas_index",
                "active_when": ["cadastros:viatura_", "cadastros:viaturas_index"],
            },
            {
                "id": "cadastros-combustiveis",
                "label": "Combustíveis",
                "url_name": "cadastros:combustiveis_index",
                "active_when": [
                    "cadastros:combustivel_",
                    "cadastros:combustiveis_index",
                ],
            },
            {
                "id": "cadastros-unidades",
                "label": "Unidades",
                "url_name": "cadastros:unidades_index",
                "active_when": ["cadastros:unidade_", "cadastros:unidades_index"],
            },
            {
                "id": "cadastros-estados",
                "label": "Estados",
                "url_name": "cadastros:estados_index",
                "active_when": ["cadastros:estado_", "cadastros:estados_index"],
            },
            {
                "id": "cadastros-cidades",
                "label": "Cidades",
                "url_name": "cadastros:cidades_index",
                "active_when": ["cadastros:cidade_", "cadastros:cidades_index"],
            },
        ],
    },
    {"id": "roteiros", "label": "Roteiros", "url_name": "roteiros:index", "icon": "RT"},
    {"id": "eventos", "label": "Eventos", "url_name": "eventos:index", "icon": "EV"},
    {"id": "oficios", "label": "Ofícios", "url_name": "oficios:index", "icon": "OF"},
    {"id": "termos", "label": "Termos", "url_name": "termos:index", "icon": "TM"},
    {
        "id": "justificativas",
        "label": "Justificativas",
        "url_name": "justificativas:index",
        "icon": "JS",
    },
    {
        "id": "planos-trabalho",
        "label": "Planos de Trabalho",
        "url_name": "planos_trabalho:index",
        "icon": "PT",
    },
    {
        "id": "ordens-servico",
        "label": "Ordens de Serviço",
        "url_name": "ordens_servico:index",
        "icon": "OS",
    },
    {
        "id": "prestacoes-contas",
        "label": "Prestações de Contas",
        "url_name": "prestacoes_contas:index",
        "icon": "PC",
    },
    {
        "id": "diario-bordo",
        "label": "Diário de Bordo",
        "url_name": "diario_bordo:index",
        "icon": "DB",
    },
    {"id": "assinaturas", "label": "Assinaturas", "url_name": "assinaturas:index", "icon": "AS"},
]


def build_navigation(request):
    current_view_name = ""
    if request.resolver_match:
        current_view_name = request.resolver_match.view_name or ""

    return [_build_item(item, current_view_name) for item in NAVIGATION_ITEMS]


def _build_item(item, current_view_name):
    built_item = deepcopy(item)
    built_item["url"] = _resolve_url(built_item.get("url_name"))

    children = [_build_item(child, current_view_name) for child in built_item.get("children", [])]
    built_item["children"] = children

    is_active = _matches_current_view(built_item, current_view_name)
    has_active_child = any(child["is_active"] or child["is_open"] for child in children)

    built_item["is_current"] = is_active
    built_item["is_active"] = is_active or has_active_child
    built_item["is_open"] = has_active_child
    built_item["has_children"] = bool(children)
    built_item["children_id"] = f"sidebar-children-{built_item['id']}"

    return built_item


def _resolve_url(url_name):
    if not url_name:
        return "#"
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def _matches_current_view(item, current_view_name):
    url_name = item.get("url_name")
    if url_name and current_view_name == url_name:
        return True

    return any(current_view_name.startswith(prefix) for prefix in item.get("active_when", []))
