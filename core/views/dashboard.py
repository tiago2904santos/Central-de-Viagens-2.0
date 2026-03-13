from django.shortcuts import render

from eventos.models import Oficio
from eventos.views import _build_oficio_justificativa_info


def dashboard_view(request):
    oficios = list(Oficio.objects.prefetch_related('trechos').all())
    justificativas_pendentes = sum(
        1 for oficio in oficios if _build_oficio_justificativa_info(oficio)['status_key'] == 'pendente'
    )
    context = {
        'total_eventos': 0,
        'total_oficios': len(oficios),
        'total_termos': 0,
        'total_pendencias': justificativas_pendentes,
    }
    return render(request, 'core/dashboard.html', context)
