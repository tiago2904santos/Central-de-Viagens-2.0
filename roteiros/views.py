from django.shortcuts import render


def index(request):
    return render(
        request,
        "roteiros/index.html",
        {
            "page_title": "Roteiros",
            "page_description": "Roteiros reutilizaveis, destinos e trechos para documentos de viagem.",
        },
    )
