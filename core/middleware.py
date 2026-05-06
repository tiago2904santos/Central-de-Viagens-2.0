from urllib.parse import urlsplit

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.shortcuts import resolve_url


class AjaxAwareLoginRequiredMiddleware(LoginRequiredMiddleware):
    """
    Mantem o redirect normal para paginas, mas devolve JSON para fetch/AJAX.

    Sem isso, uma sessao expirada faz endpoints JSON retornarem a pagina de
    login em HTML, causando erro "Unexpected token '<'" no navegador.
    """

    redirect_field_name = REDIRECT_FIELD_NAME

    def handle_no_permission(self, request, view_func):
        if _expects_json(request):
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Sessao expirada. Faca login novamente para continuar.",
                    "login_url": resolve_url(self.get_login_url(view_func)),
                },
                status=401,
            )

        path = request.build_absolute_uri()
        resolved_login_url = resolve_url(self.get_login_url(view_func))
        login_scheme, login_netloc = urlsplit(resolved_login_url)[:2]
        current_scheme, current_netloc = urlsplit(path)[:2]
        if (not login_scheme or login_scheme == current_scheme) and (
            not login_netloc or login_netloc == current_netloc
        ):
            path = request.get_full_path()

        return redirect_to_login(
            path,
            resolved_login_url,
            self.get_redirect_field_name(view_func),
        )


def _expects_json(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return True
    return request.path.startswith("/roteiros/api/") or request.path.startswith("/roteiros/trechos/")
