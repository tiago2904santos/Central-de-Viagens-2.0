from django.urls import path
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required
from .views import login_view, logout_view, em_breve_view

app_name = 'core'

urlpatterns = [
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', login_required(RedirectView.as_view(pattern_name='documentos:hub', permanent=False)), name='dashboard'),
    path('em-breve/', login_required(em_breve_view), name='em-breve'),
]
