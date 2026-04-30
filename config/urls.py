"""
URL principal do projeto Central de Viagens.
Rotas reais: admin, login/logout, dashboard, cadastros (configurações + API).
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.generic import RedirectView


def _chrome_devtools_well_known(_request):
    return HttpResponse('', status=204, content_type='application/json')

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.svg', permanent=False)),
    path('.well-known/appspecific/com.chrome.devtools.json', _chrome_devtools_well_known),
    path('admin/', admin.site.urls),
    path('cadastros/', include('cadastros.urls')),
    path('eventos/', include('eventos.urls')),
    path('assinaturas/', include('documentos.urls')),
    path('integracoes/', include('integracoes.urls')),
    path('prestacao-contas/', include('prestacao_contas.urls')),
    path('diarios-bordo/', include('diario_bordo.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
