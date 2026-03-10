from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def placeholder_view(request):
    return render(request, 'core/placeholder.html', {'modulo': 'Documentos'})
