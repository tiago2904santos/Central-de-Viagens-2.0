from django.shortcuts import render


def index(request):
    return render(
        request,
        "termos/index.html",
        {
            "page_title": "Termos de Autorizacao",
            "page_description": "CRUD proprio para termos, com vinculo a Oficios quando aplicavel.",
        },
    )
