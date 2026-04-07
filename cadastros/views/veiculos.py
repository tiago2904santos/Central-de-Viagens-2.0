from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from ..models import Veiculo, CombustivelVeiculo
from ..forms import VeiculoForm, CombustivelVeiculoForm
from core.utils.masks import _normalizar_placa

RETURN_URL_KEY = 'veiculo_form_return_url'


def _paginate(queryset, page, per_page=25):
    return Paginator(queryset, per_page).get_page(page)


def _query_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def _next_url_safe(request):
    nxt = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if not nxt:
        return ''
    if url_has_allowed_host_and_scheme(
        url=nxt,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return nxt
    return ''


def _build_veiculo_return_url(request, pk):
    """URL de retorno para edição do veículo, preservando next quando existir."""
    path = reverse('cadastros:veiculo-editar', kwargs={'pk': pk})
    next_url = _next_url_safe(request)
    if next_url:
        query = urlencode({'next': next_url})
        path = f'{path}?{query}'
    return request.build_absolute_uri(path)


def _placa_valida(norm):
    if not norm or len(norm) != 7:
        return False
    import re
    return bool(re.match(r'^[A-Z]{3}[0-9]{4}$', norm) or re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', norm))


@login_required
def veiculo_lista(request):
    qs = Veiculo.objects.select_related('combustivel').all()
    q = request.GET.get('q', '').strip()
    order_by = (request.GET.get('order_by') or 'updated_at').strip().lower()
    order_dir = (request.GET.get('order_dir') or 'desc').strip().lower()
    order_by_map = {
        'updated_at': 'updated_at',
        'placa': 'placa',
        'modelo': 'modelo',
        'status': 'status',
    }
    order_field = order_by_map.get(order_by, 'updated_at')
    order_dir = 'asc' if order_dir == 'asc' else 'desc'
    if order_dir == 'desc':
        order_field = f'-{order_field}'

    if q:
        qs = qs.filter(
            Q(placa__icontains=q) | Q(modelo__icontains=q) |
            Q(combustivel__nome__icontains=q) | Q(tipo__icontains=q) | Q(status__icontains=q)
        )
    qs = qs.order_by('-status', order_field, '-updated_at')
    page_obj = _paginate(qs, request.GET.get('page'))
    object_list = list(page_obj.object_list)
    for obj in object_list:
        obj.placa_display = obj.placa_formatada
        obj.status_display = obj.get_status_display()
    context = {
        'object_list': object_list,
        'page_obj': page_obj,
        'pagination_query': _query_without_page(request),
        'form_filter': {'q': q, 'order_by': order_by, 'order_dir': order_dir},
        'order_by_choices': [
            ('updated_at', 'Atualização'),
            ('placa', 'Placa'),
            ('modelo', 'Modelo'),
            ('status', 'Status'),
        ],
        'order_dir_choices': [('desc', 'Decrescente'), ('asc', 'Crescente')],
        'combustiveis_url': reverse('cadastros:combustivel-lista'),
        'novo_veiculo_url': reverse('cadastros:veiculo-cadastrar'),
    }
    return render(request, 'cadastros/veiculos/lista.html', context)


@login_required
def veiculo_salvar_rascunho_ir_combustiveis(request):
    """POST: cria ou atualiza veículo como RASCUNHO e redireciona para lista de combustíveis."""
    if request.method != 'POST':
        return redirect('cadastros:veiculo-lista')
    veiculo_id = request.POST.get('veiculo_id', '').strip()
    if veiculo_id and veiculo_id.isdigit():
        obj = get_object_or_404(Veiculo, pk=int(veiculo_id))
        placa_raw = (request.POST.get('placa') or '').strip()
        placa_norm = _normalizar_placa(placa_raw) if placa_raw else ''
        if placa_norm and _placa_valida(placa_norm):
            outros = Veiculo.objects.filter(placa=placa_norm).exclude(pk=obj.pk)
            if not outros.exists():
                obj.placa = placa_norm
        modelo = (request.POST.get('modelo') or '').strip()
        if modelo:
            obj.modelo = ' '.join(modelo.upper().split())
        obj.combustivel_id = request.POST.get('combustivel') or None
        obj.tipo = request.POST.get('tipo') or Veiculo.TIPO_DESCARACTERIZADO
        obj.status = Veiculo.STATUS_RASCUNHO
        obj.save()
        pk = obj.pk
    else:
        placa_raw = (request.POST.get('placa') or '').strip()
        placa_norm = _normalizar_placa(placa_raw) if placa_raw else ''
        if placa_norm and _placa_valida(placa_norm):
            if Veiculo.objects.filter(placa=placa_norm).exists():
                placa_norm = ''
        modelo = (request.POST.get('modelo') or '').strip()
        if modelo:
            modelo = ' '.join(modelo.upper().split())
        combustivel_id = request.POST.get('combustivel') or None
        tipo = request.POST.get('tipo') or Veiculo.TIPO_DESCARACTERIZADO
        obj = Veiculo.objects.create(
            placa=placa_norm or '',
            modelo=modelo or '',
            combustivel_id=combustivel_id,
            tipo=tipo,
            status=Veiculo.STATUS_RASCUNHO,
        )
        pk = obj.pk
    request.session[RETURN_URL_KEY] = _build_veiculo_return_url(request, pk)
    request.session.modified = True
    messages.info(request, 'Rascunho salvo. Ao voltar, continue editando o mesmo veículo.')
    return redirect('cadastros:combustivel-lista')


@login_required
def _legacy_veiculo_cadastrar(request):
    if request.method == 'GET':
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
    form = VeiculoForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.status = Veiculo.STATUS_FINALIZADO if obj.esta_completo() else Veiculo.STATUS_RASCUNHO
        obj.save()
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
        messages.success(request, 'Veículo cadastrado com sucesso.')
        return redirect('cadastros:veiculo-lista')
    return_url = request.build_absolute_uri()
    return render(request, 'cadastros/veiculos/form.html', {
        'form': form, 'is_create': True, 'return_url': return_url, 'object': None,
    })


@login_required
def _legacy_veiculo_editar(request, pk):
    obj = get_object_or_404(Veiculo, pk=pk)
    form = VeiculoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        obj.status = Veiculo.STATUS_FINALIZADO if obj.esta_completo() else Veiculo.STATUS_RASCUNHO
        obj.save(update_fields=['status'])
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
        messages.success(request, 'Veículo atualizado com sucesso.')
        return redirect('cadastros:veiculo-lista')
    return_url = request.build_absolute_uri()
    return render(request, 'cadastros/veiculos/form.html', {
        'form': form, 'object': obj, 'is_create': False, 'return_url': return_url,
    })


@login_required
def veiculo_excluir(request, pk):
    obj = get_object_or_404(Veiculo, pk=pk)
    if request.method == 'POST':
        identificador = obj.placa or f'Rascunho #{obj.pk}'
        obj.delete()
        messages.success(request, f'Veículo "{identificador}" excluído com sucesso.')
        return redirect('cadastros:veiculo-lista')
    return render(request, 'cadastros/veiculos/excluir_confirm.html', {'object': obj})


# --- Combustíveis ---

@login_required
def combustivel_lista(request):
    qs = CombustivelVeiculo.objects.all()
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
    page_obj = _paginate(qs, request.GET.get('page'))
    return_url = request.session.get(RETURN_URL_KEY)
    voltar_url = return_url or reverse('cadastros:veiculo-lista')
    voltar_label = 'Voltar' if return_url else 'Voltar para veículos'
    context = {
        'object_list': page_obj.object_list,
        'page_obj': page_obj,
        'pagination_query': _query_without_page(request),
        'form_filter': {'q': q, 'order_by': order_by, 'order_dir': order_dir},
        'order_by_choices': [('nome', 'Nome'), ('is_padrao', 'Padrão'), ('id', 'Cadastro')],
        'order_dir_choices': [('asc', 'Crescente'), ('desc', 'Decrescente')],
        'return_url': return_url,
        'voltar_url': voltar_url,
        'voltar_label': voltar_label,
        'novo_combustivel_url': reverse('cadastros:combustivel-cadastrar'),
    }
    return render(request, 'cadastros/veiculos/combustiveis_lista.html', context)


@login_required
def combustivel_cadastrar(request):
    form = CombustivelVeiculoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Combustível cadastrado com sucesso.')
        return redirect('cadastros:combustivel-lista')
    return render(request, 'cadastros/veiculos/combustiveis_form.html', {'form': form, 'is_create': True})


@login_required
def combustivel_editar(request, pk):
    obj = get_object_or_404(CombustivelVeiculo, pk=pk)
    form = CombustivelVeiculoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Combustível atualizado com sucesso.')
        return redirect('cadastros:combustivel-lista')
    return render(request, 'cadastros/veiculos/combustiveis_form.html', {'form': form, 'object': obj, 'is_create': False})


@login_required
def combustivel_excluir(request, pk):
    obj = get_object_or_404(CombustivelVeiculo, pk=pk)
    if request.method == 'POST':
        if obj.veiculos.exists():
            messages.error(
                request,
                f'Não é possível excluir o combustível "{obj.nome}" pois está em uso por um ou mais veículos.',
            )
            return redirect('cadastros:combustivel-lista')
        nome = str(obj.nome)
        obj.delete()
        messages.success(request, f'Combustível "{nome}" excluído com sucesso.')
        return redirect('cadastros:combustivel-lista')
    return render(request, 'cadastros/veiculos/combustiveis_excluir_confirm.html', {'object': obj})


@login_required
def combustivel_definir_padrao(request, pk):
    if request.method != 'POST':
        return redirect('cadastros:combustivel-lista')
    obj = get_object_or_404(CombustivelVeiculo, pk=pk)
    CombustivelVeiculo.objects.exclude(pk=pk).update(is_padrao=False)
    obj.is_padrao = True
    obj.save(update_fields=['is_padrao'])
    messages.success(request, f'Combustível "{obj.nome}" definido como padrão.')
    return redirect('cadastros:combustivel-lista')
@login_required
def veiculo_cadastrar(request):
    if request.method == 'GET':
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
    form = VeiculoForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.status = Veiculo.STATUS_FINALIZADO if obj.esta_completo() else Veiculo.STATUS_RASCUNHO
        obj.save()
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
        messages.success(request, 'Veículo cadastrado com sucesso.')
        next_url = _next_url_safe(request)
        if next_url:
            return redirect(next_url)
        return redirect('cadastros:veiculo-lista')
    return_url = request.build_absolute_uri()
    next_url = _next_url_safe(request)
    return render(request, 'cadastros/veiculos/form.html', {
        'form': form,
        'is_create': True,
        'return_url': return_url,
        'next_url': next_url,
        'object': None,
    })


@login_required
def veiculo_editar(request, pk):
    obj = get_object_or_404(Veiculo, pk=pk)
    form = VeiculoForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        obj.status = Veiculo.STATUS_FINALIZADO if obj.esta_completo() else Veiculo.STATUS_RASCUNHO
        obj.save(update_fields=['status'])
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
        messages.success(request, 'Veículo atualizado com sucesso.')
        next_url = _next_url_safe(request)
        if next_url:
            return redirect(next_url)
        return redirect('cadastros:veiculo-lista')
    return_url = request.build_absolute_uri()
    next_url = _next_url_safe(request)
    return render(request, 'cadastros/veiculos/form.html', {
        'form': form,
        'object': obj,
        'is_create': False,
        'return_url': return_url,
        'next_url': next_url,
    })
