from django.shortcuts import render


def index(request):
    return render(
        request,
        "ordens_servico/index.html",
        {
            "page_title": "Ordens de Servico",
            "page_description": "CRUD proprio para ordens de servico e seus vinculos documentais.",
        },
    )
