import unicodedata
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse

from ..models import ConfiguracaoSistema, Estado, Cidade, AssinaturaConfiguracao
from ..forms import ConfiguracaoSistemaForm


def _normalize_for_match(s):
    """Normaliza string para comparação case-insensitive e tolerante a acentos."""
    if not s:
        return ''
    s = (s or '').strip().lower()
    nfd = unicodedata.normalize('NFD', s)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def _resolve_cidade_sede_from_endereco(uf, cidade_endereco):
    """
    Busca Estado por sigla == uf e Cidade por estado + nome (case-insensitive, tolerante a acentos).
    Retorna Cidade ou None.
    """
    uf = (uf or '').strip().upper()
    cidade_nome = (cidade_endereco or '').strip()
    if not uf or not cidade_nome:
        return None
    try:
        estado = Estado.objects.get(sigla=uf, ativo=True)
    except Estado.DoesNotExist:
        return None
    alvo = _normalize_for_match(cidade_nome)
    for cidade in Cidade.objects.filter(estado=estado, ativo=True):
        if _normalize_for_match(cidade.nome) == alvo:
            return cidade
    return None


@login_required
def configuracoes_editar(request):
    obj = ConfiguracaoSistema.get_singleton()
    form = ConfiguracaoSistemaForm(request.POST or None, instance=obj)

    if form.is_valid():
        form.save()
        obj = ConfiguracaoSistema.get_singleton()
        uf = (form.cleaned_data.get('uf') or '').strip().upper()
        cidade_endereco = (form.cleaned_data.get('cidade_endereco') or '').strip()
        cidade_sede = _resolve_cidade_sede_from_endereco(uf, cidade_endereco)
        if cidade_sede:
            obj.cidade_sede_padrao = cidade_sede
            obj.save(update_fields=['cidade_sede_padrao'])
        else:
            if uf or cidade_endereco:
                obj.cidade_sede_padrao = None
                obj.save(update_fields=['cidade_sede_padrao'])
                messages.warning(
                    request,
                    'Base geográfica não importada ou cidade não encontrada; cidade sede padrão não foi definida.',
                )
        # Upsert assinaturas (ordem=1 por tipo)
        mapeamento = [
            ('assinatura_oficio', AssinaturaConfiguracao.TIPO_OFICIO),
            ('assinatura_justificativas', AssinaturaConfiguracao.TIPO_JUSTIFICATIVA),
            ('assinatura_planos_trabalho', AssinaturaConfiguracao.TIPO_PLANO_TRABALHO),
            ('assinatura_ordens_servico', AssinaturaConfiguracao.TIPO_ORDEM_SERVICO),
        ]
        for field_name, tipo in mapeamento:
            v = form.cleaned_data.get(field_name)
            AssinaturaConfiguracao.objects.update_or_create(
                configuracao=obj,
                tipo=tipo,
                ordem=1,
                defaults={'viajante': v, 'ativo': bool(v)},
            )
        messages.success(request, 'Configurações salvas com sucesso.')
        return redirect('cadastros:configuracoes')

    context = {
        'form': form,
        'object': obj,
        'api_consulta_cep_url': reverse('cadastros:api-consulta-cep', kwargs={'cep': '00000000'}),
    }
    return render(request, 'cadastros/configuracao_form.html', context)
