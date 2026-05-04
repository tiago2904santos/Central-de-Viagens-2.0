from django.shortcuts import render


def dashboard(request):
    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Central de Viagens 3",
            "page_description": "Base modular para gestao document-centric de viagens.",
        },
    )
