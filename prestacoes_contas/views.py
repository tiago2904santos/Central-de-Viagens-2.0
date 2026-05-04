from django.shortcuts import render


def index(request):
    return render(
        request,
        "prestacoes_contas/index.html",
        {
            "page_title": "Prestacoes de Contas",
            "page_description": "Fluxo futuro para despacho, RT, DB, comprovantes e resumo copiavel.",
        },
    )
