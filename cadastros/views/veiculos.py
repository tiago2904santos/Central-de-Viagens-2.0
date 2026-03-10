from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse

from ..models import Veiculo, CombustivelVeiculo
from ..forms import VeiculoForm, CombustivelVeiculoForm
from core.utils.masks import _normalizar_placa

RETURN_URL_KEY = 'veiculo_form_return_url'


def _placa_valida(norm):
    if not norm or len(norm) != 7:
        return False
    import re
    return bool(re.match(r'^[A-Z]{3}[0-9]{4}$', norm) or re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', norm))


@login_required
def veiculo_lista(request):
    qs = Veiculo.objects.select_related('combustivel').all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(placa__icontains=q) | Q(modelo__icontains=q) |
            Q(combustivel__nome__icontains=q) | Q(tipo__icontains=q) | Q(status__icontains=q)
        )
    qs = qs.order_by('-status', '-updated_at')
    object_list = list(qs)
    for obj in object_list:
        obj.placa_display = obj.placa_formatada
        obj.status_display = obj.get_status_display()
    context = {
        'object_list': object_list,
        'form_filter': {'q': q},
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
    request.session[RETURN_URL_KEY] = request.build_absolute_uri(reverse('cadastros:veiculo-editar', kwargs={'pk': pk}))
    request.session.modified = True
    messages.info(request, 'Rascunho salvo. Ao voltar, continue editando o mesmo veículo.')
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
        return redirect('cadastros:veiculo-lista')
    return_url = request.build_absolute_uri()
    return render(request, 'cadastros/veiculos/form.html', {
        'form': form, 'is_create': True, 'return_url': return_url, 'object': None,
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
    qs = CombustivelVeiculo.objects.all().order_by('nome')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(nome__icontains=q)
    return_url = request.session.get(RETURN_URL_KEY)
    context = {
        'object_list': qs,
        'form_filter': {'q': q},
        'return_url': return_url,
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
