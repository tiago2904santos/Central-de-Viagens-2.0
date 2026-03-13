from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Oficio, Roteiro, PlanoTrabalho, OrdemServico, Justificativa, Termo


@login_required
def hub(request):
    return render(
        request,
        'documentos/hub.html',
        {
            'total_oficios': Oficio.objects.count(),
            'total_roteiros': Roteiro.objects.count(),
            'total_planos': PlanoTrabalho.objects.count(),
            'total_ordens': OrdemServico.objects.count(),
            'total_justificativas': Justificativa.objects.count(),
            'total_termos': Termo.objects.count(),
        },
    )


@login_required
def lista_oficios(request):
    return render(request, 'documentos/lista.html', {'titulo': 'Ofícios', 'itens': Oficio.objects.all()})


@login_required
def lista_roteiros(request):
    return render(request, 'documentos/lista.html', {'titulo': 'Roteiros', 'itens': Roteiro.objects.all()})


@login_required
def lista_planos(request):
    return render(request, 'documentos/lista.html', {'titulo': 'Planos de trabalho', 'itens': PlanoTrabalho.objects.all()})


@login_required
def lista_ordens(request):
    return render(request, 'documentos/lista.html', {'titulo': 'Ordens de serviço', 'itens': OrdemServico.objects.all()})


@login_required
def lista_justificativas(request):
    return render(request, 'documentos/lista.html', {'titulo': 'Justificativas', 'itens': Justificativa.objects.all()})


@login_required
def lista_termos(request):
    return render(request, 'documentos/lista.html', {'titulo': 'Termos', 'itens': Termo.objects.all()})
