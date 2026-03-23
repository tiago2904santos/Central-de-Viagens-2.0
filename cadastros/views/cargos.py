from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse

from ..models import Cargo
from ..forms import CargoForm


RETURN_URL_KEY = 'viajante_form_return_url'


@login_required
def cargo_lista(request):
    qs = Cargo.objects.all()
    q = request.GET.get('q', '').strip()
    order_by = (request.GET.get('order_by') or 'nome').strip().lower()
    order_dir = (request.GET.get('order_dir') or 'asc').strip().lower()
    order_by_map = {
        'nome': 'nome',
        'is_padrao': 'is_padrao',
        'id': 'id',
    }
    order_field = order_by_map.get(order_by, 'nome')
    order_dir = 'asc' if order_dir == 'asc' else 'desc'
    if order_dir == 'desc':
        order_field = f'-{order_field}'

    if q:
        qs = qs.filter(nome__icontains=q)
    qs = qs.order_by(order_field, 'nome')
    return_url = request.session.get(RETURN_URL_KEY)
    voltar_url = return_url or reverse('cadastros:viajante-lista')
    voltar_label = 'Voltar' if return_url else 'Voltar para viajantes'
    context = {
        'object_list': qs,
        'form_filter': {'q': q, 'order_by': order_by, 'order_dir': order_dir},
        'order_by_choices': [('nome', 'Nome'), ('is_padrao', 'Padrão'), ('id', 'Cadastro')],
        'order_dir_choices': [('asc', 'Crescente'), ('desc', 'Decrescente')],
        'return_url': return_url,
        'voltar_url': voltar_url,
        'voltar_label': voltar_label,
        'novo_cargo_url': reverse('cadastros:cargo-cadastrar'),
    }
    return render(request, 'cadastros/cargos/lista.html', context)


@login_required
def cargo_cadastrar(request):
    form = CargoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cargo cadastrado com sucesso.')
        return redirect('cadastros:cargo-lista')
    return render(request, 'cadastros/cargos/form.html', {'form': form, 'is_create': True})


@login_required
def cargo_editar(request, pk):
    obj = get_object_or_404(Cargo, pk=pk)
    form = CargoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cargo atualizado com sucesso.')
        return redirect('cadastros:cargo-lista')
    return render(request, 'cadastros/cargos/form.html', {'form': form, 'object': obj, 'is_create': False})


@login_required
def cargo_excluir(request, pk):
    obj = get_object_or_404(Cargo, pk=pk)
    if request.method == 'POST':
        if obj.viajantes.exists():
            messages.error(
                request,
                f'Não é possível excluir o cargo "{obj.nome}" pois está em uso por um ou mais viajantes.',
            )
            return redirect('cadastros:cargo-lista')
        nome = str(obj.nome)
        obj.delete()
        messages.success(request, f'Cargo "{nome}" excluído com sucesso.')
        return redirect('cadastros:cargo-lista')
    return render(request, 'cadastros/cargos/excluir_confirm.html', {'object': obj})


@login_required
def cargo_definir_padrao(request, pk):
    """POST: define este cargo como padrão e desmarca os demais."""
    if request.method != 'POST':
        return redirect('cadastros:cargo-lista')
    obj = get_object_or_404(Cargo, pk=pk)
    Cargo.objects.exclude(pk=pk).update(is_padrao=False)
    obj.is_padrao = True
    obj.save(update_fields=['is_padrao'])
    messages.success(request, f'Cargo "{obj.nome}" definido como padrão.')
    return redirect('cadastros:cargo-lista')
