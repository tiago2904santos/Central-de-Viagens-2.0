from django.shortcuts import render
from django.urls import reverse

from .presenters import apresentar_roteiro_card
from .selectors import listar_roteiros


def index(request):
    q = request.GET.get("q", "").strip()
    roteiros = listar_roteiros(q=q)
    cards = [apresentar_roteiro_card(roteiro) for roteiro in roteiros]
    return render(
        request,
        "roteiros/index.html",
        {
            "page_title": "Roteiros",
            "page_description": "Cadastre, consulte e reutilize trajetos oficiais nos documentos de viagem.",
            "create_url": reverse("admin:roteiros_roteiro_add"),
            "cards": cards,
            "q": q,
        },
    )
