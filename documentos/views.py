from django.shortcuts import render


def index(request):
    return render(
        request,
        "documentos/index.html",
        {
            "page_title": "Documentos",
            "page_description": "Infraestrutura generica para renderizacao, validacao e downloads.",
        },
    )
