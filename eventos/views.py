import uuid
from copy import deepcopy
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods
from urllib.parse import quote, urlencode

from cadastros.models import ConfiguracaoSistema, Cidade, Estado, Veiculo, Viajante
from core.utils.masks import format_placa, format_protocolo, normalize_placa, only_digits

from .models import (
    AtividadePlanoTrabalho,
    CoordenadorOperacional,
    Evento,
    EventoAnexoSolicitante,
    EventoDestino,
    EventoFinalizacao,
    EventoParticipante,
    EventoTermoParticipante,
    Justificativa,
    ModeloJustificativa,
    ModeloMotivoViagem,
    OrdemServico,
    Oficio,
    OficioTrecho,
    PlanoTrabalho,
    HorarioAtendimentoPlanoTrabalho,
    RoteiroEvento,
    RoteiroEventoDestino,
    RoteiroEventoTrecho,
    SolicitantePlanoTrabalho,
    TermoAutorizacao,
    TipoDemandaEvento,
)
from .forms import (
    AtividadePlanoTrabalhoForm,
    CoordenadorOperacionalForm,
    EventoEtapa1Form,
    EventoFinalizacaoForm,
    HorarioAtendimentoPlanoTrabalhoForm,
    ModeloJustificativaForm,
    ModeloMotivoViagemForm,
    OficioJustificativaForm,
    OficioStep1Form,
    OficioStep2Form,
    RoteiroEventoForm,
    SolicitantePlanoTrabalhoForm,
    TipoDemandaEventoForm,
)
from .services.estimativa_local import (
    estimar_distancia_duracao,
    minutos_para_hhmm,
    ROTA_FONTE_ESTIMATIVA_LOCAL,
)
from .services.diarias import (
    PeriodMarker,
    calculate_periodized_diarias,
    formatar_valor_diarias,
    infer_tipo_destino_from_paradas,
    locations_equivalent,
    valor_por_extenso_ptbr,
)
from .services.justificativa import (
    get_dias_antecedencia_oficio,
    get_oficio_justificativa_texto,
    get_prazo_justificativa_dias,
    get_primeira_saida_oficio,
    oficio_exige_justificativa,
    oficio_tem_justificativa,
)
from .services.oficio_schema import get_oficio_justificativa_schema_status
from .services.documentos import (
    DocumentoFormato,
    DocumentoOficioTipo,
    DocumentGenerationError,
    DocumentRendererUnavailable,
    build_document_filename,
    get_docx_backend_availability,
    get_pdf_backend_availability,
    get_document_generation_status,
    get_document_type_meta,
    iter_document_type_metas,
    render_document_bytes,
)
from .services.documentos.renderer import (
    convert_docx_bytes_to_pdf_bytes,
    get_termo_autorizacao_templates_availability,
)
from .services.documentos.termo_autorizacao import (
    TERMO_MODALIDADE_COMPLETO,
    TERMO_MODALIDADE_SEMIPREENCHIDO,
    render_evento_termo_padrao_branco_docx,
    render_evento_participante_termo_docx,
    validate_evento_participante_termo_data,
)
from .termos import build_termo_context as _build_termo_context_for_oficio
from .utils import (
    buscar_viajantes_finalizados,
    buscar_veiculo_finalizado_por_placa,
    buscar_veiculos_finalizados,
    mapear_tipo_viatura_para_oficio,
    serializar_viajante_para_autocomplete,
    serializar_veiculo_para_oficio,
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
    tem_outros = any(t.is_outros for t in evento.tipos_demanda.all())
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


def _get_parana_estado():
    return Estado.objects.filter(sigla__iexact='PR', ativo=True).order_by('id').first()


def _normalize_step3_state_destinos_para_parana(state, parana_estado_id):
    if not state or not parana_estado_id:
        return state
    for destino in state.get('destinos_atuais') or []:
        if destino.get('cidade_id'):
            destino['estado_id'] = parana_estado_id
    for trecho in state.get('trechos') or []:
        if trecho.get('destino_cidade_id'):
            trecho['destino_estado_id'] = parana_estado_id
        if trecho.get('origem_cidade_id') and trecho.get('origem_nome') and trecho.get('ordem', 0) > 0:
            trecho['origem_estado_id'] = parana_estado_id
    return state


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


def _is_pdf_upload(uploaded_file):
    nome = (getattr(uploaded_file, 'name', '') or '').strip().lower()
    content_type = (getattr(uploaded_file, 'content_type', '') or '').strip().lower()
    if nome.endswith('.pdf'):
        return True
    return content_type == 'application/pdf'


def _validar_anexos_convite(arquivos):
    for arquivo in arquivos:
        if not _is_pdf_upload(arquivo):
            return False, f'O arquivo "{arquivo.name}" não é PDF. Envie apenas PDF.'
    return True, None


def _salvar_anexos_convite(evento, arquivos):
    if not arquivos:
        return
    ultima_ordem = (
        evento.anexos_solicitante.aggregate(max_ordem=Max('ordem')).get('max_ordem')
        or -1
    )
    for indice, arquivo in enumerate(arquivos, start=1):
        nome_original = (getattr(arquivo, 'name', '') or '').strip()[:255] or f'anexo-{uuid.uuid4().hex[:8]}.pdf'
        EventoAnexoSolicitante.objects.create(
            evento=evento,
            arquivo=arquivo,
            nome_original=nome_original,
            ordem=ultima_ordem + indice,
        )


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
        t_adic = getattr(t_db, 'tempo_adicional_min', None) if t_db else 0
        if t_adic is None:
            t_adic = 0
        t_cru = getattr(t_db, 'tempo_cru_estimado_min', None) if t_db else None
        if t_cru is None and t_db and t_db.duracao_estimada_min is not None:
            t_cru = max((t_db.duracao_estimada_min or 0) - t_adic, 0)
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
            'rota_fonte': (getattr(t_db, 'rota_fonte', '') or '') if t_db else '',
        })
        o_estado, o_cidade = estado_id, cidade_id
        o_nome = d_nome
        ordem += 1
    # Retorno: último destino -> sede
    sede_nome = (roteiro.origem_cidade.nome if roteiro.origem_cidade else (roteiro.origem_estado.sigla if roteiro.origem_estado else '—'))
    t_db = trechos_db.get(ordem)
    t_adic = getattr(t_db, 'tempo_adicional_min', None) if t_db else 0
    if t_adic is None:
        t_adic = 0
    t_cru = getattr(t_db, 'tempo_cru_estimado_min', None) if t_db else None
    if t_cru is None and t_db and t_db.duracao_estimada_min is not None:
        t_cru = max((t_db.duracao_estimada_min or 0) - t_adic, 0)
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
        'rota_fonte': (getattr(t_db, 'rota_fonte', '') or '') if t_db else '',
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
        rota_fonte = (data.get('rota_fonte') or '').strip()
        if dur_min is None and ((t_cru or 0) + t_adic) > 0:
            dur_min = (t_cru or 0) + t_adic
        RoteiroEventoTrecho.objects.create(
            roteiro=roteiro, ordem=idx, tipo=RoteiroEventoTrecho.TIPO_IDA,
            origem_estado_id=o_estado, origem_cidade_id=o_cidade,
            destino_estado_id=estado_id, destino_cidade_id=cidade_id,
            saida_dt=saida, chegada_dt=chegada,
            distancia_km=dist_km, duracao_estimada_min=dur_min,
            tempo_cru_estimado_min=t_cru, tempo_adicional_min=t_adic,
            rota_fonte=rota_fonte,
            rota_calculada_em=timezone.now() if dist_km is not None or t_cru is not None else None,
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
    rota_fonte_r = (data_ret.get('rota_fonte') or '').strip()
    if dur_min_r is None and ((t_cru_r or 0) + t_adic_r) > 0:
        dur_min_r = (t_cru_r or 0) + t_adic_r
    RoteiroEventoTrecho.objects.create(
        roteiro=roteiro, ordem=ordem_retorno, tipo=RoteiroEventoTrecho.TIPO_RETORNO,
        origem_estado_id=o_estado, origem_cidade_id=o_cidade,
        destino_estado_id=roteiro.origem_estado_id, destino_cidade_id=roteiro.origem_cidade_id,
        saida_dt=saida_r, chegada_dt=chegada_r,
        distancia_km=dist_km_r, duracao_estimada_min=dur_min_r,
        tempo_cru_estimado_min=t_cru_r, tempo_adicional_min=t_adic_r,
        rota_fonte=rota_fonte_r,
        rota_calculada_em=timezone.now() if dist_km_r is not None or t_cru_r is not None else None,
    )


def _atualizar_datas_roteiro_apos_salvar_trechos(roteiro):
    trechos_salvos = list(roteiro.trechos.order_by('ordem'))
    if not trechos_salvos:
        return
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


def _salvar_roteiro_com_destinos_e_trechos(roteiro, destinos_post, trechos_times):
    if roteiro.pk is None:
        roteiro.save()
    roteiro.destinos.all().delete()
    for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
        RoteiroEventoDestino.objects.create(
            roteiro=roteiro,
            estado_id=estado_id,
            cidade_id=cidade_id,
            ordem=ordem,
        )
    _salvar_trechos_roteiro(roteiro, destinos_post, trechos_times)
    _atualizar_datas_roteiro_apos_salvar_trechos(roteiro)
    return roteiro


def _parse_trechos_times_post(request, num_trechos):
    """
    Extrai do POST trecho_N_saida_dt, trecho_N_chegada_dt, trecho_N_distancia_km, trecho_N_duracao_estimada_min.
    Tenta primeiro o campo hidden combinado (trecho_N_saida_dt). Se vazio, usa os campos
    visíveis individuais (trecho_N_saida_date + trecho_N_saida_time) como fallback, garantindo
    que as datas sejam sempre salvas mesmo quando o JS não sincronizou o campo oculto.
    Retorna lista de dicts: saida_dt, chegada_dt, distancia_km (Decimal ou None), duracao_estimada_min (int ou None).
    """
    from datetime import datetime
    from decimal import Decimal, InvalidOperation
    result = []
    for i in range(num_trechos):
        s = request.POST.get(f'trecho_{i}_saida_dt', '').strip()
        c = request.POST.get(f'trecho_{i}_chegada_dt', '').strip()
        # Fallback: campos visíveis individuais, enviados sempre pelo browser independente do JS
        if not s:
            # Support both old (saida_date/saida_time) and Oficio-compatible (saida_data/saida_hora) field names
            s_date = (request.POST.get(f'trecho_{i}_saida_data', '') or
                      request.POST.get(f'trecho_{i}_saida_date', '')).strip()
            s_time = (request.POST.get(f'trecho_{i}_saida_hora', '') or
                      request.POST.get(f'trecho_{i}_saida_time', '')).strip()
            if s_date:
                s = s_date + 'T' + (s_time if s_time else '00:00')
        if not c:
            c_date = (request.POST.get(f'trecho_{i}_chegada_data', '') or
                      request.POST.get(f'trecho_{i}_chegada_date', '')).strip()
            c_time = (request.POST.get(f'trecho_{i}_chegada_hora', '') or
                      request.POST.get(f'trecho_{i}_chegada_time', '')).strip()
            if c_date:
                c = c_date + 'T' + (c_time if c_time else '00:00')
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
            if dt is not None and timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
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
        rota_fonte = request.POST.get(f'trecho_{i}_rota_fonte', '').strip()
        result.append({
            'saida_dt': saida_dt,
            'chegada_dt': chegada_dt,
            'distancia_km': distancia_km,
            'duracao_estimada_min': duracao_estimada_min,
            'tempo_cru_estimado_min': tempo_cru_min,
            'tempo_adicional_min': tempo_adic_min,
            'rota_fonte': rota_fonte,
        })
    return result


def _parse_retorno_from_post(request):
    """
    Parses retorno_* POST fields (from static retorno block) into a trechos_times
    dict compatible with _salvar_trechos_roteiro expectations.
    """
    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    def _parse_dt(date_val, time_val):
        date_val = (date_val or '').strip()
        time_val = (time_val or '').strip()
        if not date_val:
            return None
        dt_str = date_val + 'T' + (time_val if time_val else '00:00')
        try:
            dt = datetime.strptime(dt_str[:16], '%Y-%m-%dT%H:%M')
        except ValueError:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt

    saida_dt = _parse_dt(
        request.POST.get('retorno_saida_data', ''),
        request.POST.get('retorno_saida_hora', ''),
    )
    chegada_dt = _parse_dt(
        request.POST.get('retorno_chegada_data', ''),
        request.POST.get('retorno_chegada_hora', ''),
    )
    dist_km_raw = request.POST.get('retorno_distancia_km', '').strip()
    distancia_km = None
    if dist_km_raw:
        try:
            distancia_km = Decimal(dist_km_raw.replace(',', '.'))
        except (InvalidOperation, ValueError):
            pass
    tempo_cru_raw = request.POST.get('retorno_tempo_cru_estimado_min', '').strip()
    tempo_cru_min = None
    if tempo_cru_raw:
        try:
            v = int(tempo_cru_raw)
            if v >= 0:
                tempo_cru_min = v
        except (ValueError, TypeError):
            pass
    tempo_adic_raw = request.POST.get('retorno_tempo_adicional_min', '0').strip()
    try:
        tempo_adic_min = max(0, int(tempo_adic_raw))
    except (ValueError, TypeError):
        tempo_adic_min = 0
    dur_min_raw = request.POST.get('retorno_duracao_estimada_min', '').strip()
    duracao_estimada_min = None
    if dur_min_raw:
        try:
            v = int(dur_min_raw)
            if v >= 0:
                duracao_estimada_min = v
        except (ValueError, TypeError):
            pass
    if duracao_estimada_min is None and ((tempo_cru_min or 0) + tempo_adic_min) > 0:
        duracao_estimada_min = (tempo_cru_min or 0) + tempo_adic_min
    return {
        'saida_dt': saida_dt,
        'chegada_dt': chegada_dt,
        'distancia_km': distancia_km,
        'duracao_estimada_min': duracao_estimada_min,
        'tempo_cru_estimado_min': tempo_cru_min,
        'tempo_adicional_min': tempo_adic_min,
        'rota_fonte': request.POST.get('retorno_rota_fonte', '').strip(),
    }


def _distinct_items_by_pk(items):
    ordered = []
    seen = set()
    for item in items or []:
        pk = getattr(item, 'pk', None)
        marker = pk if pk is not None else id(item)
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(item)
    return ordered


def _summarize_plain_text(value, fallback='', limit=120):
    text = ' '.join(str(value or '').split())
    if not text:
        return fallback
    if len(text) <= limit:
        return text
    return f'{text[: limit - 3].rstrip()}...'


def _evento_lista_destinos_display(evento):
    labels = []
    seen = set()
    for destino in evento.destinos.all():
        cidade = destino.cidade.nome if destino.cidade_id else ''
        uf = destino.estado.sigla if destino.estado_id else ''
        label = f'{cidade}/{uf}' if cidade and uf else cidade or uf
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return ', '.join(labels) if labels else 'Destino a definir'


def _format_period_range(data_inicio, data_fim, fallback='Periodo a definir'):
    if not data_inicio:
        return fallback
    if data_fim and data_fim != data_inicio:
        return f'{data_inicio:%d/%m/%Y} a {data_fim:%d/%m/%Y}'
    return f'{data_inicio:%d/%m/%Y}'


def _evento_lista_periodo_display(evento):
    return _format_period_range(evento.data_inicio, evento.data_fim)


def _evento_lista_tipos_display(evento):
    tipos = [tipo.nome for tipo in evento.tipos_demanda.all() if getattr(tipo, 'nome', '').strip()]
    return ' / '.join(tipos) if tipos else 'Tipo a definir'


def _evento_lista_temporal_meta(evento):
    today = timezone.localdate()
    if evento.status == Evento.STATUS_ARQUIVADO:
        return {'label': 'Arquivado', 'css_class': 'is-rascunho', 'theme_class': 'is-tone-red'}
    if evento.data_inicio and evento.data_fim and evento.data_inicio <= today <= evento.data_fim:
        label = 'Hoje' if evento.data_inicio == today and evento.data_fim == today else 'Em andamento'
        return {'label': label, 'css_class': 'is-trip-ongoing', 'theme_class': 'is-tone-orange'}
    if evento.data_inicio and evento.data_inicio > today:
        return {'label': 'Programado', 'css_class': 'is-trip-future', 'theme_class': 'is-tone-blue'}
    if evento.data_fim and evento.data_fim < today:
        return {'label': 'Encerrado', 'css_class': 'is-trip-past', 'theme_class': 'is-tone-accent'}
    return {'label': 'Sem periodo', 'css_class': 'is-rascunho', 'theme_class': 'is-tone-red'}


def _evento_lista_oficio_destinos_display(oficio):
    labels = []
    seen = set()
    for trecho in oficio.trechos.all():
        cidade = trecho.destino_cidade.nome if trecho.destino_cidade_id else ''
        uf = trecho.destino_estado.sigla if trecho.destino_estado_id else ''
        label = f'{cidade}/{uf}' if cidade and uf else cidade or uf
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return ', '.join(labels) if labels else 'Destino a definir'


def _build_evento_document_maps(eventos):
    event_ids = [evento.pk for evento in eventos]
    planos_map = {evento_id: [] for evento_id in event_ids}
    ordens_map = {evento_id: [] for evento_id in event_ids}
    if not event_ids:
        return planos_map, ordens_map

    planos = list(
        PlanoTrabalho.objects.select_related('evento', 'oficio', 'roteiro')
        .prefetch_related('oficios')
        .filter(Q(evento_id__in=event_ids) | Q(oficios__evento_id__in=event_ids))
        .distinct()
        .order_by('-updated_at', '-created_at')
    )
    for plano in planos:
        related_oficios = list(plano.get_oficios_relacionados()) if hasattr(plano, 'get_oficios_relacionados') else []
        target_ids = set()
        if plano.evento_id:
            target_ids.add(plano.evento_id)
        if plano.roteiro_id and plano.roteiro and plano.roteiro.evento_id:
            target_ids.add(plano.roteiro.evento_id)
        for oficio in related_oficios:
            if oficio.evento_id:
                target_ids.add(oficio.evento_id)
        meta_parts = []
        if plano.destinos_formatados_display:
            meta_parts.append(plano.destinos_formatados_display)
        if plano.evento_data_inicio:
            meta_parts.append(_format_period_range(plano.evento_data_inicio, plano.evento_data_fim))
        if plano.oficios_relacionados_display:
            meta_parts.append(f'Oficios {plano.oficios_relacionados_display}')
        item = {
            'title': f'PT {plano.numero_formatado or f"#{plano.pk}"}',
            'meta': ' | '.join(meta_parts) if meta_parts else 'Plano vinculado ao evento.',
            'url': reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': plano.pk}),
            'badge_label': plano.get_status_display(),
        }
        for event_id in sorted(target_ids):
            if event_id in planos_map:
                planos_map[event_id].append(item)

    ordens = list(
        OrdemServico.objects.select_related('evento', 'oficio')
        .filter(Q(evento_id__in=event_ids) | Q(oficio__evento_id__in=event_ids))
        .order_by('-updated_at', '-created_at')
    )
    for ordem in ordens:
        target_ids = set()
        if ordem.evento_id:
            target_ids.add(ordem.evento_id)
        if ordem.oficio_id and ordem.oficio and ordem.oficio.evento_id:
            target_ids.add(ordem.oficio.evento_id)
        meta_parts = []
        if ordem.oficio_id and ordem.oficio:
            meta_parts.append(f'Oficio {ordem.oficio.numero_formatado}')
        finalidade = _summarize_plain_text(ordem.finalidade, fallback='')
        if finalidade:
            meta_parts.append(finalidade)
        item = {
            'title': f'OS {ordem.numero_formatado or f"#{ordem.pk}"}',
            'meta': ' | '.join(meta_parts) if meta_parts else 'Ordem de servico vinculada ao evento.',
            'url': reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': ordem.pk}),
            'badge_label': ordem.get_status_display(),
        }
        for event_id in sorted(target_ids):
            if event_id in ordens_map:
                ordens_map[event_id].append(item)

    for event_id in event_ids:
        planos_map[event_id] = _distinct_items_by_pk(planos_map[event_id])
        ordens_map[event_id] = _distinct_items_by_pk(ordens_map[event_id])
    return planos_map, ordens_map


def _decorate_evento_list_items(eventos):
    planos_map, ordens_map = _build_evento_document_maps(eventos)
    for evento in eventos:
        temporal_meta = _evento_lista_temporal_meta(evento)
        oficios_items = []
        for oficio in evento.oficios.all():
            meta_parts = []
            if oficio.protocolo_formatado:
                meta_parts.append(f'Protocolo {oficio.protocolo_formatado}')
            destino_oficio = _evento_lista_oficio_destinos_display(oficio)
            if destino_oficio:
                meta_parts.append(destino_oficio)
            oficios_items.append(
                {
                    'title': f'Oficio {oficio.numero_formatado or f"#{oficio.pk}"}',
                    'meta': ' | '.join(meta_parts) if meta_parts else 'Oficio vinculado ao evento.',
                    'url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
                    'badge_label': oficio.get_status_display(),
                }
            )
        oficios_items = _distinct_items_by_pk(oficios_items)
        planos_items = planos_map.get(evento.pk, [])
        ordens_items = ordens_map.get(evento.pk, [])

        evento.destinos_display = _evento_lista_destinos_display(evento)
        evento.periodo_display = _evento_lista_periodo_display(evento)
        evento.tipos_display = _evento_lista_tipos_display(evento)
        evento.temporal_meta = temporal_meta
        evento.card_theme_class = temporal_meta['theme_class']
        evento.document_blocks = [
            {
                'title': 'Oficios',
                'count_label': f'{len(oficios_items)} vinculado(s)',
                'items': oficios_items,
                'empty_text': 'Nenhum oficio vinculado a este evento.',
            },
            {
                'title': 'Planos de trabalho',
                'count_label': f'{len(planos_items)} vinculado(s)',
                'items': planos_items,
                'empty_text': 'Nenhum plano de trabalho relacionado a este evento.',
            },
            {
                'title': 'Ordens de servico',
                'count_label': f'{len(ordens_items)} vinculada(s)',
                'items': ordens_items,
                'empty_text': 'Nenhuma ordem de servico relacionada a este evento.',
            },
        ]
        evento.document_counts_display = (
            f'{len(oficios_items)} oficios • {len(planos_items)} PT • {len(ordens_items)} OS'
        )
        evento.quick_actions = [
            {
                'label': 'Abrir fluxo guiado',
                'url': reverse('eventos:guiado-painel', kwargs={'pk': evento.pk}),
                'css_class': 'btn-doc-action--primary',
                'icon': 'bi-box-arrow-up-right',
            },
            {
                'label': 'Editar Etapa 1',
                'url': reverse('eventos:guiado-etapa-1', kwargs={'pk': evento.pk}),
                'css_class': 'btn-doc-action--secondary',
                'icon': 'bi-pencil-square',
            },
            {
                'label': 'Editar evento',
                'url': reverse('eventos:editar', kwargs={'pk': evento.pk}),
                'css_class': 'btn-doc-action--secondary',
                'icon': 'bi-pencil-square',
            },
        ]
        evento.delete_url = reverse('eventos:excluir', kwargs={'pk': evento.pk})


@login_required
def evento_lista(request):
    qs = Evento.objects.prefetch_related(
        'tipos_demanda',
        'destinos',
        'destinos__estado',
        'destinos__cidade',
        Prefetch(
            'oficios',
            queryset=(
                Oficio.objects.prefetch_related(
                    'trechos__destino_cidade',
                    'trechos__destino_estado',
                ).order_by('-updated_at', '-created_at')
            ),
        ),
    ).all()
    filters = {
        'q': (request.GET.get('q') or '').strip(),
        'status': (request.GET.get('status') or '').strip(),
        'tipo_id': (request.GET.get('tipo_id') or '').strip(),
        'date_from': (request.GET.get('date_from') or '').strip(),
        'date_to': (request.GET.get('date_to') or '').strip(),
        'order_by': (request.GET.get('order_by') or 'data_inicio').strip().lower(),
        'order_dir': (request.GET.get('order_dir') or 'desc').strip().lower(),
    }
    order_by_map = {
        'data_inicio': 'data_inicio',
        'updated_at': 'updated_at',
        'titulo': 'titulo',
        'status': 'status',
    }
    order_field = order_by_map.get(filters['order_by'], 'data_inicio')
    filters['order_dir'] = 'asc' if filters['order_dir'] == 'asc' else 'desc'
    if filters['order_dir'] == 'desc':
        order_field = f'-{order_field}'

    if filters['q']:
        qs = qs.filter(titulo__icontains=filters['q'])
    if filters['status']:
        qs = qs.filter(status=filters['status'])
    if filters['tipo_id']:
        qs = qs.filter(tipos_demanda__id=filters['tipo_id'])
    if filters['date_from']:
        try:
            qs = qs.filter(updated_at__date__gte=datetime.strptime(filters['date_from'], '%Y-%m-%d').date())
        except ValueError:
            pass
    if filters['date_to']:
        try:
            qs = qs.filter(updated_at__date__lte=datetime.strptime(filters['date_to'], '%Y-%m-%d').date())
        except ValueError:
            pass
    object_list = list(qs.distinct().order_by(order_field, '-created_at'))
    _decorate_evento_list_items(object_list)
    context = {
        'object_list': object_list,
        'filters': filters,
        'status_choices': Evento.STATUS_CHOICES,
        'tipos_demanda_list': TipoDemandaEvento.objects.filter(ativo=True).order_by('ordem', 'nome'),
        'order_by_choices': [
            ('data_inicio', 'Data de início'),
            ('updated_at', 'Atualização'),
            ('titulo', 'Título'),
            ('status', 'Status'),
        ],
        'order_dir_choices': DOCUMENT_LIST_ORDER_DIR_CHOICES,
        'evento_novo_url': reverse('eventos:guiado-novo'),
        'clear_filters_url': reverse('eventos:lista'),
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
    get_object_or_404(Evento, pk=pk)
    return redirect('eventos:editar', pk=pk)


@login_required
@require_http_methods(['POST'])
def evento_excluir(request, pk):
    """
    Exclui o evento somente se não houver vínculos impeditivos (roteiros).
    Evento finalizado não pode ser excluído.
    """
    evento = get_object_or_404(Evento, pk=pk)
    if _evento_esta_finalizado(evento):
        messages.error(
            request,
            'Evento finalizado não pode ser excluído. Apenas consulta é permitida.',
        )
        return redirect('eventos:guiado-painel', pk=evento.pk)
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
@require_http_methods(['POST'])
def guiado_novo(request):
    """Cria um evento em RASCUNHO e redireciona para a Etapa 1. Requer POST para evitar criação acidental."""
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
        Evento.objects.prefetch_related('tipos_demanda', 'destinos', 'anexos_solicitante').prefetch_related(
            'destinos__estado',
            'destinos__cidade',
        ),
        pk=pk,
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
        arquivos_convite = [f for f in request.FILES.getlist('convite_documentos') if getattr(f, 'name', '')]
        ok_arquivos, msg_arquivos = _validar_anexos_convite(arquivos_convite)
        destinos_post = _parse_destinos_post(request)
        ok_destinos, msg_destinos = _validar_destinos(destinos_post)
        if form.is_valid() and ok_destinos and ok_arquivos:
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
            _salvar_anexos_convite(ev, arquivos_convite)
            # Destinos: remover antigos e criar novos
            obj.destinos.all().delete()
            for ordem, (estado_id, cidade_id) in enumerate(destinos_post):
                EventoDestino.objects.create(evento=obj, estado_id=estado_id, cidade_id=cidade_id, ordem=ordem)
            if getattr(obj, '_prefetched_objects_cache', None) and 'destinos' in obj._prefetched_objects_cache:
                del obj._prefetched_objects_cache['destinos']
            if not ev.tem_convite_ou_oficio_evento and ev.anexos_solicitante.exists():
                ev.tem_convite_ou_oficio_evento = True
                ev.save(update_fields=['tem_convite_ou_oficio_evento'])
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
                return redirect('eventos:guiado-etapa-2', evento_id=obj.pk)
            return redirect('eventos:guiado-etapa-1', pk=obj.pk)
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        if not ok_arquivos:
            form.add_error(None, msg_arquivos)

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
        'anexos_convite': obj.anexos_solicitante.all().order_by('ordem', '-uploaded_at', 'id'),
        'destinos_atuais': destinos_atuais,
        'estado_pr': estado_pr,
        'estados': estados_qs,
        'estados_json': json.dumps(estados_list),
        'selected_tipos_pks': selected_tipos_pks,
        'tipo_outros_pk': tipo_outros_pk,
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
    }
    return render(request, 'eventos/guiado/etapa_1.html', context)


@login_required
@require_http_methods(['GET'])
def evento_anexo_visualizar(request, anexo_id):
    anexo = get_object_or_404(
        EventoAnexoSolicitante.objects.select_related('evento'),
        pk=anexo_id,
    )
    response = FileResponse(anexo.arquivo.open('rb'), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{slugify(anexo.nome_original) or "documento"}.pdf"'
    return response


@login_required
@require_http_methods(['GET'])
def evento_anexo_baixar(request, anexo_id):
    anexo = get_object_or_404(
        EventoAnexoSolicitante.objects.select_related('evento'),
        pk=anexo_id,
    )
    return FileResponse(
        anexo.arquivo.open('rb'),
        as_attachment=True,
        filename=anexo.nome_original or f'anexo-evento-{anexo.pk}.pdf',
        content_type='application/pdf',
    )


@login_required
@require_http_methods(['POST'])
def evento_anexo_remover(request, anexo_id):
    anexo = get_object_or_404(
        EventoAnexoSolicitante.objects.select_related('evento'),
        pk=anexo_id,
    )
    evento = anexo.evento
    arquivo = anexo.arquivo
    anexo.delete()
    if arquivo:
        arquivo.delete(save=False)
    if not evento.anexos_solicitante.exists() and evento.tem_convite_ou_oficio_evento:
        evento.tem_convite_ou_oficio_evento = False
        evento.save(update_fields=['tem_convite_ou_oficio_evento'])
    messages.success(request, 'Anexo removido com sucesso.')
    next_url = request.POST.get('next') or reverse('eventos:guiado-etapa-1', kwargs={'pk': evento.pk})
    return redirect(next_url)


def _evento_roteiros_ok(evento):
    """True se existir pelo menos 1 roteiro FINALIZADO do evento."""
    return RoteiroEvento.objects.filter(
        evento=evento,
        status=RoteiroEvento.STATUS_FINALIZADO,
    ).exists()


def _evento_roteiros_em_andamento(evento):
    """True quando existem roteiros cadastrados, mas nenhum finalizado."""
    if _evento_roteiros_ok(evento):
        return False
    return RoteiroEvento.objects.filter(evento=evento).exists()


def _build_evento_oficios_summary(evento):
    total = evento.oficios.count()
    finalizados = evento.oficios.filter(status=Oficio.STATUS_FINALIZADO).count()
    return {
        'total': total,
        'finalizados': finalizados,
        'rascunhos': max(total - finalizados, 0),
        'texto': (
            f'{total} ofício(s), {finalizados} finalizado(s), '
            f'{max(total - finalizados, 0)} rascunho(s)'
        ),
    }


def _evento_oficios_ok(evento):
    """
    True quando há ao menos um ofício e todos estão finalizados.
    """
    total = evento.oficios.count()
    if total == 0:
        return False
    return not evento.oficios.exclude(status=Oficio.STATUS_FINALIZADO).exists()


def _evento_oficios_em_andamento(evento):
    """True quando já existem ofícios, mas a etapa ainda não está concluída."""
    total = evento.oficios.count()
    if total == 0:
        return False
    return not _evento_oficios_ok(evento)


def _evento_pt_os_ok(evento):
    """True quando existe ao menos um PT/OS finalizado vinculado ao evento."""
    return (
        PlanoTrabalho.objects.filter(evento=evento, status=PlanoTrabalho.STATUS_FINALIZADO).exists()
        or OrdemServico.objects.filter(evento=evento, status=OrdemServico.STATUS_FINALIZADO).exists()
    )


def _evento_pt_os_em_andamento(evento):
    """True quando há PT/OS em rascunho vinculados ao evento."""
    return (
        PlanoTrabalho.objects.filter(evento=evento, status=PlanoTrabalho.STATUS_RASCUNHO).exists()
        or OrdemServico.objects.filter(evento=evento, status=OrdemServico.STATUS_RASCUNHO).exists()
    )


def _evento_justificativa_ok(evento):
    """True quando todo ofício que exige justificativa está com justificativa preenchida (ou não há ofícios)."""
    oficios = list(evento.oficios.all())
    if not oficios:
        return True
    for oficio in oficios:
        if oficio_exige_justificativa(oficio) and not oficio_tem_justificativa(oficio):
            return False
    return True


def _evento_sincronizar_participantes(evento, viajantes_ids=None):
    """
    Mantém participantes no nível do evento.
    Se viajantes_ids vier vazio/None, sincroniza a partir dos ofícios do evento.
    """
    if evento is None:
        return
    if viajantes_ids is None:
        viajantes_ids = {
            viajante_id
            for viajante_id in evento.oficios.values_list('viajantes', flat=True)
            if viajante_id is not None
        }
    else:
        viajantes_ids = {
            int(viajante_id)
            for viajante_id in viajantes_ids
            if str(viajante_id).isdigit()
        }
    if not viajantes_ids:
        return

    existentes = set(
        EventoParticipante.objects.filter(
            evento=evento,
            viajante_id__in=viajantes_ids,
        ).values_list('viajante_id', flat=True)
    )
    faltantes = sorted(viajantes_ids - existentes)
    if not faltantes:
        return

    max_ordem = (
        EventoParticipante.objects.filter(evento=evento).aggregate(max_ordem=Max('ordem')).get('max_ordem')
        or -1
    )
    novos = []
    for idx, viajante_id in enumerate(faltantes, start=1):
        novos.append(
            EventoParticipante(
                evento=evento,
                viajante_id=viajante_id,
                ordem=max_ordem + idx,
            )
        )
    EventoParticipante.objects.bulk_create(novos, ignore_conflicts=True)


def _evento_participantes_termo(evento):
    """
    Participantes no nível do evento, com status do termo (Etapa 3).
    Sincroniza automaticamente participantes vindos de ofícios.
    Cria EventoTermoParticipante pendente para quem ainda não tem.
    Retorna lista de tuplas (viajante, EventoTermoParticipante, lista de ofícios).
    """
    _evento_sincronizar_participantes(evento)
    participantes_qs = (
        EventoParticipante.objects.filter(evento=evento)
        .select_related('viajante', 'viajante__cargo')
        .order_by('ordem', 'viajante__nome')
    )
    resultado = []
    for participante in participantes_qs:
        v = participante.viajante
        termo, _ = EventoTermoParticipante.objects.get_or_create(
            evento=evento,
            viajante=v,
            defaults={
                'status': EventoTermoParticipante.STATUS_PENDENTE,
                'modalidade': EventoTermoParticipante.MODALIDADE_COMPLETO,
            },
        )
        oficios = list(evento.oficios.filter(viajantes=v).order_by('ano', 'numero', 'id'))
        resultado.append((v, termo, oficios))
    return resultado


def _evento_termos_ok(evento):
    """
    True quando há pelo menos um participante do evento e todos
    têm status DISPENSADO ou CONCLUIDO. Sem participantes, considera OK (nada a fazer).
    """
    _evento_sincronizar_participantes(evento)
    viajante_ids = set(
        EventoParticipante.objects.filter(evento=evento).values_list('viajante_id', flat=True)
    )
    if not viajante_ids:
        return True
    termos = EventoTermoParticipante.objects.filter(evento=evento, viajante_id__in=viajante_ids)
    if termos.count() < len(viajante_ids):
        return False  # algum participante sem registro = pendente
    return not termos.exclude(status__in=EventoTermoParticipante.STATUS_FINALIZADORES).exists()


def _evento_termos_em_andamento(evento):
    """True quando existe ao menos um participante com status definido (não pendente) mas etapa não concluída."""
    if _evento_termos_ok(evento):
        return False
    _evento_sincronizar_participantes(evento)
    viajante_ids = set(
        EventoParticipante.objects.filter(evento=evento).values_list('viajante_id', flat=True)
    )
    if not viajante_ids:
        return False
    return EventoTermoParticipante.objects.filter(
        evento=evento,
        viajante_id__in=viajante_ids,
    ).exclude(status=EventoTermoParticipante.STATUS_PENDENTE).exists()


def _normalizar_modalidade_termo(value):
    normalized = (value or '').strip().upper()
    if normalized == EventoTermoParticipante.MODALIDADE_SEMIPREENCHIDO:
        return EventoTermoParticipante.MODALIDADE_SEMIPREENCHIDO
    return EventoTermoParticipante.MODALIDADE_COMPLETO


def _normalizar_status_termo(value):
    normalized = (value or '').strip().upper()
    allowed = {
        EventoTermoParticipante.STATUS_PENDENTE,
        EventoTermoParticipante.STATUS_DISPENSADO,
        EventoTermoParticipante.STATUS_GERADO,
        EventoTermoParticipante.STATUS_CONCLUIDO,
    }
    return normalized if normalized in allowed else ''


def _get_termo_participante_evento(evento, viajante_id):
    participante = get_object_or_404(
        EventoParticipante.objects.select_related('viajante', 'viajante__cargo', 'viajante__unidade_lotacao'),
        evento=evento,
        viajante_id=viajante_id,
    )
    termo, _ = EventoTermoParticipante.objects.get_or_create(
        evento=evento,
        viajante=participante.viajante,
        defaults={
            'status': EventoTermoParticipante.STATUS_PENDENTE,
            'modalidade': EventoTermoParticipante.MODALIDADE_COMPLETO,
        },
    )
    oficios = list(evento.oficios.filter(viajantes=participante.viajante).order_by('ano', 'numero', 'id'))
    return participante.viajante, termo, oficios


def _build_termo_participante_filename(evento, viajante, formato):
    formato = (formato or 'docx').lower()
    sufixo = 'docx' if formato == 'docx' else 'pdf'
    nome_slug = slugify((viajante.nome or '').strip()) or f'viajante-{viajante.pk}'
    return f'termo_autorizacao_evento_{evento.pk}_{nome_slug}.{sufixo}'


def _build_termo_padrao_filename(evento, formato):
    formato = (formato or 'docx').lower()
    sufixo = 'docx' if formato == 'docx' else 'pdf'
    return f'termo_autorizacao_evento_{evento.pk}_padrao_branco.{sufixo}'


def _build_termo_viatura_lote_filename(evento, formato):
    return f'termos_evento_{evento.pk}_viatura.zip'


def _get_veiculos_termo_queryset():
    return Veiculo.objects.filter(status=Veiculo.STATUS_FINALIZADO).select_related('combustivel').order_by('modelo', 'placa')


def _get_viajantes_disponiveis_termo(evento):
    """Lista de servidores para geração de termos na etapa do evento."""
    _evento_sincronizar_participantes(evento)
    ids_participantes = list(
        EventoParticipante.objects.filter(evento=evento).values_list('viajante_id', flat=True)
    )
    base_qs = Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).select_related('cargo', 'unidade_lotacao')
    if ids_participantes:
        return base_qs.filter(pk__in=ids_participantes).order_by('nome')
    return base_qs.order_by('nome')


def _evento_esta_finalizado(evento):
    """
    True se o evento estiver finalizado (status FINALIZADO).
    Centralizado para uso em travas e, no futuro, reabertura.
    """
    return evento is not None and evento.status == Evento.STATUS_FINALIZADO


def _evento_pendencias_finalizacao(evento):
    """
    Retorna lista de mensagens de pendências que impedem a finalização do evento.
    Ordem funcional: 1 Dados, 2 Roteiros, 3 Termos, 4 PT/OS, 5 Ofícios, 6 Justificativa.
    """
    pendencias = []
    if not _evento_etapa1_completa(evento):
        pendencias.append('Etapa 1 (Dados do evento) não concluída.')
    if not _evento_roteiros_ok(evento):
        pendencias.append('Etapa 2 (Roteiros) não concluída. Cadastre ao menos um roteiro finalizado.')
    if not _evento_termos_ok(evento):
        pendencias.append(
            'Etapa 3 (Termos) não concluída. Defina status (Dispensado ou Concluído) para todos os participantes do evento.'
        )
    if not _evento_pt_os_ok(evento):
        pendencias.append('Etapa 4 (PT / OS) não concluída. Finalize ao menos um Plano de Trabalho ou uma Ordem de Serviço.')
    if not _evento_oficios_ok(evento):
        pendencias.append('Etapa 5 (Ofícios) não concluída. Finalize todos os ofícios vinculados ao evento.')
    if not _evento_justificativa_ok(evento):
        pendencias.append(
            'Etapa 6 (Justificativa) não concluída. Preencha a justificativa nos ofícios que exigem (prazo < 10 dias).'
        )
    return pendencias


def _evento_etapa2_ok(evento):
    """Compat: etapa antiga 2 = roteiros."""
    return _evento_roteiros_ok(evento)


def _evento_etapa3_ok(evento):
    """Compat: etapa antiga 3 = ofícios."""
    return _evento_oficios_ok(evento)


def _evento_etapa4_ok(evento):
    """Compat: etapa antiga 4 = PT/OS documentais."""
    return _evento_pt_os_ok(evento)


def _evento_etapa4_em_andamento(evento):
    """Compat: etapa antiga 4 = PT/OS documentais."""
    return _evento_pt_os_em_andamento(evento)


def _evento_etapa5_ok(evento):
    """Compat: etapa antiga 5 = termos."""
    return _evento_termos_ok(evento)


def _evento_etapa5_em_andamento(evento):
    """Compat: etapa antiga 5 = termos."""
    return _evento_termos_em_andamento(evento)


def _evento_etapa6_ok(evento):
    """True quando a finalização (Etapa 7) foi registrada (finalizado_em preenchido)."""
    try:
        return evento.finalizacao.concluido
    except EventoFinalizacao.DoesNotExist:
        return False


def _evento_etapa6_em_andamento(evento):
    """True quando existe registro da etapa 7 com observações mas ainda não finalizado."""
    try:
        fin = evento.finalizacao
        return not fin.concluido and bool((fin.observacoes_finais or '').strip())
    except EventoFinalizacao.DoesNotExist:
        return False


def _build_guiado_etapa_card(
    numero,
    nome,
    url,
    *,
    ok=False,
    em_breve=False,
    em_andamento=False,
    summary='',
    description='',
    cta_label='Abrir etapa',
):
    if em_breve:
        return {
            'numero': numero,
            'nome': nome,
            'ok': False,
            'em_breve': True,
            'em_andamento': False,
            'url': url,
            'summary': summary,
            'description': description,
            'cta_label': cta_label,
            'status_label': 'Em breve',
            'badge_class': 'is-muted',
            'theme_class': 'is-tone-gray',
        }
    if ok:
        status_label = 'Concluida'
        badge_class = 'is-ready'
        theme_class = 'is-tone-accent'
    elif em_andamento:
        status_label = 'Em andamento'
        badge_class = 'is-info'
        theme_class = 'is-tone-blue'
    else:
        status_label = 'Pendente'
        badge_class = 'is-warning'
        theme_class = 'is-tone-yellow'
    return {
        'numero': numero,
        'nome': nome,
        'ok': ok,
        'em_breve': em_breve,
        'em_andamento': em_andamento,
        'url': url,
        'summary': summary,
        'description': description,
        'cta_label': cta_label,
        'status_label': status_label,
        'badge_class': badge_class,
        'theme_class': theme_class,
    }


@login_required
def guiado_painel(request, pk):
    """Painel do evento guiado — ordem funcional real: 1 Dados, 2 Roteiros, 3 Termos, 4 PT/OS, 5 Ofícios, 6 Justificativa, 7 Finalização."""
    obj = get_object_or_404(
        Evento.objects.select_related('estado_principal', 'cidade_principal', 'cidade_base')
        .prefetch_related(
            'tipos_demanda',
            'destinos',
            Prefetch(
                'oficios',
                queryset=Oficio.objects.select_related('justificativa').prefetch_related('viajantes'),
            ),
            Prefetch(
                'roteiros',
                queryset=RoteiroEvento.objects.select_related('origem_cidade', 'origem_estado'),
            ),
            Prefetch('termos_autorizacao', queryset=TermoAutorizacao.objects.only('pk', 'status', 'evento_id')),
            Prefetch('planos_trabalho', queryset=PlanoTrabalho.objects.only('pk', 'status', 'evento_id')),
            Prefetch('ordens_servico', queryset=OrdemServico.objects.only('pk', 'status', 'evento_id')),
            'finalizacao',
            Prefetch('termos_participantes', queryset=EventoTermoParticipante.objects.select_related('viajante')),
        ),
        pk=pk
    )
    etapa1_ok = _evento_etapa1_completa(obj)
    etapa2_ok = _evento_roteiros_ok(obj)
    etapa2_em_andamento = _evento_roteiros_em_andamento(obj)
    etapa3_ok = _evento_termos_ok(obj)
    etapa3_em_andamento = _evento_termos_em_andamento(obj)
    etapa4_ok = _evento_pt_os_ok(obj)
    etapa4_em_andamento = _evento_pt_os_em_andamento(obj)
    etapa5_ok = _evento_oficios_ok(obj)
    etapa5_em_andamento = _evento_oficios_em_andamento(obj)
    etapa6_ok = _evento_justificativa_ok(obj)
    etapa7_ok = _evento_etapa6_ok(obj)
    etapa7_em_andamento = _evento_etapa6_em_andamento(obj)
    oficios_summary = _build_evento_oficios_summary(obj)
    termos_urls = _build_evento_termos_urls(obj)
    roteiros_total = len(obj.roteiros.all())
    termos_documentais_total = len(obj.termos_autorizacao.all())
    planos_total = len(obj.planos_trabalho.all())
    ordens_total = len(obj.ordens_servico.all())
    obj.destinos_display = _evento_lista_destinos_display(obj)
    obj.periodo_display = _evento_lista_periodo_display(obj)
    obj.tipos_display = _evento_lista_tipos_display(obj)
    obj.temporal_meta = _evento_lista_temporal_meta(obj)
    obj.card_theme_class = obj.temporal_meta['theme_class']
    obj.document_counts_display = (
        f'{oficios_summary["total"]} oficios • '
        f'{termos_documentais_total} termos • '
        f'{planos_total} PT • '
        f'{ordens_total} OS'
    )
    resumo_cards = [
        {'label': 'Roteiros', 'value': f'{roteiros_total} cadastrado(s)'},
        {'label': 'Termos', 'value': f'{termos_documentais_total} registro(s) no modulo documental'},
        {'label': 'PT / OS', 'value': f'{planos_total} PT • {ordens_total} OS'},
        {'label': 'Oficios', 'value': oficios_summary['texto']},
    ]
    etapas = [
        _build_guiado_etapa_card(
            1,
            'Dados do evento',
            reverse('eventos:guiado-etapa-1', kwargs={'pk': obj.pk}),
            ok=etapa1_ok,
            summary=obj.tipos_display,
            description='Base cadastral, periodo, destinos e tipo de demanda.',
            cta_label='Revisar dados',
        ),
        _build_guiado_etapa_card(
            2,
            'Roteiros',
            reverse('eventos:guiado-etapa-2', kwargs={'evento_id': obj.pk}),
            ok=etapa2_ok,
            em_andamento=etapa2_em_andamento,
            summary=f'{roteiros_total} roteiro(s) vinculado(s)' if roteiros_total else 'Nenhum roteiro cadastrado.',
            description='Planejamento operacional do deslocamento e da malha de destinos.',
            cta_label='Abrir roteiros',
        ),
        _build_guiado_etapa_card(
            3,
            'Termos',
            termos_urls['list_url'],
            ok=etapa3_ok,
            em_andamento=etapa3_em_andamento,
            summary=(
                f'{termos_documentais_total} termo(s) no modulo documental'
                if termos_documentais_total
                else 'A etapa agora usa o modulo documental real filtrado por evento.'
            ),
            description='Orquestracao para o modulo documental real de Termos de autorizacao.',
            cta_label='Abrir modulo',
        ),
        {'numero': 4, 'nome': 'Plano de Trabalho / Ordem de Serviço', 'ok': etapa4_ok, 'em_breve': False, 'em_andamento': etapa4_em_andamento, 'url': reverse('eventos:guiado-etapa-4', kwargs={'evento_id': obj.pk})},
        {'numero': 5, 'nome': 'Ofícios', 'ok': etapa5_ok, 'em_breve': False, 'em_andamento': etapa5_em_andamento, 'url': reverse('eventos:guiado-etapa-5', kwargs={'evento_id': obj.pk}), 'summary': oficios_summary['texto']},
        {'numero': 6, 'nome': 'Justificativa', 'ok': etapa6_ok, 'em_breve': False, 'em_andamento': False, 'url': reverse('eventos:guiado-etapa-6', kwargs={'evento_id': obj.pk})},
        {'numero': 7, 'nome': 'Finalização', 'ok': etapa7_ok, 'em_breve': False, 'em_andamento': etapa7_em_andamento, 'url': reverse('eventos:guiado-etapa-7', kwargs={'evento_id': obj.pk})},
    ]
    context = {
        'object': obj,
        'etapas': etapas,
        'etapa1_ok': etapa1_ok,
        'oficios_summary': oficios_summary,
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


@login_required
def plano_trabalho_atividades_lista(request):
    """Lista de atividades gerenciáveis do Plano de Trabalho."""
    lista = AtividadePlanoTrabalho.objects.all().order_by('ordem', 'nome')
    context = {
        'object_list': lista,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_atividades/lista.html', context)


@login_required
def plano_trabalho_atividades_cadastrar(request):
    """Cadastro de atividade do Plano de Trabalho com meta e recurso obrigatórios."""
    form = AtividadePlanoTrabalhoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Atividade cadastrada com sucesso.')
        return redirect('eventos:plano-trabalho-atividades-lista')
    context = {
        'form': form,
        'object': None,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_atividades/form.html', context)


@login_required
def plano_trabalho_atividades_editar(request, pk):
    """Edição de atividade do Plano de Trabalho."""
    obj = get_object_or_404(AtividadePlanoTrabalho, pk=pk)
    form = AtividadePlanoTrabalhoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Atividade atualizada com sucesso.')
        return redirect('eventos:plano-trabalho-atividades-lista')
    context = {
        'form': form,
        'object': obj,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_atividades/form.html', context)


@login_required
def plano_trabalho_atividades_excluir(request, pk):
    """Exclusão de atividade (bloqueia se em uso em Plano de Trabalho)."""
    obj = get_object_or_404(AtividadePlanoTrabalho, pk=pk)
    if request.method == 'POST':
        codigo = obj.codigo
        em_uso = PlanoTrabalho.objects.filter(
            Q(atividades_codigos=codigo)
            | Q(atividades_codigos__startswith=f'{codigo},')
            | Q(atividades_codigos__endswith=f',{codigo}')
            | Q(atividades_codigos__contains=f',{codigo},')
        ).exists()
        if em_uso:
            messages.error(request, 'Não é possível excluir: atividade em uso por pelo menos um Plano de Trabalho.')
            return redirect('eventos:plano-trabalho-atividades-editar', pk=obj.pk)
        obj.delete()
        messages.success(request, 'Atividade excluída com sucesso.')
        return redirect('eventos:plano-trabalho-atividades-lista')
    return render(
        request,
        'eventos/plano_trabalho_atividades/excluir_confirm.html',
        {'object': obj, 'hide_page_header': True},
    )


@login_required
def plano_trabalho_coordenadores_lista(request):
    """Lista de coordenadores operacionais do Plano de Trabalho."""
    lista = CoordenadorOperacional.objects.all().order_by('ordem', 'nome')
    context = {
        'object_list': lista,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_coordenadores/lista.html', context)


@login_required
def plano_trabalho_coordenadores_cadastrar(request):
    """Cadastro de coordenador operacional com estado/cidade."""
    form = CoordenadorOperacionalForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Coordenador cadastrado com sucesso.')
        return redirect('eventos:coordenadores-operacionais-lista')
    estado_parana = Estado.objects.filter(sigla__iexact='PR', ativo=True).first()
    context = {
        'form': form,
        'object': None,
        'hide_page_header': True,
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
        'estado_parana_id': estado_parana.pk if estado_parana else '',
    }
    return render(request, 'eventos/plano_trabalho_coordenadores/form.html', context)


@login_required
def plano_trabalho_coordenadores_editar(request, pk):
    """Edição de coordenador operacional."""
    obj = get_object_or_404(CoordenadorOperacional, pk=pk)
    form = CoordenadorOperacionalForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Coordenador atualizado com sucesso.')
        return redirect('eventos:coordenadores-operacionais-lista')
    estado_parana = Estado.objects.filter(sigla__iexact='PR', ativo=True).first()
    context = {
        'form': form,
        'object': obj,
        'hide_page_header': True,
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
        'estado_parana_id': estado_parana.pk if estado_parana else '',
    }
    return render(request, 'eventos/plano_trabalho_coordenadores/form.html', context)


@login_required
def plano_trabalho_coordenadores_excluir(request, pk):
    """Exclusão de coordenador operacional (bloqueia se estiver em uso em Plano de Trabalho)."""
    obj = get_object_or_404(CoordenadorOperacional, pk=pk)
    if request.method == 'POST':
        em_uso = PlanoTrabalho.objects.filter(
            Q(coordenador_operacional=obj) | Q(coordenadores=obj)
        ).exists()
        if em_uso:
            messages.error(request, 'Não é possível excluir: coordenador em uso por pelo menos um Plano de Trabalho.')
            return redirect('eventos:coordenadores-operacionais-editar', pk=obj.pk)
        obj.delete()
        messages.success(request, 'Coordenador excluído com sucesso.')
        return redirect('eventos:coordenadores-operacionais-lista')
    return render(
        request,
        'eventos/plano_trabalho_coordenadores/excluir_confirm.html',
        {'object': obj, 'hide_page_header': True},
    )


@login_required
def plano_trabalho_solicitantes_lista(request):
    """Lista de solicitantes gerenciáveis do Plano de Trabalho."""
    lista = SolicitantePlanoTrabalho.objects.all().order_by('ordem', 'nome')
    context = {
        'object_list': lista,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_solicitantes/lista.html', context)


@login_required
def plano_trabalho_solicitantes_cadastrar(request):
    """Cadastro de solicitante para uso no Plano de Trabalho."""
    form = SolicitantePlanoTrabalhoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Solicitante cadastrado com sucesso.')
        return redirect('eventos:plano-trabalho-solicitantes-lista')
    context = {
        'form': form,
        'object': None,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_solicitantes/form.html', context)


@login_required
def plano_trabalho_solicitantes_editar(request, pk):
    """Edição de solicitante do Plano de Trabalho."""
    obj = get_object_or_404(SolicitantePlanoTrabalho, pk=pk)
    form = SolicitantePlanoTrabalhoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Solicitante atualizado com sucesso.')
        return redirect('eventos:plano-trabalho-solicitantes-lista')
    context = {
        'form': form,
        'object': obj,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_solicitantes/form.html', context)


@login_required
def plano_trabalho_solicitantes_excluir(request, pk):
    """Exclusão de solicitante (bloqueia se estiver em uso em Plano de Trabalho)."""
    obj = get_object_or_404(SolicitantePlanoTrabalho, pk=pk)
    if request.method == 'POST':
        em_uso = PlanoTrabalho.objects.filter(solicitante=obj).exists()
        if em_uso:
            messages.error(request, 'Não é possível excluir: solicitante em uso por pelo menos um Plano de Trabalho.')
            return redirect('eventos:plano-trabalho-solicitantes-editar', pk=obj.pk)
        obj.delete()
        messages.success(request, 'Solicitante excluído com sucesso.')
        return redirect('eventos:plano-trabalho-solicitantes-lista')
    return render(
        request,
        'eventos/plano_trabalho_solicitantes/excluir_confirm.html',
        {'object': obj, 'hide_page_header': True},
    )


@login_required
def plano_trabalho_horarios_lista(request):
    """Lista de horários de atendimento gerenciáveis do Plano de Trabalho."""
    lista = HorarioAtendimentoPlanoTrabalho.objects.all().order_by('ordem', 'descricao')
    context = {
        'object_list': lista,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_horarios/lista.html', context)


@login_required
def plano_trabalho_horarios_cadastrar(request):
    """Cadastro de horário de atendimento para uso no Plano de Trabalho."""
    form = HorarioAtendimentoPlanoTrabalhoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Horário de atendimento cadastrado com sucesso.')
        return redirect('eventos:plano-trabalho-horarios-lista')
    context = {
        'form': form,
        'object': None,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_horarios/form.html', context)


@login_required
def plano_trabalho_horarios_editar(request, pk):
    """Edição de horário de atendimento do Plano de Trabalho."""
    obj = get_object_or_404(HorarioAtendimentoPlanoTrabalho, pk=pk)
    form = HorarioAtendimentoPlanoTrabalhoForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Horário de atendimento atualizado com sucesso.')
        return redirect('eventos:plano-trabalho-horarios-lista')
    context = {
        'form': form,
        'object': obj,
        'hide_page_header': True,
    }
    return render(request, 'eventos/plano_trabalho_horarios/form.html', context)


@login_required
def plano_trabalho_horarios_excluir(request, pk):
    """Exclusão de horário de atendimento (bloqueia se estiver em uso em Plano de Trabalho)."""
    obj = get_object_or_404(HorarioAtendimentoPlanoTrabalho, pk=pk)
    if request.method == 'POST':
        em_uso = PlanoTrabalho.objects.filter(horario_atendimento__iexact=obj.descricao).exists()
        if em_uso:
            messages.error(request, 'Não é possível excluir: horário em uso por pelo menos um Plano de Trabalho.')
            return redirect('eventos:plano-trabalho-horarios-editar', pk=obj.pk)
        obj.delete()
        messages.success(request, 'Horário de atendimento excluído com sucesso.')
        return redirect('eventos:plano-trabalho-horarios-lista')
    return render(
        request,
        'eventos/plano_trabalho_horarios/excluir_confirm.html',
        {'object': obj, 'hide_page_header': True},
    )


# ---------- Modelos de motivo (CRUD) ----------

def _modelos_motivo_lista_url(volta_step1=''):
    url = reverse('eventos:modelos-motivo-lista')
    volta = (volta_step1 or '').strip()
    if volta:
        return f'{url}?{urlencode({"volta_step1": volta})}'
    return url


def _append_query_params(url, **params):
    filtered = {}
    for key, value in params.items():
        normalized = str(value or '').strip()
        if normalized:
            filtered[key] = normalized
    if not filtered:
        return url
    return f'{url}?{urlencode(filtered)}'


def _build_evento_termos_urls(evento):
    panel_url = reverse('eventos:guiado-painel', kwargs={'pk': evento.pk})
    return {
        'panel_url': panel_url,
        'list_url': _append_query_params(
            reverse('eventos:documentos-termos'),
            evento_id=evento.pk,
        ),
        'new_url': _append_query_params(
            reverse('eventos:documentos-termos-novo'),
            context_source='evento',
            preselected_event_id=evento.pk,
            return_to=panel_url,
        ),
    }


DOCUMENT_LIST_ORDER_DIR_CHOICES = [
    ('desc', 'Decrescente'),
    ('asc', 'Crescente'),
]


def _resolve_document_list_ordering(order_by, order_dir, allowed_fields, default_key):
    order_key = (order_by or default_key).strip().lower()
    direction = (order_dir or 'desc').strip().lower()
    order_key = order_key if order_key in allowed_fields else default_key
    direction = 'asc' if direction == 'asc' else 'desc'
    field_name = allowed_fields[order_key]
    if direction == 'desc':
        field_name = f'-{field_name}'
    return order_key, direction, field_name


def _get_safe_next_url(request, default_url=''):
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
    if not next_url:
        return default_url
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default_url


@login_required
def modelos_motivo_lista(request):
    """Lista de modelos de motivo para uso no Step 1 do Ofício."""
    volta_step1 = request.GET.get('volta_step1', '')
    q = (request.GET.get('q') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    order_by = (request.GET.get('order_by') or 'nome').strip().lower()
    order_dir = (request.GET.get('order_dir') or 'asc').strip().lower()
    lista = ModeloMotivoViagem.objects.all()
    if q:
        lista = lista.filter(Q(nome__icontains=q) | Q(texto__icontains=q))
    if date_from:
        try:
            lista = lista.filter(updated_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            lista = lista.filter(updated_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    order_by, order_dir, ordering = _resolve_document_list_ordering(
        order_by,
        order_dir,
        {
            'nome': 'nome',
            'updated_at': 'updated_at',
            'created_at': 'created_at',
            'padrao': 'padrao',
        },
        'nome',
    )
    lista = lista.order_by(ordering, 'nome')
    context = {
        'object_list': lista,
        'volta_step1': volta_step1,
        'filters': {
            'q': q,
            'date_from': date_from,
            'date_to': date_to,
            'order_by': order_by,
            'order_dir': order_dir,
        },
        'order_by_choices': [
            ('nome', 'Nome'),
            ('updated_at', 'Atualizacao'),
            ('created_at', 'Criacao'),
            ('padrao', 'Padrao'),
        ],
        'order_dir_choices': DOCUMENT_LIST_ORDER_DIR_CHOICES,
        'clear_filters_url': _modelos_motivo_lista_url(volta_step1),
        'hide_page_header': True,
    }
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
    context = {
        'form': form,
        'object': None,
        'volta_step1': volta_step1,
        'hide_page_header': True,
    }
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
    context = {
        'form': form,
        'object': obj,
        'volta_step1': volta_step1,
        'hide_page_header': True,
    }
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
    context = {
        'object': obj,
        'volta_step1': volta_step1,
        'hide_page_header': True,
    }
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


# ---------- Modelos de justificativa (CRUD) ----------

def _modelos_justificativa_lista_url(volta_justificativa='', next_url=''):
    return _append_query_params(
        reverse('eventos:modelos-justificativa-lista'),
        volta_justificativa=volta_justificativa,
        next=next_url,
    )


def _oficio_justificativa_url(oficio, next_url=''):
    return _append_query_params(
        reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
        next=next_url,
    )


@login_required
def modelos_justificativa_lista(request):
    volta_justificativa = request.GET.get('volta_justificativa', '')
    next_url = _get_safe_next_url(request, '')
    q = (request.GET.get('q') or '').strip()
    date_from = (request.GET.get('date_from') or '').strip()
    date_to = (request.GET.get('date_to') or '').strip()
    order_by = (request.GET.get('order_by') or 'nome').strip().lower()
    order_dir = (request.GET.get('order_dir') or 'asc').strip().lower()
    lista = ModeloJustificativa.objects.filter(ativo=True)
    if q:
        lista = lista.filter(Q(nome__icontains=q) | Q(texto__icontains=q))
    if date_from:
        try:
            lista = lista.filter(updated_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass
    if date_to:
        try:
            lista = lista.filter(updated_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass
    order_by, order_dir, ordering = _resolve_document_list_ordering(
        order_by,
        order_dir,
        {
            'nome': 'nome',
            'updated_at': 'updated_at',
            'created_at': 'created_at',
            'padrao': 'padrao',
        },
        'nome',
    )
    lista = lista.order_by(ordering, 'nome')
    context = {
        'object_list': lista,
        'volta_justificativa': volta_justificativa,
        'next_url': next_url,
        'filters': {
            'q': q,
            'date_from': date_from,
            'date_to': date_to,
            'order_by': order_by,
            'order_dir': order_dir,
        },
        'order_by_choices': [
            ('nome', 'Nome'),
            ('updated_at', 'Atualizacao'),
            ('created_at', 'Criacao'),
            ('padrao', 'Padrao'),
        ],
        'order_dir_choices': DOCUMENT_LIST_ORDER_DIR_CHOICES,
        'clear_filters_url': _modelos_justificativa_lista_url(volta_justificativa, next_url),
    }
    return render(request, 'eventos/modelos_justificativa/lista.html', context)


@login_required
def modelos_justificativa_cadastrar(request):
    volta_justificativa = request.POST.get('volta_justificativa') or request.GET.get('volta_justificativa', '')
    next_url = _get_safe_next_url(request, '')
    form = ModeloJustificativaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Modelo de justificativa salvo com sucesso.')
        return redirect(_modelos_justificativa_lista_url(volta_justificativa, next_url))
    context = {
        'form': form,
        'object': None,
        'volta_justificativa': volta_justificativa,
        'next_url': next_url,
    }
    return render(request, 'eventos/modelos_justificativa/form.html', context)


@login_required
def modelos_justificativa_editar(request, pk):
    volta_justificativa = request.POST.get('volta_justificativa') or request.GET.get('volta_justificativa', '')
    next_url = _get_safe_next_url(request, '')
    obj = get_object_or_404(ModeloJustificativa, pk=pk)
    form = ModeloJustificativaForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Modelo de justificativa atualizado com sucesso.')
        return redirect(_modelos_justificativa_lista_url(volta_justificativa, next_url))
    context = {
        'form': form,
        'object': obj,
        'volta_justificativa': volta_justificativa,
        'next_url': next_url,
    }
    return render(request, 'eventos/modelos_justificativa/form.html', context)


@login_required
def modelos_justificativa_excluir(request, pk):
    volta_justificativa = request.POST.get('volta_justificativa') or request.GET.get('volta_justificativa', '')
    next_url = _get_safe_next_url(request, '')
    obj = get_object_or_404(ModeloJustificativa, pk=pk)
    if request.method == 'POST':
        nome = obj.nome
        obj.delete()
        messages.success(request, f'Modelo "{nome}" excluído com sucesso.')
        return redirect(_modelos_justificativa_lista_url(volta_justificativa, next_url))
    context = {
        'object': obj,
        'volta_justificativa': volta_justificativa,
        'next_url': next_url,
    }
    return render(request, 'eventos/modelos_justificativa/excluir_confirm.html', context)


@login_required
@require_http_methods(['POST'])
def modelos_justificativa_definir_padrao(request, pk):
    volta_justificativa = request.POST.get('volta_justificativa') or request.GET.get('volta_justificativa', '')
    next_url = _get_safe_next_url(request, '')
    obj = get_object_or_404(ModeloJustificativa, pk=pk)
    ModeloJustificativa.objects.exclude(pk=obj.pk).update(padrao=False)
    obj.padrao = True
    obj.save()
    messages.success(request, f'Modelo "{obj.nome}" definido como padrão.')
    return redirect(_modelos_justificativa_lista_url(volta_justificativa, next_url))


@login_required
def modelo_justificativa_texto_api(request, pk):
    modelo = get_object_or_404(ModeloJustificativa, pk=pk, ativo=True)
    return JsonResponse({'ok': True, 'texto': modelo.texto, 'nome': modelo.nome})


# ---------- Ofícios do evento (hub; etapa 5 no fluxo de negócio) ----------

@login_required
def guiado_etapa_3(request, evento_id):
    """Ofícios do evento (Etapa 5): listar ofícios, criar novo, editar (wizard)."""
    evento = get_object_or_404(Evento, pk=evento_id)
    oficios_qs = evento.oficios.prefetch_related('trechos').order_by('ano', 'numero', 'id')
    oficios = list(oficios_qs)
    for oficio in oficios:
        oficio.justificativa_info = _build_oficio_justificativa_info(oficio)
    oficios_summary = _build_evento_oficios_summary(evento)
    context = {
        'evento': evento,
        'object': evento,
        'oficios': oficios,
        'oficios_summary': oficios_summary,
    }
    return render(request, 'eventos/guiado/etapa_3.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def guiado_etapa_3_criar_oficio(request, evento_id):
    """
    Cria rascunho de ofício vinculado ao evento e redireciona para o Step 1 do wizard.

    Esta view é apenas um hub/orquestrador da Etapa 5: delega a criação para a
    view global de criação de ofício (`oficio_novo`), passando o evento_id.
    """
    evento = get_object_or_404(Evento, pk=evento_id)
    if request.method != 'POST':
        return redirect('eventos:guiado-etapa-5', evento_id=evento.pk)

    # Redireciona para a criação global, que centraliza a regra de contexto
    # (avulso vs. evento) e de tipo_origem.
    novo_url = f"{reverse('eventos:oficio-novo')}?evento_id={evento.pk}"
    return redirect(novo_url)


def _guiado_etapa_em_breve(request, evento_id, numero, nome):
    """Renderiza página 'Em breve' para etapa do evento ainda não implementada."""
    evento = get_object_or_404(Evento, pk=evento_id)
    return render(request, 'eventos/guiado/etapa_em_breve.html', {
        'evento': evento,
        'object': evento,
        'etapa_numero': numero,
        'etapa_nome': nome,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def guiado_etapa_4(request, evento_id):
    """PT / OS do evento (Etapa 4): apenas consumo dos cadastros reais de PT e OS."""
    evento = get_object_or_404(
        Evento.objects.prefetch_related('oficios', 'destinos', 'tipos_demanda', 'anexos_solicitante'),
        pk=evento_id,
    )

    oficios = list(evento.oficios.order_by('ano', 'numero', 'id'))
    for oficio in oficios:
        oficio.justificativa_info = _build_oficio_justificativa_info(oficio)

    planos = list(PlanoTrabalho.objects.filter(evento=evento).select_related('oficio').order_by('-updated_at'))
    ordens = list(OrdemServico.objects.filter(evento=evento).select_related('oficio').order_by('-updated_at'))

    return_to = reverse('eventos:guiado-etapa-4', kwargs={'evento_id': evento.pk})
    novo_pt_url = (
        f"{reverse('eventos:documentos-planos-trabalho-novo')}?"
        f"context_source=evento&preselected_event_id={evento.pk}&return_to={quote(return_to)}"
    )
    novo_os_url = (
        f"{reverse('eventos:documentos-ordens-servico-novo')}?"
        f"context_source=evento&preselected_event_id={evento.pk}&return_to={quote(return_to)}"
    )

    context = {
        'evento': evento,
        'object': evento,
        'oficios': oficios,
        'anexos_convite': evento.anexos_solicitante.all().order_by('ordem', '-uploaded_at', 'id'),
        'planos_trabalho': planos,
        'ordens_servico': ordens,
        'novo_plano_trabalho_url': novo_pt_url,
        'nova_ordem_servico_url': novo_os_url,
        'return_to': return_to,
    }
    return render(request, 'eventos/guiado/etapa_4.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def guiado_etapa_5(request, evento_id):
    """Termos (Etapa 3): controle por participante no nível do evento."""
    evento = get_object_or_404(
        Evento.objects.prefetch_related('oficios', 'destinos', 'tipos_demanda'),
        pk=evento_id,
    )
    evento_apenas_consulta = _evento_esta_finalizado(evento)
    if request.method == 'POST' and evento_apenas_consulta:
        messages.error(
            request,
            'Evento finalizado. Não é possível alterar os termos.',
        )
        return redirect('eventos:guiado-painel', pk=evento.pk)

    oficios = list(evento.oficios.order_by('ano', 'numero', 'id'))
    participantes = _evento_participantes_termo(evento)

    if request.method == 'POST':
        updated = 0
        acao_participante = (request.POST.get('acao_participante') or '').strip()
        if ':' in acao_participante:
            acao, viajante_id_raw = acao_participante.split(':', 1)
            if str(viajante_id_raw).isdigit():
                viajante_id = int(viajante_id_raw)
                for viajante, termo, _oficios in participantes:
                    if viajante.pk != viajante_id:
                        continue
                    new_status = termo.status
                    if acao == 'dispensar':
                        new_status = EventoTermoParticipante.STATUS_DISPENSADO
                    elif acao == 'concluir':
                        new_status = EventoTermoParticipante.STATUS_CONCLUIDO
                    elif acao == 'reabrir':
                        new_status = EventoTermoParticipante.STATUS_PENDENTE
                    if new_status != termo.status:
                        termo.status = new_status
                        termo.save(update_fields=['status', 'updated_at'])
                        updated += 1
                    break
        else:
            acao_lote = _normalizar_status_termo(request.POST.get('acao_lote'))
            if acao_lote:
                for _viajante, termo, _oficios in participantes:
                    if termo.status != acao_lote:
                        termo.status = acao_lote
                        termo.save(update_fields=['status', 'updated_at'])
                        updated += 1
            else:
                for viajante, termo, _oficios in participantes:
                    status_key = f'status_{viajante.pk}'
                    modalidade_key = f'modalidade_{viajante.pk}'
                    new_status = _normalizar_status_termo(request.POST.get(status_key)) or termo.status
                    new_modalidade = _normalizar_modalidade_termo(request.POST.get(modalidade_key))
                    update_fields = []
                    if new_status != termo.status:
                        termo.status = new_status
                        update_fields.append('status')
                    if new_modalidade != termo.modalidade:
                        termo.modalidade = new_modalidade
                        update_fields.append('modalidade')
                    if update_fields:
                        update_fields.append('updated_at')
                        termo.save(update_fields=update_fields)
                        updated += 1
        if updated:
            messages.success(request, 'Termos atualizados com sucesso.')
        voltar = request.POST.get('voltar_painel')
        if voltar:
            return redirect('eventos:guiado-painel', pk=evento.pk)
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    total_participantes = len(participantes)
    termos_concluidos = sum(1 for _v, t, _o in participantes if t.status == EventoTermoParticipante.STATUS_CONCLUIDO)
    termos_dispensados = sum(1 for _v, t, _o in participantes if t.status == EventoTermoParticipante.STATUS_DISPENSADO)
    termos_gerados = sum(1 for _v, t, _o in participantes if t.status == EventoTermoParticipante.STATUS_GERADO)
    termos_pendentes = sum(1 for _v, t, _o in participantes if t.status == EventoTermoParticipante.STATUS_PENDENTE)
    template_status = get_termo_autorizacao_templates_availability()
    pdf_backend_status = get_pdf_backend_availability()
    veiculos = list(_get_veiculos_termo_queryset())
    viajantes_disponiveis = list(_get_viajantes_disponiveis_termo(evento))
    participantes_rows = []
    for viajante, termo, oficios_part in participantes:
        participantes_rows.append(
            {
                'viajante': viajante,
                'termo': termo,
                'oficios': oficios_part,
                'rg': getattr(viajante, 'rg_formatado', '') or '—',
                'cpf': getattr(viajante, 'cpf_formatado', '') or '—',
                'telefone': getattr(viajante, 'telefone_formatado', '') or '—',
                'lotacao': (getattr(getattr(viajante, 'unidade_lotacao', None), 'nome', '') or '—'),
                'download_docx_url': reverse(
                    'eventos:guiado-etapa-3-termo-download',
                    kwargs={
                        'evento_id': evento.pk,
                        'viajante_id': viajante.pk,
                        'formato': 'docx',
                    },
                ),
                'download_pdf_url': reverse(
                    'eventos:guiado-etapa-3-termo-download',
                    kwargs={
                        'evento_id': evento.pk,
                        'viajante_id': viajante.pk,
                        'formato': 'pdf',
                    },
                ),
            }
        )

    context = {
        'evento': evento,
        'object': evento,
        'oficios': oficios,
        'participantes': participantes_rows,
        'status_choices': EventoTermoParticipante.STATUS_CHOICES,
        'modalidade_choices': EventoTermoParticipante.MODALIDADE_CHOICES,
        'total_participantes': total_participantes,
        'termos_concluidos': termos_concluidos,
        'termos_dispensados': termos_dispensados,
        'termos_gerados': termos_gerados,
        'termos_pendentes': termos_pendentes,
        'termo_templates_available': template_status['available'],
        'termo_template_errors': template_status['errors'],
        'pdf_backend_available': pdf_backend_status['available'],
        'pdf_backend_message': pdf_backend_status['message'],
        'evento_apenas_consulta': evento_apenas_consulta,
        'veiculos': veiculos,
        'viajantes_disponiveis': viajantes_disponiveis,
        'termo_padrao_docx_url': reverse('eventos:guiado-etapa-3-termo-padrao-download', kwargs={'evento_id': evento.pk, 'formato': 'docx'}),
        'termo_padrao_pdf_url': reverse('eventos:guiado-etapa-3-termo-padrao-download', kwargs={'evento_id': evento.pk, 'formato': 'pdf'}),
        'termo_viatura_docx_url': reverse('eventos:guiado-etapa-3-termo-viatura-download', kwargs={'evento_id': evento.pk, 'formato': 'docx'}),
        'termo_viatura_pdf_url': reverse('eventos:guiado-etapa-3-termo-viatura-download', kwargs={'evento_id': evento.pk, 'formato': 'pdf'}),
    }
    return render(request, 'eventos/guiado/etapa_5.html', context)


@login_required
@require_http_methods(['GET'])
def guiado_etapa_5_termo_download(request, evento_id, viajante_id, formato):
    evento = get_object_or_404(
        Evento.objects.prefetch_related('oficios', 'destinos', 'tipos_demanda'),
        pk=evento_id,
    )
    formato = (formato or '').strip().lower()
    if formato not in {'docx', 'pdf'}:
        raise Http404('Formato de documento inválido.')

    _evento_sincronizar_participantes(evento)
    viajante, termo, oficios_relacionados = _get_termo_participante_evento(evento, viajante_id)
    if termo.status == EventoTermoParticipante.STATUS_DISPENSADO:
        messages.error(request, 'Participante dispensado de termo. Reabra o termo para gerar o documento.')
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    validation_errors = validate_evento_participante_termo_data(
        evento,
        viajante,
        termo.modalidade,
    )
    if validation_errors:
        messages.error(request, validation_errors[0])
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    template_status = get_termo_autorizacao_templates_availability()
    if not template_status['available']:
        messages.error(request, template_status['errors'][0])
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    try:
        docx_bytes = render_evento_participante_termo_docx(
            evento,
            viajante,
            termo.modalidade,
            oficios_relacionados,
        )
        payload = docx_bytes
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if formato == 'pdf':
            payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
            content_type = 'application/pdf'
    except (DocumentGenerationError, DocumentRendererUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    if not _evento_esta_finalizado(evento):
        if termo.status not in {
            EventoTermoParticipante.STATUS_CONCLUIDO,
            EventoTermoParticipante.STATUS_DISPENSADO,
        }:
            termo.status = EventoTermoParticipante.STATUS_GERADO
        termo.ultimo_formato_gerado = formato
        termo.ultima_geracao_em = timezone.now()
        termo.save(update_fields=['status', 'ultimo_formato_gerado', 'ultima_geracao_em', 'updated_at'])

    filename = _build_termo_participante_filename(evento, viajante, formato)
    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def guiado_etapa_5_termo_padrao_download(request, evento_id, formato):
    evento = get_object_or_404(
        Evento.objects.prefetch_related('destinos', 'tipos_demanda'),
        pk=evento_id,
    )
    formato = (formato or '').strip().lower()
    if formato not in {'docx', 'pdf'}:
        raise Http404('Formato de documento inválido.')
    validation_errors = validate_evento_participante_termo_data(
        evento,
        viajante=None,
        modalidade=TERMO_MODALIDADE_SEMIPREENCHIDO,
    )
    if validation_errors:
        messages.error(request, validation_errors[0])
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    template_status = get_termo_autorizacao_templates_availability()
    if not template_status['available']:
        messages.error(request, template_status['errors'][0])
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    try:
        docx_bytes = render_evento_termo_padrao_branco_docx(evento)
        payload = docx_bytes
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if formato == 'pdf':
            payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
            content_type = 'application/pdf'
    except (DocumentGenerationError, DocumentRendererUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{_build_termo_padrao_filename(evento, formato)}"'
    return response


@login_required
@require_http_methods(['POST'])
def guiado_etapa_5_termo_viatura_lote_download(request, evento_id, formato):
    evento = get_object_or_404(
        Evento.objects.prefetch_related('destinos', 'tipos_demanda'),
        pk=evento_id,
    )
    formato = (formato or '').strip().lower()
    if formato not in {'docx', 'pdf'}:
        raise Http404('Formato de documento inválido.')

    veiculo_id_raw = (request.POST.get('veiculo_id') or '').strip()
    viajantes_ids_raw = request.POST.getlist('viajantes')
    viajantes_ids = [int(v) for v in viajantes_ids_raw if str(v).isdigit()]
    if not veiculo_id_raw.isdigit():
        messages.error(request, 'Selecione uma viatura para gerar termos completos por viatura.')
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)
    if not viajantes_ids:
        messages.error(request, 'Selecione ao menos um servidor para gerar termos por viatura.')
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    veiculo = get_object_or_404(_get_veiculos_termo_queryset(), pk=int(veiculo_id_raw))
    evento_apenas_consulta = _evento_esta_finalizado(evento)
    if evento_apenas_consulta:
        participantes_ids = set(
            EventoParticipante.objects.filter(evento=evento).values_list('viajante_id', flat=True)
        )
        if not set(viajantes_ids).issubset(participantes_ids):
            messages.error(
                request,
                'Evento finalizado: gere apenas termos de participantes já vinculados ao evento.',
            )
            return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)
    else:
        _evento_sincronizar_participantes(evento, viajantes_ids=viajantes_ids)

    viajantes = list(
        Viajante.objects.filter(pk__in=viajantes_ids).select_related('cargo', 'unidade_lotacao').order_by('nome')
    )
    if not viajantes:
        messages.error(request, 'Não foi possível localizar os servidores selecionados.')
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    template_status = get_termo_autorizacao_templates_availability()
    if not template_status['available']:
        messages.error(request, template_status['errors'][0])
        return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)

    files_payload = []
    for viajante in viajantes:
        errors = validate_evento_participante_termo_data(
            evento,
            viajante,
            TERMO_MODALIDADE_COMPLETO,
        )
        if errors:
            messages.error(request, errors[0])
            return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)
        termo, _ = EventoTermoParticipante.objects.get_or_create(
            evento=evento,
            viajante=viajante,
            defaults={
                'status': EventoTermoParticipante.STATUS_PENDENTE,
                'modalidade': EventoTermoParticipante.MODALIDADE_COMPLETO,
            },
        )
        termo.modalidade = EventoTermoParticipante.MODALIDADE_COMPLETO
        if not evento_apenas_consulta:
            termo.save(update_fields=['modalidade', 'updated_at'])
        try:
            docx_bytes = render_evento_participante_termo_docx(
                evento,
                viajante,
                TERMO_MODALIDADE_COMPLETO,
                list(evento.oficios.filter(viajantes=viajante).order_by('ano', 'numero', 'id')),
                veiculo_override=veiculo,
            )
            payload = docx_bytes
            if formato == 'pdf':
                payload = convert_docx_bytes_to_pdf_bytes(docx_bytes)
        except (DocumentGenerationError, DocumentRendererUnavailable) as exc:
            messages.error(request, str(exc))
            return redirect('eventos:guiado-etapa-3', evento_id=evento.pk)
        filename = _build_termo_participante_filename(evento, viajante, formato)
        files_payload.append((filename, payload))
        if not evento_apenas_consulta:
            termo.status = EventoTermoParticipante.STATUS_GERADO
            termo.ultimo_formato_gerado = formato
            termo.ultima_geracao_em = timezone.now()
            termo.save(update_fields=['status', 'ultimo_formato_gerado', 'ultima_geracao_em', 'updated_at'])

    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, mode='w', compression=ZIP_DEFLATED) as zip_file:
        for filename, payload in files_payload:
            zip_file.writestr(filename, payload)
    zip_bytes = zip_buffer.getvalue()
    response = HttpResponse(zip_bytes, content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="{_build_termo_viatura_lote_filename(evento, formato)}"'
    )
    return response


@login_required
@require_http_methods(['GET'])
def guiado_etapa_6_justificativa(request, evento_id):
    """Etapa 6 — Justificativa: exigida quando prazo entre data-base e data do evento < 10 dias; lista ofícios que precisam preencher."""
    evento = get_object_or_404(
        Evento.objects.prefetch_related('oficios', 'destinos', 'tipos_demanda'),
        pk=evento_id,
    )
    oficios = list(evento.oficios.order_by('ano', 'numero', 'id'))
    prazo_minimo = get_prazo_justificativa_dias()
    oficios_com_status = []
    for oficio in oficios:
        exige = oficio_exige_justificativa(oficio)
        preenchida = oficio_tem_justificativa(oficio)
        dias = get_dias_antecedencia_oficio(oficio)
        oficios_com_status.append({
            'oficio': oficio,
            'exige_justificativa': exige,
            'justificativa_preenchida': preenchida,
            'dias_antecedencia': dias,
            'ok': not exige or preenchida,
        })
    justificativa_ok = _evento_justificativa_ok(evento)
    context = {
        'evento': evento,
        'object': evento,
        'oficios_com_status': oficios_com_status,
        'prazo_minimo': prazo_minimo,
        'justificativa_ok': justificativa_ok,
    }
    return render(request, 'eventos/guiado/etapa_6_justificativa.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def guiado_etapa_6(request, evento_id):
    """Etapa 7 — Finalização: checklist, pendências, observações finais e ação de finalizar evento."""
    evento = get_object_or_404(
        Evento.objects.prefetch_related('oficios', 'destinos', 'tipos_demanda'),
        pk=evento_id,
    )
    if request.method == 'POST' and _evento_esta_finalizado(evento):
        messages.error(
            request,
            'Evento já está finalizado. Não é possível alterar a finalização.',
        )
        return redirect('eventos:guiado-painel', pk=evento.pk)

    finalizacao, _ = EventoFinalizacao.objects.get_or_create(
        evento=evento,
        defaults={'observacoes_finais': ''},
    )
    pendencias = _evento_pendencias_finalizacao(evento)
    pode_finalizar = len(pendencias) == 0 and not finalizacao.concluido
    etapa1_ok = _evento_etapa1_completa(evento)
    etapa2_ok = _evento_roteiros_ok(evento)
    etapa3_ok = _evento_termos_ok(evento)
    etapa4_ok = _evento_pt_os_ok(evento)
    etapa5_ok = _evento_oficios_ok(evento)
    etapa6_ok = _evento_justificativa_ok(evento)
    oficios_count = evento.oficios.count()
    roteiros_count = evento.roteiros.count()
    participantes_count = EventoParticipante.objects.filter(evento=evento).count()
    oficios = list(evento.oficios.order_by('ano', 'numero', 'id'))

    if request.method == 'POST':
        form = EventoFinalizacaoForm(request.POST, instance=finalizacao)
        if form.is_valid():
            form.save()
            if request.POST.get('finalizar') and pode_finalizar:
                finalizacao.refresh_from_db()
                finalizacao.finalizado_em = timezone.now()
                finalizacao.finalizado_por = request.user
                finalizacao.save()
                if evento.status != Evento.STATUS_FINALIZADO:
                    evento.status = Evento.STATUS_FINALIZADO
                    evento.save(update_fields=['status'])
                messages.success(request, 'Evento finalizado com sucesso.')
                return redirect('eventos:guiado-painel', pk=evento.pk)
            messages.success(request, 'Observações finais salvas.')
            if request.POST.get('voltar_painel'):
                return redirect('eventos:guiado-painel', pk=evento.pk)
            return redirect('eventos:guiado-etapa-7', evento_id=evento.pk)
    else:
        form = EventoFinalizacaoForm(instance=finalizacao)

    context = {
        'evento': evento,
        'object': evento,
        'finalizacao': finalizacao,
        'form': form,
        'pendencias': pendencias,
        'pode_finalizar': pode_finalizar,
        'etapa1_ok': etapa1_ok,
        'etapa2_ok': etapa2_ok,
        'etapa3_ok': etapa3_ok,
        'etapa4_ok': etapa4_ok,
        'etapa5_ok': etapa5_ok,
        'etapa6_ok': etapa6_ok,
        'oficios_count': oficios_count,
        'roteiros_count': roteiros_count,
        'participantes_count': participantes_count,
        'oficios': oficios,
    }
    return render(request, 'eventos/guiado/etapa_6.html', context)


@login_required
def oficio_editar(request, pk):
    """Redireciona para o Step 1 do wizard do ofício."""
    return redirect('eventos:oficio-step1', pk=pk)


@login_required
@require_http_methods(['GET'])
def oficio_novo(request):
    """
    Cria um novo ofício em rascunho e redireciona para o Step 1 do wizard.

    - Sem evento_id na querystring => ofício avulso (tipo_origem = AVULSO).
    - Com evento_id válido         => ofício vinculado ao evento (tipo_origem = EVENTO).
    """
    evento_id_raw = request.GET.get('evento_id')
    evento = None
    if evento_id_raw:
        try:
            evento = Evento.objects.get(pk=int(evento_id_raw))
        except (ValueError, Evento.DoesNotExist):
            evento = None

    if evento:
        oficio = Oficio.objects.create(
            evento=evento,
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_EVENTO,
        )
    else:
        oficio = Oficio.objects.create(
            evento=None,
            status=Oficio.STATUS_RASCUNHO,
            tipo_origem=Oficio.ORIGEM_AVULSO,
        )
    messages.success(request, 'Ofício criado. Preencha os dados no wizard.')
    return redirect('eventos:oficio-step1', pk=oficio.pk)


def _oficio_redirect_pos_exclusao(oficio):
    """Redireciona sempre para a lista global de oficios."""
    return reverse('eventos:oficios-global')


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_excluir(request, pk):
    """Exclusão segura de ofício com redirecionamento coerente."""
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    redirect_url = _oficio_redirect_pos_exclusao(oficio)
    if request.method == 'POST':
        if oficio.evento_id and _evento_esta_finalizado(oficio.evento):
            messages.error(
                request,
                'Não é possível excluir ofício vinculado a evento finalizado.',
            )
            return redirect(redirect_url)
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

def _get_oficio_or_404_for_user(pk, user=None):
    """
    Carrega o ofício com as relações necessárias para o wizard.

    Nesta fase, ofícios finalizados continuam editáveis e qualquer usuário autenticado
    pode operar o fluxo; o parâmetro `user` centraliza um eventual endurecimento futuro.
    """
    queryset = Oficio.objects.prefetch_related('viajantes', 'trechos').select_related(
        'evento',
        'veiculo',
        'motorista_viajante',
        'modelo_motivo',
        'roteiro_evento',
        'carona_oficio_referencia',
    )
    return get_object_or_404(queryset, pk=pk)


def _save_oficio_preserving_status(oficio, update_fields):
    """
    Steps 1–3 podem editar um ofício finalizado sem rebaixar o status nesta fase.
    """
    fields = [field for field in update_fields if field != 'status']
    oficio.save(update_fields=list(dict.fromkeys([*fields, 'updated_at'])))


def _is_autosave_request(request):
    return (
        request.method == 'POST'
        and request.POST.get('autosave') == '1'
        and request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )


def _autosave_success_response(extra=None):
    payload = {
        'ok': True,
        'saved_at': timezone.localtime().strftime('%H:%M:%S'),
    }
    if extra:
        payload.update(extra)
    return JsonResponse(payload)


def _build_oficio_wizard_steps(oficio, current_key, justificativa_info=None):
    justificativa_info = justificativa_info or _build_oficio_justificativa_info(oficio)
    resumo_url = reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk})
    justificativa_required = bool(justificativa_info.get('required'))
    justificativa_text = str(justificativa_info.get('texto') or '').strip()
    steps = [
        {
            'key': 'step1',
            'number': 1,
            'label': 'Dados e viajantes',
            'url': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
        },
        {
            'key': 'step2',
            'number': 2,
            'label': 'Transporte',
            'url': reverse('eventos:oficio-step2', kwargs={'pk': oficio.pk}),
        },
        {
            'key': 'step3',
            'number': 3,
            'label': 'Roteiro e diárias',
            'url': reverse('eventos:oficio-step3', kwargs={'pk': oficio.pk}),
        },
        {
            'key': 'justificativa',
            'number': 4,
            'label': 'Justificativa',
            'url': reverse('eventos:oficio-justificativa', kwargs={'pk': oficio.pk}),
        },
        {
            'key': 'summary',
            'number': 5,
            'label': 'Resumo e termos',
            'url': resumo_url,
        },
    ]
    current_step = next((item for item in steps if item['key'] == current_key), None)
    current_number = current_step['number'] if current_step else 0
    for item in steps:
        item['active'] = item['key'] == current_key
        if item['active']:
            item['state'] = 'active'
        elif item['key'] == 'justificativa' and not justificativa_required and not justificativa_text:
            item['state'] = 'optional'
        elif item['number'] < current_number:
            item['state'] = 'completed'
        else:
            item['state'] = 'pending'
        item['state_label'] = {
            'active': 'Etapa atual',
            'completed': 'Concluído',
            'optional': 'Opcional',
            'pending': 'Pendente',
        }.get(item['state'], 'Pendente')
    return steps


def _build_oficio_wizard_glance_data(oficio, step1_preview=None, step2_preview=None, step3_preview=None):
    step1_preview = step1_preview or _build_oficio_step1_preview(oficio)
    if step2_preview is None:
        step2_form = OficioStep2Form(initial=_build_oficio_step2_initial(oficio), oficio=oficio)
        step2_preview = _build_step2_preview_data(oficio, step2_form)
    if step3_preview is None:
        saved_state = _get_oficio_step3_saved_state(oficio)
        if saved_state:
            try:
                diarias_resultado = _calculate_step3_diarias_from_state(oficio, saved_state)
            except ValueError:
                diarias_resultado = _build_step3_diarias_fallback(oficio)
        else:
            diarias_resultado = _build_step3_diarias_fallback(oficio)
        step3_preview = _build_oficio_step3_preview(oficio, saved_state, diarias_resultado=diarias_resultado)

    viajantes = step1_preview.get('viajantes') or []
    evento = oficio.evento
    if evento and evento.data_inicio:
        inicio = evento.data_inicio.strftime('%d/%m/%Y')
        fim = evento.data_fim.strftime('%d/%m/%Y') if evento.data_fim else ''
        data_label = inicio if not fim or fim == inicio else f'{inicio} até {fim}'
    else:
        data_label = step3_preview.get('periodo_display') or ''
    return {
        'oficio': step1_preview.get('oficio') or '',
        'protocolo': format_protocolo(step1_preview.get('protocolo') or ''),
        'viajantes_count': len(viajantes),
        'viajantes': [
            {
                'nome': getattr(v, 'nome', '') or '',
                'cargo': getattr(getattr(v, 'cargo', None), 'nome', '') or '',
                'lotacao': getattr(getattr(v, 'unidade_lotacao', None), 'nome', '') or '',
            }
            for v in viajantes
            if getattr(v, 'nome', '').strip()
        ],
        'destino': step3_preview.get('destino_principal') or '',
        'data_evento': data_label,
    }


def _apply_oficio_wizard_context(context, oficio, current_key, page_title, justificativa_info=None):
    step1_preview = context.get('step1_preview')
    step2_preview = context.get('step2_preview')
    step3_preview = context.get('step3_preview')
    context.update(
        {
            'hide_page_header': True,
            'wizard_page_title': page_title,
            'wizard_header_title': page_title,
            'wizard_header_subtitle': 'Fluxo guiado com resumo essencial integrado ao topo e sem atalhos soltos no cabeçalho.',
            'wizard_steps': _build_oficio_wizard_steps(
                oficio,
                current_key,
                justificativa_info=justificativa_info,
            ),
            'wizard_glance': _build_oficio_wizard_glance_data(
                oficio,
                step1_preview=step1_preview,
                step2_preview=step2_preview,
                step3_preview=step3_preview,
            ),
        }
    )
    return context


def _normalizar_ids_inteiros(raw_values):
    ids = []
    vistos = set()
    for raw_value in raw_values or []:
        value = str(raw_value).strip()
        if not value.isdigit() or value in vistos:
            continue
        vistos.add(value)
        ids.append(int(value))
    return ids


def _carregar_viajantes_por_ids(viajantes_ids):
    if not viajantes_ids:
        return []
    queryset = Viajante.objects.select_related('cargo', 'unidade_lotacao').filter(pk__in=viajantes_ids)
    viajantes_por_id = {viajante.pk: viajante for viajante in queryset}
    return [viajantes_por_id[pk] for pk in viajantes_ids if pk in viajantes_por_id]


def _serializar_viajante_oficio(viajante):
    return serializar_viajante_para_autocomplete(viajante)


def _build_custeio_preview_text(custeio_tipo, nome_instituicao=''):
    texto = dict(Oficio.CUSTEIO_CHOICES).get(custeio_tipo, custeio_tipo or '')
    instituicao = str(nome_instituicao or '').strip()
    if custeio_tipo == Oficio.CUSTEIO_OUTRA_INSTITUICAO and instituicao:
        texto = f'{texto} - {instituicao}'
    return texto


def _build_oficio_step1_preview(oficio):
    viajantes_ids = list(oficio.viajantes.values_list('pk', flat=True))
    selected_viajantes = _carregar_viajantes_por_ids(viajantes_ids)
    data_criacao = (
        oficio.data_criacao
        or (timezone.localtime(oficio.created_at).date() if oficio.created_at else None)
    )
    return {
        'oficio': oficio.numero_formatado or '',
        'protocolo': format_protocolo(oficio.protocolo or ''),
        'data_criacao': data_criacao.strftime('%d/%m/%Y') if data_criacao else '',
        'motivo': oficio.motivo or '',
        'custeio': _build_custeio_preview_text(oficio.custeio_tipo or Oficio.CUSTEIO_UNIDADE, oficio.nome_instituicao_custeio),
        'viajantes': selected_viajantes,
    }


def _build_oficio_step1_initial(oficio):
    data_criacao_exibicao = (
        oficio.data_criacao
        or (timezone.localtime(oficio.created_at).date() if oficio.created_at else timezone.localdate())
    )
    modelo_inicial = oficio.modelo_motivo
    if not modelo_inicial:
        modelo_inicial = ModeloMotivoViagem.objects.filter(padrao=True).order_by('nome').first()
    return {
        'oficio_numero': oficio.numero_formatado if oficio.numero and oficio.ano else '',
        'protocolo': Oficio.format_protocolo(oficio.protocolo or ''),
        'data_criacao': data_criacao_exibicao,
        'modelo_motivo': modelo_inicial.pk if modelo_inicial else None,
        'motivo': oficio.motivo or (modelo_inicial.texto if modelo_inicial else ''),
        'custeio_tipo': oficio.custeio_tipo or Oficio.CUSTEIO_UNIDADE,
        'nome_instituicao_custeio': oficio.nome_instituicao_custeio or '',
        'viajantes': list(oficio.viajantes.values_list('pk', flat=True)),
    }


def _viajantes_step1_ids_para_contexto(request, oficio):
    if request.method == 'POST':
        return _normalizar_ids_inteiros(request.POST.getlist('viajantes'))
    return list(oficio.viajantes.values_list('pk', flat=True))


def _autosave_oficio_step1(oficio, request):
    modelo_motivo = None
    modelo_motivo_id = _parse_int(request.POST.get('modelo_motivo'))
    if modelo_motivo_id:
        modelo_motivo = ModeloMotivoViagem.objects.filter(pk=modelo_motivo_id).first()
    custeio_tipo = request.POST.get('custeio_tipo') or Oficio.CUSTEIO_UNIDADE
    if custeio_tipo not in dict(Oficio.CUSTEIO_CHOICES):
        custeio_tipo = Oficio.CUSTEIO_UNIDADE
    assunto_tipo = request.POST.get('assunto_tipo') or Oficio.ASSUNTO_TIPO_AUTORIZACAO
    if assunto_tipo not in dict(Oficio.ASSUNTO_TIPO_CHOICES):
        assunto_tipo = Oficio.ASSUNTO_TIPO_AUTORIZACAO
    data_criacao = request.POST.get('data_criacao') or ''
    try:
        data_criacao_value = datetime.strptime(data_criacao, '%d/%m/%Y').date() if data_criacao else None
    except ValueError:
        try:
            data_criacao_value = datetime.strptime(data_criacao, '%Y-%m-%d').date() if data_criacao else None
        except ValueError:
            data_criacao_value = None
    viajantes_ids = _normalizar_ids_inteiros(request.POST.getlist('viajantes'))
    viajantes = list(Viajante.objects.filter(pk__in=viajantes_ids))

    oficio.protocolo = Oficio.normalize_protocolo(request.POST.get('protocolo') or '')
    oficio.data_criacao = data_criacao_value or oficio.data_criacao or timezone.localdate()
    oficio.modelo_motivo = modelo_motivo
    oficio.motivo = (request.POST.get('motivo') or '').strip()
    oficio.assunto_tipo = oficio.compute_assunto_tipo()
    oficio.custeio_tipo = custeio_tipo
    oficio.nome_instituicao_custeio = (
        (request.POST.get('nome_instituicao_custeio') or '').strip()
        if custeio_tipo == Oficio.CUSTEIO_OUTRA_INSTITUICAO
        else ''
    )
    _save_oficio_preserving_status(
        oficio,
        [
            'protocolo',
            'data_criacao',
            'modelo_motivo',
            'motivo',
            'assunto_tipo',
            'custeio_tipo',
            'nome_instituicao_custeio',
        ],
    )
    oficio.viajantes.set(viajantes)
    if oficio.evento_id:
        _evento_sincronizar_participantes(
            oficio.evento,
            viajantes_ids=[viajante.pk for viajante in viajantes],
        )


@login_required
@require_http_methods(['GET'])
def oficio_step1_viajantes_api(request):
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'results': []})
    viajantes = buscar_viajantes_finalizados(q, limit=20)
    return JsonResponse({'results': [_serializar_viajante_oficio(viajante) for viajante in viajantes]})


@login_required
@require_http_methods(['GET'])
def oficio_step2_motoristas_api(request):
    q = (request.GET.get('q') or '').strip()
    if not q:
        return JsonResponse({'results': []})
    motoristas = buscar_viajantes_finalizados(q, limit=20)
    return JsonResponse({'results': [_serializar_viajante_oficio(motorista) for motorista in motoristas]})


def _bloquear_edicao_oficio_se_evento_finalizado(request, oficio):
    """
    Regra atual: mesmo que o evento esteja finalizado, a edição de ofícios continua permitida.
    Mantemos esta função por compatibilidade, mas ela não bloqueia mais a edição.
    """
    return False


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step1(request, pk):
    """Wizard Step 1 — Dados gerais + viajantes (fiel ao legado)."""
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    if _bloquear_edicao_oficio_se_evento_finalizado(request, oficio):
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    evento = oficio.evento
    if _is_autosave_request(request):
        _autosave_oficio_step1(oficio, request)
        return _autosave_success_response()
    initial = _build_oficio_step1_initial(oficio)
    selected_viajantes_ids = _viajantes_step1_ids_para_contexto(request, oficio)
    if selected_viajantes_ids:
        initial['viajantes'] = selected_viajantes_ids
    form = OficioStep1Form(
        request.POST or None,
        initial=initial,
        selected_viajantes_ids=selected_viajantes_ids,
    )
    selected_viajantes = _carregar_viajantes_por_ids(selected_viajantes_ids)
    selected_viajantes_payload = [
        _serializar_viajante_oficio(viajante)
        for viajante in selected_viajantes
    ]
    if request.method == 'POST' and form.is_valid():
        oficio.protocolo = form.cleaned_data.get('protocolo') or ''
        oficio.data_criacao = (
            form.cleaned_data.get('data_criacao')
            or oficio.data_criacao
            or timezone.localdate()
        )
        oficio.modelo_motivo = form.cleaned_data.get('modelo_motivo')
        oficio.motivo = (form.cleaned_data.get('motivo') or '').strip()
        oficio.assunto_tipo = oficio.compute_assunto_tipo()
        oficio.custeio_tipo = form.cleaned_data.get('custeio_tipo') or Oficio.CUSTEIO_UNIDADE
        oficio.nome_instituicao_custeio = (form.cleaned_data.get('nome_instituicao_custeio') or '').strip()
        _save_oficio_preserving_status(oficio, [
            'protocolo', 'data_criacao', 'modelo_motivo',
            'motivo', 'assunto_tipo', 'custeio_tipo', 'nome_instituicao_custeio',
        ])
        viajantes_oficio = form.cleaned_data.get('viajantes') or []
        oficio.viajantes.set(viajantes_oficio)
        if evento:
            _evento_sincronizar_participantes(
                evento,
                viajantes_ids=[viajante.pk for viajante in viajantes_oficio],
            )

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
            _save_oficio_preserving_status(oficio, ['modelo_motivo'])
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
    custeio_preview_text = dict(Oficio.CUSTEIO_CHOICES).get(custeio_atual, custeio_atual or '')
    instituicao_preview = (
        form.data.get('nome_instituicao_custeio')
        if form.is_bound
        else (initial.get('nome_instituicao_custeio') or '')
    )
    if mostrar_nome_instituicao and str(instituicao_preview or '').strip():
        custeio_preview_text = f"{custeio_preview_text} - {str(instituicao_preview).strip()}"

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
        'custeio_preview_text': custeio_preview_text,
        'buscar_viajantes_url': reverse('eventos:oficio-step1-viajantes-api'),
        'selected_viajantes': selected_viajantes,
        'selected_viajantes_payload': selected_viajantes_payload,
    }
    return render(
        request,
        'eventos/oficio/wizard_step1.html',
        _apply_oficio_wizard_context(context, oficio, 'step1', 'Dados e viajantes'),
    )


@login_required
@require_http_methods(['GET', 'POST'])
def _legacy_oficio_step2(request, pk):
    """Wizard Step 2 — Transporte. Placa, modelo, combustível obrigatórios; motorista carona exige ofício/protocolo."""
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    evento = oficio.evento
    initial = {
        'placa': oficio.placa or '',
        'modelo': oficio.modelo or '',
        'combustivel': oficio.combustivel or '',
        'tipo_viatura': oficio.tipo_viatura or Oficio.TIPO_VIATURA_DESCARACTERIZADA,
        'porte_transporte_armas': oficio.porte_transporte_armas,
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
        oficio.porte_transporte_armas = bool(form.cleaned_data.get('porte_transporte_armas'))
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
            'placa', 'modelo', 'combustivel', 'tipo_viatura', 'porte_transporte_armas', 'motorista_viajante_id', 'motorista',
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


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_step3_date(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_step3_time(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:5], '%H:%M').time().replace(second=0, microsecond=0)
    except ValueError:
        return None


def _step3_date_input(value):
    if not value:
        return ''
    if isinstance(value, str):
        return value
    return value.strftime('%Y-%m-%d')


def _step3_time_input(value):
    if not value:
        return ''
    if isinstance(value, str):
        return value[:5]
    return value.strftime('%H:%M')


def _step3_local_label(cidade=None, estado=None):
    cidade_nome = ''
    estado_sigla = ''
    if cidade:
        cidade_nome = cidade.nome
        estado_sigla = getattr(getattr(cidade, 'estado', None), 'sigla', '') or estado_sigla
    if estado and not estado_sigla:
        estado_sigla = estado.sigla
    if cidade_nome and estado_sigla:
        return f'{cidade_nome}/{estado_sigla}'
    return cidade_nome or estado_sigla or ''


def _step3_get_local_parts(cidade=None, estado=None, nome=''):
    cidade_nome = ''
    estado_sigla = ''
    if cidade:
        cidade_nome = getattr(cidade, 'nome', '') or ''
        estado_sigla = getattr(getattr(cidade, 'estado', None), 'sigla', '') or ''
    if estado and not estado_sigla:
        estado_sigla = getattr(estado, 'sigla', '') or ''
    if nome and not cidade_nome:
        raw_nome = str(nome or '').strip()
        if '/' in raw_nome:
            cidade_nome, _, maybe_uf = raw_nome.partition('/')
            if not estado_sigla:
                estado_sigla = maybe_uf.strip().upper()
        else:
            cidade_nome = raw_nome
    return cidade_nome.strip(), estado_sigla.strip().upper()


def _step3_locations_equivalent(*, cidade_a=None, estado_a=None, nome_a='', cidade_b=None, estado_b=None, nome_b=''):
    cidade_a_nome, estado_a_sigla = _step3_get_local_parts(cidade=cidade_a, estado=estado_a, nome=nome_a)
    cidade_b_nome, estado_b_sigla = _step3_get_local_parts(cidade=cidade_b, estado=estado_b, nome=nome_b)
    return locations_equivalent(cidade_a_nome, estado_a_sigla, cidade_b_nome, estado_b_sigla)


def _build_step3_bate_volta_diario_state(data=None):
    payload = data or {}
    return {
        'ativo': bool(payload.get('ativo')),
        'data_inicio': payload.get('data_inicio') or '',
        'data_fim': payload.get('data_fim') or '',
        'ida_saida_hora': payload.get('ida_saida_hora') or '',
        'ida_tempo_min': payload.get('ida_tempo_min') or '',
        'volta_saida_hora': payload.get('volta_saida_hora') or '',
        'volta_tempo_min': payload.get('volta_tempo_min') or '',
    }


def _extract_step3_posted_trechos(request):
    pattern = re.compile(r'^trecho_(\d+)_(.+)$')
    indexed = {}
    for key in request.POST:
        match = pattern.match(key)
        if not match:
            continue
        idx = int(match.group(1))
        field_name = match.group(2)
        indexed.setdefault(idx, {})[field_name] = request.POST.get(key)
    return [indexed[idx] for idx in sorted(indexed)]


def _infer_step3_destinos_from_trechos(raw_trechos, sede_estado=None, sede_cidade=None):
    destinos = []
    seen = set()
    for trecho in raw_trechos or []:
        destino_estado_id = _parse_int(trecho.get('destino_estado_id'))
        destino_cidade_id = _parse_int(trecho.get('destino_cidade_id'))
        destino_nome = trecho.get('destino_nome') or ''
        destino_cidade = Cidade.objects.select_related('estado').filter(pk=destino_cidade_id, ativo=True).first() if destino_cidade_id else None
        destino_estado = Estado.objects.filter(pk=destino_estado_id or getattr(destino_cidade, 'estado_id', None), ativo=True).first() if (destino_estado_id or destino_cidade) else None
        if _step3_locations_equivalent(
            cidade_a=destino_cidade,
            estado_a=destino_estado,
            nome_a=destino_nome,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        ):
            continue
        key = (destino_estado_id, destino_cidade_id, str(destino_nome or '').strip().upper())
        if key in seen:
            continue
        seen.add(key)
        destinos.append(
            {
                'estado_id': destino_estado_id,
                'cidade_id': destino_cidade_id,
                'estado': destino_estado,
                'cidade': destino_cidade,
            }
        )
    return destinos


def _step3_has_intermediate_return_to_sede(state):
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(state.get('sede_cidade_id')), ativo=True).first()
    sede_estado = Estado.objects.filter(pk=_parse_int(state.get('sede_estado_id')) or getattr(sede_cidade, 'estado_id', None), ativo=True).first()
    if not sede_cidade and not sede_estado:
        return False
    return any(
        _step3_locations_equivalent(
            cidade_a=Cidade.objects.select_related('estado').filter(pk=_parse_int(trecho.get('destino_cidade_id')), ativo=True).first(),
            estado_a=Estado.objects.filter(pk=_parse_int(trecho.get('destino_estado_id')), ativo=True).first(),
            nome_a=trecho.get('destino_nome') or '',
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        )
        for trecho in (state.get('trechos') or [])
    )


def _step3_format_date_time_br(data_value, hora_value):
    data_obj = data_value if hasattr(data_value, 'strftime') and not isinstance(data_value, str) else _parse_step3_date(data_value)
    hora_obj = hora_value if hasattr(hora_value, 'strftime') and not isinstance(hora_value, str) else _parse_step3_time(hora_value)
    partes = []
    if data_obj:
        partes.append(data_obj.strftime('%d/%m/%Y'))
    if hora_obj:
        partes.append(hora_obj.strftime('%H:%M'))
    return ' '.join(partes)


def _split_route_datetime(dt):
    if not dt:
        return '', ''
    if getattr(dt, 'tzinfo', None):
        dt = timezone.localtime(dt)
    return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M')


def _destinos_para_template(destinos_list):
    if not destinos_list:
        return []
    estado_ids = {estado_id for estado_id, _ in destinos_list if estado_id}
    cidade_ids = {cidade_id for _, cidade_id in destinos_list if cidade_id}
    estados_map = {obj.pk: obj for obj in Estado.objects.filter(pk__in=estado_ids, ativo=True)}
    cidades_map = {
        obj.pk: obj
        for obj in Cidade.objects.select_related('estado').filter(pk__in=cidade_ids, ativo=True)
    }
    return [
        {
            'estado_id': estado_id,
            'cidade_id': cidade_id,
            'estado': estados_map.get(estado_id),
            'cidade': cidades_map.get(cidade_id),
        }
        for estado_id, cidade_id in destinos_list
    ]


def _build_step3_state_from_estrutura(estrutura, destinos_atuais, sede_estado_id, sede_cidade_id, seed_source_label=''):
    trechos = []
    retorno = {
        'origem_nome': '',
        'destino_nome': '',
        'saida_cidade': '',
        'chegada_cidade': '',
        'saida_data': '',
        'saida_hora': '',
        'chegada_data': '',
        'chegada_hora': '',
        'distancia_km': '',
        'duracao_estimada_min': '',
        'tempo_cru_estimado_min': '',
        'tempo_adicional_min': 0,
        'rota_fonte': '',
    }
    for item in estrutura or []:
        saida_data, saida_hora = _split_route_datetime(item.get('saida_dt'))
        chegada_data, chegada_hora = _split_route_datetime(item.get('chegada_dt'))
        tempo_adicional = item.get('tempo_adicional_min') or 0
        mapped = {
            'ordem': item.get('ordem', 0),
            'origem_nome': item.get('origem_nome') or '',
            'destino_nome': item.get('destino_nome') or '',
            'origem_estado_id': item.get('origem_estado_id'),
            'origem_cidade_id': item.get('origem_cidade_id'),
            'destino_estado_id': item.get('destino_estado_id'),
            'destino_cidade_id': item.get('destino_cidade_id'),
            'saida_data': saida_data,
            'saida_hora': saida_hora,
            'chegada_data': chegada_data,
            'chegada_hora': chegada_hora,
            'distancia_km': _step3_decimal_input(item.get('distancia_km')),
            'duracao_estimada_min': item.get('duracao_estimada_min'),
            'tempo_cru_estimado_min': _step3_resolve_travel_minutes(
                item.get('tempo_cru_estimado_min'),
                item.get('duracao_estimada_min'),
                tempo_adicional,
            ),
            'tempo_adicional_min': tempo_adicional,
            'rota_fonte': item.get('rota_fonte') or '',
        }
        if item.get('tipo') == RoteiroEventoTrecho.TIPO_RETORNO:
            retorno.update(
                {
                    'origem_nome': mapped['origem_nome'],
                    'destino_nome': mapped['destino_nome'],
                    'saida_cidade': mapped['origem_nome'],
                    'chegada_cidade': mapped['destino_nome'],
                    'saida_data': mapped['saida_data'],
                    'saida_hora': mapped['saida_hora'],
                    'chegada_data': mapped['chegada_data'],
                    'chegada_hora': mapped['chegada_hora'],
                    'distancia_km': mapped['distancia_km'],
                    'duracao_estimada_min': mapped['duracao_estimada_min'],
                    'tempo_cru_estimado_min': mapped['tempo_cru_estimado_min'],
                    'tempo_adicional_min': mapped['tempo_adicional_min'],
                    'rota_fonte': mapped['rota_fonte'],
                }
            )
            continue
        trechos.append(mapped)
    return {
        'roteiro_modo': Oficio.ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': None,
        'roteiro_evento_label': '',
        'sede_estado_id': sede_estado_id,
        'sede_cidade_id': sede_cidade_id,
        'destinos_atuais': destinos_atuais,
        'trechos': trechos,
        'retorno': retorno,
        'bate_volta_diario': _build_step3_bate_volta_diario_state(),
        'seed_source_label': seed_source_label,
    }


def _parse_step3_decimal(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        if ',' in raw and '.' in raw:
            if raw.rfind(',') > raw.rfind('.'):
                raw = raw.replace('.', '').replace(',', '.')
            else:
                raw = raw.replace(',', '')
        else:
            raw = raw.replace(',', '.')
        return Decimal(raw)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _step3_decimal_input(value):
    decimal_value = _parse_step3_decimal(value)
    if decimal_value is None:
        return ''
    return f'{decimal_value.quantize(Decimal("0.01")):.2f}'


def _step3_resolve_travel_minutes(raw_minutes, total_minutes, additional_minutes=0):
    value = _parse_int(raw_minutes)
    if value is not None:
        return value
    total = _parse_int(total_minutes)
    additional = _parse_int(additional_minutes) or 0
    if total is None:
        return ''
    return max(total - additional, 0)


def _build_step3_roteiro_label(roteiro):
    origem = _step3_local_label(roteiro.origem_cidade, roteiro.origem_estado) or 'Sede não informada'
    destinos = [
        _step3_local_label(destino.cidade, destino.estado)
        for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'id')
    ]
    resumo = ' -> '.join(destinos[:3]) if destinos else 'Sem destinos'
    if len(destinos) > 3:
        resumo += ' -> ...'
    return f'Roteiro #{roteiro.pk} - {origem} -> {resumo}'


def _serialize_step3_state(state):
    retorno = state.get('retorno') or {}
    return {
        'roteiro_modo': state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': state.get('roteiro_evento_id'),
        'roteiro_evento_label': state.get('roteiro_evento_label') or '',
        'sede_estado_id': state.get('sede_estado_id'),
        'sede_cidade_id': state.get('sede_cidade_id'),
        'destinos_atuais': [
            {
                'estado_id': item.get('estado_id'),
                'cidade_id': item.get('cidade_id'),
            }
            for item in (state.get('destinos_atuais') or [])
        ],
        'trechos': [
            {
                'ordem': trecho.get('ordem', 0),
                'origem_nome': trecho.get('origem_nome') or '',
                'destino_nome': trecho.get('destino_nome') or '',
                'origem_estado_id': trecho.get('origem_estado_id'),
                'origem_cidade_id': trecho.get('origem_cidade_id'),
                'destino_estado_id': trecho.get('destino_estado_id'),
                'destino_cidade_id': trecho.get('destino_cidade_id'),
                'saida_data': trecho.get('saida_data') or '',
                'saida_hora': trecho.get('saida_hora') or '',
                'chegada_data': trecho.get('chegada_data') or '',
                'chegada_hora': trecho.get('chegada_hora') or '',
                'distancia_km': _step3_decimal_input(trecho.get('distancia_km')),
                'duracao_estimada_min': trecho.get('duracao_estimada_min'),
                'tempo_cru_estimado_min': trecho.get('tempo_cru_estimado_min'),
                'tempo_adicional_min': trecho.get('tempo_adicional_min') or 0,
                'rota_fonte': trecho.get('rota_fonte') or '',
            }
            for trecho in (state.get('trechos') or [])
        ],
        'retorno': {
            'origem_nome': retorno.get('origem_nome') or '',
            'destino_nome': retorno.get('destino_nome') or '',
            'saida_cidade': retorno.get('saida_cidade') or '',
            'chegada_cidade': retorno.get('chegada_cidade') or '',
            'saida_data': retorno.get('saida_data') or '',
            'saida_hora': retorno.get('saida_hora') or '',
            'chegada_data': retorno.get('chegada_data') or '',
            'chegada_hora': retorno.get('chegada_hora') or '',
            'distancia_km': _step3_decimal_input(retorno.get('distancia_km')),
            'duracao_estimada_min': retorno.get('duracao_estimada_min') or '',
            'tempo_cru_estimado_min': retorno.get('tempo_cru_estimado_min') or '',
            'tempo_adicional_min': retorno.get('tempo_adicional_min') or 0,
            'rota_fonte': retorno.get('rota_fonte') or '',
        },
        'bate_volta_diario': _build_step3_bate_volta_diario_state(state.get('bate_volta_diario')),
        'seed_source_label': state.get('seed_source_label') or '',
    }


def _build_step3_empty_state(oficio, roteiro_modo=None, seed_source_label='', roteiro_evento_id=None, roteiro_evento_label=''):
    sede_cidade = None
    sede_estado = None
    if oficio.evento_id:
        sede_cidade = oficio.evento.cidade_base or oficio.evento.cidade_principal
        sede_estado = getattr(sede_cidade, 'estado', None) or oficio.evento.estado_principal
    if not sede_cidade and not sede_estado:
        config = ConfiguracaoSistema.get_singleton()
        sede_cidade = getattr(config, 'cidade_sede_padrao', None) if config else None
        sede_estado = getattr(sede_cidade, 'estado', None)
    return {
        'roteiro_modo': roteiro_modo or Oficio.ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': roteiro_evento_id,
        'roteiro_evento_label': roteiro_evento_label or '',
        'sede_estado_id': sede_estado.pk if sede_estado else None,
        'sede_cidade_id': sede_cidade.pk if sede_cidade else None,
        'destinos_atuais': [{'estado_id': None, 'cidade_id': None, 'estado': None, 'cidade': None}],
        'trechos': [],
        'retorno': {
            'origem_nome': '',
            'destino_nome': _step3_local_label(sede_cidade, sede_estado),
            'saida_cidade': '',
            'chegada_cidade': _step3_local_label(sede_cidade, sede_estado),
            'saida_data': '',
            'saida_hora': '',
            'chegada_data': '',
            'chegada_hora': '',
            'distancia_km': '',
            'duracao_estimada_min': '',
            'tempo_cru_estimado_min': '',
            'tempo_adicional_min': 0,
            'rota_fonte': '',
        },
        'bate_volta_diario': _build_step3_bate_volta_diario_state(),
        'seed_source_label': seed_source_label or '',
    }


def _get_step3_saved_routes(oficio, include_ids=None):
    include_ids = {int(value) for value in (include_ids or []) if value}
    queryset = (
        RoteiroEvento.objects.filter(Q(status=RoteiroEvento.STATUS_FINALIZADO) | Q(pk__in=include_ids))
        .select_related('evento', 'origem_estado', 'origem_cidade', 'origem_cidade__estado')
        .prefetch_related(
            'destinos',
            'destinos__estado',
            'destinos__cidade',
            'trechos',
            'trechos__origem_estado',
            'trechos__origem_cidade',
            'trechos__origem_cidade__estado',
            'trechos__destino_estado',
            'trechos__destino_cidade',
            'trechos__destino_cidade__estado',
        )
        .distinct()
    )
    routes = list(queryset)
    return sorted(
        routes,
        key=lambda roteiro: (
            0 if roteiro.pk == oficio.roteiro_evento_id else 1,
            0 if oficio.evento_id and roteiro.evento_id == oficio.evento_id else 1,
            0 if roteiro.tipo == RoteiroEvento.TIPO_AVULSO else 1,
            -(roteiro.created_at.timestamp() if roteiro.created_at else 0),
        ),
    )


def _build_step3_state_from_roteiro_evento(roteiro, seed_source_label='Pré-preenchido com o roteiro salvo.'):
    state = _build_step3_state_from_estrutura(
        _estrutura_trechos(roteiro),
        _destinos_roteiro_para_template(roteiro),
        roteiro.origem_estado_id,
        roteiro.origem_cidade_id,
        seed_source_label,
    )
    state['roteiro_modo'] = Oficio.ROTEIRO_MODO_EVENTO
    state['roteiro_evento_id'] = roteiro.pk
    state['roteiro_evento_label'] = _build_step3_roteiro_label(roteiro)
    if not state['retorno']['saida_data']:
        state['retorno']['saida_data'], state['retorno']['saida_hora'] = _split_route_datetime(roteiro.retorno_saida_dt)
    if not state['retorno']['chegada_data']:
        state['retorno']['chegada_data'], state['retorno']['chegada_hora'] = _split_route_datetime(roteiro.retorno_chegada_dt)
    return state


def _build_step3_route_options(oficio):
    options = []
    state_map = {}
    include_ids = [oficio.roteiro_evento_id] if oficio.roteiro_evento_id else []
    for roteiro in _get_step3_saved_routes(oficio, include_ids=include_ids):
        destinos = [
            _step3_local_label(destino.cidade, destino.estado)
            for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'id')
        ]
        resumo = ' -> '.join(destinos[:3]) if destinos else 'Sem destinos'
        if len(destinos) > 3:
            resumo += ' -> ...'
        state = _build_step3_state_from_roteiro_evento(roteiro)
        state_map[roteiro.pk] = state
        tipo_label = 'Avulso' if roteiro.tipo == RoteiroEvento.TIPO_AVULSO else 'Evento'
        if roteiro.evento_id and roteiro.evento:
            tipo_label = f'{tipo_label}: {roteiro.evento.titulo}'
        options.append(
            {
                'id': roteiro.pk,
                'label': state['roteiro_evento_label'],
                'resumo': resumo,
                'status': roteiro.status,
                'tipo_label': tipo_label,
                'state': _serialize_step3_state(state),
            }
        )
    return options, state_map


def _get_oficio_step3_saved_state(oficio):
    trechos_salvos = list(
        OficioTrecho.objects.filter(oficio=oficio)
        .select_related(
            'origem_estado',
            'origem_cidade',
            'origem_cidade__estado',
            'destino_estado',
            'destino_cidade',
            'destino_cidade__estado',
        )
        .order_by('ordem', 'id')
    )
    if trechos_salvos:
        destinos_atuais = []
        destinos_seen = set()
        trechos = []
        sede_estado_id = oficio.estado_sede_id or trechos_salvos[0].origem_estado_id
        sede_cidade_id = oficio.cidade_sede_id or trechos_salvos[0].origem_cidade_id
        sede_cidade = oficio.cidade_sede or trechos_salvos[0].origem_cidade
        sede_estado = oficio.estado_sede or getattr(sede_cidade, 'estado', None) or trechos_salvos[0].origem_estado
        for trecho in trechos_salvos:
            destino_estado = trecho.destino_estado or getattr(trecho.destino_cidade, 'estado', None)
            destino_estado_id = destino_estado.pk if destino_estado else trecho.destino_estado_id
            destino_key = (destino_estado_id, trecho.destino_cidade_id)
            if trecho.destino_cidade_id and not _step3_locations_equivalent(
                cidade_a=trecho.destino_cidade,
                estado_a=destino_estado,
                cidade_b=sede_cidade,
                estado_b=sede_estado,
            ) and destino_key not in destinos_seen:
                destinos_seen.add(destino_key)
                destinos_atuais.append(
                    {
                        'estado_id': destino_estado_id,
                        'cidade_id': trecho.destino_cidade_id,
                        'estado': destino_estado,
                        'cidade': trecho.destino_cidade,
                    }
                )
            trechos.append(
                {
                    'ordem': trecho.ordem,
                    'origem_nome': _step3_local_label(trecho.origem_cidade, trecho.origem_estado),
                    'destino_nome': _step3_local_label(trecho.destino_cidade, trecho.destino_estado),
                    'origem_estado_id': trecho.origem_estado_id,
                    'origem_cidade_id': trecho.origem_cidade_id,
                    'destino_estado_id': trecho.destino_estado_id,
                    'destino_cidade_id': trecho.destino_cidade_id,
                    'saida_data': _step3_date_input(trecho.saida_data),
                    'saida_hora': _step3_time_input(trecho.saida_hora),
                    'chegada_data': _step3_date_input(trecho.chegada_data),
                    'chegada_hora': _step3_time_input(trecho.chegada_hora),
                    'distancia_km': _step3_decimal_input(trecho.distancia_km),
                    'duracao_estimada_min': trecho.duracao_estimada_min,
                    'tempo_cru_estimado_min': _step3_resolve_travel_minutes(
                        trecho.tempo_cru_estimado_min,
                        trecho.duracao_estimada_min,
                        trecho.tempo_adicional_min,
                    ),
                    'tempo_adicional_min': trecho.tempo_adicional_min or 0,
                    'rota_fonte': trecho.rota_fonte or '',
                }
            )
        ultimo_trecho = trechos_salvos[-1]
        retorno_saida = oficio.retorno_saida_cidade or _step3_local_label(ultimo_trecho.destino_cidade, ultimo_trecho.destino_estado)
        retorno_chegada = oficio.retorno_chegada_cidade or _step3_local_label(sede_cidade, sede_estado)
        return {
            'roteiro_modo': oficio.roteiro_modo or (Oficio.ROTEIRO_MODO_EVENTO if oficio.roteiro_evento_id else Oficio.ROTEIRO_MODO_PROPRIO),
            'roteiro_evento_id': oficio.roteiro_evento_id,
            'roteiro_evento_label': _build_step3_roteiro_label(oficio.roteiro_evento) if oficio.roteiro_evento_id else '',
            'sede_estado_id': sede_estado_id,
            'sede_cidade_id': sede_cidade_id,
            'destinos_atuais': destinos_atuais,
            'trechos': trechos,
            'retorno': {
                'origem_nome': retorno_saida,
                'destino_nome': retorno_chegada,
                'saida_cidade': retorno_saida,
                'chegada_cidade': retorno_chegada,
                'saida_data': _step3_date_input(oficio.retorno_saida_data),
                'saida_hora': _step3_time_input(oficio.retorno_saida_hora),
                'chegada_data': _step3_date_input(oficio.retorno_chegada_data),
                'chegada_hora': _step3_time_input(oficio.retorno_chegada_hora),
                'distancia_km': _step3_decimal_input(oficio.retorno_distancia_km),
                'duracao_estimada_min': oficio.retorno_duracao_estimada_min or '',
                'tempo_cru_estimado_min': _step3_resolve_travel_minutes(
                    oficio.retorno_tempo_cru_estimado_min,
                    oficio.retorno_duracao_estimada_min,
                    oficio.retorno_tempo_adicional_min,
                ),
                'tempo_adicional_min': oficio.retorno_tempo_adicional_min or 0,
                'rota_fonte': oficio.retorno_rota_fonte or '',
            },
            'bate_volta_diario': _build_step3_bate_volta_diario_state(
                {
                    'ativo': any(
                        _step3_locations_equivalent(
                            cidade_a=item.destino_cidade,
                            estado_a=item.destino_estado or getattr(item.destino_cidade, 'estado', None),
                            cidade_b=sede_cidade,
                            estado_b=sede_estado,
                        )
                        for item in trechos_salvos
                    ),
                }
            ),
            'seed_source_label': '',
        }
    if oficio.roteiro_evento_id:
        base_state = _build_step3_state_from_roteiro_evento(oficio.roteiro_evento, seed_source_label='')
    elif (
        oficio.estado_sede_id
        or oficio.cidade_sede_id
        or oficio.retorno_saida_data
        or oficio.retorno_chegada_data
    ):
        base_state = _build_step3_empty_state(
            oficio,
            roteiro_modo=oficio.roteiro_modo or Oficio.ROTEIRO_MODO_PROPRIO,
            roteiro_evento_id=oficio.roteiro_evento_id,
            roteiro_evento_label=_build_step3_roteiro_label(oficio.roteiro_evento) if oficio.roteiro_evento_id else '',
        )
        base_state['sede_estado_id'] = oficio.estado_sede_id
        base_state['sede_cidade_id'] = oficio.cidade_sede_id
    else:
        return None

    base_state['retorno'].update(
        {
            'origem_nome': oficio.retorno_saida_cidade or base_state['retorno'].get('origem_nome') or '',
            'destino_nome': oficio.retorno_chegada_cidade or base_state['retorno'].get('destino_nome') or '',
            'saida_cidade': oficio.retorno_saida_cidade or base_state['retorno'].get('saida_cidade') or '',
            'chegada_cidade': oficio.retorno_chegada_cidade or base_state['retorno'].get('chegada_cidade') or '',
            'saida_data': _step3_date_input(oficio.retorno_saida_data),
            'saida_hora': _step3_time_input(oficio.retorno_saida_hora),
            'chegada_data': _step3_date_input(oficio.retorno_chegada_data),
            'chegada_hora': _step3_time_input(oficio.retorno_chegada_hora),
            'distancia_km': _step3_decimal_input(oficio.retorno_distancia_km),
            'duracao_estimada_min': oficio.retorno_duracao_estimada_min or '',
            'tempo_cru_estimado_min': _step3_resolve_travel_minutes(
                oficio.retorno_tempo_cru_estimado_min,
                oficio.retorno_duracao_estimada_min,
                oficio.retorno_tempo_adicional_min,
            ),
            'tempo_adicional_min': oficio.retorno_tempo_adicional_min or 0,
            'rota_fonte': oficio.retorno_rota_fonte or '',
        }
    )
    base_state['seed_source_label'] = ''
    return base_state


# Step 3 overrides - escolha de roteiro do evento, roteiro próprio e diárias legadas

def _get_oficio_step3_seed_state(oficio, route_options, route_state_map):
    saved_state = _get_oficio_step3_saved_state(oficio)
    if saved_state:
        return saved_state
    if oficio.roteiro_evento_id and oficio.roteiro_evento_id in route_state_map:
        return deepcopy(route_state_map[oficio.roteiro_evento_id])
    if len(route_options) == 1:
        return deepcopy(route_state_map[route_options[0]['id']])
    if len(route_options) > 1:
        return _build_step3_empty_state(
            oficio,
            roteiro_modo=Oficio.ROTEIRO_MODO_EVENTO,
            seed_source_label='Selecione um roteiro salvo para carregar os trechos.',
        )
    if oficio.evento_id and oficio.evento.destinos.exists():
        sede_cidade = oficio.evento.cidade_base or oficio.evento.cidade_principal
        sede_estado = getattr(sede_cidade, 'estado', None) or oficio.evento.estado_principal
        if sede_cidade or sede_estado:
            destinos_atuais = _destinos_roteiro_para_template(oficio.evento)
            destinos_list = [
                (item.get('estado_id'), item.get('cidade_id'))
                for item in destinos_atuais
                if item.get('estado_id') and item.get('cidade_id')
            ]
            roteiro_virtual = _roteiro_virtual_para_trechos(
                {
                    'origem_estado': sede_estado.pk if sede_estado else None,
                    'origem_cidade': sede_cidade.pk if sede_cidade else None,
                }
            )
            state = _build_step3_state_from_estrutura(
                _estrutura_trechos(roteiro_virtual, destinos_list),
                destinos_atuais,
                sede_estado.pk if sede_estado else None,
                sede_cidade.pk if sede_cidade else None,
                'Pré-preenchido com os destinos do evento.',
            )
            state['roteiro_modo'] = Oficio.ROTEIRO_MODO_PROPRIO
            return state
    return _build_step3_empty_state(oficio, roteiro_modo=Oficio.ROTEIRO_MODO_PROPRIO)


def _build_step3_state_from_post(request, oficio=None, route_state_map=None):
    route_state_map = route_state_map or {}
    roteiro_modo = (request.POST.get('roteiro_modo') or '').strip()
    if roteiro_modo not in {Oficio.ROTEIRO_MODO_EVENTO, Oficio.ROTEIRO_MODO_PROPRIO}:
        roteiro_modo = Oficio.ROTEIRO_MODO_EVENTO if route_state_map else Oficio.ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = _parse_int(request.POST.get('roteiro_evento_id'))
    sede_estado_id = _parse_int(request.POST.get('sede_estado'))
    sede_cidade_id = _parse_int(request.POST.get('sede_cidade'))
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=sede_cidade_id, ativo=True).first() if sede_cidade_id else None
    sede_estado = Estado.objects.filter(pk=sede_estado_id or getattr(sede_cidade, 'estado_id', None), ativo=True).first() if (sede_estado_id or sede_cidade) else None
    destinos_list = _parse_destinos_post(request)
    posted_trechos = _extract_step3_posted_trechos(request)
    has_structure = bool(
        sede_estado_id
        or sede_cidade_id
        or destinos_list
        or posted_trechos
    )

    if roteiro_modo == Oficio.ROTEIRO_MODO_EVENTO and roteiro_evento_id and roteiro_evento_id in route_state_map and not has_structure:
        state = deepcopy(route_state_map[roteiro_evento_id])
    elif posted_trechos:
        state = _build_step3_empty_state(
            oficio,
            roteiro_modo=roteiro_modo,
            roteiro_evento_id=roteiro_evento_id,
            roteiro_evento_label=route_state_map.get(roteiro_evento_id, {}).get('roteiro_evento_label', ''),
        )
        state['sede_estado_id'] = sede_estado_id
        state['sede_cidade_id'] = sede_cidade_id
        state['trechos'] = []
        for idx, trecho in enumerate(posted_trechos):
            state['trechos'].append(
                {
                    'ordem': idx,
                    'origem_nome': (trecho.get('origem_nome') or '').strip(),
                    'destino_nome': (trecho.get('destino_nome') or '').strip(),
                    'origem_estado_id': _parse_int(trecho.get('origem_estado_id')),
                    'origem_cidade_id': _parse_int(trecho.get('origem_cidade_id')),
                    'destino_estado_id': _parse_int(trecho.get('destino_estado_id')),
                    'destino_cidade_id': _parse_int(trecho.get('destino_cidade_id')),
                    'saida_data': (trecho.get('saida_data') or '').strip(),
                    'saida_hora': (trecho.get('saida_hora') or '').strip(),
                    'chegada_data': (trecho.get('chegada_data') or '').strip(),
                    'chegada_hora': (trecho.get('chegada_hora') or '').strip(),
                    'distancia_km': (trecho.get('distancia_km') or '').strip(),
                    'tempo_cru_estimado_min': (trecho.get('tempo_cru_estimado_min') or '').strip(),
                    'tempo_adicional_min': (trecho.get('tempo_adicional_min') or '').strip() or 0,
                    'duracao_estimada_min': (trecho.get('duracao_estimada_min') or '').strip(),
                    'rota_fonte': (trecho.get('rota_fonte') or '').strip(),
                }
            )
        state['destinos_atuais'] = _infer_step3_destinos_from_trechos(state['trechos'], sede_estado=sede_estado, sede_cidade=sede_cidade)
        if not state['destinos_atuais'] and destinos_list:
            state['destinos_atuais'] = _destinos_para_template(destinos_list)
    else:
        destinos_atuais = _destinos_para_template(destinos_list)
        estrutura = []
        if sede_estado_id or sede_cidade_id:
            roteiro_virtual = _roteiro_virtual_para_trechos(
                {'origem_estado': sede_estado_id, 'origem_cidade': sede_cidade_id}
            )
            estrutura = _estrutura_trechos(roteiro_virtual, destinos_list)
        state = _build_step3_state_from_estrutura(
            estrutura,
            destinos_atuais or [{'estado_id': None, 'cidade_id': None, 'estado': None, 'cidade': None}],
            sede_estado_id,
            sede_cidade_id,
            '',
        )

    def _posted_or_default(name, default=''):
        if name in request.POST:
            return (request.POST.get(name) or '').strip()
        return default

    for idx, trecho in enumerate(state.get('trechos', [])):
        trecho['saida_data'] = _posted_or_default(f'trecho_{idx}_saida_data', trecho.get('saida_data', ''))
        trecho['saida_hora'] = _posted_or_default(f'trecho_{idx}_saida_hora', trecho.get('saida_hora', ''))
        trecho['chegada_data'] = _posted_or_default(f'trecho_{idx}_chegada_data', trecho.get('chegada_data', ''))
        trecho['chegada_hora'] = _posted_or_default(f'trecho_{idx}_chegada_hora', trecho.get('chegada_hora', ''))
        trecho['distancia_km'] = _posted_or_default(f'trecho_{idx}_distancia_km', _step3_decimal_input(trecho.get('distancia_km')))
        trecho['tempo_cru_estimado_min'] = _posted_or_default(f'trecho_{idx}_tempo_cru_estimado_min', trecho.get('tempo_cru_estimado_min') or '')
        trecho['tempo_adicional_min'] = _posted_or_default(f'trecho_{idx}_tempo_adicional_min', trecho.get('tempo_adicional_min') or 0)
        trecho['duracao_estimada_min'] = _posted_or_default(f'trecho_{idx}_duracao_estimada_min', trecho.get('duracao_estimada_min') or '')
        trecho['rota_fonte'] = _posted_or_default(f'trecho_{idx}_rota_fonte', trecho.get('rota_fonte') or '')

    state['retorno'].update(
        {
            'saida_data': _posted_or_default('retorno_saida_data', state['retorno'].get('saida_data', '')),
            'saida_hora': _posted_or_default('retorno_saida_hora', state['retorno'].get('saida_hora', '')),
            'chegada_data': _posted_or_default('retorno_chegada_data', state['retorno'].get('chegada_data', '')),
            'chegada_hora': _posted_or_default('retorno_chegada_hora', state['retorno'].get('chegada_hora', '')),
            'distancia_km': _posted_or_default('retorno_distancia_km', state['retorno'].get('distancia_km', '')),
            'tempo_cru_estimado_min': _posted_or_default('retorno_tempo_cru_estimado_min', state['retorno'].get('tempo_cru_estimado_min', '')),
            'tempo_adicional_min': _posted_or_default('retorno_tempo_adicional_min', state['retorno'].get('tempo_adicional_min', 0)),
            'duracao_estimada_min': _posted_or_default('retorno_duracao_estimada_min', state['retorno'].get('duracao_estimada_min', '')),
            'rota_fonte': _posted_or_default('retorno_rota_fonte', state['retorno'].get('rota_fonte', '')),
        }
    )
    tempo_cru_retorno = _parse_int(state['retorno'].get('tempo_cru_estimado_min'))
    tempo_adicional_retorno = _parse_int(state['retorno'].get('tempo_adicional_min')) or 0
    if tempo_adicional_retorno < 0:
        tempo_adicional_retorno = 0
    duracao_retorno = _parse_int(state['retorno'].get('duracao_estimada_min'))
    if duracao_retorno is None and ((tempo_cru_retorno or 0) + tempo_adicional_retorno) > 0:
        duracao_retorno = (tempo_cru_retorno or 0) + tempo_adicional_retorno
    state['retorno']['tempo_adicional_min'] = tempo_adicional_retorno
    state['retorno']['duracao_estimada_min'] = duracao_retorno if duracao_retorno is not None else ''
    state['bate_volta_diario'] = _build_step3_bate_volta_diario_state(
        {
            'ativo': request.POST.get('bate_volta_diario_ativo') in {'1', 'true', 'True', 'on'},
            'data_inicio': (request.POST.get('bate_volta_data_inicio') or '').strip(),
            'data_fim': (request.POST.get('bate_volta_data_fim') or '').strip(),
            'ida_saida_hora': (request.POST.get('bate_volta_ida_saida_hora') or '').strip(),
            'ida_tempo_min': (request.POST.get('bate_volta_ida_tempo_min') or '').strip(),
            'volta_saida_hora': (request.POST.get('bate_volta_volta_saida_hora') or '').strip(),
            'volta_tempo_min': (request.POST.get('bate_volta_volta_tempo_min') or '').strip(),
        }
    )
    state['seed_source_label'] = ''
    state['roteiro_modo'] = roteiro_modo
    if roteiro_modo == Oficio.ROTEIRO_MODO_EVENTO and roteiro_evento_id and roteiro_evento_id in route_state_map:
        state['roteiro_evento_id'] = roteiro_evento_id
        state['roteiro_evento_label'] = route_state_map[roteiro_evento_id].get('roteiro_evento_label') or ''
    else:
        state['roteiro_evento_id'] = None
        state['roteiro_evento_label'] = ''
    return state


def _autosave_oficio_step3(oficio, state):
    roteiro_evento = None
    roteiro_evento_id = _parse_int(state.get('roteiro_evento_id'))
    if roteiro_evento_id:
        roteiro_evento = RoteiroEvento.objects.filter(pk=roteiro_evento_id).first()
    roteiro_modo = state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO
    if roteiro_modo not in {Oficio.ROTEIRO_MODO_EVENTO, Oficio.ROTEIRO_MODO_PROPRIO}:
        roteiro_modo = Oficio.ROTEIRO_MODO_PROPRIO
    if roteiro_modo != Oficio.ROTEIRO_MODO_EVENTO:
        roteiro_evento = None

    sede_estado = Estado.objects.filter(pk=_parse_int(state.get('sede_estado_id')), ativo=True).first()
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(state.get('sede_cidade_id')), ativo=True).first()
    if sede_cidade and not sede_estado:
        sede_estado = getattr(sede_cidade, 'estado', None)

    cleaned_trechos = []
    for idx, trecho in enumerate(state.get('trechos', [])):
        if not any(
            [
                trecho.get('origem_estado_id'),
                trecho.get('origem_cidade_id'),
                trecho.get('destino_estado_id'),
                trecho.get('destino_cidade_id'),
                trecho.get('saida_data'),
                trecho.get('saida_hora'),
                trecho.get('chegada_data'),
                trecho.get('chegada_hora'),
                trecho.get('distancia_km'),
                trecho.get('tempo_cru_estimado_min'),
                trecho.get('tempo_adicional_min'),
                trecho.get('rota_fonte'),
            ]
        ):
            continue
        origem_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(trecho.get('origem_cidade_id')), ativo=True).first()
        destino_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(trecho.get('destino_cidade_id')), ativo=True).first()
        origem_estado = Estado.objects.filter(
            pk=_parse_int(trecho.get('origem_estado_id')) or getattr(origem_cidade, 'estado_id', None),
            ativo=True,
        ).first()
        destino_estado = Estado.objects.filter(
            pk=_parse_int(trecho.get('destino_estado_id')) or getattr(destino_cidade, 'estado_id', None),
            ativo=True,
        ).first()
        tempo_cru = _parse_int(trecho.get('tempo_cru_estimado_min'))
        tempo_adicional = _parse_int(trecho.get('tempo_adicional_min')) or 0
        if tempo_adicional < 0:
            tempo_adicional = 0
        duracao_estimada = _parse_int(trecho.get('duracao_estimada_min'))
        if duracao_estimada is None and ((tempo_cru or 0) + tempo_adicional) > 0:
            duracao_estimada = (tempo_cru or 0) + tempo_adicional
        cleaned_trechos.append(
            {
                'ordem': idx,
                'origem_estado_id': getattr(origem_estado, 'pk', None),
                'origem_cidade_id': getattr(origem_cidade, 'pk', None),
                'destino_estado_id': getattr(destino_estado, 'pk', None),
                'destino_cidade_id': getattr(destino_cidade, 'pk', None),
                'saida_data': _parse_step3_date(trecho.get('saida_data')),
                'saida_hora': _parse_step3_time(trecho.get('saida_hora')),
                'chegada_data': _parse_step3_date(trecho.get('chegada_data')),
                'chegada_hora': _parse_step3_time(trecho.get('chegada_hora')),
                'distancia_km': _parse_step3_decimal(trecho.get('distancia_km')),
                'tempo_cru_estimado_min': tempo_cru,
                'tempo_adicional_min': tempo_adicional,
                'duracao_estimada_min': duracao_estimada,
                'rota_fonte': (trecho.get('rota_fonte') or '').strip(),
            }
        )

    retorno = state.get('retorno') or {}
    retorno_tempo_cru = _parse_int(retorno.get('tempo_cru_estimado_min'))
    retorno_tempo_adicional = _parse_int(retorno.get('tempo_adicional_min')) or 0
    if retorno_tempo_adicional < 0:
        retorno_tempo_adicional = 0
    retorno_duracao = _parse_int(retorno.get('duracao_estimada_min'))
    if retorno_duracao is None and ((retorno_tempo_cru or 0) + retorno_tempo_adicional) > 0:
        retorno_duracao = (retorno_tempo_cru or 0) + retorno_tempo_adicional

    diarias_resultado = None
    tipo_destino = ''
    validated = _validate_step3_state(state, oficio=oficio)
    if validated['ok']:
        try:
            _, paradas, _, _, _ = _collect_step3_markers_payload(state, oficio=oficio)
            tipo_destino = infer_tipo_destino_from_paradas(paradas)
            diarias_resultado = _calculate_step3_diarias_from_state(oficio, state)
        except ValueError:
            diarias_resultado = None
            tipo_destino = ''

    oficio.roteiro_modo = roteiro_modo
    oficio.roteiro_evento = roteiro_evento
    oficio.estado_sede = sede_estado
    oficio.cidade_sede = sede_cidade
    oficio.tipo_destino = tipo_destino
    oficio.retorno_saida_cidade = (retorno.get('saida_cidade') or retorno.get('origem_nome') or '').strip()
    oficio.retorno_saida_data = _parse_step3_date(retorno.get('saida_data'))
    oficio.retorno_saida_hora = _parse_step3_time(retorno.get('saida_hora'))
    oficio.retorno_chegada_cidade = (retorno.get('chegada_cidade') or retorno.get('destino_nome') or '').strip()
    oficio.retorno_chegada_data = _parse_step3_date(retorno.get('chegada_data'))
    oficio.retorno_chegada_hora = _parse_step3_time(retorno.get('chegada_hora'))
    oficio.retorno_distancia_km = _parse_step3_decimal(retorno.get('distancia_km'))
    oficio.retorno_duracao_estimada_min = retorno_duracao
    oficio.retorno_tempo_cru_estimado_min = retorno_tempo_cru
    oficio.retorno_tempo_adicional_min = retorno_tempo_adicional
    oficio.retorno_rota_fonte = (retorno.get('rota_fonte') or '').strip()
    oficio.retorno_rota_calculada_em = (
        timezone.now()
        if oficio.retorno_distancia_km is not None or oficio.retorno_tempo_cru_estimado_min is not None
        else None
    )
    oficio.quantidade_diarias = (diarias_resultado or {}).get('totais', {}).get('total_diarias', '')
    oficio.valor_diarias = (diarias_resultado or {}).get('totais', {}).get('total_valor', '')
    oficio.valor_diarias_extenso = (diarias_resultado or {}).get('totais', {}).get('valor_extenso', '')

    with transaction.atomic():
        _save_oficio_preserving_status(
            oficio,
            [
                'roteiro_modo',
                'roteiro_evento',
                'estado_sede',
                'cidade_sede',
                'tipo_destino',
                'retorno_saida_cidade',
                'retorno_saida_data',
                'retorno_saida_hora',
                'retorno_chegada_cidade',
                'retorno_chegada_data',
                'retorno_chegada_hora',
                'retorno_distancia_km',
                'retorno_duracao_estimada_min',
                'retorno_tempo_cru_estimado_min',
                'retorno_tempo_adicional_min',
                'retorno_rota_fonte',
                'retorno_rota_calculada_em',
                'quantidade_diarias',
                'valor_diarias',
                'valor_diarias_extenso',
            ],
        )
        oficio.trechos.all().delete()
        if cleaned_trechos:
            OficioTrecho.objects.bulk_create(
                [
                    OficioTrecho(
                        oficio=oficio,
                        ordem=trecho['ordem'],
                        origem_estado_id=trecho.get('origem_estado_id'),
                        origem_cidade_id=trecho.get('origem_cidade_id'),
                        destino_estado_id=trecho.get('destino_estado_id'),
                        destino_cidade_id=trecho.get('destino_cidade_id'),
                        saida_data=trecho.get('saida_data'),
                        saida_hora=trecho.get('saida_hora'),
                        chegada_data=trecho.get('chegada_data'),
                        chegada_hora=trecho.get('chegada_hora'),
                        distancia_km=trecho.get('distancia_km'),
                        duracao_estimada_min=trecho.get('duracao_estimada_min'),
                        tempo_cru_estimado_min=trecho.get('tempo_cru_estimado_min'),
                        tempo_adicional_min=trecho.get('tempo_adicional_min'),
                        rota_fonte=trecho.get('rota_fonte') or '',
                        rota_calculada_em=timezone.now() if trecho.get('distancia_km') is not None or trecho.get('tempo_cru_estimado_min') is not None else None,
                    )
                    for trecho in cleaned_trechos
                ]
            )


def _validate_step3_state(state, oficio=None):
    errors = []
    roteiro_modo = state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = state.get('roteiro_evento_id')
    roteiro_evento = None
    if roteiro_modo == Oficio.ROTEIRO_MODO_EVENTO:
        if not roteiro_evento_id:
            errors.append('Selecione um roteiro salvo para usar neste ofício.')
        else:
            roteiro_evento = RoteiroEvento.objects.filter(pk=roteiro_evento_id).first()
            if not roteiro_evento:
                errors.append('O roteiro salvo selecionado não está mais disponível.')

    sede_estado_id = state.get('sede_estado_id')
    sede_cidade_id = state.get('sede_cidade_id')
    sede_estado = Estado.objects.filter(pk=sede_estado_id, ativo=True).first() if sede_estado_id else None
    sede_cidade = (
        Cidade.objects.select_related('estado').filter(pk=sede_cidade_id, ativo=True).first()
        if sede_cidade_id
        else None
    )
    if not sede_estado_id:
        errors.append('Informe o estado da sede.')
    if not sede_cidade_id:
        errors.append('Informe a cidade da sede.')
    if sede_estado and sede_cidade and sede_cidade.estado_id != sede_estado.id:
        errors.append('A cidade da sede deve pertencer ao estado selecionado.')

    destinos_list = [
        (item.get('estado_id'), item.get('cidade_id'))
        for item in state.get('destinos_atuais', [])
        if item.get('estado_id') and item.get('cidade_id')
    ]
    ok_destinos, msg_destinos = _validar_destinos(destinos_list)
    if not ok_destinos:
        errors.append(msg_destinos)
    bate_volta_diario = _build_step3_bate_volta_diario_state(state.get('bate_volta_diario'))
    if bate_volta_diario['ativo'] and len(destinos_list) != 1:
        errors.append('No modo bate-volta diário, informe exatamente um destino operacional.')

    cleaned_trechos = []
    raw_trechos = state.get('trechos', [])
    if not raw_trechos:
        errors.append('Adicione ao menos um trecho antes de salvar.')
    for idx, trecho in enumerate(raw_trechos, start=1):
        if not trecho.get('origem_estado_id') or not trecho.get('origem_cidade_id'):
            errors.append(f'Trecho {idx}: informe uma origem válida.')
        if not trecho.get('destino_estado_id') or not trecho.get('destino_cidade_id'):
            errors.append(f'Trecho {idx}: informe um destino válido.')
        saida_data = _parse_step3_date(trecho.get('saida_data'))
        saida_hora = _parse_step3_time(trecho.get('saida_hora'))
        chegada_data = _parse_step3_date(trecho.get('chegada_data'))
        chegada_hora = _parse_step3_time(trecho.get('chegada_hora'))
        if not saida_data or not saida_hora:
            errors.append(f'Trecho {idx}: informe a saída (data e hora).')
        if not chegada_data or not chegada_hora:
            errors.append(f'Trecho {idx}: informe a chegada (data e hora).')
        if saida_data and saida_hora and chegada_data and chegada_hora:
            if datetime.combine(chegada_data, chegada_hora) < datetime.combine(saida_data, saida_hora):
                errors.append(f'Trecho {idx}: a chegada deve ocorrer no mesmo momento ou após a saída.')

        tempo_cru = trecho.get('tempo_cru_estimado_min')
        try:
            tempo_cru = int(tempo_cru) if str(tempo_cru).strip() != '' else None
        except (TypeError, ValueError):
            tempo_cru = None
        tempo_adicional = trecho.get('tempo_adicional_min')
        try:
            tempo_adicional = max(0, int(tempo_adicional))
        except (TypeError, ValueError):
            tempo_adicional = 0
        duracao_estimada = trecho.get('duracao_estimada_min')
        try:
            duracao_estimada = int(duracao_estimada) if str(duracao_estimada).strip() != '' else None
        except (TypeError, ValueError):
            duracao_estimada = None
        if duracao_estimada is None and ((tempo_cru or 0) + tempo_adicional) > 0:
            duracao_estimada = (tempo_cru or 0) + tempo_adicional

        cleaned_trechos.append(
            {
                'ordem': idx - 1,
                'origem_estado_id': trecho.get('origem_estado_id'),
                'origem_cidade_id': trecho.get('origem_cidade_id'),
                'destino_estado_id': trecho.get('destino_estado_id'),
                'destino_cidade_id': trecho.get('destino_cidade_id'),
                'saida_data': saida_data,
                'saida_hora': saida_hora,
                'chegada_data': chegada_data,
                'chegada_hora': chegada_hora,
                'distancia_km': _parse_step3_decimal(trecho.get('distancia_km')),
                'tempo_cru_estimado_min': tempo_cru,
                'tempo_adicional_min': tempo_adicional,
                'duracao_estimada_min': duracao_estimada,
                'rota_fonte': (trecho.get('rota_fonte') or '').strip(),
            }
        )

    retorno = state.get('retorno', {})
    retorno_saida_data = _parse_step3_date(retorno.get('saida_data'))
    retorno_saida_hora = _parse_step3_time(retorno.get('saida_hora'))
    retorno_chegada_data = _parse_step3_date(retorno.get('chegada_data'))
    retorno_chegada_hora = _parse_step3_time(retorno.get('chegada_hora'))
    if not retorno_saida_data or not retorno_saida_hora:
        errors.append('Informe a saída do retorno (data e hora).')
    if not retorno_chegada_data or not retorno_chegada_hora:
        errors.append('Informe a chegada do retorno (data e hora).')
    if retorno_saida_data and retorno_saida_hora and retorno_chegada_data and retorno_chegada_hora:
        if datetime.combine(retorno_chegada_data, retorno_chegada_hora) < datetime.combine(retorno_saida_data, retorno_saida_hora):
            errors.append('O retorno deve chegar no mesmo momento ou após a saída.')
    ultimo_trecho = cleaned_trechos[-1] if cleaned_trechos else None
    ultimo_trecho_retorna_sede = False
    if ultimo_trecho and sede_cidade:
        ultimo_destino_cidade = Cidade.objects.select_related('estado').filter(pk=ultimo_trecho.get('destino_cidade_id'), ativo=True).first()
        ultimo_destino_estado = Estado.objects.filter(pk=ultimo_trecho.get('destino_estado_id'), ativo=True).first()
        ultimo_trecho_retorna_sede = _step3_locations_equivalent(
            cidade_a=ultimo_destino_cidade,
            estado_a=ultimo_destino_estado,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        )
    if (
        ultimo_trecho
        and not ultimo_trecho_retorna_sede
        and ultimo_trecho.get('chegada_data')
        and ultimo_trecho.get('chegada_hora')
        and retorno_saida_data
        and retorno_saida_hora
    ):
        chegada_final_ida = datetime.combine(ultimo_trecho['chegada_data'], ultimo_trecho['chegada_hora'])
        saida_retorno = datetime.combine(retorno_saida_data, retorno_saida_hora)
        if saida_retorno < chegada_final_ida:
            errors.append('O retorno deve sair no mesmo momento ou após a chegada do último trecho.')

    return {
        'ok': not errors,
        'errors': errors,
        'roteiro_modo': roteiro_modo,
        'roteiro_evento': roteiro_evento,
        'sede_estado': sede_estado,
        'sede_cidade': sede_cidade,
        'trechos': cleaned_trechos,
        'retorno_saida_data': retorno_saida_data,
        'retorno_saida_hora': retorno_saida_hora,
        'retorno_chegada_data': retorno_chegada_data,
        'retorno_chegada_hora': retorno_chegada_hora,
    }


def _collect_step3_markers_payload(state, oficio=None):
    roteiro_modo = state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO
    roteiro_evento_id = state.get('roteiro_evento_id')
    if roteiro_modo == Oficio.ROTEIRO_MODO_EVENTO and not roteiro_evento_id:
        raise ValueError('Selecione um roteiro salvo para usar neste ofício.')
    trechos = state.get('trechos') or []
    if not trechos:
        raise ValueError('Preencha datas e horas para calcular.')

    cidade_ids = {item.get('destino_cidade_id') for item in trechos if item.get('destino_cidade_id')}
    estado_ids = {item.get('destino_estado_id') for item in trechos if item.get('destino_estado_id')}
    cidades_map = {
        obj.pk: obj
        for obj in Cidade.objects.select_related('estado').filter(pk__in=cidade_ids, ativo=True)
    }
    estados_map = {obj.pk: obj for obj in Estado.objects.filter(pk__in=estado_ids, ativo=True)}
    sede_cidade = Cidade.objects.select_related('estado').filter(pk=_parse_int(state.get('sede_cidade_id')), ativo=True).first()
    sede_estado = Estado.objects.filter(pk=_parse_int(state.get('sede_estado_id')) or getattr(sede_cidade, 'estado_id', None), ativo=True).first() if (state.get('sede_estado_id') or sede_cidade) else None

    markers = []
    paradas = []
    for trecho in trechos:
        saida_data = _parse_step3_date(trecho.get('saida_data'))
        saida_hora = _parse_step3_time(trecho.get('saida_hora'))
        if not saida_data or not saida_hora:
            raise ValueError('Preencha datas e horas para calcular.')
        cidade = cidades_map.get(trecho.get('destino_cidade_id'))
        estado = getattr(cidade, 'estado', None) or estados_map.get(trecho.get('destino_estado_id'))
        cidade_nome = cidade.nome if cidade else (trecho.get('destino_nome') or '').split('/', 1)[0]
        uf_sigla = estado.sigla if estado else ''
        if not _step3_locations_equivalent(
            cidade_a=cidade,
            estado_a=estado,
            nome_a=cidade_nome,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        ):
            paradas.append((cidade_nome, uf_sigla))
        markers.append(
            PeriodMarker(
                saida=datetime.combine(saida_data, saida_hora),
                destino_cidade=cidade_nome,
                destino_uf=uf_sigla,
            )
        )

    retorno = state.get('retorno') or {}
    retorno_chegada_data = _parse_step3_date(retorno.get('chegada_data'))
    retorno_chegada_hora = _parse_step3_time(retorno.get('chegada_hora'))
    if not retorno_chegada_data or not retorno_chegada_hora:
        raise ValueError('Preencha datas e horas para calcular.')
    chegada_final = datetime.combine(retorno_chegada_data, retorno_chegada_hora)
    sede_cidade_nome, sede_uf_sigla = _step3_get_local_parts(cidade=sede_cidade, estado=sede_estado)
    return markers, paradas, chegada_final, sede_cidade_nome, sede_uf_sigla


def _calculate_step3_diarias_from_state(oficio, state):
    markers, paradas, chegada_final, sede_cidade, sede_uf = _collect_step3_markers_payload(state, oficio=oficio)
    total_servidores = oficio.viajantes.count()
    if total_servidores < 1:
        raise ValueError('Selecione ao menos um viajante no Step 1 para calcular as diárias.')
    resultado = calculate_periodized_diarias(
        markers,
        chegada_final,
        quantidade_servidores=total_servidores,
        sede_cidade=sede_cidade,
        sede_uf=sede_uf,
    )
    resultado['tipo_destino'] = infer_tipo_destino_from_paradas(paradas)
    return resultado


def _build_step3_diarias_fallback(oficio):
    if not (oficio.quantidade_diarias or oficio.valor_diarias or oficio.valor_diarias_extenso):
        return None
    valor_extenso = (oficio.valor_diarias_extenso or '').strip()
    if not valor_extenso and (oficio.valor_diarias or '').strip():
        valor_extenso = valor_por_extenso_ptbr(oficio.valor_diarias)
    return {
        'periodos': [],
        'totais': {
            'total_diarias': oficio.quantidade_diarias or '',
            'total_horas': '',
            'total_valor': oficio.valor_diarias or '',
            'valor_extenso': valor_extenso,
            'quantidade_servidores': oficio.viajantes.count(),
            'diarias_por_servidor': oficio.quantidade_diarias or '',
            'valor_por_servidor': oficio.valor_diarias or '',
            'valor_unitario_referencia': '',
        },
        'tipo_destino': oficio.tipo_destino or '',
    }


def _step3_combine_date_time(data_value, hora_value):
    if not data_value or not hora_value:
        return None
    return datetime.combine(data_value, hora_value)


def _build_step3_trechos_para_roteiro(validated, state):
    trechos = []
    for trecho in validated['trechos']:
        trechos.append(
            {
                'saida_dt': _step3_combine_date_time(trecho.get('saida_data'), trecho.get('saida_hora')),
                'chegada_dt': _step3_combine_date_time(trecho.get('chegada_data'), trecho.get('chegada_hora')),
                'distancia_km': trecho.get('distancia_km'),
                'duracao_estimada_min': trecho.get('duracao_estimada_min'),
                'tempo_cru_estimado_min': trecho.get('tempo_cru_estimado_min'),
                'tempo_adicional_min': trecho.get('tempo_adicional_min') or 0,
                'rota_fonte': (trecho.get('rota_fonte') or '').strip(),
            }
        )
    retorno_state = state.get('retorno') or {}
    retorno_tempo_cru = _parse_int(retorno_state.get('tempo_cru_estimado_min'))
    retorno_tempo_adicional = _parse_int(retorno_state.get('tempo_adicional_min')) or 0
    if retorno_tempo_adicional < 0:
        retorno_tempo_adicional = 0
    retorno_duracao = _parse_int(retorno_state.get('duracao_estimada_min'))
    if retorno_duracao is None and ((retorno_tempo_cru or 0) + retorno_tempo_adicional) > 0:
        retorno_duracao = (retorno_tempo_cru or 0) + retorno_tempo_adicional
    trechos.append(
        {
            'saida_dt': _step3_combine_date_time(validated.get('retorno_saida_data'), validated.get('retorno_saida_hora')),
            'chegada_dt': _step3_combine_date_time(validated.get('retorno_chegada_data'), validated.get('retorno_chegada_hora')),
            'distancia_km': _parse_step3_decimal(retorno_state.get('distancia_km')),
            'duracao_estimada_min': retorno_duracao,
            'tempo_cru_estimado_min': retorno_tempo_cru,
            'tempo_adicional_min': retorno_tempo_adicional,
            'rota_fonte': (retorno_state.get('rota_fonte') or '').strip(),
        }
    )
    return trechos


def _step3_signature_datetime(value):
    if not value:
        return ''
    if getattr(value, 'tzinfo', None):
        value = timezone.localtime(value)
    return value.strftime('%Y-%m-%dT%H:%M')


def _step3_signature_decimal(value):
    decimal_value = _parse_step3_decimal(value)
    if decimal_value is None:
        return ''
    return f'{decimal_value.quantize(Decimal("0.01")):.2f}'


def _build_step3_signature_from_state(validated, state):
    destinos = tuple(
        (item.get('estado_id'), item.get('cidade_id'))
        for item in state.get('destinos_atuais', [])
        if item.get('estado_id') and item.get('cidade_id')
    )
    trechos = tuple(
        (
            _step3_signature_datetime(trecho.get('saida_dt')),
            _step3_signature_datetime(trecho.get('chegada_dt')),
            _step3_signature_decimal(trecho.get('distancia_km')),
            trecho.get('duracao_estimada_min') or '',
            trecho.get('tempo_cru_estimado_min') or '',
            trecho.get('tempo_adicional_min') or 0,
        )
        for trecho in _build_step3_trechos_para_roteiro(validated, state)
    )
    return (
        getattr(validated.get('sede_estado'), 'pk', None),
        getattr(validated.get('sede_cidade'), 'pk', None),
        destinos,
        trechos,
    )


def _build_step3_signature_from_roteiro(roteiro):
    destinos = tuple(
        (destino.estado_id, destino.cidade_id)
        for destino in roteiro.destinos.select_related('estado', 'cidade').order_by('ordem', 'id')
    )
    trechos = tuple(
        (
            _step3_signature_datetime(trecho.saida_dt),
            _step3_signature_datetime(trecho.chegada_dt),
            _step3_signature_decimal(trecho.distancia_km),
            trecho.duracao_estimada_min or '',
            trecho.tempo_cru_estimado_min or '',
            trecho.tempo_adicional_min or 0,
        )
        for trecho in roteiro.trechos.order_by('ordem', 'id')
    )
    return (
        roteiro.origem_estado_id,
        roteiro.origem_cidade_id,
        destinos,
        trechos,
    )


def _find_existing_step3_route(oficio, state, validated):
    signature = _build_step3_signature_from_state(validated, state)
    include_ids = [validated['roteiro_evento'].pk] if validated.get('roteiro_evento') else []
    for roteiro in _get_step3_saved_routes(oficio, include_ids=include_ids):
        if _build_step3_signature_from_roteiro(roteiro) == signature:
            return roteiro
    return None


def _salvar_roteiro_reutilizavel_oficio(oficio, state, validated):
    destinos_post = [
        (item.get('estado_id'), item.get('cidade_id'))
        for item in state.get('destinos_atuais', [])
        if item.get('estado_id') and item.get('cidade_id')
    ]
    roteiro = RoteiroEvento(
        evento=oficio.evento if oficio.evento_id else None,
        origem_estado=validated['sede_estado'],
        origem_cidade=validated['sede_cidade'],
        tipo=RoteiroEvento.TIPO_EVENTO if oficio.evento_id else RoteiroEvento.TIPO_AVULSO,
        observacoes='',
    )
    trechos_times = _build_step3_trechos_para_roteiro(validated, state)
    return _salvar_roteiro_com_destinos_e_trechos(roteiro, destinos_post, trechos_times)


def _step3_can_create_reusable_route(state, validated):
    destinos_post = [
        (item.get('estado_id'), item.get('cidade_id'))
        for item in state.get('destinos_atuais', [])
        if item.get('estado_id') and item.get('cidade_id')
    ]
    if len(validated.get('trechos', [])) != len(destinos_post):
        return False
    sede_cidade = validated.get('sede_cidade')
    sede_estado = validated.get('sede_estado')
    for trecho in validated.get('trechos', []):
        destino_cidade = Cidade.objects.select_related('estado').filter(pk=trecho.get('destino_cidade_id'), ativo=True).first()
        destino_estado = Estado.objects.filter(pk=trecho.get('destino_estado_id'), ativo=True).first()
        if _step3_locations_equivalent(
            cidade_a=destino_cidade,
            estado_a=destino_estado,
            cidade_b=sede_cidade,
            estado_b=sede_estado,
        ):
            return False
    return True


def _ensure_reusable_step3_route(oficio, state, validated):
    if not _step3_can_create_reusable_route(state, validated):
        return None, False
    existente = _find_existing_step3_route(oficio, state, validated)
    if existente:
        return existente, False
    return _salvar_roteiro_reutilizavel_oficio(oficio, state, validated), True


def _apply_saved_route_reference_to_step3(state, validated, roteiro_salvo):
    if validated.get('roteiro_modo') != Oficio.ROTEIRO_MODO_EVENTO or not roteiro_salvo:
        return
    state['roteiro_evento_id'] = roteiro_salvo.pk
    state['roteiro_evento_label'] = _build_step3_roteiro_label(roteiro_salvo)
    validated['roteiro_evento'] = roteiro_salvo


def _salvar_step3_oficio(oficio, state, validated):
    trechos_data = validated['trechos']
    sede_estado = validated['sede_estado']
    sede_cidade = validated['sede_cidade']
    retorno_state = state.get('retorno') or {}
    ultimo_trecho = trechos_data[-1] if trechos_data else None
    retorno_saida_cidade = (retorno_state.get('saida_cidade') or retorno_state.get('origem_nome') or '').strip()
    if not retorno_saida_cidade and ultimo_trecho:
        retorno_saida_cidade = _step3_local_label(
            Cidade.objects.select_related('estado').filter(pk=ultimo_trecho.get('destino_cidade_id')).first(),
            Estado.objects.filter(pk=ultimo_trecho.get('destino_estado_id')).first(),
        )
    retorno_chegada_cidade = (retorno_state.get('chegada_cidade') or retorno_state.get('destino_nome') or '').strip()
    if not retorno_chegada_cidade:
        retorno_chegada_cidade = _step3_local_label(sede_cidade, sede_estado)
    diarias_resultado = None
    tipo_destino = ''
    try:
        _, paradas, _, _, _ = _collect_step3_markers_payload(state, oficio=oficio)
        tipo_destino = infer_tipo_destino_from_paradas(paradas)
        diarias_resultado = _calculate_step3_diarias_from_state(oficio, state)
    except ValueError:
        pass

    oficio.roteiro_modo = validated['roteiro_modo']
    oficio.roteiro_evento = validated['roteiro_evento'] if validated['roteiro_modo'] == Oficio.ROTEIRO_MODO_EVENTO else None
    oficio.estado_sede = sede_estado
    oficio.cidade_sede = sede_cidade
    oficio.tipo_destino = tipo_destino
    oficio.retorno_saida_cidade = retorno_saida_cidade
    oficio.retorno_saida_data = validated['retorno_saida_data']
    oficio.retorno_saida_hora = validated['retorno_saida_hora']
    oficio.retorno_chegada_cidade = retorno_chegada_cidade
    oficio.retorno_chegada_data = validated['retorno_chegada_data']
    oficio.retorno_chegada_hora = validated['retorno_chegada_hora']
    oficio.retorno_distancia_km = _parse_step3_decimal(retorno_state.get('distancia_km'))
    oficio.retorno_tempo_cru_estimado_min = _parse_int(retorno_state.get('tempo_cru_estimado_min'))
    oficio.retorno_tempo_adicional_min = _parse_int(retorno_state.get('tempo_adicional_min')) or 0
    oficio.retorno_duracao_estimada_min = _parse_int(retorno_state.get('duracao_estimada_min'))
    if oficio.retorno_duracao_estimada_min is None and (
        (oficio.retorno_tempo_cru_estimado_min or 0) + (oficio.retorno_tempo_adicional_min or 0)
    ) > 0:
        oficio.retorno_duracao_estimada_min = (
            (oficio.retorno_tempo_cru_estimado_min or 0) + (oficio.retorno_tempo_adicional_min or 0)
        )
    oficio.retorno_rota_fonte = (retorno_state.get('rota_fonte') or '').strip()
    oficio.retorno_rota_calculada_em = (
        timezone.now()
        if oficio.retorno_distancia_km is not None or oficio.retorno_tempo_cru_estimado_min is not None
        else None
    )
    oficio.quantidade_diarias = (diarias_resultado or {}).get('totais', {}).get('total_diarias', '')
    oficio.valor_diarias = (diarias_resultado or {}).get('totais', {}).get('total_valor', '')
    oficio.valor_diarias_extenso = (diarias_resultado or {}).get('totais', {}).get('valor_extenso', '')

    with transaction.atomic():
        _save_oficio_preserving_status(
            oficio,
            [
                'roteiro_modo',
                'roteiro_evento',
                'estado_sede',
                'cidade_sede',
                'tipo_destino',
                'retorno_saida_cidade',
                'retorno_saida_data',
                'retorno_saida_hora',
                'retorno_chegada_cidade',
                'retorno_chegada_data',
                'retorno_chegada_hora',
                'retorno_distancia_km',
                'retorno_tempo_cru_estimado_min',
                'retorno_tempo_adicional_min',
                'retorno_duracao_estimada_min',
                'retorno_rota_fonte',
                'retorno_rota_calculada_em',
                'quantidade_diarias',
                'valor_diarias',
                'valor_diarias_extenso',
            ],
        )
        oficio.trechos.all().delete()
        OficioTrecho.objects.bulk_create(
            [
                OficioTrecho(
                    oficio=oficio,
                    ordem=trecho['ordem'],
                    origem_estado_id=trecho.get('origem_estado_id'),
                    origem_cidade_id=trecho.get('origem_cidade_id'),
                    destino_estado_id=trecho.get('destino_estado_id'),
                    destino_cidade_id=trecho.get('destino_cidade_id'),
                    saida_data=trecho.get('saida_data'),
                    saida_hora=trecho.get('saida_hora'),
                    chegada_data=trecho.get('chegada_data'),
                    chegada_hora=trecho.get('chegada_hora'),
                    distancia_km=trecho.get('distancia_km'),
                    duracao_estimada_min=trecho.get('duracao_estimada_min'),
                    tempo_cru_estimado_min=trecho.get('tempo_cru_estimado_min'),
                    tempo_adicional_min=trecho.get('tempo_adicional_min'),
                    rota_fonte=trecho.get('rota_fonte') or '',
                    rota_calculada_em=timezone.now() if trecho.get('distancia_km') or trecho.get('tempo_cru_estimado_min') else None,
                )
                for trecho in trechos_data
            ]
        )


def _build_oficio_step3_preview(oficio, state=None, diarias_resultado=None):
    current_state = state or _get_oficio_step3_saved_state(oficio) or {
        'roteiro_modo': oficio.roteiro_modo or Oficio.ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': oficio.roteiro_evento_id,
        'roteiro_evento_label': _build_step3_roteiro_label(oficio.roteiro_evento) if oficio.roteiro_evento_id else '',
        'trechos': [],
        'retorno': {},
    }
    trechos_preview = []
    for trecho in current_state.get('trechos', []):
        try:
            cru = int(trecho.get('tempo_cru_estimado_min') or 0)
        except (TypeError, ValueError):
            cru = 0
        try:
            adicional = int(trecho.get('tempo_adicional_min') or 0)
        except (TypeError, ValueError):
            adicional = 0
        tempo_total = minutos_para_hhmm(cru + adicional) if (cru + adicional) > 0 else ''
        trechos_preview.append(
            {
                'ordem': trecho.get('ordem', 0),
                'rota': f"{trecho.get('origem_nome') or '\u2014'} \u2192 {trecho.get('destino_nome') or '\u2014'}",
                'saida': _step3_format_date_time_br(trecho.get('saida_data'), trecho.get('saida_hora')),
                'chegada': _step3_format_date_time_br(trecho.get('chegada_data'), trecho.get('chegada_hora')),
                'distancia': _step3_decimal_input(trecho.get('distancia_km')),
                'tempo_total': tempo_total,
            }
        )
    retorno = current_state.get('retorno', {})
    retorno_preview = {
        'show': bool(
            retorno.get('origem_nome')
            or retorno.get('destino_nome')
            or retorno.get('saida_data')
            or retorno.get('chegada_data')
        ),
        'rota': f"{retorno.get('origem_nome') or '\u2014'} \u2192 {retorno.get('destino_nome') or '\u2014'}",
        'saida': _step3_format_date_time_br(retorno.get('saida_data'), retorno.get('saida_hora')),
        'chegada': _step3_format_date_time_br(retorno.get('chegada_data'), retorno.get('chegada_hora')),
    }
    totais_diarias = (diarias_resultado or {}).get('totais', {})
    valor_extenso = totais_diarias.get('valor_extenso') or ''
    if not valor_extenso and totais_diarias.get('total_valor'):
        valor_extenso = valor_por_extenso_ptbr(totais_diarias.get('total_valor'))
    return {
        'roteiro_modo': current_state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO,
        'roteiro_modo_label': dict(Oficio.ROTEIRO_MODO_CHOICES).get(
            current_state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO,
            '',
        ),
        'roteiro_evento_label': current_state.get('roteiro_evento_label') or '',
        'tipo_destino': (diarias_resultado or {}).get('tipo_destino') or oficio.tipo_destino or '',
        'periodo_display': _build_step3_periodo_display_from_state(current_state),
        'destino_principal': _build_step3_destino_principal_from_state(current_state),
        'trechos': trechos_preview,
        'retorno': retorno_preview,
        'tem_trechos': bool(trechos_preview),
        'diarias': {
            'show': bool(totais_diarias.get('total_diarias') or totais_diarias.get('total_valor')),
            'quantidade': totais_diarias.get('total_diarias') or '',
            'valor_total': totais_diarias.get('total_valor') or '',
            'valor_extenso': valor_extenso,
        },
    }


def _build_oficio_justificativa_info(oficio):
    prazo_minimo = get_prazo_justificativa_dias()
    primeira_saida = get_primeira_saida_oficio(oficio)
    dias_antecedencia = get_dias_antecedencia_oficio(oficio)
    exige = oficio_exige_justificativa(oficio)
    texto = get_oficio_justificativa_texto(oficio)
    preenchida = bool(texto)

    if dias_antecedencia is None:
        status_key = 'indefinida'
        status_label = 'Aguardando dados válidos do Step 3'
    elif exige and not preenchida:
        status_key = 'pendente'
        status_label = 'Pendente'
    elif preenchida:
        status_key = 'preenchida'
        status_label = 'Preenchida'
    else:
        status_key = 'nao_exigida'
        status_label = 'Não exigida'

    return {
        'required': exige,
        'filled': preenchida,
        'schema_available': True,
        'schema_message': '',
        'prazo_minimo_dias': prazo_minimo,
        'dias_antecedencia': dias_antecedencia,
        'primeira_saida': primeira_saida,
        'primeira_saida_display': primeira_saida.strftime('%d/%m/%Y %H:%M') if primeira_saida else '',
        'status_key': status_key,
        'status_label': status_label,
        'texto': texto,
    }


def _validate_oficio_for_finalize(oficio):
    section_labels = {
        'step1': 'Step 1 — Dados gerais',
        'step2': 'Step 2 — Transporte',
        'step3': 'Step 3 — Trechos e diárias',
        'justificativa': 'Justificativa',
    }
    errors_by_section = {key: [] for key in section_labels}

    protocolo = Oficio.normalize_protocolo(oficio.protocolo or '')
    if not protocolo:
        errors_by_section['step1'].append('Informe o protocolo do ofício.')
    elif len(protocolo) != 9:
        errors_by_section['step1'].append('Informe um protocolo válido no formato XX.XXX.XXX-X.')
    if not oficio.viajantes.exists():
        errors_by_section['step1'].append('Selecione ao menos um viajante.')
    if not (oficio.motivo or '').strip():
        errors_by_section['step1'].append('Informe o motivo da viagem.')
    if (
        oficio.custeio_tipo == Oficio.CUSTEIO_OUTRA_INSTITUICAO
        and not (oficio.nome_instituicao_custeio or '').strip()
    ):
        errors_by_section['step1'].append('Informe a instituição responsável pelo custeio.')

    if not (oficio.placa or '').strip():
        errors_by_section['step2'].append('Informe a placa do veículo.')
    if not (oficio.modelo or '').strip():
        errors_by_section['step2'].append('Informe o modelo do veículo.')
    if not (oficio.combustivel or '').strip():
        errors_by_section['step2'].append('Informe o combustível do veículo.')
    if not (oficio.motorista_viajante_id or (oficio.motorista or '').strip()):
        errors_by_section['step2'].append('Informe o motorista do ofício.')
    motorista_protocolo = Oficio.normalize_protocolo(oficio.motorista_protocolo or '')
    if oficio.motorista_carona:
        if not oficio.motorista_oficio_numero:
            errors_by_section['step2'].append('Informe o número do ofício do motorista carona.')
        if not oficio.motorista_oficio_ano:
            errors_by_section['step2'].append('Informe o ano do ofício do motorista carona.')
        if not motorista_protocolo:
            errors_by_section['step2'].append('Informe o protocolo do motorista carona.')
        elif len(motorista_protocolo) != 9:
            errors_by_section['step2'].append('Informe um protocolo válido para o motorista carona.')

    saved_state = _get_oficio_step3_saved_state(oficio)
    if not saved_state:
        errors_by_section['step3'].append('Preencha e salve o Step 3 antes de finalizar.')
    else:
        step3_validation = _validate_step3_state(saved_state, oficio=oficio)
        errors_by_section['step3'].extend(step3_validation['errors'])
    if not (oficio.tipo_destino or '').strip():
        errors_by_section['step3'].append('Defina o tipo de destino no Step 3.')
    diarias_values = [
        (oficio.quantidade_diarias or '').strip(),
        (oficio.valor_diarias or '').strip(),
        (oficio.valor_diarias_extenso or '').strip(),
    ]
    if not all(diarias_values):
        errors_by_section['step3'].append('Calcule e salve as diárias do Step 3.')

    justificativa_info = _build_oficio_justificativa_info(oficio)
    if justificativa_info['required'] and not justificativa_info['filled']:
        dias_antecedencia = justificativa_info['dias_antecedencia']
        prazo_minimo = justificativa_info['prazo_minimo_dias']
        if dias_antecedencia is None:
            errors_by_section['justificativa'].append(
                'Preencha a justificativa antes de finalizar o ofício.'
            )
        else:
            errors_by_section['justificativa'].append(
                f'Preencha a justificativa. A antecedência da viagem é de {dias_antecedencia} dia(s), abaixo do prazo mínimo de {prazo_minimo} dia(s).'
            )

    sections = []
    flat_errors = []
    for section_key, label in section_labels.items():
        unique_errors = list(dict.fromkeys(errors_by_section[section_key]))
        if not unique_errors:
            continue
        sections.append(
            {
                'id': section_key,
                'label': label,
                'errors': unique_errors,
            }
        )
        flat_errors.extend(unique_errors)
    has_non_justificativa_errors = any(
        errors_by_section[section_key]
        for section_key in section_labels
        if section_key != 'justificativa'
    )
    return {
        'ok': not sections,
        'sections': sections,
        'errors': flat_errors,
        'justificativa_required': justificativa_info['required'],
        'justificativa_missing': bool(errors_by_section['justificativa']),
        'has_non_justificativa_errors': has_non_justificativa_errors,
    }


def _build_oficio_step4_context(oficio, finalize_validation=None):
    saved_state = _get_oficio_step3_saved_state(oficio)
    if saved_state:
        try:
            diarias_resultado = _calculate_step3_diarias_from_state(oficio, saved_state)
        except ValueError:
            diarias_resultado = _build_step3_diarias_fallback(oficio)
    else:
        diarias_resultado = _build_step3_diarias_fallback(oficio)
    justificativa_info = _build_oficio_justificativa_info(oficio)
    step1_preview = _build_oficio_step1_preview(oficio)
    step2_form = OficioStep2Form(initial=_build_oficio_step2_initial(oficio), oficio=oficio)
    step2_preview = _build_step2_preview_data(oficio, step2_form)
    step3_preview = _build_oficio_step3_preview(oficio, saved_state, diarias_resultado=diarias_resultado)
    return {
        'oficio': oficio,
        'evento': oficio.evento,
        'step': 4,
        'step1_preview': step1_preview,
        'selected_viajantes': step1_preview['viajantes'],
        'step2_preview': step2_preview,
        'step3_preview': step3_preview,
        'finalize_validation': finalize_validation,
        'justificativa_info': justificativa_info,
        'oficio_downloads': _build_oficio_document_download_context(oficio, DocumentoOficioTipo.OFICIO),
        'termo_autorizacao': _build_oficio_termo_autorizacao_context(oficio),
        'justificativa_url': _oficio_justificativa_url(
            oficio,
            next_url=reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
        ),
    }


def _build_oficio_document_download_context(oficio, tipo_documento):
    meta = get_document_type_meta(tipo_documento)
    actions = []
    errors = []
    for formato in (DocumentoFormato.DOCX, DocumentoFormato.PDF):
        if not meta.supports(formato):
            continue
        status_info = get_document_generation_status(oficio, meta.tipo, formato)
        actions.append(
            {
                'label': formato.value.upper(),
                'download_label': f'Baixar {formato.value.upper()}',
                'url': reverse(
                    'eventos:oficio-documento-download',
                    kwargs={
                        'pk': oficio.pk,
                        'tipo_documento': meta.slug,
                        'formato': formato.value,
                    },
                ),
                'status': status_info['status'],
                'available': status_info['status'] == 'available',
                'errors': status_info.get('errors') or [],
            }
        )
        if status_info['status'] != 'available':
            errors.extend(status_info.get('errors') or [])
    return {
        'label': meta.label,
        'slug': meta.slug,
        'available': any(action['available'] for action in actions),
        'actions': actions,
        'errors': list(dict.fromkeys([error for error in errors if error])),
    }


def _build_oficio_termo_autorizacao_context(oficio):
    meta = get_document_type_meta(DocumentoOficioTipo.TERMO_AUTORIZACAO)
    actions = []
    errors = []
    for formato in (DocumentoFormato.DOCX, DocumentoFormato.PDF):
        if not meta.supports(formato):
            continue
        status_info = get_document_generation_status(oficio, meta.tipo, formato)
        if status_info['status'] == 'available':
            actions.append(
                {
                    'label': formato.value.upper(),
                    'url': reverse(
                        'eventos:oficio-documento-download',
                        kwargs={
                            'pk': oficio.pk,
                            'tipo_documento': meta.slug,
                            'formato': formato.value,
                        },
                    ),
                }
            )
        else:
            errors.extend(status_info.get('errors') or [])
    return {
        'label': meta.label,
        'available': bool(actions),
        'actions': actions,
        'errors': list(dict.fromkeys([error for error in errors if error])),
    }


def _build_oficio_justificativa_context(oficio, next_url=''):
    saved_state = _get_oficio_step3_saved_state(oficio)
    if saved_state:
        try:
            diarias_resultado = _calculate_step3_diarias_from_state(oficio, saved_state)
        except ValueError:
            diarias_resultado = _build_step3_diarias_fallback(oficio)
    else:
        diarias_resultado = _build_step3_diarias_fallback(oficio)
    step1_preview = _build_oficio_step1_preview(oficio)
    step2_form = OficioStep2Form(initial=_build_oficio_step2_initial(oficio), oficio=oficio)
    step2_preview = _build_step2_preview_data(oficio, step2_form)
    step3_preview = _build_oficio_step3_preview(oficio, saved_state, diarias_resultado=diarias_resultado)
    justificativa_info = _build_oficio_justificativa_info(oficio)
    return {
        'oficio': oficio,
        'evento': oficio.evento,
        'step1_preview': step1_preview,
        'selected_viajantes': step1_preview['viajantes'],
        'step2_preview': step2_preview,
        'step3_preview': step3_preview,
        'justificativa_info': justificativa_info,
        'next_url': next_url,
        'voltar_step4_url': next_url or reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
        'modelos_justificativa_url': _append_query_params(
            reverse('eventos:modelos-justificativa-lista'),
            volta_justificativa=oficio.pk,
            next=next_url,
        ),
    }


def _build_oficio_documentos_context(oficio):
    backend_docx_status = get_docx_backend_availability()
    backend_pdf_status = get_pdf_backend_availability()
    status_labels = {
        'available': 'Disponível',
        'pending': 'Pendente',
        'unavailable': 'Indisponível no ambiente',
        'planned': 'Em breve',
    }
    status_priority = {
        'available': 0,
        'pending': 1,
        'unavailable': 2,
        'planned': 3,
    }

    def build_action(meta, formato, backend_status):
        status_info = get_document_generation_status(oficio, meta.tipo, formato)
        url = None
        if meta.supports(formato):
            url = reverse(
                'eventos:oficio-documento-download',
                kwargs={
                    'pk': oficio.pk,
                    'tipo_documento': meta.slug,
                    'formato': formato.value,
                },
            )
        return {
            'format': formato.value,
            'label': formato.value.upper(),
            'status': status_info['status'],
            'status_label': status_labels.get(status_info['status'], 'Indisponível no ambiente'),
            'errors': status_info.get('errors') or [],
            'url': url,
            'global_backend_issue': (
                not backend_status['available']
                and status_info['status'] == 'unavailable'
                and backend_status['message'] in (status_info.get('errors') or [])
            ),
        }

    def pick_primary_action(actions):
        if not actions:
            return {
                'status': 'planned',
                'errors': ['Ainda não implementado nesta fase.'],
                'global_backend_issue': False,
            }
        return sorted(actions, key=lambda action: status_priority.get(action['status'], 99))[0]

    backend_alertas = []
    if not backend_docx_status['available']:
        backend_alertas.append({'format': 'DOCX', 'message': backend_docx_status['message']})
    if not backend_pdf_status['available']:
        backend_alertas.append({'format': 'PDF', 'message': backend_pdf_status['message']})

    documentos = []
    for meta in iter_document_type_metas():
        grupo = 'principais'
        if meta.tipo in {
            DocumentoOficioTipo.TERMO_AUTORIZACAO,
            DocumentoOficioTipo.PLANO_TRABALHO,
            DocumentoOficioTipo.ORDEM_SERVICO,
        }:
            grupo = 'complementares'
        docx_action = (
            build_action(meta, DocumentoFormato.DOCX, backend_docx_status)
            if meta.supports(DocumentoFormato.DOCX)
            else None
        )
        pdf_action = (
            build_action(meta, DocumentoFormato.PDF, backend_pdf_status)
            if meta.supports(DocumentoFormato.PDF)
            else None
        )
        actions = [action for action in [docx_action, pdf_action] if action]
        primary_action = pick_primary_action(actions)
        item_errors = []
        if primary_action['status'] == 'pending':
            item_errors = primary_action.get('errors') or []
        elif primary_action['status'] == 'unavailable' and not primary_action.get('global_backend_issue'):
            item_errors = primary_action.get('errors') or []

        documentos.append(
            {
                'tipo': meta.tipo.value,
                'slug': meta.slug,
                'label': meta.label,
                'group': grupo,
                'status': primary_action['status'],
                'status_label': status_labels.get(primary_action['status'], 'Indisponível no ambiente'),
                'errors': item_errors,
                'global_backend_issue_only': (
                    primary_action['status'] == 'unavailable'
                    and primary_action.get('global_backend_issue', False)
                    and not item_errors
                ),
                'docx': docx_action,
                'pdf': pdf_action,
                'actions': actions,
            }
        )

    documentos_principais = [item for item in documentos if item['group'] == 'principais']
    documentos_complementares = [item for item in documentos if item['group'] == 'complementares']
    return {
        'oficio': oficio,
        'evento': oficio.evento,
        'documentos': documentos,
        'documentos_principais': documentos_principais,
        'documentos_complementares': documentos_complementares,
        'backend_alertas': backend_alertas,
        'docx_backend_available': backend_docx_status['available'],
        'pdf_backend_available': backend_pdf_status['available'],
        'docx_backend_status': backend_docx_status,
        'pdf_backend_status': backend_pdf_status,
        'docx_disponivel': backend_docx_status['available'],
        'docx_indisponivel_motivo': backend_docx_status['message'],
        'pdf_disponivel': backend_pdf_status['available'],
        'pdf_indisponivel_motivo': backend_pdf_status['message'],
    }


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step3(request, pk):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    if _bloquear_edicao_oficio_se_evento_finalizado(request, oficio):
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    evento = oficio.evento
    validation_errors = []
    route_options, route_state_map = _build_step3_route_options(oficio)
    destino_estado_fixo = _get_parana_estado()
    if _is_autosave_request(request):
        step3_state = _build_step3_state_from_post(
            request,
            oficio=oficio,
            route_state_map=route_state_map,
        )
        _autosave_oficio_step3(oficio, step3_state)
        return _autosave_success_response()
    if request.method == 'POST':
        step3_state = _build_step3_state_from_post(
            request,
            oficio=oficio,
            route_state_map=route_state_map,
        )
        validated = _validate_step3_state(step3_state, oficio=oficio)
        if validated['ok']:
            if request.POST.get('salvar_roteiro'):
                roteiro_salvo, _created = _ensure_reusable_step3_route(oficio, step3_state, validated)
                _apply_saved_route_reference_to_step3(step3_state, validated, roteiro_salvo)
                with transaction.atomic():
                    _salvar_step3_oficio(oficio, step3_state, validated)
                messages.success(request, 'Roteiro salvo para reutilização.')
                justificativa_info = _build_oficio_justificativa_info(oficio)
                if justificativa_info['required'] and not justificativa_info['filled']:
                    return redirect(
                        _oficio_justificativa_url(
                            oficio,
                            next_url=reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
                        )
                    )
                return redirect('eventos:oficio-step4', pk=oficio.pk)
            _salvar_step3_oficio(oficio, step3_state, validated)
            messages.success(request, 'Step 3 do ofício salvo.')
            if request.POST.get('avancar'):
                return redirect('eventos:oficio-step4', pk=oficio.pk)
            return redirect('eventos:oficio-step3', pk=oficio.pk)
        validation_errors = validated['errors']
    else:
        step3_state = _get_oficio_step3_seed_state(oficio, route_options, route_state_map)

    try:
        diarias_resultado = _calculate_step3_diarias_from_state(oficio, step3_state)
    except ValueError:
        diarias_resultado = _build_step3_diarias_fallback(oficio)

    estados_qs = Estado.objects.filter(ativo=True).order_by('nome')
    sede_estado_id = step3_state.get('sede_estado_id')
    sede_cidades_qs = (
        Cidade.objects.filter(estado_id=sede_estado_id, ativo=True).order_by('nome')
        if sede_estado_id
        else Cidade.objects.none()
    )
    step1_preview = _build_oficio_step1_preview(oficio)
    step2_form = OficioStep2Form(initial=_build_oficio_step2_initial(oficio), oficio=oficio)
    step2_preview = _build_step2_preview_data(oficio, step2_form)
    step3_preview = _build_oficio_step3_preview(oficio, step3_state, diarias_resultado=diarias_resultado)
    justificativa_info = _build_oficio_justificativa_info(oficio)
    context = {
        'oficio': oficio,
        'evento': evento,
        'step': 3,
        'next_step_url': reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
        'estados': estados_qs,
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
        'api_calcular_diarias_url': reverse('eventos:oficio-step3-calcular-diarias', kwargs={'pk': oficio.pk}),
        'sede_estado_id': step3_state.get('sede_estado_id'),
        'sede_cidade_id': step3_state.get('sede_cidade_id'),
        'sede_cidades_qs': sede_cidades_qs,
        'destinos_atuais': step3_state.get('destinos_atuais') or [{'estado_id': None, 'cidade_id': None, 'estado': None, 'cidade': None}],
        'trechos_state': step3_state.get('trechos', []),
        'retorno_state': step3_state.get('retorno', {}),
        'step3_state_json': _serialize_step3_state(step3_state),
        'step3_seed_source_label': step3_state.get('seed_source_label', ''),
        'validation_errors': validation_errors,
        'step1_preview': step1_preview,
        'selected_viajantes': step1_preview['viajantes'],
        'step2_preview': step2_preview,
        'step3_preview': step3_preview,
        'justificativa_info': justificativa_info,
        'step3_diarias_resultado': diarias_resultado,
        'roteiros_evento': route_options,
        'roteiros_evento_json': route_options,
        'roteiro_modo': step3_state.get('roteiro_modo') or Oficio.ROTEIRO_MODO_PROPRIO,
        'roteiro_evento_id': step3_state.get('roteiro_evento_id'),
        'has_event_routes': bool(route_options),
        'destino_estado_fixo_id': getattr(destino_estado_fixo, 'pk', None),
        'destino_estado_fixo_nome': (
            f'{destino_estado_fixo.nome} ({destino_estado_fixo.sigla})'
            if destino_estado_fixo
            else 'Paraná (PR)'
        ),
    }
    wizard_key = 'step3'
    wizard_title = 'Roteiro e diárias'
    return render(
        request,
        'eventos/oficio/wizard_step3.html',
        _apply_oficio_wizard_context(
            context,
            oficio,
            wizard_key,
            wizard_title,
            justificativa_info=justificativa_info,
        ),
    )


def _autosave_oficio_justificativa(oficio, request):
    modelo_id = _parse_int(request.POST.get('modelo_justificativa'))
    modelo = ModeloJustificativa.objects.filter(pk=modelo_id).first() if modelo_id else None
    texto = (request.POST.get('justificativa_texto') or '').strip()
    justificativa, _ = Justificativa.objects.get_or_create(oficio=oficio)
    justificativa.modelo = modelo
    justificativa.texto = texto
    justificativa.save(update_fields=['modelo', 'texto', 'updated_at'])
    return None


def _parse_step4_termo_choice(request, oficio):
    raw_value = (request.POST.get('gerar_termo_preenchido') or '').strip()
    if raw_value not in {'0', '1'}:
        return bool(oficio.gerar_termo_preenchido)
    return raw_value == '1'


def _autosave_oficio_step4(oficio, request):
    oficio.gerar_termo_preenchido = _parse_step4_termo_choice(request, oficio)
    _save_oficio_preserving_status(oficio, ['gerar_termo_preenchido'])
    return None


@login_required
@require_http_methods(['POST'])
def oficio_step3_calcular_diarias(request, pk):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    _, route_state_map = _build_step3_route_options(oficio)
    step3_state = _build_step3_state_from_post(
        request,
        oficio=oficio,
        route_state_map=route_state_map,
    )
    validated = _validate_step3_state(step3_state, oficio=oficio)
    if not validated['ok']:
        return JsonResponse(
            {
                'ok': False,
                'error': 'Revise os dados do roteiro antes de calcular as diárias.',
                'errors': validated['errors'],
            },
            status=400,
        )
    roteiro_salvo, roteiro_criado = _ensure_reusable_step3_route(oficio, step3_state, validated)
    _apply_saved_route_reference_to_step3(step3_state, validated, roteiro_salvo)
    with transaction.atomic():
        _salvar_step3_oficio(oficio, step3_state, validated)
    try:
        resultado = _calculate_step3_diarias_from_state(oficio, step3_state)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    justificativa_info = _build_oficio_justificativa_info(oficio)
    payload = {'ok': True}
    payload.update(resultado)
    payload.update(
        {
            'roteiro_salvo_id': roteiro_salvo.pk if roteiro_salvo else None,
            'roteiro_salvo_criado': roteiro_criado,
            'justificativa_required': justificativa_info['required'],
            'justificativa_filled': justificativa_info['filled'],
            'justificativa_status_label': justificativa_info['status_label'],
            'justificativa_url': (
                _oficio_justificativa_url(
                    oficio,
                    next_url=reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}),
                )
                if justificativa_info['required'] and not justificativa_info['filled']
                else ''
            ),
            'step3_url': reverse('eventos:oficio-step3', kwargs={'pk': oficio.pk}),
        }
    )
    return JsonResponse(payload)


@login_required
@require_http_methods(['GET', 'POST'])
def _legacy_oficio_step4(request, pk):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    evento = oficio.evento
    if request.method == 'POST':
        if request.POST.get('finalizar'):
            oficio.status = Oficio.STATUS_FINALIZADO
            oficio.save(update_fields=['status', 'updated_at'])
            messages.success(request, 'Ofício finalizado.')
        if request.POST.get('voltar_etapa3') and evento:
            return redirect('eventos:guiado-etapa-5', evento_id=evento.pk)
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    saved_state = _get_oficio_step3_saved_state(oficio)
    if saved_state:
        try:
            diarias_resultado = _calculate_step3_diarias_from_state(oficio, saved_state)
        except ValueError:
            diarias_resultado = _build_step3_diarias_fallback(oficio)
    else:
        diarias_resultado = _build_step3_diarias_fallback(oficio)
    context = {
        'oficio': oficio,
        'evento': evento,
        'step': 4,
        'step3_preview': _build_oficio_step3_preview(oficio, saved_state, diarias_resultado=diarias_resultado),
    }
    return render(request, 'eventos/oficio/wizard_step4.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_justificativa(request, pk):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    default_next_url = reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk})
    next_url = _get_safe_next_url(request, default_next_url)
    if _is_autosave_request(request):
        _autosave_oficio_justificativa(oficio, request)
        return _autosave_success_response()
    form = OficioJustificativaForm(request.POST or None, oficio=oficio)
    if request.method == 'POST' and form.is_valid():
        justificativa, _ = Justificativa.objects.get_or_create(oficio=oficio)
        justificativa.modelo = form.cleaned_data.get('modelo_justificativa')
        justificativa.texto = form.cleaned_data.get('justificativa_texto') or ''
        justificativa.save(update_fields=['modelo', 'texto', 'updated_at'])
        messages.success(request, 'Justificativa salva com sucesso.')
        return redirect(next_url)
    context = _build_oficio_justificativa_context(oficio, next_url=next_url)
    context['form'] = form
    return render(
        request,
        'eventos/oficio/justificativa.html',
        _apply_oficio_wizard_context(
            context,
            oficio,
            'justificativa',
            'Justificativa',
            justificativa_info=context.get('justificativa_info'),
        ),
    )


@login_required
@require_http_methods(['GET'])
def oficio_documentos(request, pk):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    messages.info(request, 'Os downloads agora acontecem diretamente no resumo do oficio.')
    return redirect('eventos:oficio-step4', pk=oficio.pk)


def _get_or_create_termos_from_oficio(oficio, user=None):
    """
    Obtém ou cria registros TermoAutorizacao vinculados a este Ofício.
    Retorna (lista_de_termos, created_bool).
    """
    context = _build_termo_context_for_oficio(oficios=[oficio])
    viajantes = list(context['viajantes'])
    veiculo = context['veiculo_inferido']
    modo = TermoAutorizacao.infer_modo_geracao(
        has_servidores=bool(viajantes),
        has_viatura=bool(veiculo),
    )
    lote = uuid.uuid4() if modo != TermoAutorizacao.MODO_RAPIDO else None
    common = {
        'evento': context['evento'],
        'roteiro': context['roteiro'],
        'oficio': oficio,
        'destino': context['destino'] or '',
        'data_evento': context['data_evento'],
        'data_evento_fim': context['data_evento_fim'],
        'criado_por': user,
        'veiculo': veiculo,
        'status': TermoAutorizacao.STATUS_GERADO,
        'modo_geracao': modo,
        'template_variant': TermoAutorizacao.template_variant_for_mode(modo),
    }
    existing = list(
        TermoAutorizacao.objects.filter(oficio=oficio)
        .select_related('viajante', 'veiculo')
        .order_by('created_at', 'pk')
    )

    def sync_term(termo, *, viajante=None, lote_uuid=None):
        for field, value in common.items():
            setattr(termo, field, value)
        termo.viajante = viajante
        termo.lote_uuid = lote_uuid
        if user and not termo.criado_por_id:
            termo.criado_por = user
        termo.populate_snapshots_from_relations(force=True)
        termo.save()
        termo.oficios.add(oficio)
        return termo

    termos = []
    created = False
    if modo == TermoAutorizacao.MODO_RAPIDO:
        termo = next((item for item in existing if not item.viajante_id), None)
        if termo is None:
            termo = TermoAutorizacao()
            created = True
        termo = sync_term(termo, viajante=None, lote_uuid=None)
        termos.append(termo)
    else:
        terms_by_viajante_id = {
            item.viajante_id: item for item in existing if item.viajante_id
        }
        generic_terms = [item for item in existing if not item.viajante_id]
        for viajante in viajantes:
            termo = terms_by_viajante_id.get(viajante.pk)
            if termo is None and generic_terms:
                termo = generic_terms.pop(0)
            if termo is None:
                termo = TermoAutorizacao()
                created = True
            termo = sync_term(termo, viajante=viajante, lote_uuid=lote)
            termos.append(termo)
    used_term_ids = {termo.pk for termo in termos if termo.pk}
    for termo in existing:
        if not termo.pk or termo.pk in used_term_ids:
            continue
        changed_fields = []
        if termo.oficio_id == oficio.pk:
            termo.oficio = None
            changed_fields.append('oficio')
        if changed_fields:
            termo.save(update_fields=[*changed_fields, 'updated_at'])
        termo.oficios.remove(oficio)
    termos.sort(key=lambda item: ((item.viajante is None), item.servidor_display or '', item.pk or 0))
    return termos, created


def _download_oficio_documento(request, oficio, tipo_documento, formato):
    try:
        meta = get_document_type_meta(tipo_documento)
        formato = DocumentoFormato(formato)
    except (KeyError, ValueError):
        raise Http404('Documento inválido.')
    # Termo de Autorização: cria registro persistente e redireciona para download oficial
    if meta.tipo == DocumentoOficioTipo.TERMO_AUTORIZACAO:
        termos, created = _get_or_create_termos_from_oficio(oficio, user=request.user)
        if not termos:
            messages.error(request, 'Não foi possível registrar o termo de autorização para este ofício.')
            return redirect('eventos:oficio-step4', pk=oficio.pk)
        if created:
            messages.success(
                request,
                f'{len(termos)} termo(s) de autorização registrado(s) e vinculado(s) ao ofício.',
            )
        return redirect(
            reverse(
                'eventos:documentos-termos-download',
                kwargs={'pk': termos[0].pk, 'formato': formato.value},
            )
        )
    status_info = get_document_generation_status(oficio, meta.tipo, formato)
    if status_info['status'] != 'available':
        messages.error(
            request,
            (status_info.get('errors') or ['O documento solicitado não está disponível para download.'])[0],
        )
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    try:
        payload = render_document_bytes(oficio, meta.tipo, formato)
    except (DocumentGenerationError, DocumentRendererUnavailable) as exc:
        messages.error(request, str(exc))
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    filename = build_document_filename(oficio, meta.tipo, formato)
    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    if formato == DocumentoFormato.PDF:
        content_type = 'application/pdf'
    response = HttpResponse(payload, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def oficio_documento_download(request, pk, tipo_documento, formato):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    return _download_oficio_documento(request, oficio, tipo_documento, formato)


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step4(request, pk):
    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    if _bloquear_edicao_oficio_se_evento_finalizado(request, oficio):
        return redirect('eventos:oficios-global')
    evento = oficio.evento
    step4_url = reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk})
    if _is_autosave_request(request):
        _autosave_oficio_step4(oficio, request)
        return _autosave_success_response()
    if request.method == 'POST':
        gerar_termo_preenchido = _parse_step4_termo_choice(request, oficio)
        termo_changed = oficio.gerar_termo_preenchido != gerar_termo_preenchido
        if termo_changed:
            oficio.gerar_termo_preenchido = gerar_termo_preenchido
        if request.POST.get('salvar_oficio'):
            _save_oficio_preserving_status(oficio, ['gerar_termo_preenchido'])
            messages.success(request, 'Ofício salvo.')
            return redirect(step4_url)
        if termo_changed:
            _save_oficio_preserving_status(oficio, ['gerar_termo_preenchido'])
        if request.POST.get('voltar_etapa3') and evento:
            return redirect('eventos:guiado-etapa-5', evento_id=evento.pk)
        if request.POST.get('finalizar'):
            finalize_validation = _validate_oficio_for_finalize(oficio)
            if not finalize_validation['ok']:
                if (
                    finalize_validation['justificativa_missing']
                    and not finalize_validation['has_non_justificativa_errors']
                ):
                    messages.error(request, 'Preencha a justificativa antes de finalizar o ofício.')
                    return redirect(_oficio_justificativa_url(oficio, next_url=step4_url))
                messages.error(request, 'O ofício não pode ser finalizado enquanto houver pendências.')
                context = _build_oficio_step4_context(oficio, finalize_validation=finalize_validation)
                return render(
                    request,
                    'eventos/oficio/wizard_step4.html',
                    _apply_oficio_wizard_context(
                        context,
                        oficio,
                        'summary',
                        'Resumo',
                        justificativa_info=context.get('justificativa_info'),
                    ),
                )
            termos = []
            termos_created = False
            with transaction.atomic():
                if termo_changed:
                    _save_oficio_preserving_status(oficio, ['gerar_termo_preenchido'])
                oficio.status = Oficio.STATUS_FINALIZADO
                oficio.save(update_fields=['status', 'updated_at'])
                if gerar_termo_preenchido:
                    termos, termos_created = _get_or_create_termos_from_oficio(oficio, user=request.user)

            messages.success(request, 'Ofício finalizado com sucesso.')
            if gerar_termo_preenchido:
                if termos and termos_created:
                    messages.success(
                        request,
                        f'{len(termos)} termo(s) de autorização gerado(s) e vinculado(s) ao ofício.',
                    )
                elif termos:
                    messages.info(
                        request,
                        f'{len(termos)} termo(s) de autorização já existente(s) para este ofício.',
                    )
                else:
                    messages.warning(
                        request,
                        'Não foi possível gerar termos de autorização para este ofício.',
                    )
        return redirect('eventos:oficios-global')
    context = _build_oficio_step4_context(oficio)
    return render(
        request,
        'eventos/oficio/wizard_step4.html',
        _apply_oficio_wizard_context(
            context,
            oficio,
            'summary',
            'Resumo',
            justificativa_info=context.get('justificativa_info'),
        ),
    )


# ---------- Roteiros do evento (etapa 2 no fluxo de negócio) ----------

def _get_evento_etapa2(evento_id):
    """Retorna o evento ou 404 (rotas legadas de roteiros)."""
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
    """Lista de roteiros do evento (Etapa 2). RASCUNHO primeiro, depois FINALIZADO."""
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


def _build_roteiro_avulso_route_options():
    """
    Build route_options from all avulso roteiros.
    Returns (options_list, state_map) mirroring _build_step3_route_options.
    """
    options = []
    state_map = {}
    roteiros = (
        RoteiroEvento.objects
        .filter(tipo=RoteiroEvento.TIPO_AVULSO)
        .prefetch_related(
            'destinos', 'destinos__estado', 'destinos__cidade',
            'trechos', 'trechos__origem_estado', 'trechos__origem_cidade',
            'trechos__destino_estado', 'trechos__destino_cidade',
            'origem_cidade', 'origem_estado',
        )
        .order_by('-pk')[:50]
    )
    for roteiro in roteiros:
        destinos = [
            _step3_local_label(destino.cidade, destino.estado)
            for destino in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem', 'id')
        ]
        resumo = ' -> '.join(destinos[:3]) if destinos else 'Sem destinos'
        if len(destinos) > 3:
            resumo += ' -> ...'
        state = _build_step3_state_from_roteiro_evento(roteiro)
        state_map[roteiro.pk] = state
        options.append({
            'id': roteiro.pk,
            'label': state.get('roteiro_evento_label') or f'Roteiro #{roteiro.pk}',
            'resumo': resumo,
            'status': roteiro.status,
            'tipo_label': 'Avulso',
            'state': _serialize_step3_state(state),
        })
    return options, state_map


def _build_avulso_step3_state_from_post(request, route_state_map=None):
    """Reuses Step 3 parser with avulso field aliases (origem_* -> sede_*)."""
    from types import SimpleNamespace

    post_data = request.POST.copy()
    if 'sede_estado' not in post_data and 'origem_estado' in post_data:
        post_data['sede_estado'] = post_data.get('origem_estado')
    if 'sede_cidade' not in post_data and 'origem_cidade' in post_data:
        post_data['sede_cidade'] = post_data.get('origem_cidade')

    fake_request = SimpleNamespace(POST=post_data)
    fake_oficio = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
    return _build_step3_state_from_post(
        fake_request,
        oficio=fake_oficio,
        route_state_map=route_state_map or {},
    )


def _calculate_avulso_diarias_from_state(state):
    """Calculates roteiro avulso diarias using official service with fixed one-server rule."""
    markers, paradas, chegada_final, sede_cidade, sede_uf = _collect_step3_markers_payload(state)
    resultado = calculate_periodized_diarias(
        markers,
        chegada_final,
        quantidade_servidores=1,
        sede_cidade=sede_cidade,
        sede_uf=sede_uf,
    )
    resultado['tipo_destino'] = infer_tipo_destino_from_paradas(paradas)
    return resultado


def _build_roteiro_form_context(*, evento, form, obj, destinos_atuais, trechos_list, is_avulso=False, step3_state=None, route_options=None, seed_source_label=''):
    """
    Monta contexto completo para o formulário de roteiro (guiado e avulso).
    Quando step3_state é fornecido, usa diretamente; caso contrário, constrói
    a partir de trechos_list + destinos_atuais (compatibilidade com forms guiados).
    """
    if step3_state is None:
        instance = obj or form.instance
        sede_estado_id = getattr(instance, 'origem_estado_id', None)
        sede_cidade_id = getattr(instance, 'origem_cidade_id', None)
        step3_state = _build_step3_state_from_estrutura(
            trechos_list,
            [{'estado_id': d.get('estado_id'), 'cidade_id': d.get('cidade_id')} for d in (destinos_atuais or [])],
            sede_estado_id,
            sede_cidade_id,
            seed_source_label,
        )
        step3_state['roteiro_modo'] = 'ROTEIRO_PROPRIO'

    sede_estado_id = step3_state.get('sede_estado_id')
    sede_cidade_id = step3_state.get('sede_cidade_id')
    estados_qs = Estado.objects.filter(ativo=True).order_by('nome')
    sede_cidades_qs = (
        Cidade.objects.filter(estado_id=sede_estado_id, ativo=True).order_by('nome')
        if sede_estado_id
        else Cidade.objects.none()
    )
    diarias_resultado = None
    if is_avulso:
        try:
            diarias_resultado = _calculate_avulso_diarias_from_state(step3_state)
        except ValueError:
            diarias_resultado = None
    destino_estado_fixo = _get_parana_estado()
    return {
        'evento': evento,
        'object': obj,
        'form': form,
        'destinos_atuais': destinos_atuais,
        'estados': estados_qs,
        'api_cidades_por_estado_url': reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': 0}),
        'trechos': trechos_list,
        'step3_state_json': _serialize_step3_state(step3_state),
        'step3_diarias_resultado': diarias_resultado,
        'step3_seed_source_label': step3_state.get('seed_source_label', ''),
        'api_calcular_diarias_url': (
            reverse('eventos:roteiro-avulso-calcular-diarias')
            if is_avulso
            else ''
        ),
        'roteiro_modo': step3_state.get('roteiro_modo', 'ROTEIRO_PROPRIO'),
        'roteiro_evento_id': step3_state.get('roteiro_evento_id'),
        'roteiros_evento': route_options or [],
        'roteiros_evento_json': route_options or [],
        'has_event_routes': bool(route_options),
        'is_avulso': is_avulso,
        'retorno_state': step3_state.get('retorno', {}),
        'sede_estado_id': sede_estado_id,
        'sede_cidade_id': sede_cidade_id,
        'sede_cidades_qs': sede_cidades_qs,
        'destino_estado_fixo_id': getattr(destino_estado_fixo, 'pk', None),
        'destino_estado_fixo_nome': (
            f'{destino_estado_fixo.nome} ({destino_estado_fixo.sigla})'
            if destino_estado_fixo
            else 'Paraná (PR)'
        ),
    }


@login_required
def guiado_etapa_2_cadastrar(request, evento_id):
    """Criar roteiro. Sede pré-preenchida da ConfiguracaoSistema; destinos pré-preenchidos da Etapa 1 do evento.
    Usa o mesmo template e a mesma lógica de trechos da edição; trechos já vêm renderizados no primeiro load."""
    evento = _get_evento_etapa2(evento_id)
    from types import SimpleNamespace
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
            num_trechos = len(destinos_post)
            trechos_times = _parse_trechos_times_post(request, num_trechos)
            retorno_data = _parse_retorno_from_post(request)
            trechos_times.append(retorno_data)
            _salvar_roteiro_com_destinos_e_trechos(roteiro, destinos_post, trechos_times)
            return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        destinos_atuais = [
            {'estado_id': eid, 'cidade_id': cid, 'cidade': None, 'estado': None}
            for eid, cid in destinos_post
        ]
    if not destinos_atuais and request.method != 'POST':
        destinos_atuais = [{'estado_id': None, 'cidade_id': None, 'cidade': None, 'estado': None}]
    trechos_list = []
    if request.method != 'POST' and destinos_atuais:
        destinos_list = [(d.get('estado_id'), d.get('cidade_id')) for d in destinos_atuais if d.get('estado_id') and d.get('cidade_id')]
        if destinos_list and (initial.get('origem_estado') or initial.get('origem_cidade')):
            roteiro_virtual = _roteiro_virtual_para_trechos(initial)
            trechos_list = _estrutura_trechos(roteiro_virtual, destinos_list)
    route_options, _ = _build_step3_route_options(
        SimpleNamespace(roteiro_evento_id=None, evento_id=evento.pk)
    )
    context = _build_roteiro_form_context(
        evento=evento,
        form=form,
        obj=None,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=False,
        route_options=route_options,
    )
    return render(request, 'eventos/guiado/roteiro_form.html', context)


@login_required
def guiado_etapa_2_editar(request, evento_id, pk):
    """Editar roteiro (mostra dados salvos; trechos com horários próprios editáveis)."""
    evento = _get_evento_etapa2(evento_id)
    from types import SimpleNamespace
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
            num_trechos = len(destinos_post)
            trechos_times = _parse_trechos_times_post(request, num_trechos)
            retorno_data = _parse_retorno_from_post(request)
            trechos_times.append(retorno_data)
            _salvar_roteiro_com_destinos_e_trechos(roteiro, destinos_post, trechos_times)
            return redirect('eventos:guiado-etapa-2', evento_id=evento.pk)
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        destinos_atuais = [{'estado_id': eid, 'cidade_id': cid, 'cidade': None, 'estado': None} for eid, cid in destinos_post]
        if destinos_post:
            trechos_list = _estrutura_trechos(roteiro, destinos_post)
        else:
            trechos_list = []
    else:
        destinos_atuais = _destinos_roteiro_para_template(roteiro)
        trechos_list = _estrutura_trechos(roteiro)
    if not destinos_atuais:
        destinos_atuais = [{'estado_id': None, 'cidade_id': None, 'cidade': None, 'estado': None}]
    route_options, _ = _build_step3_route_options(
        SimpleNamespace(roteiro_evento_id=roteiro.pk, evento_id=evento.pk)
    )
    context = _build_roteiro_form_context(
        evento=evento,
        form=form,
        obj=roteiro,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=False,
        route_options=route_options,
    )
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
@require_http_methods(['GET', 'POST'])
def roteiro_avulso_cadastrar(request):
    """Cadastro de roteiro avulso — espelha lógica do oficio_step3."""
    from cadastros.models import ConfiguracaoSistema

    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    if getattr(config, 'cidade_sede_padrao', None):
        initial['origem_cidade'] = config.cidade_sede_padrao_id
        if config.cidade_sede_padrao.estado_id:
            initial['origem_estado'] = config.cidade_sede_padrao.estado_id
    form = RoteiroEventoForm(request.POST or None, initial=initial)
    form.instance.tipo = RoteiroEvento.TIPO_AVULSO
    if request.method != 'POST' and initial:
        form.instance.origem_cidade_id = initial.get('origem_cidade')
        form.instance.origem_estado_id = initial.get('origem_estado')
    _setup_roteiro_querysets(form, request, None)
    route_options, route_state_map = _build_roteiro_avulso_route_options()
    if request.method == 'POST':
        roteiro_modo = (request.POST.get('roteiro_modo') or '').strip()
        if roteiro_modo not in {'EVENTO_EXISTENTE', 'ROTEIRO_PROPRIO'}:
            roteiro_modo = 'ROTEIRO_PROPRIO'
        roteiro_evento_id = _parse_int(request.POST.get('roteiro_evento_id'))
        destinos_post = _parse_destinos_post(request)
        ok_destinos, msg_destinos = _validar_destinos(destinos_post)
        if form.is_valid() and ok_destinos:
            roteiro = form.save(commit=False)
            roteiro.evento = None
            roteiro.tipo = RoteiroEvento.TIPO_AVULSO
            roteiro.save()
            num_trechos = len(destinos_post)
            trechos_times = _parse_trechos_times_post(request, num_trechos)
            retorno_data = _parse_retorno_from_post(request)
            trechos_times.append(retorno_data)
            _salvar_roteiro_com_destinos_e_trechos(roteiro, destinos_post, trechos_times)
            return redirect('eventos:roteiros-global')
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        destinos_atuais = [
            {'estado_id': eid, 'cidade_id': cid, 'cidade': None, 'estado': None}
            for eid, cid in destinos_post
        ]
        trechos_list = _estrutura_trechos(form.instance, destinos_post) if destinos_post and (form.instance.origem_estado_id or form.instance.origem_cidade_id) else []
        step3_state = _build_step3_state_from_estrutura(
            trechos_list,
            [{'estado_id': d['estado_id'], 'cidade_id': d['cidade_id']} for d in destinos_atuais],
            form.instance.origem_estado_id, form.instance.origem_cidade_id, '',
        )
        step3_state['roteiro_modo'] = roteiro_modo
        step3_state['roteiro_evento_id'] = roteiro_evento_id
    else:
        roteiro_modo = 'ROTEIRO_PROPRIO'
        roteiro_evento_id = None
        destinos_atuais = [{'estado_id': None, 'cidade_id': None, 'cidade': None, 'estado': None}]
        trechos_list = []
        step3_state = _build_step3_state_from_estrutura(
            trechos_list,
            [{'estado_id': None, 'cidade_id': None}],
            initial.get('origem_estado'), initial.get('origem_cidade'), '',
        )
        step3_state['roteiro_modo'] = roteiro_modo
    context = _build_roteiro_form_context(
        evento=None,
        form=form,
        obj=None,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        step3_state=step3_state,
        route_options=route_options,
    )
    return render(request, 'eventos/global/roteiro_avulso_form.html', context)


@login_required
@require_http_methods(['GET', 'POST'])
def roteiro_avulso_editar(request, pk):
    """Edição de roteiro avulso — espelha lógica do oficio_step3."""
    roteiro = get_object_or_404(
        RoteiroEvento.objects.prefetch_related(
            'destinos', 'destinos__estado', 'destinos__cidade',
            'trechos', 'trechos__origem_estado', 'trechos__origem_cidade',
            'trechos__destino_estado', 'trechos__destino_cidade',
        ).select_related('origem_estado', 'origem_cidade'),
        pk=pk,
    )
    form = RoteiroEventoForm(request.POST or None, instance=roteiro)
    _setup_roteiro_querysets(form, request, roteiro)
    route_options, route_state_map = _build_roteiro_avulso_route_options()
    if request.method == 'POST':
        roteiro_modo = (request.POST.get('roteiro_modo') or '').strip()
        if roteiro_modo not in {'EVENTO_EXISTENTE', 'ROTEIRO_PROPRIO'}:
            roteiro_modo = 'ROTEIRO_PROPRIO'
        roteiro_evento_id = _parse_int(request.POST.get('roteiro_evento_id'))
        destinos_post = _parse_destinos_post(request)
        ok_destinos, msg_destinos = _validar_destinos(destinos_post)
        if form.is_valid() and ok_destinos:
            roteiro_saved = form.save(commit=False)
            roteiro_saved.evento = roteiro.evento
            roteiro_saved.tipo = roteiro.tipo or RoteiroEvento.TIPO_AVULSO
            roteiro_saved.save()
            num_trechos = len(destinos_post)
            trechos_times = _parse_trechos_times_post(request, num_trechos)
            retorno_data = _parse_retorno_from_post(request)
            trechos_times.append(retorno_data)
            _salvar_roteiro_com_destinos_e_trechos(roteiro_saved, destinos_post, trechos_times)
            return redirect('eventos:roteiros-global')
        if not ok_destinos:
            form.add_error(None, msg_destinos)
        destinos_atuais = [
            {'estado_id': eid, 'cidade_id': cid, 'cidade': None, 'estado': None}
            for eid, cid in destinos_post
        ]
        trechos_list = _estrutura_trechos(roteiro, destinos_post) if destinos_post else []
        step3_state = _build_step3_state_from_estrutura(
            trechos_list,
            [{'estado_id': d['estado_id'], 'cidade_id': d['cidade_id']} for d in destinos_atuais],
            roteiro.origem_estado_id, roteiro.origem_cidade_id, '',
        )
        step3_state['roteiro_modo'] = roteiro_modo
        step3_state['roteiro_evento_id'] = roteiro_evento_id
    else:
        destinos_atuais = _destinos_roteiro_para_template(roteiro)
        if not destinos_atuais:
            destinos_atuais = [{'estado_id': None, 'cidade_id': None, 'cidade': None, 'estado': None}]
        destinos_list = [(d.get('estado_id'), d.get('cidade_id')) for d in destinos_atuais if d.get('estado_id') and d.get('cidade_id')]
        trechos_list = _estrutura_trechos(roteiro, destinos_list) if destinos_list else []
        step3_state = _build_step3_state_from_roteiro_evento(roteiro)
        step3_state['roteiro_modo'] = 'ROTEIRO_PROPRIO'
    context = _build_roteiro_form_context(
        evento=None,
        form=form,
        obj=roteiro,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        step3_state=step3_state,
        route_options=route_options,
    )
    return render(request, 'eventos/global/roteiro_avulso_form.html', context)


@login_required
@require_http_methods(['POST'])
def roteiro_avulso_calcular_diarias(request):
    """Realtime diarias calculation for roteiro avulso (always one server)."""
    from types import SimpleNamespace

    route_options, route_state_map = _build_roteiro_avulso_route_options()
    step3_state = _build_avulso_step3_state_from_post(request, route_state_map=route_state_map)
    fake_oficio = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
    validated = _validate_step3_state(step3_state, oficio=fake_oficio)
    if not validated['ok']:
        return JsonResponse(
            {
                'ok': False,
                'error': 'Revise os dados do roteiro antes de calcular as diárias.',
                'errors': validated['errors'],
            },
            status=400,
        )
    try:
        resultado = _calculate_avulso_diarias_from_state(step3_state)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    payload = {'ok': True, 'quantidade_servidores_fixo': 1, 'roteiros_disponiveis': len(route_options)}
    payload.update(resultado)
    return JsonResponse(payload)


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
        trecho.duracao_estimada_min = out['duracao_estimada_min']  # inclui correção final por distância
        trecho.rota_fonte = ROTA_FONTE_ESTIMATIVA_LOCAL
        trecho.rota_calculada_em = timezone.now()
        trecho.save(update_fields=[
            'distancia_km', 'tempo_cru_estimado_min', 'tempo_adicional_min',
            'duracao_estimada_min', 'rota_fonte', 'rota_calculada_em', 'updated_at'
        ])

    return JsonResponse({
        'ok': out['ok'],
        'distancia_km': float(out['distancia_km']) if out['distancia_km'] is not None else None,
        'distancia_linha_reta_km': out.get('distancia_linha_reta_km'),
        'distancia_rodoviaria_km': out.get('distancia_rodoviaria_km'),
        'duracao_estimada_min': out['duracao_estimada_min'],
        'duracao_estimada_hhmm': out['duracao_estimada_hhmm'],
        'tempo_viagem_estimado_min': out.get('tempo_viagem_estimado_min'),
        'tempo_viagem_estimado_hhmm': out.get('tempo_viagem_estimado_hhmm'),
        'buffer_operacional_sugerido_min': out.get('buffer_operacional_sugerido_min'),
        'tempo_cru_estimado_min': out.get('tempo_cru_estimado_min'),
        'tempo_adicional_sugerido_min': out.get('tempo_adicional_sugerido_min'),
        'correcao_final_min': out.get('correcao_final_min'),
        'velocidade_media_kmh': out.get('velocidade_media_kmh'),
        'perfil_rota': out.get('perfil_rota'),
        'corredor': out.get('corredor'),
        'corredor_macro': out.get('corredor_macro'),
        'corredor_fino': out.get('corredor_fino'),
        'rota_fonte': out.get('rota_fonte', ROTA_FONTE_ESTIMATIVA_LOCAL),
        'fallback_usado': out.get('fallback_usado'),
        'confianca_estimativa': out.get('confianca_estimativa'),
        'refs_predominantes': out.get('refs_predominantes') or [],
        'pedagio_presente': out.get('pedagio_presente', False),
        'travessia_urbana_presente': out.get('travessia_urbana_presente', False),
        'serra_presente': out.get('serra_presente', False),
        'erro': out['erro'],
    })


def _step2_field_value(form, field_name):
    if form.is_bound:
        return (form.data.get(field_name) or '').strip()
    value = form.initial.get(field_name)
    if value is None:
        return ''
    return str(value).strip()


def _build_motorista_preview_data(form):
    selected_value = getattr(form, 'selected_motorista_value', '')
    manual_name = _step2_field_value(form, 'motorista_nome')
    is_manual = getattr(form, 'motorista_manual_selected', False)
    is_carona = getattr(form, 'motorista_carona_selected', False)
    selected_option = getattr(form, 'selected_motorista_payload', None) or {}
    numero = _step2_field_value(form, 'motorista_oficio_numero')
    ano = _step2_field_value(form, 'motorista_oficio_ano')
    protocolo = _step2_field_value(form, 'motorista_protocolo')
    nome = manual_name if is_manual else selected_option.get('nome', '')
    cargo = '' if is_manual else selected_option.get('cargo', '')
    rg = '' if is_manual else selected_option.get('rg', '')
    cpf = '' if is_manual else selected_option.get('cpf', '')
    if is_carona and numero and ano:
        try:
            oficio = f'{int(numero):02d}/{int(ano)}'
        except (TypeError, ValueError):
            oficio = f'{numero}/{ano}'
    else:
        oficio = ''
    protocolo_value = format_protocolo(protocolo) if (is_carona and protocolo) else ''

    return {
        'selected_value': selected_value,
        'manual_name': manual_name,
        'is_manual': is_manual,
        'is_carona': is_carona,
        'has_value': bool(nome),
        'nome': nome,
        'nome_display': f'{nome} (carona)' if nome and is_carona else nome,
        'cpf': cpf,
        'rg': rg,
        'cargo': cargo,
        'show_cargo': bool(cargo),
        'show_cpf': bool(cpf),
        'show_rg': bool(rg),
        'oficio': oficio,
        'protocolo': protocolo_value,
        'show_oficio': bool(oficio),
        'show_protocolo': bool(protocolo_value),
    }


def _build_oficio_step2_initial(oficio):
    return {
        'placa': oficio.placa or '',
        'modelo': oficio.modelo or '',
        'combustivel': oficio.combustivel or '',
        'tipo_viatura': oficio.tipo_viatura or Oficio.TIPO_VIATURA_DESCARACTERIZADA,
        'porte_transporte_armas': oficio.porte_transporte_armas,
        'motorista_viajante': oficio.motorista_viajante_id,
        'motorista_nome': '' if oficio.motorista_viajante_id else (oficio.motorista or ''),
        'motorista_carona': oficio.motorista_carona,
        'motorista_oficio_numero': oficio.motorista_oficio_numero,
        'motorista_oficio_ano': oficio.motorista_oficio_ano or timezone.localdate().year,
        'motorista_protocolo': oficio.motorista_protocolo or '',
    }


def _build_step2_preview_data(oficio, form):
    tipo_value = _step2_field_value(form, 'tipo_viatura') or Oficio.TIPO_VIATURA_DESCARACTERIZADA
    porte_raw = _step2_field_value(form, 'porte_transporte_armas')
    porte_transporte_armas = str(porte_raw).strip().lower() not in ('0', 'false', 'nao', 'n\u00e3o')
    motorista_preview = _build_motorista_preview_data(form)
    veiculo = None
    if not form.is_bound:
        veiculo = oficio.veiculo
        if not veiculo and oficio.placa:
            from .utils import buscar_veiculo_finalizado_por_placa
            veiculo = buscar_veiculo_finalizado_por_placa(oficio.placa)

    veiculo_lookup = {
        'found': bool(veiculo),
        'message': '',
    }
    if veiculo:
        veiculo_lookup['message'] = f'Viatura localizada: {veiculo.modelo}.'
    elif _step2_field_value(form, 'placa'):
        veiculo_lookup['message'] = 'Placa não localizada no cadastro. Você pode preencher manualmente.'

    return {
        'placa': _step2_field_value(form, 'placa'),
        'modelo': _step2_field_value(form, 'modelo'),
        'combustivel': _step2_field_value(form, 'combustivel'),
        'tipo_viatura': tipo_value,
        'tipo_viatura_label': dict(Oficio.TIPO_VIATURA_CHOICES).get(tipo_value, ''),
        'porte_transporte_armas': porte_transporte_armas,
        'porte_transporte_armas_label': 'Sim' if porte_transporte_armas else 'N\u00e3o',
        'motorista': motorista_preview,
        'veiculo_lookup': veiculo_lookup,
    }


def _get_plano_trabalho_preferencial(oficio):
    if not oficio:
        return None
    plano = PlanoTrabalho.objects.filter(oficios=oficio).order_by('-updated_at').first()
    if plano:
        return plano
    plano = PlanoTrabalho.objects.filter(oficio=oficio).order_by('-updated_at').first()
    if plano:
        return plano
    if oficio.evento_id:
        return (
            PlanoTrabalho.objects.filter(Q(evento=oficio.evento) | Q(oficios__evento=oficio.evento))
            .distinct()
            .order_by('-updated_at')
            .first()
        )
    return None


def _display_name_or_str(obj):
    if not obj:
        return ''
    return (getattr(obj, 'nome', '') or str(obj)).strip()


def _build_oficio_responsavel_label(oficio):
    plano = _get_plano_trabalho_preferencial(oficio)
    if not plano:
        return ''
    if plano.coordenador_operacional_id and plano.coordenador_operacional:
        return _display_name_or_str(plano.coordenador_operacional)
    if plano.coordenador_administrativo_id and plano.coordenador_administrativo:
        return _display_name_or_str(plano.coordenador_administrativo)
    if plano.solicitante_id and plano.solicitante:
        return _display_name_or_str(plano.solicitante)
    return (plano.solicitante_outros or '').strip()


def _build_step3_periodo_display_from_state(state):
    state = state or {}
    trechos = state.get('trechos') or []
    retorno = state.get('retorno') or {}
    inicio = ''
    fim = ''
    if trechos:
        primeiro = trechos[0]
        inicio = _step3_format_date_time_br(primeiro.get('saida_data'), primeiro.get('saida_hora'))
        ultimo = trechos[-1]
        fim = _step3_format_date_time_br(ultimo.get('chegada_data'), ultimo.get('chegada_hora'))
    fim_retorno = _step3_format_date_time_br(retorno.get('chegada_data'), retorno.get('chegada_hora'))
    if fim_retorno:
        fim = fim_retorno
    if inicio and fim:
        return f'{inicio} até {fim}'
    return inicio or fim


def _build_step3_destino_principal_from_state(state):
    destinos = []
    vistos = set()
    for trecho in (state or {}).get('trechos') or []:
        nome = (trecho.get('destino_nome') or '').strip()
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        destinos.append(nome)
    if not destinos:
        return ''
    if len(destinos) == 1:
        return destinos[0]
    return f'{destinos[0]} (+{len(destinos) - 1})'


def _autosave_oficio_step2(oficio, request):
    from .utils import buscar_veiculo_finalizado_por_placa, mapear_tipo_viatura_para_oficio

    placa = normalize_placa(request.POST.get('placa') or '')
    veiculo = buscar_veiculo_finalizado_por_placa(placa) if placa else None
    modelo = ' '.join(((request.POST.get('modelo') or '').strip().upper()).split())
    combustivel = ' '.join(((request.POST.get('combustivel') or '').strip().upper()).split())
    tipo_viatura = request.POST.get('tipo_viatura') or Oficio.TIPO_VIATURA_DESCARACTERIZADA
    if tipo_viatura not in dict(Oficio.TIPO_VIATURA_CHOICES):
        tipo_viatura = Oficio.TIPO_VIATURA_DESCARACTERIZADA
    porte_raw = (request.POST.get('porte_transporte_armas') or '1').strip().lower()
    porte_transporte_armas = porte_raw not in ('0', 'false', 'nao', 'não')
    if veiculo:
        if not modelo:
            modelo = (veiculo.modelo or '').strip().upper()
        if not combustivel and getattr(veiculo, 'combustivel_id', None):
            combustivel = ((veiculo.combustivel.nome or '').strip().upper())
        if not request.POST.get('tipo_viatura'):
            tipo_viatura = mapear_tipo_viatura_para_oficio(veiculo.tipo)

    motorista_raw = (request.POST.get('motorista_viajante') or '').strip()
    motorista_manual = ' '.join(((request.POST.get('motorista_nome') or '').strip().upper()).split())
    motorista_obj = None
    if motorista_raw.isdigit():
        motorista_obj = Viajante.objects.filter(pk=int(motorista_raw)).first()
    manual_selected = motorista_raw == OficioStep2Form.MOTORISTA_SEM_CADASTRO or (
        not motorista_raw and bool(motorista_manual)
    )
    motorista_nome_final = motorista_obj.nome if motorista_obj else motorista_manual
    viajantes_ids = set(oficio.viajantes.values_list('pk', flat=True))
    motorista_carona = bool(manual_selected or (motorista_obj and motorista_obj.pk not in viajantes_ids))
    motorista_oficio_numero = _parse_int(request.POST.get('motorista_oficio_numero'))
    motorista_oficio_ano = _parse_int(request.POST.get('motorista_oficio_ano')) or timezone.localdate().year
    motorista_protocolo = Oficio.normalize_protocolo(request.POST.get('motorista_protocolo') or '')

    oficio.veiculo = veiculo
    oficio.placa = placa
    oficio.modelo = modelo
    oficio.combustivel = combustivel
    oficio.tipo_viatura = tipo_viatura
    oficio.porte_transporte_armas = porte_transporte_armas
    oficio.motorista_viajante = motorista_obj
    oficio.motorista = motorista_nome_final if motorista_nome_final else ''
    oficio.motorista_carona = motorista_carona
    if motorista_carona:
        oficio.motorista_oficio_numero = motorista_oficio_numero
        oficio.motorista_oficio_ano = motorista_oficio_ano if motorista_oficio_numero else None
        oficio.motorista_oficio = (
            f'{int(motorista_oficio_numero):02d}/{int(motorista_oficio_ano)}'
            if motorista_oficio_numero and motorista_oficio_ano
            else ''
        )
        oficio.motorista_protocolo = motorista_protocolo
        if oficio.motorista_oficio_numero and oficio.motorista_oficio_ano:
            oficio.carona_oficio_referencia = (
                Oficio.objects.filter(
                    numero=oficio.motorista_oficio_numero,
                    ano=oficio.motorista_oficio_ano,
                )
                .exclude(pk=oficio.pk)
                .first()
            )
        else:
            oficio.carona_oficio_referencia = None
    else:
        oficio.motorista_oficio_numero = None
        oficio.motorista_oficio_ano = None
        oficio.motorista_oficio = ''
        oficio.motorista_protocolo = ''
        oficio.carona_oficio_referencia = None

    _save_oficio_preserving_status(
        oficio,
        [
            'veiculo_id',
            'placa',
            'modelo',
            'combustivel',
            'tipo_viatura',
            'porte_transporte_armas',
            'motorista_viajante_id',
            'motorista',
            'motorista_carona',
            'motorista_oficio',
            'motorista_oficio_numero',
            'motorista_oficio_ano',
            'motorista_protocolo',
            'carona_oficio_referencia_id',
        ],
    )


@login_required
@require_http_methods(['GET'])
def oficio_step2_veiculos_busca_api(request):
    """Busca viaturas finalizadas por placa/modelo para o autocomplete do Step 2."""
    termo = (request.GET.get('q') or request.GET.get('placa') or '').strip()
    veiculos = buscar_veiculos_finalizados(termo, limit=10)
    results = []
    for veiculo in veiculos:
        payload = serializar_veiculo_para_oficio(veiculo)
        payload['id'] = veiculo.pk
        payload['label'] = (
            f"{payload['placa_formatada']} — {payload['modelo']} — "
            f"{payload['combustivel'] or 'Sem combustível'}"
        )
        results.append(payload)
    return JsonResponse({'results': results})


@login_required
@require_http_methods(['GET'])
def oficio_step2_veiculo_api(request):
    """Busca veículo finalizado por placa para autopreenchimento do Step 2."""
    placa = (request.GET.get('placa') or '').strip()
    veiculo = buscar_veiculo_finalizado_por_placa(placa)
    if not veiculo:
        return JsonResponse({'ok': True, 'found': False})
    payload = serializar_veiculo_para_oficio(veiculo)
    payload.update({'ok': True, 'found': True})
    return JsonResponse(payload)


@login_required
@require_http_methods(['GET', 'POST'])
def oficio_step2(request, pk):
    """Wizard Step 2 — Transporte do ofício com lookup de viatura e regra automática de carona."""
    from cadastros.models import CombustivelVeiculo

    oficio = _get_oficio_or_404_for_user(pk, user=request.user)
    if _bloquear_edicao_oficio_se_evento_finalizado(request, oficio):
        return redirect('eventos:oficio-step4', pk=oficio.pk)
    evento = oficio.evento
    if _is_autosave_request(request):
        _autosave_oficio_step2(oficio, request)
        return _autosave_success_response()
    initial = _build_oficio_step2_initial(oficio)
    form = OficioStep2Form(request.POST or None, initial=initial, oficio=oficio)
    if request.method == 'POST' and form.is_valid():
        motorista_obj = form.cleaned_data.get('motorista_viajante_obj')
        oficio.veiculo = form.cleaned_data.get('veiculo_cadastrado')
        oficio.placa = (form.cleaned_data.get('placa') or '').strip()
        oficio.modelo = (form.cleaned_data.get('modelo') or '').strip()
        oficio.combustivel = (form.cleaned_data.get('combustivel') or '').strip()
        oficio.tipo_viatura = form.cleaned_data.get('tipo_viatura') or Oficio.TIPO_VIATURA_DESCARACTERIZADA
        oficio.porte_transporte_armas = bool(form.cleaned_data.get('porte_transporte_armas'))
        oficio.motorista_viajante_id = motorista_obj.pk if motorista_obj else None
        oficio.motorista = (form.cleaned_data.get('motorista_nome_final') or '').strip()
        oficio.motorista_carona = form.cleaned_data.get('motorista_carona') or False
        oficio.motorista_oficio_numero = form.cleaned_data.get('motorista_oficio_numero') or None
        oficio.motorista_oficio_ano = form.cleaned_data.get('motorista_oficio_ano') or None
        oficio.motorista_oficio = form.cleaned_data.get('motorista_oficio') or ''
        oficio.motorista_protocolo = (form.cleaned_data.get('motorista_protocolo') or '').strip()
        # Preencher carona_oficio_referencia quando motorista carona e número/ano informados
        if oficio.motorista_carona and oficio.motorista_oficio_numero is not None and oficio.motorista_oficio_ano is not None:
            ref = Oficio.objects.filter(
                numero=oficio.motorista_oficio_numero,
                ano=oficio.motorista_oficio_ano,
            ).exclude(pk=oficio.pk).first()
            oficio.carona_oficio_referencia = ref
        else:
            oficio.carona_oficio_referencia = None
        _save_oficio_preserving_status(oficio, [
            'veiculo_id', 'placa', 'modelo', 'combustivel', 'tipo_viatura',
            'porte_transporte_armas',
            'motorista_viajante_id', 'motorista', 'motorista_carona',
            'motorista_oficio', 'motorista_oficio_numero', 'motorista_oficio_ano',
            'motorista_protocolo', 'carona_oficio_referencia_id',
        ])
        messages.success(request, 'Transporte e motorista salvos.')
        if request.POST.get('avancar'):
            return redirect('eventos:oficio-step3', pk=oficio.pk)
        return redirect('eventos:oficio-step2', pk=oficio.pk)

    combustivel_opcoes = list(
        CombustivelVeiculo.objects.order_by('nome').values_list('nome', flat=True)
    )
    step1_preview = _build_oficio_step1_preview(oficio)
    step2_preview = _build_step2_preview_data(oficio, form)
    context = {
        'oficio': oficio,
        'evento': evento,
        'form': form,
        'step': 2,
        'next_step_url': reverse('eventos:oficio-step3', kwargs={'pk': oficio.pk}),
        'buscar_veiculos_url': reverse('eventos:oficio-step2-veiculos-busca-api'),
        'buscar_veiculo_url': reverse('eventos:oficio-step2-veiculo-api'),
        'buscar_motoristas_url': reverse('eventos:oficio-step2-motoristas-api'),
        'cadastrar_veiculo_url': (
            f"{reverse('cadastros:veiculo-cadastrar')}?next="
            f"{quote(reverse('eventos:oficio-step2', kwargs={'pk': oficio.pk}))}"
        ),
        'cadastrar_viajante_url': (
            f"{reverse('cadastros:viajante-cadastrar')}?next="
            f"{quote(reverse('eventos:oficio-step2', kwargs={'pk': oficio.pk}))}"
        ),
        'combustivel_opcoes': combustivel_opcoes,
        'motorista_selected_value': getattr(form, 'selected_motorista_value', ''),
        'selected_motorista_payload': getattr(form, 'selected_motorista_payload', None),
        'mostrar_motorista_manual': getattr(form, 'motorista_manual_selected', False),
        'mostrar_campos_carona': getattr(form, 'motorista_carona_selected', False),
        'motorista_oficio_ano_display': getattr(form, 'motorista_oficio_ano_display', timezone.localdate().year),
        'motorista_sem_cadastro_value': getattr(form, 'MOTORISTA_SEM_CADASTRO', '__manual__'),
        'oficio_viajantes_ids_csv': ','.join(str(pk) for pk in oficio.viajantes.values_list('pk', flat=True)),
        'step1_preview': step1_preview,
        'selected_viajantes': step1_preview['viajantes'],
        'step2_preview': step2_preview,
    }
    return render(
        request,
        'eventos/oficio/wizard_step2.html',
        _apply_oficio_wizard_context(context, oficio, 'step2', 'Transporte'),
    )


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
        'distancia_linha_reta_km': out.get('distancia_linha_reta_km'),
        'distancia_rodoviaria_km': out.get('distancia_rodoviaria_km'),
        'duracao_estimada_min': out['duracao_estimada_min'],
        'duracao_estimada_hhmm': out['duracao_estimada_hhmm'],
        'tempo_viagem_estimado_min': out.get('tempo_viagem_estimado_min'),
        'tempo_viagem_estimado_hhmm': out.get('tempo_viagem_estimado_hhmm'),
        'buffer_operacional_sugerido_min': out.get('buffer_operacional_sugerido_min'),
        'tempo_cru_estimado_min': out.get('tempo_cru_estimado_min'),
        'tempo_adicional_sugerido_min': out.get('tempo_adicional_sugerido_min'),
        'correcao_final_min': out.get('correcao_final_min'),
        'velocidade_media_kmh': out.get('velocidade_media_kmh'),
        'perfil_rota': out.get('perfil_rota'),
        'corredor': out.get('corredor'),
        'corredor_macro': out.get('corredor_macro'),
        'corredor_fino': out.get('corredor_fino'),
        'rota_fonte': out.get('rota_fonte', ROTA_FONTE_ESTIMATIVA_LOCAL),
        'fallback_usado': out.get('fallback_usado'),
        'confianca_estimativa': out.get('confianca_estimativa'),
        'refs_predominantes': out.get('refs_predominantes') or [],
        'pedagio_presente': out.get('pedagio_presente', False),
        'travessia_urbana_presente': out.get('travessia_urbana_presente', False),
        'serra_presente': out.get('serra_presente', False),
        'erro': out['erro'],
    })
