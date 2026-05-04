from django.shortcuts import render


def index(request):
    return render(
        request,
        "oficios/index.html",
        {
            "page_title": "Oficios",
            "page_description": "Documento principal do sistema, com vinculos opcionais a roteiro e evento.",
        },
    )
