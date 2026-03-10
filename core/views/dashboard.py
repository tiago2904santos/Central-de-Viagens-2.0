from django.shortcuts import render

from eventos.models import Evento


def dashboard_view(request):
    context = {
        'total_eventos': Evento.objects.count(),
        'total_oficios': 0,
        'total_termos': 0,
        'total_pendencias': 0,
    }
    return render(request, 'core/dashboard.html', context)
