from .navigation import NAVIGATION_ITEMS


def navigation(request):
    return {
        "navigation_items": NAVIGATION_ITEMS,
    }