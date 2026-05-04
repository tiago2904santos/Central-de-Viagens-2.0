from django.shortcuts import render


def index(request):
    return render(
        request,
        "diario_bordo/index.html",
        {
            "page_title": "Diario de Bordo",
            "page_description": "Base futura para geracao de diario de bordo a partir de modelo XLSX.",
        },
    )
