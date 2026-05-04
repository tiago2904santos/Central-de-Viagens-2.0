from django.shortcuts import render


def index(request):
    return render(
        request,
        "integracoes/google_drive/index.html",
        {
            "page_title": "Google Drive",
            "page_description": "Base futura para OAuth e armazenamento de documentos no Drive.",
        },
    )
