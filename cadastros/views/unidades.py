from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse

from ..models import UnidadeLotacao
from ..forms import UnidadeLotacaoForm

RETURN_URL_KEY = 'viajante_form_return_url'


def _paginate(queryset, page, per_page=25):
    return Paginator(queryset, per_page).get_page(page)


def _query_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


@login_required
def unidade_lotacao_lista(request):
    qs = UnidadeLotacao.objects.all()
    q = request.GET.get('q', '').strip()
    order_by = (request.GET.get('order_by') or 'nome').strip().lower()
    order_dir = (request.GET.get('order_dir') or 'asc').strip().lower()
    order_by_map = {
        'nome': 'nome',
        'id': 'id',
    }
    order_field = order_by_map.get(order_by, 'nome')
    order_dir = 'asc' if order_dir == 'asc' else 'desc'
    if order_dir == 'desc':
        order_field = f'-{order_field}'

    if q:
        qs = qs.filter(nome__icontains=q)
    qs = qs.order_by(order_field, 'nome')
    page_obj = _paginate(qs, request.GET.get('page'))
    return_url = request.session.get(RETURN_URL_KEY)
    voltar_url = return_url or reverse('cadastros:viajante-lista')
    voltar_label = 'Voltar' if return_url else 'Voltar para viajantes'
    context = {
        'object_list': page_obj.object_list,
        'page_obj': page_obj,
        'pagination_query': _query_without_page(request),
        'form_filter': {'q': q, 'order_by': order_by, 'order_dir': order_dir},
        'order_by_choices': [('nome', 'Nome'), ('id', 'Cadastro')],
        'order_dir_choices': [('asc', 'Crescente'), ('desc', 'Decrescente')],
        'return_url': return_url,
        'voltar_url': voltar_url,
        'voltar_label': voltar_label,
        'nova_unidade_url': reverse('cadastros:unidade-lotacao-cadastrar'),
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
