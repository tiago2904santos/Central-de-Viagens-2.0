from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages

from ..models import UnidadeLotacao
from ..forms import UnidadeLotacaoForm

RETURN_URL_KEY = 'viajante_form_return_url'


@login_required
def unidade_lotacao_lista(request):
    qs = UnidadeLotacao.objects.all().order_by('nome')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(nome__icontains=q)
    return_url = request.session.get(RETURN_URL_KEY)
    context = {
        'object_list': qs,
        'form_filter': {'q': q},
        'return_url': return_url,
    }
    return render(request, 'cadastros/unidades/lista.html', context)


@login_required
def unidade_lotacao_cadastrar(request):
    form = UnidadeLotacaoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Unidade de lotação cadastrada com sucesso.')
        return redirect('cadastros:unidade-lotacao-lista')
    return render(request, 'cadastros/unidades/form.html', {'form': form, 'is_create': True})


@login_required
def unidade_lotacao_editar(request, pk):
    obj = get_object_or_404(UnidadeLotacao, pk=pk)
    form = UnidadeLotacaoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Unidade de lotação atualizada com sucesso.')
        return redirect('cadastros:unidade-lotacao-lista')
    return render(request, 'cadastros/unidades/form.html', {'form': form, 'object': obj, 'is_create': False})


@login_required
def unidade_lotacao_excluir(request, pk):
    obj = get_object_or_404(UnidadeLotacao, pk=pk)
    if request.method == 'POST':
        if obj.viajantes.exists():
            messages.error(
                request,
                f'Não é possível excluir a unidade "{obj.nome}" pois está em uso por um ou mais viajantes.',
            )
            return redirect('cadastros:unidade-lotacao-lista')
        nome = str(obj.nome)
        obj.delete()
        messages.success(request, f'Unidade "{nome}" excluída com sucesso.')
        return redirect('cadastros:unidade-lotacao-lista')
    return render(request, 'cadastros/unidades/excluir_confirm.html', {'object': obj})
