from django.shortcuts import render


def index(request):
    return render(
        request,
        "assinaturas/index.html",
        {
            "page_title": "Assinaturas",
            "page_description": "Base futura para assinatura eletronica, carimbo visual e validacao de integridade.",
        },
    )
