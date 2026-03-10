from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from urllib.parse import quote, urlencode

from cadastros.models import ConfiguracaoSistema, Cidade, Estado

from .models import (
    Evento,
    EventoParticipante,
    EventoDestino,
    ModeloMotivoViagem,
    Oficio,
    RoteiroEvento,
    RoteiroEventoDestino,
    RoteiroEventoTrecho,
    TipoDemandaEvento,
)
from .forms import (
    EventoEtapa1Form,
    ModeloMotivoViagemForm,
    OficioStep1Form,
    OficioStep2Form,
    RoteiroEventoForm,
    TipoDemandaEventoForm,
)
from .services.estimativa_local import (
    estimar_distancia_duracao,
    minutos_para_hhmm,
    ROTA_FONTE_ESTIMATIVA_LOCAL,
)


def _evento_etapa1_completa(evento):
    """
    Etapa 1 = OK se: ao menos 1 tipo de demanda, ao menos 1 destino,
    datas válidas, descrição válida, título gerado.
    """
    if not evento.data_inicio or not evento.data_fim:
        return False
    if evento.data_fim < evento.data_inicio:
        return False
    if not evento.titulo or not evento.titulo.strip():
        return False
    if not evento.tipos_demanda.exists():
        return False
    if not evento.destinos.exists():
        return False
    # Se tem tipo OUTROS, descrição obrigatória
    tem_outros = evento.tipos_demanda.filter(is_outros=True).exists()
    if tem_outros and not (evento.descricao and evento.descricao.strip()):
        return False
    return True


def _parse_destinos_post(request):
    """
    Extrai da request.POST lista de (estado_id, cidade_id).
    Retorna (lista de tuplas (estado_id, cidade_id), erro ou None).
    """
    prefix_estado = 'destino_estado_'
    prefix_cidade = 'destino_cidade_'
    indices = set()
    for key in request.POST:
        if key.startswith(prefix_estado):
            try:
                idx = int(key[len(prefix_estado):])
                indices.add(idx)
            except ValueError:
                pass
    destinos = []
    for idx in sorted(indices):
        estado_id = request.POST.get(f'{prefix_estado}{idx}')
        cidade_id = request.POST.get(f'{prefix_cidade}{idx}')
        if estado_id and cidade_id:
            try:
                destinos.append((int(estado_id), int(cidade_id)))
            except (TypeError, ValueError):
                pass
    return destinos


def _validar_destinos(destinos):
    """
    Valida lista de (estado_id, cidade_id). Retorna (True, None) ou (False, mensagem).
    """
    if not destinos:
        return False, 'Selecione pelo menos um destino (estado e cidade).'
    for estado_id, cidade_id in destinos:
        try:
            cidade = Cidade.objects.get(pk=cidade_id, ativo=True)
            if cidade.estado_id != estado_id:
                return False, 'A cidade deve pertencer ao estado selecionado.'
        except Cidade.DoesNotExist:
            return False, 'Cidade inválida.'
        if not Estado.objects.filter(pk=estado_id, ativo=True).exists():
            return False, 'Estado inválido.'
    return True, None


def _estrutura_trechos(roteiro, destinos_list=None):
    """
    Monta a estrutura de trechos (ida + retorno) a partir da sede e dos destinos do roteiro.
    Se destinos_list for None, usa roteiro.destinos. Retorna lista de dicts para o template:
    ordem, tipo, origem_estado, origem_cidade, destino_estado, destino_cidade,
    saida_dt, chegada_dt (do DB se existir), origem_nome, destino_nome, id (pk do trecho se existir).
    """
    from datetime import datetime
    if not roteiro.origem_estado_id and not roteiro.origem_cidade_id:
        return []
    if destinos_list is None:
        destinos_qs = roteiro.destinos.select_related('estado', 'cidade').order_by('ordem')
        destinos_list = [(d.estado_id, d.cidade_id) for d in destinos_qs]
    if not destinos_list:
        return []
    trechos_db = {}
    if roteiro.pk:
        for t in roteiro.trechos.select_related('origem_estado', 'origem_cidade', 'destino_estado', 'destino_cidade').order_by('ordem'):
            trechos_db[t.ordem] = t
    out = []
    ordem = 0
    # Origem = sede
    o_estado, o_cidade = roteiro.origem_estado_id, roteiro.origem_cidade_id
    o_nome = (roteiro.origem_cidade.nome if roteiro.origem_cidade else (roteiro.origem_estado.sigla if roteiro.origem_estado else '—'))
    for estado_id, cidade_id in destinos_list:
        try:
            d_cidade = Cidade.objects.filter(pk=cidade_id).select_related('estado').first()
            d_nome = d_cidade.nome if d_cidade else Estado.objects.filter(pk=estado_id).first().sigla if estado_id else '—'
        except Exception:
            d_nome = '—'
        t_db = trechos_db.get(ordem)
        t_cru = getattr(t_db, 'tempo_cru_estimado_min', None) if t_db else None
        t_adic = getattr(t_db, 'tempo_adicional_min', None) if t_db else 0
        if t_adic is None:
            t_adic = 0
        out.append({
            'ordem': ordem,
            'tipo': RoteiroEventoTrecho.TIPO_IDA,
            'origem_estado_id': o_estado,
            'origem_cidade_id': o_cidade,
            'destino_estado_id': estado_id,
            'destino_cidade_id': cidade_id,
            'origem_nome': o_nome,
            'destino_nome': d_nome,
            'saida_dt': t_db.saida_dt if t_db else None,
            'chegada_dt': t_db.chegada_dt if t_db else None,
            'id': t_db.pk if t_db else None,
            'distancia_km': t_db.distancia_km if t_db else None,
            'duracao_estimada_min': t_db.duracao_estimada_min if t_db else None,
            'tempo_cru_estimado_min': t_cru,
            'tempo_adicional_min': t_adic,
        })
        o_estado, o_cidade = estado_id, cidade_id
        o_nome = d_nome
        ordem += 1
    # Retorno: último destino -> sede
    sede_nome = (roteiro.origem_cidade.nome if roteiro.origem_cidade else (roteiro.origem_estado.sigla if roteiro.origem_estado else '—'))
    t_db = trechos_db.get(ordem)
    t_cru = getattr(t_db, 'tempo_cru_estimado_min', None) if t_db else None
    t_adic = getattr(t_db, 'tempo_adicional_min', None) if t_db else 0
    if t_adic is None:
        t_adic = 0
    out.append({
        'ordem': ordem,
        'tipo': RoteiroEventoTrecho.TIPO_RETORNO,
        'origem_estado_id': o_estado,
        'origem_cidade_id': o_cidade,
        'destino_estado_id': roteiro.origem_estado_id,
        'destino_cidade_id': roteiro.origem_cidade_id,
        'origem_nome': o_nome,
        'destino_nome': sede_nome,
        'saida_dt': t_db.saida_dt if t_db else None,
        'chegada_dt': t_db.chegada_dt if t_db else None,
        'id': t_db.pk if t_db else None,
        'distancia_km': t_db.distancia_km if t_db else None,
        'duracao_estimada_min': t_db.duracao_estimada_min if t_db else None,
        'tempo_cru_estimado_min': t_cru,
        'tempo_adicional_min': t_adic,
    })
    return out


def _salvar_trechos_roteiro(roteiro, destinos_list, trechos_data):
    """
    Substitui os trechos do roteiro pela estrutura sede + destinos_list.
    trechos_data = lista de dicts com saida_dt, chegada_dt, distancia_km, duracao_estimada_min (por ordem).
    Índice i de trechos_data corresponde ao trecho de ordem i (ida 0..n-1, depois retorno n).
    """
    roteiro.trechos.all().delete()
    if not roteiro.origem_estado_id and not roteiro.origem_cidade_id:
        return
    if not destinos_list:
        return
    o_estado, o_cidade = roteiro.origem_estado_id, roteiro.origem_cidade_id
    for idx in range(len(destinos_list)):
        estado_id, cidade_id = destinos_list[idx]
        data = trechos_data[idx] if idx < len(trechos_data) else {}
        saida = data.get('saida_dt')
        chegada = data.get('chegada_dt')
        dist_km = data.get('distancia_km')
        t_cru = data.get('tempo_cru_estimado_min')
        t_adic = data.get('tempo_adicional_min', 0) or 0
        dur_min = data.get('duracao_estimada_min')
        if dur_min is None and ((t_cru or 0) + t_adic) > 0:
            dur_min = (t_cru or 0) + t_adic
        RoteiroEventoTrecho.objects.create(
            roteiro=roteiro, ordem=idx, tipo=RoteiroEventoTrecho.TIPO_IDA,
            origem_estado_id=o_estado, origem_cidade_id=o_cidade,
            destino_estado_id=estado_id, destino_cidade_id=cidade_id,
            saida_dt=saida, chegada_dt=chegada,
            distancia_km=dist_km, duracao_estimada_min=dur_min,
            tempo_cru_estimado_min=t_cru, tempo_adicional_min=t_adic,
        )
        o_estado, o_cidade = estado_id, cidade_id
    ordem_retorno = len(destinos_list)
    data_ret = trechos_data[ordem_retorno] if ordem_retorno < len(trechos_data) else {}
    saida_r = data_ret.get('saida_dt')
    chegada_r = data_ret.get('chegada_dt')
    dist_km_r = data_ret.get('distancia_km')
    t_cru_r = data_ret.get('tempo_cru_estimado_min')
    t_adic_r = data_ret.get('tempo_adicional_min', 0) or 0
    dur_min_r = data_ret.get('duracao_estimada_min')
    if dur_min_r is None and ((t_cru_r or 0) + t_adic_r) > 0:
        dur_min_r = (t_cru_r or 0) + t_adic_r
    RoteiroEventoTrecho.objects.create(
        roteiro=roteiro, ordem=ordem_retorno, tipo=RoteiroEventoTrecho.TIPO_RETORNO,
        origem_estado_id=o_estado, origem_cidade_id=o_cidade,
        destino_estado_id=roteiro.origem_estado_id, destino_cidade_id=roteiro.origem_cidade_id,
        saida_dt=saida_r, chegada_dt=chegada_r,
        distancia_km=dist_km_r, duracao_estimada_min=dur_min_r,
        tempo_cru_estimado_min=t_cru_r, tempo_adicional_min=t_adic_r,
    )


def _parse_trechos_times_post(request, num_trechos):
    """
    Extrai do POST trecho_N_saida_dt, trecho_N_chegada_dt, trecho_N_distancia_km, trecho_N_duracao_estimada_min.
    Retorna lista de dicts: saida_dt, chegada_dt, distancia_km (Decimal ou None), duracao_estimada_min (int ou None).
    """
    from datetime import datetime
    from decimal import Decimal, InvalidOperation
    result = []
    for i in range(num_trechos):
        s = request.POST.get(f'trecho_{i}_saida_dt', '').strip()
        c = request.POST.get(f'trecho_{i}_chegada_dt', '').strip()
        dist_km = request.POST.get(f'trecho_{i}_distancia_km', '').strip()
        dur_min = request.POST.get(f'trecho_{i}_duracao_estimada_min', '').strip()
        tempo_cru = request.POST.get(f'trecho_{i}_tempo_cru_estimado_min', '').strip()
        tempo_adic = request.POST.get(f'trecho_{i}_tempo_adicional_min', '').strip()
        saida_dt, chegada_dt = None, None
        for val, name in [(s, 'saida'), (c, 'chegada')]:
            if not val:
                continue
            dt = None
            if 'T' in val:
                try:
                    dt = datetime.strptime(val[:16], '%Y-%m-%dT%H:%M')
                except ValueError:
                    pass
            if dt is None and len(val) >= 10:
                try:
                    dt = datetime.strptime(val[:10] + ' 00:00', '%Y-%m-%d %H:%M')
                except ValueError:
                    pass
            if name == 'saida':
                saida_dt = dt
            else:
                chegada_dt = dt
        distancia_km = None
        if dist_km:
            try:
                distancia_km = Decimal(dist_km.replace(',', '.'))
            except (InvalidOperation, ValueError):
                pass
        duracao_estimada_min = None
        if dur_min:
            try:
                duracao_estimada_min = int(dur_min)
                if duracao_estimada_min < 0:
                    duracao_estimada_min = None
            except (TypeError, ValueError):
                pass
        tempo_cru_min = None
        if tempo_cru:
            try:
                tempo_cru_min = int(tempo_cru)
                if tempo_cru_min < 0:
                    tempo_cru_min = None
            except (TypeError, ValueError):
                pass
        tempo_adic_min = 0
        if tempo_adic:
            try:
                tempo_adic_min = max(0, int(tempo_adic))
            except (TypeError, ValueError):
                pass
        total_computed = (tempo_cru_min or 0) + tempo_adic_min
        if total_computed > 0 and duracao_estimada_min is None:
            duracao_estimada_min = total_computed
        result.append({
            'saida_dt': saida_dt,
            'chegada_dt': chegada_dt,
            'distancia_km': distancia_km,
            'duracao_estimada_min': duracao_estimada_min,
            'tempo_cru_estimado_min': tempo_cru_min,
            'tempo_adicional_min': tempo_adic_min,
        })
    return result


@login_required
def evento_lista(request):
    qs = Evento.objects.prefetch_related('tipos_demanda', 'destinos', 'destinos__estado', 'destinos__cidade').all()
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(titulo__icontains=q)
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    tipo_id = request.GET.get('tipo_id', '')
    if tipo_id:
        qs = qs.filter(tipos_demanda__id=tipo_id)
    context = {
        'object_list': qs,
        'form_filter': {'q': q, 'status': status, 'tipo_id': tipo_id},
        'status_choices': Evento.STATUS_CHOICES,
        'tipos_demanda_list': TipoDemandaEvento.objects.filter(ativo=True).order_by('ordem', 'nome'),
    }
    return render(request, 'eventos/evento_lista.html', context)


@login_required
def evento_cadastrar(request):
    """Criação unificada: redireciona para o fluxo guiado (novo evento → Etapa 1)."""
    return redirect('eventos:guiado-novo')


@login_required
def evento_editar(request, pk):
    """Edição unificada: redireciona para a Etapa 1 do fluxo guiado (mesma tela e lógica)."""
    get_object_or_404(Evento, pk=pk)
    return redirect('eventos:guiado-etapa-1', pk=pk)


@login_required
def evento_detalhe(request, pk):
    obj = get_object_or_404(
        Evento.objects.select_related('estado_principal', 'cidade_principal', 'cidade_base').prefetch_related('tipos_demanda', 'destinos'),
        pk=pk
    )
    return render(request, 'eventos/evento_detalhe.html', {'object': obj})


@login_required
@require_http_methods(['POST'])
def evento_excluir(request, pk):
    """
    Exclui o evento somente se não houver vínculos impeditivos (roteiros).
    Tipos de demanda (M2M) e destinos (EventoDestino) são excluídos em cascata pelo Django.
    """
    evento = get_object_or_404(Evento, pk=pk)
    if evento.roteiros.exists():
        messages.error(
            request,
            'Este evento não pode ser excluído porque já possui dados vinculados (roteiros).'
        )
        return redirect('eventos:lista')
    evento.delete()
    messages.success(request, 'Evento excluído com sucesso.')
    return redirect('eventos:lista')


# ---------- Fluxo guiado ----------

@login_required
def guiado_novo(request):
    """Cria um evento em RASCUNHO e redireciona para a Etapa 1. Título e tipos preenchidos na Etapa 1."""
    from datetime import date
    hoje = date.today()
    evento = Evento.objects.create(
        titulo='',
        data_inicio=hoje,
        data_fim=hoje,
        status=Evento.STATUS_RASCUNHO,
    )
    config = ConfiguracaoSistema.get_singleton()
    if config.cidade_sede_padrao_id:
        evento.cidade_base_id = config.cidade_sede_padrao_id
        evento.save(update_fields=['cidade_base'])
    return redirect('eventos:guiado-etapa-1', pk=evento.pk)


@login_required
def guiado_etapa_1(request, pk):
    """GET+POST da Etapa 1 do fluxo guiado refatorado: tipos, datas, destinos, descrição. Título gerado automaticamente."""
    obj = get_object_or_404(
        Evento.objects.prefetch_related('tipos_demanda', 'destinos').prefetch_related('destinos__estado', 'destinos__cidade'),
        pk=pk
    )
    form = EventoEtapa1Form(request.POST or None, instance=obj)
    destinos_atuais = list(obj.destinos.select_related('estado', 'cidade').order_by('ordem', 'id'))
    estado_pr = Estado.objects.filter(sigla='PR').first()
    # Sempre pelo menos 1 bloco de destino visível (placeholder se não houver nenhum)
    if not destinos_atuais:
        destinos_atuais = [type('DestinoPlaceholder', (), {'estado_id': estado_pr.id if estado_pr else None, 'cidade_id': None, 'cidade': None, 'estado': estado_pr})()]
    tipo_outros = TipoDemandaEvento.objects.filter(ativo=True, is_outros=True).first()
    tipo_outros_pk = tipo_outros.pk if tipo_outros else None

    if request.method == 'POST':
        destinos_post = _parse_destinos_post(request)
        ok_destinos, msg_destinos = _validar_destinos(destinos_post)
        if form.is_valid() and ok_destinos:
            # Salvar evento (tipos, data_unica, data_inicio, data_fim, descricao, tem_convite)
            ev = form.save(commit=False)
            # Garantir persistência explícita das datas (fonte: form.cleaned_data)
            data_inicio = form.cleaned_data.get('data_inicio')
            data_fim = form.cleaned_data.get('data_fim')
            data_unica = form.cleaned_data.get('data_unica', False)
            if data_inicio is not None:
                ev.data_inicio = data_inicio
            if data_unica and data_inicio is not None:
                ev.data_fim = data_inicio
            elif data_fim is not None:
                ev.data_fim = data_fim
            ev.data_unica = data_unica
            ev.save()
            form.save_m2m()
            # Destinos: remover antigos e criar novos
            obj.destinos.all().delete()
            for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
                EventoDestino.objects.create(evento=obj, estado_id=estado_id, cidade_id=cidade_id, ordem=ordem)
            if getattr(obj, '_prefetched_objects_cache', None) and 'destinos' in obj._prefetched_objects_cache:
                del obj._prefetched_objects_cache['destinos']
            # Descrição: só manter quando tipo OUTROS está selecionado; senão limpar (form já pode ter setado '' no clean)
            tem_outros = obj.tipos_demanda.filter(is_outros=True).exists()
            if not tem_outros:
                obj.descricao = ''
                obj.save(update_fields=['descricao'])
            # Título automático
            obj.titulo = obj.gerar_titulo()
            obj.save(update_fields=['titulo'])
            if _evento_etapa1_completa(obj) and obj.status == Evento.STATUS_RASCUNHO:
                obj.status = Evento.STATUS_EM_ANDAMENTO
                obj.save(update_fields=['status'])
            if request.POST.get('continuar'):
                return redirect('eventos:guiado-painel', pk=obj.pk)
            return redirect('eventos:guiado-etapa-1', pk=obj.pk)
        if not ok_destinos:
            form.add_error(None, msg_destinos)

    import json
    estados_qs = Estado.objects.filter(ativo=True).order_by('nome')
    estados_list = list(estados_qs.values('id', 'nome', 'sigla'))
    if request.method == 'POST':
        selected_tipos_pks = [int(x) for x in request.POST.getlist('tipos_demanda') if x.isdigit()]
    else:
        selected_tipos_pks = list(obj.tipos_demanda.values_list('pk', flat=True))
    context = {
        'form': form,
        'object': obj,
        'destinos_atuais': destinos_atuais,
        'estado_pr': estado_pr,
        'estados': estados_qs,
        'estados_json': json.dumps(estados_list),
        'selected_tipos_pks': selected_tipos_pks,
        'tipo_outros_pk': tipo_outros_pk,
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
    }
    return render(request, 'eventos/guiado/etapa_1.html', context)


def _evento_etapa2_ok(evento):
    """True se existir pelo menos 1 roteiro FINALIZADO do evento."""
    return RoteiroEvento.objects.filter(evento=evento, status=RoteiroEvento.STATUS_FINALIZADO).exists()


def _evento_etapa3_ok(evento):
    """True se existir ao menos um ofício vinculado ao evento (conforme legado: Etapa 3 = Ofícios do evento)."""
    return evento.oficios.exists()


@login_required
def guiado_painel(request, pk):
    """Painel do evento guiado: resumo, status e etapas (1–3 implementadas; 4–6 Em breve). Blocos clicáveis."""
    obj = get_object_or_404(
        Evento.objects.select_related('estado_principal', 'cidade_principal', 'cidade_base')
        .prefetch_related('tipos_demanda', 'destinos'),
        pk=pk
    )
    etapa1_ok = _evento_etapa1_completa(obj)
    etapa2_ok = _evento_etapa2_ok(obj)
    etapa3_ok = _evento_etapa3_ok(obj)
    etapas = [
        {'numero': 1, 'nome': 'Evento', 'ok': etapa1_ok, 'em_breve': False, 'url': reverse('eventos:guiado-etapa-1', kwargs={'pk': obj.pk})},
        {'numero': 2, 'nome': 'Roteiros', 'ok': etapa2_ok, 'em_breve': False, 'url': reverse('eventos:guiado-etapa-2', kwargs={'evento_id': obj.pk})},
        {'numero': 3, 'nome': 'Ofícios do evento', 'ok': etapa3_ok, 'em_breve': False, 'url': reverse('eventos:guiado-etapa-3', kwargs={'evento_id': obj.pk})},
        {'numero': 4, 'nome': 'Fundamentação / PT-OS', 'ok': False, 'em_breve': True, 'url': None},
        {'numero': 5, 'nome': 'Termos', 'ok': False, 'em_breve': True, 'url': None},
        {'numero': 6, 'nome': 'Finalização', 'ok': False, 'em_breve': True, 'url': None},
    ]
    context = {
        'object': obj,
        'etapas': etapas,
        'etapa1_ok': etapa1_ok,
    }
    return render(request, 'eventos/guiado/painel.html', context)


# ---------- Tipos de demanda (CRUD) ----------

@login_required
def tipos_demanda_lista(request):
    """Lista de tipos de demanda para eventos. Ordenado por ordem, depois nome."""
    volta_etapa1 = request.GET.get('volta_etapa1', '')
    lista = TipoDemandaEvento.objects.all().order_by('ordem', 'nome')
    context = {'object_list': lista, 'volta_etapa1': volta_etapa1}
    return render(request, 'eventos/tipos_demanda/lista.html', context)


@login_required
def tipos_demanda_cadastrar(request):
    """Cadastrar tipo de demanda."""
    form = TipoDemandaEventoForm(request.POST or None)
    if form.is_valid():
        form.save()
        volta = request.GET.get('volta_etapa1')
        if volta:
            return redirect('eventos:guiado-etapa-1', pk=int(volta))
        return redirect('eventos:tipos-demanda-lista')
    context = {'form': form, 'object': None, 'volta_etapa1': request.GET.get('volta_etapa1', '')}
    return render(request, 'eventos/tipos_demanda/form.html', context)


@login_required
def tipos_demanda_editar(request, pk):
    """Editar tipo de demanda."""
    obj = get_object_or_404(TipoDemandaEvento, pk=pk)
    form = TipoDemandaEventoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        volta = request.GET.get('volta_etapa1')
        if volta:
            return redirect('eventos:guiado-etapa-1', pk=int(volta))
        return redirect('eventos:tipos-demanda-lista')
    context = {'form': form, 'object': obj, 'volta_etapa1': request.GET.get('volta_etapa1', '')}
    return render(request, 'eventos/tipos_demanda/form.html', context)


@login_required
def tipos_demanda_excluir(request, pk):
    """Excluir tipo de demanda. Bloqueia se estiver em uso por algum evento."""
    obj = get_object_or_404(TipoDemandaEvento, pk=pk)
    if request.method == 'POST':
        em_uso = Evento.objects.filter(tipos_demanda=obj).exists()
        if em_uso:
            messages.error(request, 'Não é possível excluir: este tipo está em uso por pelo menos um evento.')
            return redirect('eventos:tipos-demanda-editar', pk=pk)
        obj.delete()
        volta = request.GET.get('volta_etapa1')
        if volta:
            return redirect('eventos:guiado-etapa-1', pk=int(volta))
        return redirect('eventos:tipos-demanda-lista')
    context = {'object': obj, 'volta_etapa1': request.GET.get('volta_etapa1', '')}
    return render(request, 'eventos/tipos_demanda/excluir_confirm.html', context)


# ---------- Modelos de motivo (CRUD) ----------

def _modelos_motivo_lista_url(volta_step1=''):
    url = reverse('eventos:modelos-motivo-lista')
    volta = (volta_step1 or '').strip()
    if volta:
        return f'{url}?{urlencode({"volta_step1": volta})}'
    return url


@login_required
def modelos_motivo_lista(request):
    """Lista de modelos de motivo para uso no Step 1 do Ofício."""
    volta_step1 = request.GET.get('volta_step1', '')
    lista = ModeloMotivoViagem.objects.all().order_by('nome')
    context = {'object_list': lista, 'volta_step1': volta_step1}
    return render(request, 'eventos/modelos_motivo/lista.html', context)


@login_required
def modelos_motivo_cadastrar(request):
    """Cadastro de modelo de motivo."""
    volta_step1 = request.GET.get('volta_step1', '')
    form = ModeloMotivoViagemForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Modelo de motivo salvo com sucesso.')
        return redirect(_modelos_motivo_lista_url(volta_step1))
    context = {'form': form, 'object': None, 'volta_step1': volta_step1}
    return render(request, 'eventos/modelos_motivo/form.html', context)


@login_required
def modelos_motivo_editar(request, pk):
    """Edição de modelo de motivo."""
    volta_step1 = request.GET.get('volta_step1', '')
    obj = get_object_or_404(ModeloMotivoViagem, pk=pk)
    form = ModeloMotivoViagemForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Modelo de motivo atualizado com sucesso.')
        return redirect(_modelos_motivo_lista_url(volta_step1))
    context = {'form': form, 'object': obj, 'volta_step1': volta_step1}
    return render(request, 'eventos/modelos_motivo/form.html', context)


@login_required
def modelos_motivo_excluir(request, pk):
    """Exclusão de modelo de motivo."""
    volta_step1 = request.GET.get('volta_step1', '')
    obj = get_object_or_404(ModeloMotivoViagem, pk=pk)
    if request.method == 'POST':
        nome = obj.nome
        obj.delete()
        messages.success(request, f'Modelo "{nome}" excluído com sucesso.')
        return redirect(_modelos_motivo_lista_url(volta_step1))
    context = {'object': obj, 'volta_step1': volta_step1}
    return render(request, 'eventos/modelos_motivo/excluir_confirm.html', context)


@login_required
@require_http_methods(['POST'])
def modelos_motivo_definir_padrao(request, pk):
    """Define modelo de motivo padrão para preseleção no Step 1 do Ofício."""
    volta_step1 = request.GET.get('volta_step1', '')
    obj = get_object_or_404(ModeloMotivoViagem, pk=pk)
    ModeloMotivoViagem.objects.exclude(pk=obj.pk).update(padrao=False)
    obj.padrao = True
    obj.save()
    messages.success(request, f'Modelo "{obj.nome}" definido como padrão.')
    return redirect(_modelos_motivo_lista_url(volta_step1))


@login_required
def modelo_motivo_texto_api(request, pk):
    """Retorna texto do modelo de motivo para preenchimento automático no Step 1."""
    modelo = get_object_or_404(ModeloMotivoViagem, pk=pk)
    return JsonResponse({'ok': True, 'texto': modelo.texto, 'nome': modelo.nome})


# ---------- Etapa 3: Ofícios do evento (hub) ----------

@login_required
def guiado_etapa_3(request, evento_id):
    """Etapa 3 — Ofícios do evento: listar ofícios, criar novo, editar (wizard). Sem central de documentos nesta entrega."""
    evento = get_object_or_404(
        Evento.objects.prefetch_related('oficios'),
        pk=evento_id
    )
    oficios = list(evento.oficios.order_by('ano', 'numero', 'id'))
    context = {
        'evento': evento,
        'object': evento,
        'oficios': oficios,
    }
    return render(request, 'eventos/guiado/etapa_3.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def guiado_etapa_3_criar_oficio(request, evento_id):
    """Cria rascunho de ofício vinculado ao evento e redireciona para o Step 1 do wizard."""
    evento = get_object_or_404(Evento, pk=evento_id)
    if request.method == 'POST' or request.method == 'GET':
        oficio = Oficio.objects.create(
            evento=evento,
            status=Oficio.STATUS_RASCUNHO,
        )
        messages.success(request, 'Ofício criado. Preencha os dados no wizard.')
        return redirect('eventos:oficio-step1', pk=oficio.pk)
    return redirect('eventos:guiado-etapa-3', evento_id=evento_id)


@login_required
def oficio_editar(request, pk):
    """Redireciona para o Step 1 do wizard do ofício."""
    return redirect('eventos:oficio-step1', pk=pk)


def _oficio_redirect_pos_exclusao(oficio):
    if oficio.evento_id:
        return reverse('eventos:guiado-etapa-3', kwargs={'evento_id': oficio.evento_id})
    return reverse('eventos:lista')


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_excluir(request, pk):
    """Exclusão segura de ofício com redirecionamento coerente."""
    oficio = _get_oficio_for_wizard(pk)
    redirect_url = _oficio_redirect_pos_exclusao(oficio)
    if request.method == 'POST':
        numero = oficio.numero_formatado
        oficio.delete()
        messages.success(request, f'Ofício {numero} excluído com sucesso.')
        return redirect(redirect_url)
    context = {
        'oficio': oficio,
        'evento': oficio.evento,
        'cancel_url': redirect_url,
    }
    return render(request, 'eventos/oficio/excluir_confirm.html', context)


# ---------- Wizard do Ofício (Steps 1–4) ----------

def _get_oficio_for_wizard(pk):
    """Carrega ofício com relações necessárias para o wizard."""
    return get_object_or_404(
        Oficio.objects.prefetch_related('viajantes').select_related(
            'evento', 'veiculo', 'motorista_viajante', 'modelo_motivo'
        ),
        pk=pk
    )


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step1(request, pk):
    """Wizard Step 1 — Dados gerais + viajantes (fiel ao legado)."""
    oficio = _get_oficio_for_wizard(pk)
    evento = oficio.evento
    data_criacao_exibicao = (
        oficio.data_criacao
        or (timezone.localtime(oficio.created_at).date() if oficio.created_at else timezone.localdate())
    )
    protocolo_exibicao = Oficio.format_protocolo(oficio.protocolo or '')
    modelo_inicial = oficio.modelo_motivo
    if not modelo_inicial:
        modelo_inicial = ModeloMotivoViagem.objects.filter(padrao=True).order_by('nome').first()

    initial = {
        'oficio_numero': oficio.numero_formatado if oficio.numero and oficio.ano else '',
        'protocolo': protocolo_exibicao,
        'data_criacao': data_criacao_exibicao,
        'modelo_motivo': modelo_inicial.pk if modelo_inicial else None,
        'motivo': oficio.motivo or (modelo_inicial.texto if modelo_inicial else ''),
        'custeio_tipo': oficio.custeio_tipo or Oficio.CUSTEIO_UNIDADE,
        'nome_instituicao_custeio': oficio.nome_instituicao_custeio or '',
        'viajantes': list(oficio.viajantes.all()),
    }
    form = OficioStep1Form(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        oficio.protocolo = form.cleaned_data.get('protocolo') or ''
        oficio.data_criacao = (
            form.cleaned_data.get('data_criacao')
            or oficio.data_criacao
            or timezone.localdate()
        )
        oficio.modelo_motivo = form.cleaned_data.get('modelo_motivo')
        oficio.motivo = (form.cleaned_data.get('motivo') or '').strip()
        oficio.custeio_tipo = form.cleaned_data.get('custeio_tipo') or Oficio.CUSTEIO_UNIDADE
        oficio.nome_instituicao_custeio = (form.cleaned_data.get('nome_instituicao_custeio') or '').strip()
        oficio.save(update_fields=[
            'protocolo', 'data_criacao', 'modelo_motivo',
            'motivo', 'custeio_tipo', 'nome_instituicao_custeio', 'updated_at'
        ])
        oficio.viajantes.set(form.cleaned_data.get('viajantes') or [])

        if request.POST.get('salvar_modelo_motivo'):
            texto_atual = (oficio.motivo or '').strip()
            if not texto_atual:
                messages.error(request, 'Informe o motivo da viagem antes de salvar como modelo.')
                return redirect('eventos:oficio-step1', pk=oficio.pk)
            nome_modelo = (request.POST.get('novo_modelo_nome') or '').strip()
            if not nome_modelo:
                nome_modelo = f'Modelo {timezone.localtime().strftime("%d/%m/%Y %H:%M")}'
            novo_modelo = ModeloMotivoViagem.objects.create(
                nome=nome_modelo,
                texto=texto_atual,
            )
            oficio.modelo_motivo = novo_modelo
            oficio.save(update_fields=['modelo_motivo', 'updated_at'])
            messages.success(request, 'Motivo salvo como novo modelo.')
            return redirect('eventos:oficio-step1', pk=oficio.pk)

        messages.success(request, 'Dados do Step 1 salvos.')
        if request.POST.get('avancar'):
            return redirect('eventos:oficio-step2', pk=oficio.pk)
        return redirect('eventos:oficio-step1', pk=oficio.pk)
    custeio_atual = (
        form.data.get('custeio_tipo')
        if form.is_bound
        else (initial.get('custeio_tipo') or Oficio.CUSTEIO_UNIDADE)
    )
    mostrar_nome_instituicao = custeio_atual == Oficio.CUSTEIO_OUTRA_INSTITUICAO

    context = {
        'oficio': oficio,
        'evento': evento,
        'form': form,
        'step': 1,
        'next_step_url': reverse('eventos:oficio-step2', kwargs={'pk': oficio.pk}),
        'gerenciar_modelos_motivo_url': (
            f"{reverse('eventos:modelos-motivo-lista')}?volta_step1={oficio.pk}"
        ),
        'cadastrar_viajante_url': (
            f"{reverse('cadastros:viajante-cadastrar')}?next="
            f"{quote(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))}"
        ),
        'modelo_texto_api_pattern': reverse('eventos:modelos-motivo-texto-api', kwargs={'pk': 0}),
        'mostrar_nome_instituicao': mostrar_nome_instituicao,
    }
    return render(request, 'eventos/oficio/wizard_step1.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step2(request, pk):
    """Wizard Step 2 — Transporte. Placa, modelo, combustível obrigatórios; motorista carona exige ofício/protocolo."""
    oficio = _get_oficio_for_wizard(pk)
    evento = oficio.evento
    initial = {
        'placa': oficio.placa or '',
        'modelo': oficio.modelo or '',
        'combustivel': oficio.combustivel or '',
        'tipo_viatura': oficio.tipo_viatura or Oficio.TIPO_VIATURA_DESCARACTERIZADA,
        'motorista_viajante': oficio.motorista_viajante_id,
        'motorista_nome': oficio.motorista or '',
        'motorista_carona': oficio.motorista_carona,
        'motorista_oficio_numero': oficio.motorista_oficio_numero,
        'motorista_oficio_ano': oficio.motorista_oficio_ano,
        'motorista_protocolo': oficio.motorista_protocolo or '',
    }
    form = OficioStep2Form(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        oficio.placa = (form.cleaned_data.get('placa') or '').strip().upper()
        oficio.modelo = (form.cleaned_data.get('modelo') or '').strip()
        oficio.combustivel = (form.cleaned_data.get('combustivel') or '').strip()
        oficio.tipo_viatura = form.cleaned_data.get('tipo_viatura') or Oficio.TIPO_VIATURA_DESCARACTERIZADA
        oficio.motorista_viajante_id = form.cleaned_data.get('motorista_viajante') and form.cleaned_data['motorista_viajante'].pk or None
        oficio.motorista = (form.cleaned_data.get('motorista_nome') or '').strip()
        oficio.motorista_carona = form.cleaned_data.get('motorista_carona') or False
        oficio.motorista_oficio_numero = form.cleaned_data.get('motorista_oficio_numero') or None
        oficio.motorista_oficio_ano = form.cleaned_data.get('motorista_oficio_ano') or None
        oficio.motorista_protocolo = (form.cleaned_data.get('motorista_protocolo') or '').strip()
        if oficio.motorista_oficio_numero and oficio.motorista_oficio_ano:
            oficio.motorista_oficio = f'{oficio.motorista_oficio_numero}/{oficio.motorista_oficio_ano}'
        else:
            oficio.motorista_oficio = ''
        oficio.save(update_fields=[
            'placa', 'modelo', 'combustivel', 'tipo_viatura', 'motorista_viajante_id', 'motorista',
            'motorista_carona', 'motorista_oficio', 'motorista_oficio_numero', 'motorista_oficio_ano', 'motorista_protocolo', 'updated_at'
        ])
        messages.success(request, 'Transporte e motorista salvos.')
        if request.POST.get('avancar'):
            return redirect('eventos:oficio-step3', pk=oficio.pk)
        return redirect('eventos:oficio-step2', pk=oficio.pk)
    context = {
        'oficio': oficio,
        'evento': evento,
        'form': form,
        'step': 2,
        'next_step_url': reverse('eventos:oficio-step3', kwargs={'pk': oficio.pk}),
    }
    return render(request, 'eventos/oficio/wizard_step2.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step3(request, pk):
    """Wizard Step 3 — Trechos. Placeholder: integração com roteiros do evento será implementada em breve."""
    oficio = _get_oficio_for_wizard(pk)
    evento = oficio.evento
    if request.method == 'POST' and request.POST.get('avancar'):
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    context = {
        'oficio': oficio,
        'evento': evento,
        'step': 3,
        'next_step_url': reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
    }
    return render(request, 'eventos/oficio/wizard_step3.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step4(request, pk):
    """Wizard Step 4 — Resumo e finalização. Opção de marcar como finalizado."""
    oficio = _get_oficio_for_wizard(pk)
    evento = oficio.evento
    if request.method == 'POST':
        if request.POST.get('finalizar'):
            oficio.status = Oficio.STATUS_FINALIZADO
            oficio.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Ofício finalizado.')
        if request.POST.get('voltar_etapa3') and evento:
            return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    context = {
        'oficio': oficio,
        'evento': evento,
        'step': 4,
    }
    return render(request, 'eventos/oficio/wizard_step4.html', context)


# ---------- Etapa 2: Roteiros ----------

def _get_evento_etapa2(evento_id):
    """Retorna o evento ou 404 (para rotas guiado etapa-2)."""
    return get_object_or_404(
        Evento.objects.prefetch_related('destinos', 'destinos__estado', 'destinos__cidade').select_related('cidade_base', 'cidade_base__estado'),
        pk=evento_id
    )


def _setup_roteiro_querysets(form, request, instance=None):
    """Preenche querysets de estado/cidade para sede (origem). No cadastro novo usa initial da config."""
    form.fields['origem_estado'].queryset = Estado.objects.filter(ativo=True).order_by('nome')
    estado_id = None
    if request.method == 'POST':
        estado_id = request.POST.get('origem_estado')
        if estado_id:
            try:
                estado_id = int(estado_id)
            except (TypeError, ValueError):
                estado_id = None
    elif instance and instance.origem_estado_id:
        estado_id = instance.origem_estado_id
    else:
        # Cadastro novo: usar initial (ex.: cidade_sede_padrao da config)
        est = form.initial.get('origem_estado')
        if est is not None:
            estado_id = getattr(est, 'pk', est)
    if estado_id:
        form.fields['origem_cidade'].queryset = Cidade.objects.filter(
            estado_id=estado_id, ativo=True
        ).order_by('nome')
    else:
        form.fields['origem_cidade'].queryset = Cidade.objects.none()


@login_required
def guiado_etapa_2_lista(request, evento_id):
    """Lista de roteiros do evento (Etapa 2). RASCUNHO primeiro, depois FINALIZADO; dentro de cada grupo, mais recentes primeiro."""
    evento = _get_evento_etapa2(evento_id)
    from django.db.models import Case, Value, When
    roteiros = (
        RoteiroEvento.objects.filter(evento=evento)
        .select_related('origem_estado', 'origem_cidade')
        .prefetch_related('destinos', 'destinos__estado', 'destinos__cidade')
        .order_by(
            Case(When(status=RoteiroEvento.STATUS_RASCUNHO, then=Value(0)), default=Value(1)),
            '-created_at',
        )
    )
    context = {'evento': evento, 'roteiros': roteiros}
    return render(request, 'eventos/guiado/etapa_2_lista.html', context)


def _destinos_roteiro_para_template(objeto):
    """Lista de dicts {estado_id, cidade_id, cidade, estado} a partir de objeto com .destinos (Evento ou RoteiroEvento)."""
    destinos_qs = objeto.destinos.select_related('estado', 'cidade').order_by('ordem', 'id')
    return [
        {'estado_id': d.estado_id, 'cidade_id': d.cidade_id, 'cidade': getattr(d, 'cidade', None), 'estado': getattr(d, 'estado', None)}
        for d in destinos_qs
    ]


def _roteiro_virtual_para_trechos(initial):
    """
    Objeto estilo roteiro (sem pk) para usar em _estrutura_trechos no cadastro novo.
    initial deve ter 'origem_estado' e/ou 'origem_cidade'. Retorna objeto com pk=None e atributos de origem.
    """
    from types import SimpleNamespace
    r = SimpleNamespace(pk=None, origem_estado_id=None, origem_cidade_id=None, origem_estado=None, origem_cidade=None)
    r.origem_estado_id = initial.get('origem_estado')
    r.origem_cidade_id = initial.get('origem_cidade')
    if r.origem_cidade_id:
        r.origem_cidade = Cidade.objects.filter(pk=r.origem_cidade_id).select_related('estado').first()
        if r.origem_cidade:
            r.origem_estado = r.origem_cidade.estado
    if not r.origem_estado and r.origem_estado_id:
        r.origem_estado = Estado.objects.filter(pk=r.origem_estado_id).first()
    return r


def _build_trechos_initial(trechos_list):
    """Monta lista de dicts para trechos_json (saida_dt, chegada_dt, id, ...). Datetimes em hora local para o front."""
    out = []
    for t in trechos_list:
        sd = t.get('saida_dt')
        cd = t.get('chegada_dt')
        if sd and hasattr(sd, 'tzinfo') and sd.tzinfo:
            sd = timezone.localtime(sd)
        if cd and hasattr(cd, 'tzinfo') and cd.tzinfo:
            cd = timezone.localtime(cd)
        d_km = t.get('distancia_km')
        t_cru = t.get('tempo_cru_estimado_min')
        t_adic = t.get('tempo_adicional_min', 0) or 0
        total = (t_cru or 0) + t_adic
        out.append({
            'saida_dt': sd.strftime('%Y-%m-%dT%H:%M') if sd else '',
            'chegada_dt': cd.strftime('%Y-%m-%dT%H:%M') if cd else '',
            'id': t.get('id'),
            'distancia_km': str(d_km) if d_km is not None else '',
            'tempo_cru_estimado_min': t_cru,
            'tempo_adicional_min': t_adic,
            'tempo_total_final_min': total if total > 0 else (t.get('duracao_estimada_min')),
            'duracao_estimada_min': total if total > 0 else t.get('duracao_estimada_min'),
            'duracao_estimada_hhmm': minutos_para_hhmm(total) if total > 0 else minutos_para_hhmm(t.get('duracao_estimada_min')),
            'origem_cidade_id': t.get('origem_cidade_id'),
            'destino_cidade_id': t.get('destino_cidade_id'),
        })
    return out


@login_required
def guiado_etapa_2_cadastrar(request, evento_id):
    """Criar roteiro. Sede pré-preenchida da ConfiguracaoSistema; destinos pré-preenchidos da Etapa 1 do evento.
    Usa o mesmo template e a mesma lógica de trechos da edição; trechos já vêm renderizados no primeiro load."""
    evento = _get_evento_etapa2(evento_id)
    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    if config and config.cidade_sede_padrao_id:
        initial['origem_cidade'] = config.cidade_sede_padrao_id
        if config.cidade_sede_padrao and config.cidade_sede_padrao.estado_id:
            initial['origem_estado'] = config.cidade_sede_padrao.estado_id
    form = RoteiroEventoForm(request.POST or None, initial=initial)
    form.instance.evento = evento
    if request.method != 'POST' and initial:
        form.instance.origem_cidade_id = initial.get('origem_cidade')
        form.instance.origem_estado_id = initial.get('origem_estado')
    _setup_roteiro_querysets(form, request, None)
    destinos_atuais = _destinos_roteiro_para_template(evento) if request.method != 'POST' else []
    if request.method == 'POST':
        destinos_post = _parse_destinos_post(request)
        ok_destinos, msg_destinos = _validar_destinos(destinos_post)
        if form.is_valid() and ok_destinos:
            roteiro = form.save()
            roteiro.destinos.all().delete()
            for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
                RoteiroEventoDestino.objects.create(
                    roteiro=roteiro,
                    estado_id=estado_id,
                    cidade_id=cidade_id,
                    ordem=ordem,
                )
            roteiro.save()
            num_trechos = len(destinos_post) + 1
            trechos_times = _parse_trechos_times_post(request, num_trechos)
            _salvar_trechos_roteiro(roteiro, destinos_post, trechos_times)
            trechos_salvos = list(roteiro.trechos.order_by('ordem'))
            if trechos_salvos:
                update_fields = []
                primeira_saida = trechos_salvos[0].saida_dt
                if primeira_saida is not None:
                    roteiro.saida_dt = primeira_saida
                    update_fields.append('saida_dt')
                if trechos_salvos[-1].tipo == RoteiroEventoTrecho.TIPO_RETORNO:
                    ultima_saida_retorno = trechos_salvos[-1].saida_dt
                    if ultima_saida_retorno is not None:
                        roteiro.retorno_saida_dt = ultima_saida_retorno
                        update_fields.append('retorno_saida_dt')
                    if len(trechos_salvos) >= 2 and trechos_salvos[-2].chegada_dt is not None:
                        roteiro.chegada_dt = trechos_salvos[-2].chegada_dt
                        update_fields.append('chegada_dt')
                    if trechos_salvos[-1].chegada_dt is not None:
                        roteiro.retorno_chegada_dt = trechos_salvos[-1].chegada_dt
                        update_fields.append('retorno_chegada_dt')
                else:
                    if trechos_salvos[-1].chegada_dt is not None:
                        roteiro.chegada_dt = trechos_salvos[-1].chegada_dt
                        update_fields.append('chegada_dt')
                if update_fields:
                    update_fields.append('status')
                    roteiro.save(update_fields=update_fields)
            return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        destinos_atuais = [
            {'estado_id': eid, 'cidade_id': cid, 'cidade': None, 'estado': None}
            for eid, cid in destinos_post
        ]
    if not destinos_atuais and request.method != 'POST':
        destinos_atuais = [{'estado_id': None, 'cidade_id': None, 'cidade': None, 'estado': None}]
    estados_qs = Estado.objects.filter(ativo=True).order_by('nome')
    import json
    estados_list = list(estados_qs.values('id', 'nome', 'sigla'))
    # Mesma estrutura de trechos da edição: trechos_list + trechos_json para o JS
    trechos_list = []
    if request.method != 'POST' and destinos_atuais:
        destinos_list = [(d.get('estado_id'), d.get('cidade_id')) for d in destinos_atuais if d.get('estado_id') and d.get('cidade_id')]
        if destinos_list and (initial.get('origem_estado') or initial.get('origem_cidade')):
            roteiro_virtual = _roteiro_virtual_para_trechos(initial)
            trechos_list = _estrutura_trechos(roteiro_virtual, destinos_list)
    trechos_initial = _build_trechos_initial(trechos_list)
    context = {
        'evento': evento,
        'form': form,
        'object': None,
        'destinos_atuais': destinos_atuais,
        'estados': estados_qs,
        'estados_json': json.dumps(estados_list),
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
        'trechos': trechos_list,
        'trechos_json': json.dumps(trechos_initial),
    }
    return render(request, 'eventos/guiado/roteiro_form.html', context)


@login_required
def guiado_etapa_2_editar(request, evento_id, pk):
    """Editar roteiro (mostra dados salvos; trechos com horários próprios editáveis)."""
    evento = _get_evento_etapa2(evento_id)
    roteiro = get_object_or_404(
        RoteiroEvento.objects.prefetch_related(
            'destinos', 'destinos__estado', 'destinos__cidade',
            'trechos', 'trechos__origem_estado', 'trechos__origem_cidade',
            'trechos__destino_estado', 'trechos__destino_cidade',
        ),
        pk=pk, evento=evento
    )
    form = RoteiroEventoForm(request.POST or None, instance=roteiro)
    _setup_roteiro_querysets(form, request, roteiro)
    if request.method == 'POST':
        destinos_post = _parse_destinos_post(request)
        ok_destinos, msg_destinos = _validar_destinos(destinos_post)
        if form.is_valid() and ok_destinos:
            form.save()
            roteiro.destinos.all().delete()
            for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
                RoteiroEventoDestino.objects.create(roteiro=roteiro, estado_id=estado_id, cidade_id=cidade_id, ordem=ordem)
            roteiro.save()
            num_trechos = len(destinos_post) + 1
            trechos_times = _parse_trechos_times_post(request, num_trechos)
            _salvar_trechos_roteiro(roteiro, destinos_post, trechos_times)
            trechos_salvos = list(roteiro.trechos.order_by('ordem'))
            if trechos_salvos:
                update_fields = []
                primeira_saida = trechos_salvos[0].saida_dt
                if primeira_saida is not None:
                    roteiro.saida_dt = primeira_saida
                    update_fields.append('saida_dt')
                if trechos_salvos[-1].tipo == RoteiroEventoTrecho.TIPO_RETORNO:
                    ultima_saida_retorno = trechos_salvos[-1].saida_dt
                    if ultima_saida_retorno is not None:
                        roteiro.retorno_saida_dt = ultima_saida_retorno
                        update_fields.append('retorno_saida_dt')
                    if len(trechos_salvos) >= 2 and trechos_salvos[-2].chegada_dt is not None:
                        roteiro.chegada_dt = trechos_salvos[-2].chegada_dt
                        update_fields.append('chegada_dt')
                    if trechos_salvos[-1].chegada_dt is not None:
                        roteiro.retorno_chegada_dt = trechos_salvos[-1].chegada_dt
                        update_fields.append('retorno_chegada_dt')
                else:
                    if trechos_salvos[-1].chegada_dt is not None:
                        roteiro.chegada_dt = trechos_salvos[-1].chegada_dt
                        update_fields.append('chegada_dt')
                if update_fields:
                    update_fields.append('status')
                    roteiro.save(update_fields=update_fields)
            return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        destinos_atuais = [{'estado_id': eid, 'cidade_id': cid, 'cidade': None, 'estado': None} for eid, cid in destinos_post]
        if destinos_post:
            trechos_list = _estrutura_trechos(roteiro, destinos_post)
            num_t = len(trechos_list)
            times = _parse_trechos_times_post(request, num_t)
            for i, data in enumerate(times):
                if i < len(trechos_list):
                    trechos_list[i]['saida_dt'] = data.get('saida_dt')
                    trechos_list[i]['chegada_dt'] = data.get('chegada_dt')
                    trechos_list[i]['distancia_km'] = data.get('distancia_km')
                    trechos_list[i]['duracao_estimada_min'] = data.get('duracao_estimada_min')
                    trechos_list[i]['tempo_cru_estimado_min'] = data.get('tempo_cru_estimado_min')
                    trechos_list[i]['tempo_adicional_min'] = data.get('tempo_adicional_min', 0)
        else:
            trechos_list = []
    else:
        destinos_atuais = _destinos_roteiro_para_template(roteiro)
        trechos_list = _estrutura_trechos(roteiro)
    if not destinos_atuais:
        destinos_atuais = [{'estado_id': None, 'cidade_id': None, 'cidade': None, 'estado': None}]
    estados_qs = Estado.objects.filter(ativo=True).order_by('nome')
    import json
    estados_list = list(estados_qs.values('id', 'nome', 'sigla'))
    trechos_initial = _build_trechos_initial(trechos_list)
    context = {
        'evento': evento,
        'object': roteiro,
        'form': form,
        'destinos_atuais': destinos_atuais,
        'estados': estados_qs,
        'estados_json': json.dumps(estados_list),
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
        'trechos': trechos_list,
        'trechos_json': json.dumps(trechos_initial),
    }
    return render(request, 'eventos/guiado/roteiro_form.html', context)


@login_required
def guiado_etapa_2_excluir(request, evento_id, pk):
    """Excluir roteiro do evento (POST)."""
    evento = _get_evento_etapa2(evento_id)
    roteiro = get_object_or_404(RoteiroEvento, pk=pk, evento=evento)
    if request.method == 'POST':
        roteiro.delete()
        return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)
    return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)


@login_required
@require_http_methods(['POST'])
def trecho_calcular_km(request, pk):
    """
    POST: calcula distância e duração do trecho via estimativa local (coordenadas, sem API externa).
    Retorna JSON: ok, distancia_km, duracao_estimada_min, duracao_estimada_hhmm, rota_fonte, erro.
    """
    trecho = get_object_or_404(
        RoteiroEventoTrecho.objects.select_related(
            'origem_cidade', 'origem_estado', 'destino_cidade', 'destino_estado',
            'origem_cidade__estado', 'destino_cidade__estado',
        ),
        pk=pk,
    )
    origem = getattr(trecho, 'origem_cidade', None)
    destino = getattr(trecho, 'destino_cidade', None)
    if not origem or not destino:
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': 'Origem e destino devem ser cidades.',
        })
    if origem.latitude is None or origem.longitude is None:
        nome_uf = f'{origem.nome}/{origem.estado.sigla}' if origem.estado_id else origem.nome
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': f'Cidade de origem sem coordenadas: {nome_uf}',
        })
    if destino.latitude is None or destino.longitude is None:
        nome_uf = f'{destino.nome}/{destino.estado.sigla}' if destino.estado_id else destino.nome
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': f'Cidade de destino sem coordenadas: {nome_uf}',
        })
    out = estimar_distancia_duracao(
        origem_lat=origem.latitude,
        origem_lon=origem.longitude,
        destino_lat=destino.latitude,
        destino_lon=destino.longitude,
    )

    if out['ok']:
        t_cru = out.get('tempo_cru_estimado_min')
        t_adic_sug = out.get('tempo_adicional_sugerido_min', 0) or 0
        trecho.distancia_km = out['distancia_km']
        trecho.tempo_cru_estimado_min = t_cru
        trecho.tempo_adicional_min = t_adic_sug
        trecho.duracao_estimada_min = (t_cru or 0) + t_adic_sug
        trecho.rota_fonte = ROTA_FONTE_ESTIMATIVA_LOCAL
        trecho.rota_calculada_em = timezone.now()
        trecho.save(update_fields=[
            'distancia_km', 'tempo_cru_estimado_min', 'tempo_adicional_min',
            'duracao_estimada_min', 'rota_fonte', 'rota_calculada_em', 'updated_at'
        ])

    return JsonResponse({
        'ok': out['ok'],
        'distancia_km': float(out['distancia_km']) if out['distancia_km'] is not None else None,
        'duracao_estimada_min': out['duracao_estimada_min'],
        'duracao_estimada_hhmm': out['duracao_estimada_hhmm'],
        'tempo_cru_estimado_min': out.get('tempo_cru_estimado_min'),
        'tempo_adicional_sugerido_min': out.get('tempo_adicional_sugerido_min'),
        'perfil_rota': out.get('perfil_rota'),
        'rota_fonte': out.get('rota_fonte', ROTA_FONTE_ESTIMATIVA_LOCAL),
        'erro': out['erro'],
    })


@login_required
@require_http_methods(['POST'])
def estimar_km_por_cidades(request):
    """
    POST JSON: { origem_cidade_id, destino_cidade_id }.
    Retorna o mesmo JSON de trecho_calcular_km (ok, distancia_km, tempo_cru_estimado_min, tempo_adicional_sugerido_min, ...)
    sem salvar em trecho. Usado no cadastro quando o trecho ainda não tem ID.
    """
    try:
        body = __import__('json').loads(request.body or '{}')
        origem_id = body.get('origem_cidade_id')
        destino_id = body.get('destino_cidade_id')
    except (ValueError, TypeError):
        origem_id = destino_id = None
    if not origem_id or not destino_id:
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'tempo_cru_estimado_min': None,
            'tempo_adicional_sugerido_min': None,
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': 'Informe origem_cidade_id e destino_cidade_id.',
        })
    origem = Cidade.objects.filter(pk=origem_id).select_related('estado').first()
    destino = Cidade.objects.filter(pk=destino_id).select_related('estado').first()
    if not origem or not destino:
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'tempo_cru_estimado_min': None,
            'tempo_adicional_sugerido_min': None,
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': 'Cidade de origem ou destino não encontrada.',
        })
    if origem.latitude is None or origem.longitude is None:
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'tempo_cru_estimado_min': None,
            'tempo_adicional_sugerido_min': None,
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': f'Cidade de origem sem coordenadas: {origem.nome}',
        })
    if destino.latitude is None or destino.longitude is None:
        return JsonResponse({
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'tempo_cru_estimado_min': None,
            'tempo_adicional_sugerido_min': None,
            'rota_fonte': ROTA_FONTE_ESTIMATIVA_LOCAL,
            'erro': f'Cidade de destino sem coordenadas: {destino.nome}',
        })
    out = estimar_distancia_duracao(
        origem_lat=origem.latitude,
        origem_lon=origem.longitude,
        destino_lat=destino.latitude,
        destino_lon=destino.longitude,
    )
    return JsonResponse({
        'ok': out['ok'],
        'distancia_km': float(out['distancia_km']) if out['distancia_km'] is not None else None,
        'duracao_estimada_min': out['duracao_estimada_min'],
        'duracao_estimada_hhmm': out['duracao_estimada_hhmm'],
        'tempo_cru_estimado_min': out.get('tempo_cru_estimado_min'),
        'tempo_adicional_sugerido_min': out.get('tempo_adicional_sugerido_min'),
        'perfil_rota': out.get('perfil_rota'),
        'rota_fonte': out.get('rota_fonte', ROTA_FONTE_ESTIMATIVA_LOCAL),
        'erro': out['erro'],
    })
