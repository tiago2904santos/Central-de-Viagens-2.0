from django.shortcuts import render


def index(request):
    return render(
        request,
        "cadastros/index.html",
        {
            "page_title": "Cadastros",
            "page_description": "Dados-base reutilizaveis: servidores, motoristas, viaturas, cidades e unidades.",
        },
    )
