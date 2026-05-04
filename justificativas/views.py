from django.shortcuts import render


def index(request):
    return render(
        request,
        "justificativas/index.html",
        {
            "page_title": "Justificativas",
            "page_description": "CRUD proprio para justificativas e vinculos documentais quando fizer sentido.",
        },
    )
