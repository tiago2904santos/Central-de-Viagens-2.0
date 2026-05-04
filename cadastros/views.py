from django.shortcuts import render


def index(request):
    return render(
        request,
        "cadastros/index.html",
        {
            "page_title": "Cadastros",
            "page_section": "Dados-base",
            "page_description": "Base para servidores, motoristas, viaturas, cidades e unidades.",
        },
    )


def servidores_index(request):
    return render(request, "cadastros/servidores/index.html")


def motoristas_index(request):
    return render(request, "cadastros/motoristas/index.html")


def viaturas_index(request):
    return render(request, "cadastros/viaturas/index.html")


def cidades_index(request):
    return render(request, "cadastros/cidades/index.html")


def unidades_index(request):
    return render(request, "cadastros/unidades/index.html")
