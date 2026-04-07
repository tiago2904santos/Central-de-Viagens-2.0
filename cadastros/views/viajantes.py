import re
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Case, When, Value, IntegerField
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from ..models import Viajante
from ..forms import ViajanteForm
from core.utils.masks import (
    RG_NAO_POSSUI_CANONICAL,
    format_masked_display,
    format_rg_display,
    only_digits,
)

RETURN_URL_KEY = 'viajante_form_return_url'


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


def _build_viajante_return_url(request, pk):
    """URL de retorno para edição do viajante, preservando next quando existir."""
    path = reverse('cadastros:viajante-editar', kwargs={'pk': pk})
    next_url = _next_url_safe(request)
    if next_url:
        query = urlencode({'next': next_url})
        path = f'{path}?{query}'
    return request.build_absolute_uri(path)


def _rg_display(obj):
    """RG para exibição na lista."""
    return format_rg_display(obj.rg, sem_rg=obj.sem_rg)


def _cpf_display(obj):
    """CPF para exibição na lista."""
    return format_masked_display('cpf', obj.cpf)


def _telefone_display(obj):
    """Telefone para exibição na lista."""
    return format_masked_display('telefone', obj.telefone)


def _extrair_dados_rascunho_post(post, obj_existente=None):
    """
    Extrai dados do POST para criar/atualizar um Viajante em rascunho.
    Retorna dict com campos normalizados; evita conflito de unicity quando possível.
    """
    nome_raw = (post.get('nome') or '').strip()
    nome = ' '.join(nome_raw.upper().split()) if nome_raw else ''
    cargo_id = post.get('cargo') or None
    if cargo_id and not str(cargo_id).strip().isdigit():
        cargo_id = None
    unidade_id = post.get('unidade_lotacao') or None
    if unidade_id and not str(unidade_id).strip().isdigit():
        unidade_id = None
    sem_rg = post.get('sem_rg') == 'on'
    rg_raw = (post.get('rg') or '').strip() if not sem_rg else ''
    rg = only_digits(rg_raw) or (RG_NAO_POSSUI_CANONICAL if sem_rg else '')
    cpf_raw = post.get('cpf') or ''
    cpf = re.sub(r'\D', '', cpf_raw)
    if len(cpf) != 11:
        cpf = ''
    telefone_raw = post.get('telefone') or ''
    telefone = re.sub(r'\D', '', telefone_raw)
    if len(telefone) not in (10, 11):
        telefone = ''

    # Evitar conflito de unicidade ao criar novo: limpar cpf/rg/telefone se já existir outro
    if not obj_existente:
        if cpf and Viajante.objects.filter(cpf=cpf).exists():
            cpf = ''
        if rg and rg != RG_NAO_POSSUI_CANONICAL and Viajante.objects.filter(rg=rg).exists():
            rg = ''
        if telefone and Viajante.objects.filter(telefone=telefone).exists():
            telefone = ''
        if nome and Viajante.objects.filter(nome=nome).exists():
            nome = ''

    return {
        'nome': nome,
        'cargo_id': int(cargo_id) if cargo_id else None,
        'unidade_lotacao_id': int(unidade_id) if unidade_id else None,
        'sem_rg': sem_rg,
        'rg': rg or (RG_NAO_POSSUI_CANONICAL if sem_rg else ''),
        'cpf': cpf,
        'telefone': telefone,
        'status': Viajante.STATUS_RASCUNHO,
    }


@login_required
def viajante_lista(request):
    qs = Viajante.objects.select_related('cargo', 'unidade_lotacao').all()
    q = request.GET.get('q', '').strip()
    order_by = (request.GET.get('order_by') or 'updated_at').strip().lower()
    order_dir = (request.GET.get('order_dir') or 'desc').strip().lower()
    order_by_map = {
        'updated_at': 'updated_at',
        'nome': 'nome',
        'cargo': 'cargo__nome',
        'status': 'status',
    }
    order_field = order_by_map.get(order_by, 'updated_at')
    order_dir = 'asc' if order_dir == 'asc' else 'desc'
    if order_dir == 'desc':
        order_field = f'-{order_field}'

    if q:
        qs = qs.filter(
            Q(nome__icontains=q) | Q(cargo__nome__icontains=q) |
            Q(rg__icontains=q) | Q(cpf__icontains=q) |
            Q(telefone__icontains=q) |
            Q(unidade_lotacao__nome__icontains=q) | Q(status__icontains=q)
        )
    qs = qs.annotate(
        _sort_status=Case(
            When(status=Viajante.STATUS_RASCUNHO, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('_sort_status', order_field, '-updated_at')
    page_obj = _paginate(qs, request.GET.get('page'))
    object_list = list(page_obj.object_list)
    for obj in object_list:
        obj.nome_display = obj.nome or '(Rascunho)'
        obj.rg_display = _rg_display(obj)
        obj.cpf_display = _cpf_display(obj)
        obj.telefone_display = _telefone_display(obj)
        obj.status_display = obj.get_status_display()
    context = {
        'object_list': object_list,
        'page_obj': page_obj,
        'pagination_query': _query_without_page(request),
        'form_filter': {'q': q, 'order_by': order_by, 'order_dir': order_dir},
        'order_by_choices': [
            ('updated_at', 'Atualização'),
            ('nome', 'Nome'),
            ('cargo', 'Cargo'),
            ('status', 'Status'),
        ],
        'order_dir_choices': [('desc', 'Decrescente'), ('asc', 'Crescente')],
        'cargos_url': reverse('cadastros:cargo-lista'),
        'unidades_url': reverse('cadastros:unidade-lotacao-lista'),
        'novo_viajante_url': reverse('cadastros:viajante-cadastrar'),
    }
    return render(request, 'cadastros/viajantes/lista.html', context)


@login_required
def viajante_salvar_rascunho_ir_cargos(request):
    """POST: cria ou atualiza viajante como RASCUNHO e redireciona para lista de cargos."""
    if request.method != 'POST':
        return redirect('cadastros:viajante-lista')
    viajante_id = request.POST.get('viajante_id', '').strip()
    if viajante_id and viajante_id.isdigit():
        obj = get_object_or_404(Viajante, pk=int(viajante_id))
        dados = _extrair_dados_rascunho_post(request.POST, obj_existente=obj)
        for key, value in dados.items():
            setattr(obj, key, value)
        obj.status = Viajante.STATUS_RASCUNHO
        obj.save()
        pk = obj.pk
    else:
        dados = _extrair_dados_rascunho_post(request.POST)
        obj = Viajante.objects.create(**dados)
        pk = obj.pk
    request.session[RETURN_URL_KEY] = _build_viajante_return_url(request, pk)
    request.session.modified = True
    messages.info(request, 'Rascunho salvo. Ao voltar, continue editando o mesmo viajante.')
    return redirect('cadastros:cargo-lista')


@login_required
def viajante_salvar_rascunho_ir_unidades(request):
    """POST: cria ou atualiza viajante como RASCUNHO e redireciona para lista de unidades."""
    if request.method != 'POST':
        return redirect('cadastros:viajante-lista')
    viajante_id = request.POST.get('viajante_id', '').strip()
    if viajante_id and viajante_id.isdigit():
        obj = get_object_or_404(Viajante, pk=int(viajante_id))
        dados = _extrair_dados_rascunho_post(request.POST, obj_existente=obj)
        for key, value in dados.items():
            setattr(obj, key, value)
        obj.status = Viajante.STATUS_RASCUNHO
        obj.save()
        pk = obj.pk
    else:
        dados = _extrair_dados_rascunho_post(request.POST)
        obj = Viajante.objects.create(**dados)
        pk = obj.pk
    request.session[RETURN_URL_KEY] = _build_viajante_return_url(request, pk)
    request.session.modified = True
    messages.info(request, 'Rascunho salvo. Ao voltar, continue editando o mesmo viajante.')
    return redirect('cadastros:unidade-lotacao-lista')


@login_required
def viajante_cadastrar(request):
    if request.method == 'GET':
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
    form = ViajanteForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.status = Viajante.STATUS_FINALIZADO if obj.esta_completo() else Viajante.STATUS_RASCUNHO
        obj.save()
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
        messages.success(request, 'Viajante cadastrado com sucesso.')
        next_url = _next_url_safe(request)
        if next_url:
            return redirect(next_url)
        return redirect('cadastros:viajante-lista')
    return_url = request.build_absolute_uri()
    next_url = _next_url_safe(request)
    return render(request, 'cadastros/viajantes/form.html', {
        'form': form, 'is_create': True, 'return_url': return_url, 'next_url': next_url, 'object': None,
    })


@login_required
def viajante_editar(request, pk):
    obj = get_object_or_404(Viajante, pk=pk)
    form = ViajanteForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        obj.status = Viajante.STATUS_FINALIZADO if obj.esta_completo() else Viajante.STATUS_RASCUNHO
        obj.save(update_fields=['status'])
        if RETURN_URL_KEY in request.session:
            del request.session[RETURN_URL_KEY]
            request.session.modified = True
        messages.success(request, 'Viajante atualizado com sucesso.')
        next_url = _next_url_safe(request)
        if next_url:
            return redirect(next_url)
        return redirect('cadastros:viajante-lista')
    return_url = request.build_absolute_uri()
    next_url = _next_url_safe(request)
    return render(request, 'cadastros/viajantes/form.html', {
        'form': form, 'object': obj, 'is_create': False, 'return_url': return_url, 'next_url': next_url,
    })


@login_required
def viajante_excluir(request, pk):
    obj = get_object_or_404(Viajante, pk=pk)
    if request.method == 'POST':
        identificador = obj.nome or f'Rascunho #{obj.pk}'
        obj.delete()
        messages.success(request, f'Viajante "{identificador}" excluído com sucesso.')
        return redirect('cadastros:viajante-lista')
    return render(request, 'cadastros/viajantes/excluir_confirm.html', {'object': obj})
