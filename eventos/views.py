from django.shortcuts import render


def index(request):
    return render(
        request,
        "eventos/index.html",
        {
            "page_title": "Eventos",
            "page_description": "Agrupadores opcionais para organizar documentos relacionados.",
        },
    )
