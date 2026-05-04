from django.shortcuts import render


def index(request):
    return render(
        request,
        "planos_trabalho/index.html",
        {
            "page_title": "Planos de Trabalho",
            "page_description": "Fluxo proprio para planos, etapas e calculos futuros de diarias.",
        },
    )
