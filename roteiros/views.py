from django.shortcuts import render

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
            "page_description": "Cadastre e reutilize roteiros de deslocamento para documentos e fluxos da Central de Viagens.",
            "cards": cards,
            "q": q,
        },
    )
