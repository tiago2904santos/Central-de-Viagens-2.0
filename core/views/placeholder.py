from django.shortcuts import render


def em_breve_view(request):
    """Página única 'Em breve' para módulos não implementados (uso interno)."""
    return render(request, 'core/em_breve.html', {})
