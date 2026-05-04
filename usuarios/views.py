from django.shortcuts import render


def index(request):
    return render(
        request,
        "usuarios/index.html",
        {
            "page_title": "Usuarios",
            "page_description": "Base futura para usuarios, perfis e permissoes.",
        },
    )
