from django.urls import reverse

from eventos.services.documento_vinculos import resolver_vinculos_ordem_servico, resolver_vinculos_plano_trabalho


def build_ordem_vinculos_semanticos(ordem):
    resolved = resolver_vinculos_ordem_servico(ordem)
    diretos = []
    herdados = []
    for vinculo in resolved.get('diretos') or []:
        diretos.append({'titulo': vinculo.rotulo, 'origem': 'direto'})
    for vinculo in resolved.get('herdados') or []:
        herdados.append({'titulo': vinculo.rotulo, 'origem': 'herdado'})
    return {'diretos': diretos, 'herdados': herdados}


def build_plano_vinculos_semanticos(plano):
    resolved = resolver_vinculos_plano_trabalho(plano)
    diretos = []
    herdados = []
    for vinculo in resolved.get('diretos') or []:
        diretos.append({'titulo': vinculo.rotulo, 'origem': 'direto'})
    for vinculo in resolved.get('herdados') or []:
        herdados.append({'titulo': vinculo.rotulo, 'origem': 'herdado'})
    return {'diretos': diretos, 'herdados': herdados}


def build_evento_vinculo_url(tipo, pk):
    if tipo == 'evento':
        return reverse('eventos:guiado-etapa-1', kwargs={'pk': pk})
    if tipo == 'oficio':
        return reverse('eventos:oficio-step1', kwargs={'pk': pk})
    if tipo == 'roteiro':
        return reverse('eventos:roteiro-avulso-editar', kwargs={'pk': pk})
    return ''
