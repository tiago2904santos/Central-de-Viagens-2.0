from django.shortcuts import render

from django.contrib.auth.views import LoginView as DjangoLoginView

from .forms import LoginForm


class LoginView(DjangoLoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True
    authentication_form = LoginForm


def dashboard(request):
    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Central de Viagens 3",
            "page_section": "Dashboard",
            "page_description": "Fundacao visual para os fluxos documentais do sistema.",
        },
    )
