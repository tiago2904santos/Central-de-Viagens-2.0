from django.contrib import admin
from .models import Oficio, Roteiro, PlanoTrabalho, OrdemServico, Justificativa, Termo


for model in [Oficio, Roteiro, PlanoTrabalho, OrdemServico, Justificativa, Termo]:
    admin.site.register(model)
