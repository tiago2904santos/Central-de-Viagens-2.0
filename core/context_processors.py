from .navigation import build_navigation


def navigation(request):
    return {
        "navigation_items": build_navigation(request),
    }
