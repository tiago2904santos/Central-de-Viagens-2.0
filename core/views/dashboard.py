from django.shortcuts import render

from documentos.models import Oficio, TermoAutorizacao


def dashboard_view(request):
    context = {
        'total_oficios': Oficio.objects.count(),
        'total_termos': TermoAutorizacao.objects.count(),
        'total_pendencias': 0,
    }
    return render(request, 'core/dashboard.html', context)
