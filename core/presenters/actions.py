def build_action(label, url, variant="secondary", method="get", icon=None):
    if not url:
        return None
    if url in {"#", "javascript:void(0)", "javascript:void(0);"}:
        return None
    payload = {
        "label": label,
        "href": url,
        "variant": variant,
        "method": method.lower(),
    }
    if icon:
        payload["icon"] = icon
    return payload


def build_open_action(url):
    return build_action("Abrir", url, variant="secondary")


def build_edit_action(url):
    return build_action("Editar", url, variant="secondary")


def build_delete_action(url):
    return build_action("Excluir", url, variant="danger", method="post")


def build_post_action(label, url, variant="secondary"):
    return build_action(label, url, variant=variant, method="post")
