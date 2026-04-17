from django.urls import reverse

from eventos.services.documento_vinculos import (
    resolver_vinculos_oficio,
    resolver_vinculos_ordem_servico,
    resolver_vinculos_plano_trabalho,
)


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


def build_oficio_vinculos_semanticos(oficio):
    resolved = resolver_vinculos_oficio(oficio)
    diretos = []
    herdados = []
    for vinculo in resolved.get('diretos') or []:
        diretos.append({'titulo': vinculo.rotulo, 'origem': 'direto'})
    for vinculo in resolved.get('herdados') or []:
        herdados.append({'titulo': vinculo.rotulo, 'origem': 'herdado'})
    return {'diretos': diretos, 'herdados': herdados}


def build_vinculo_documental_url(tipo, pk, *, oficio_pk=None):
    """URL canónica para itens devolvidos por `resolver_vinculos_*`."""
    if tipo == 'evento':
        return reverse('eventos:guiado-etapa-1', kwargs={'pk': pk})
    if tipo == 'oficio':
        return reverse('eventos:oficio-step1', kwargs={'pk': pk})
    if tipo == 'roteiro':
        return reverse('eventos:roteiro-avulso-editar', kwargs={'pk': pk})
    if tipo == 'ordem_servico':
        return reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': pk})
    if tipo == 'plano_trabalho':
        return reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': pk})
    if tipo == 'justificativa':
        if oficio_pk:
            return reverse('eventos:oficio-justificativa', kwargs={'pk': oficio_pk})
        return reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': pk})
    if tipo in {'termo', 'termo_autorizacao'}:
        return reverse('eventos:documentos-termos-detalhe', kwargs={'pk': pk})
    return ''


def build_evento_vinculo_url(tipo, pk, *, oficio_pk=None):
    """Alias retrocompatível; prefira `build_vinculo_documental_url`."""
    return build_vinculo_documental_url(tipo, pk, oficio_pk=oficio_pk)
