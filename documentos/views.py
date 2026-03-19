from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import date

from .models import (
    Oficio, OficioViajante, OficioTrecho,
    Roteiro, RoteiroTrecho,
    TermoAutorizacao, Justificativa, PlanoTrabalho, OrdemServico,
    Evento, ModeloMotivo, ModeloJustificativa,
)
from cadastros.models import Viajante, Veiculo, Cidade


def _next_safe(request):
    nxt = (request.POST.get('return_to') or request.GET.get('return_to') or '').strip()
    if not nxt:
        return ''
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return ''


# ─── HUB ──────────────────────────────────────────────────────────────────────

@login_required
def hub(request):
    return render(request, 'documentos/hub.html', {
        'total_oficios': Oficio.objects.count(),
        'total_roteiros': Roteiro.objects.count(),
        'total_planos': PlanoTrabalho.objects.count(),
        'total_ordens': OrdemServico.objects.count(),
        'total_justificativas': Justificativa.objects.count(),
        'total_termos': TermoAutorizacao.objects.count(),
        'total_eventos': Evento.objects.count(),
    })


# ─── OFÍCIOS — WIZARD ─────────────────────────────────────────────────────────

@login_required
def oficio_lista(request):
    oficios = (
        Oficio.objects
        .prefetch_related('viajantes', 'termos')
        .select_related('motorista', 'evento')
        .order_by('-criado_em')
    )
    return render(request, 'documentos/oficios/lista.html', {'oficios': oficios})


@login_required
def oficio_step1(request, pk=None):
    """Step 1 — Dados gerais e viajantes."""
    oficio = get_object_or_404(Oficio, pk=pk) if pk else None
    viajantes_selecionados = list(oficio.viajantes.select_related('viajante').order_by('ordem')) if oficio else []
    modelos_motivo = ModeloMotivo.objects.all()
    eventos = Evento.objects.all().order_by('nome')

    if request.method == 'POST':
        if not oficio:
            oficio = Oficio()

        oficio.numero = request.POST.get('numero', '').strip()
        oficio.protocolo = request.POST.get('protocolo', '').strip()

        try:
            oficio.ano = int(request.POST.get('ano') or timezone.now().year)
        except (ValueError, TypeError):
            oficio.ano = timezone.now().year

        data_str = request.POST.get('data_criacao', '').strip()
        if data_str:
            try:
                oficio.data_criacao = date.fromisoformat(data_str)
            except ValueError:
                pass

        oficio.motivo = request.POST.get('motivo', '').strip()
        modelo_motivo_id = request.POST.get('modelo_motivo')
        oficio.modelo_motivo_id = int(modelo_motivo_id) if modelo_motivo_id else None

        oficio.custeio_tipo = request.POST.get('custeio_tipo', 'PROPRIO')
        oficio.nome_instituicao_custeio = request.POST.get('nome_instituicao_custeio', '').strip()
        oficio.tipo_destino = request.POST.get('tipo_destino', 'NACIONAL')

        evento_id = request.POST.get('evento_id')
        if evento_id == 'novo':
            nome_evento = request.POST.get('evento_nome_novo', '').strip()
            if nome_evento:
                evento = Evento.objects.create(nome=nome_evento)
                oficio.evento = evento
        elif evento_id:
            try:
                oficio.evento_id = int(evento_id)
            except (ValueError, TypeError):
                oficio.evento = None
        else:
            oficio.evento = None

        oficio.save()

        oficio.viajantes.all().delete()
        viajante_ids = request.POST.getlist('viajante_ids')
        for idx, vid in enumerate(viajante_ids, start=1):
            try:
                v = Viajante.objects.get(pk=int(vid))
                OficioViajante.objects.create(oficio=oficio, viajante=v, ordem=idx)
            except (ValueError, Viajante.DoesNotExist):
                pass

        messages.success(request, 'Dados salvos com sucesso.')
        return redirect('documentos:oficio-step2', pk=oficio.pk)

    return render(request, 'documentos/oficios/step1.html', {
        'oficio': oficio,
        'viajantes_selecionados': viajantes_selecionados,
        'todos_viajantes': Viajante.objects.filter(status='FINALIZADO').order_by('nome'),
        'modelos_motivo': modelos_motivo,
        'eventos': eventos,
        'return_to': _next_safe(request),
        'step': 1,
    })


@login_required
def oficio_step2(request, pk):
    """Step 2 — Transporte."""
    oficio = get_object_or_404(Oficio, pk=pk)
    veiculos = Veiculo.objects.filter(status='FINALIZADO').order_by('placa')
    motoristas = Viajante.objects.filter(status='FINALIZADO').order_by('nome')

    if request.method == 'POST':
        veiculo_id = request.POST.get('veiculo_id')
        if veiculo_id:
            try:
                v = Veiculo.objects.get(pk=int(veiculo_id))
                oficio.veiculo = v
                oficio.placa = v.placa
                oficio.modelo_veiculo = v.modelo
                oficio.combustivel_snapshot = str(v.combustivel) if v.combustivel else ''
                oficio.tipo_viatura = v.tipo
            except (ValueError, Veiculo.DoesNotExist):
                pass
        else:
            oficio.veiculo = None
            oficio.placa = request.POST.get('placa', '').strip()
            oficio.modelo_veiculo = request.POST.get('modelo_veiculo', '').strip()
            oficio.combustivel_snapshot = request.POST.get('combustivel_snapshot', '').strip()
            oficio.tipo_viatura = request.POST.get('tipo_viatura', '').strip()

        oficio.porte_transporte_armas = bool(request.POST.get('porte_transporte_armas'))

        motorista_id = request.POST.get('motorista_id')
        if motorista_id:
            try:
                oficio.motorista_id = int(motorista_id)
            except (ValueError, TypeError):
                oficio.motorista = None
        else:
            oficio.motorista = None

        oficio.motorista_carona = bool(request.POST.get('motorista_carona'))
        oficio.motorista_oficio_numero = request.POST.get('motorista_oficio_numero', '').strip()
        try:
            oficio.motorista_oficio_ano = int(request.POST.get('motorista_oficio_ano') or 0) or None
        except (ValueError, TypeError):
            oficio.motorista_oficio_ano = None
        oficio.motorista_protocolo = request.POST.get('motorista_protocolo', '').strip()

        oficio.save()
        messages.success(request, 'Transporte salvo com sucesso.')
        return redirect('documentos:oficio-step3', pk=oficio.pk)

    return render(request, 'documentos/oficios/step2.html', {
        'oficio': oficio,
        'veiculos': veiculos,
        'motoristas': motoristas,
        'return_to': _next_safe(request),
        'step': 2,
    })


@login_required
def oficio_step3(request, pk):
    """Step 3 — Roteiro e Diárias."""
    oficio = get_object_or_404(Oficio, pk=pk)
    roteiros = Roteiro.objects.all().order_by('-criado_em')
    trechos = list(oficio.trechos.select_related('origem', 'destino').order_by('ordem'))

    if request.method == 'POST':
        roteiro_opcao = request.POST.get('roteiro_opcao', 'nenhum')
        if roteiro_opcao == 'existente':
            rid = request.POST.get('roteiro_id')
            if rid:
                try:
                    oficio.roteiro_id = int(rid)
                except (ValueError, TypeError):
                    pass
        elif roteiro_opcao == 'novo':
            nome_roteiro = request.POST.get('roteiro_nome_novo', '').strip()
            r = Roteiro.objects.create(nome=nome_roteiro or f'Roteiro do Ofício {oficio.identificacao}')
            oficio.roteiro = r
        else:
            oficio.roteiro = None

        try:
            oficio.quantidade_diarias = float(request.POST.get('quantidade_diarias') or 0) or None
        except (ValueError, TypeError):
            oficio.quantidade_diarias = None
        try:
            oficio.valor_diarias = float(request.POST.get('valor_diarias') or 0) or None
        except (ValueError, TypeError):
            oficio.valor_diarias = None
        oficio.valor_diarias_extenso = request.POST.get('valor_diarias_extenso', '').strip()

        oficio.save()

        oficio.trechos.all().delete()
        origens = request.POST.getlist('trecho_origem')
        destinos = request.POST.getlist('trecho_destino')
        datas_saida = request.POST.getlist('trecho_data_saida')
        datas_chegada = request.POST.getlist('trecho_data_chegada')
        is_retornos = request.POST.getlist('trecho_retorno')

        for idx, (orig, dest) in enumerate(zip(origens, destinos), start=1):
            if not orig and not dest:
                continue
            ds = None
            dc = None
            try:
                ds = date.fromisoformat(datas_saida[idx - 1]) if idx <= len(datas_saida) and datas_saida[idx - 1] else None
            except (ValueError, IndexError):
                pass
            try:
                dc = date.fromisoformat(datas_chegada[idx - 1]) if idx <= len(datas_chegada) and datas_chegada[idx - 1] else None
            except (ValueError, IndexError):
                pass
            is_retorno = str(idx) in is_retornos
            OficioTrecho.objects.create(
                oficio=oficio,
                ordem=idx,
                origem_nome=orig,
                destino_nome=dest,
                data_saida=ds,
                data_chegada=dc,
                is_retorno=is_retorno,
            )

        messages.success(request, 'Roteiro e diárias salvos.')
        return redirect('documentos:oficio-step4', pk=oficio.pk)

    return render(request, 'documentos/oficios/step3.html', {
        'oficio': oficio,
        'roteiros': roteiros,
        'trechos': trechos,
        'return_to': _next_safe(request),
        'step': 3,
    })


@login_required
def oficio_step4(request, pk):
    """Step 4 — Resumo e Finalização."""
    oficio = get_object_or_404(Oficio, pk=pk)
    viajantes = oficio.viajantes.select_related('viajante').order_by('ordem')
    trechos = oficio.trechos.order_by('ordem')

    if request.method == 'POST':
        acao = request.POST.get('acao', 'salvar')
        if acao == 'finalizar':
            oficio.status = 'FINALIZADO'
            oficio.save()
            messages.success(request, 'Ofício finalizado com sucesso.')
        else:
            oficio.save()
            messages.success(request, 'Ofício salvo como rascunho.')
        return redirect('documentos:oficios')

    return render(request, 'documentos/oficios/step4.html', {
        'oficio': oficio,
        'viajantes': viajantes,
        'trechos': trechos,
        'step': 4,
    })


@login_required
def oficio_justificativa(request, pk):
    """Justificativa do ofício — gerencia o registro Justificativa vinculado ao ofício."""
    oficio = get_object_or_404(Oficio, pk=pk)
    modelos = ModeloJustificativa.objects.all()
    # Obtém ou inicializa a justificativa vinculada
    just = oficio.justificativas.order_by('criado_em').first()

    if request.method == 'POST':
        modelo_id = request.POST.get('modelo_id')
        texto = request.POST.get('justificativa_texto', '').strip()
        modelo = None
        if modelo_id:
            try:
                modelo = ModeloJustificativa.objects.get(pk=int(modelo_id))
                if not texto:
                    texto = modelo.texto
            except (ValueError, ModeloJustificativa.DoesNotExist):
                pass

        if just is None:
            just = Justificativa(oficio=oficio)
        just.texto = texto
        just.modelo = modelo
        just.save()

        # Manter compatibilidade: sincroniza snapshot em Oficio
        oficio.justificativa_texto = texto
        oficio.modelo_justificativa = modelo
        oficio.gerar_termo_preenchido = bool(request.POST.get('gerar_termo_preenchido'))
        oficio.save()

        messages.success(request, 'Justificativa salva.')
        return redirect('documentos:oficio-step4', pk=oficio.pk)

    return render(request, 'documentos/oficios/justificativa.html', {
        'oficio': oficio,
        'just': just,
        'modelos': modelos,
        'step': 'justificativa',
    })


@login_required
def oficio_excluir(request, pk):
    oficio = get_object_or_404(Oficio, pk=pk)
    if request.method == 'POST':
        oficio.delete()
        messages.success(request, 'Ofício excluído.')
        return redirect('documentos:oficios')
    return render(request, 'documentos/oficios/confirmar_exclusao.html', {'oficio': oficio})


# ─── ROTEIROS ─────────────────────────────────────────────────────────────────

@login_required
def roteiro_lista(request):
    roteiros = Roteiro.objects.all().order_by('-criado_em')
    return render(request, 'documentos/roteiros/lista.html', {'roteiros': roteiros})


@login_required
def roteiro_form(request, pk=None):
    roteiro = get_object_or_404(Roteiro, pk=pk) if pk else None
    eventos = Evento.objects.all().order_by('nome')
    return_to = _next_safe(request)

    if request.method == 'POST':
        if not roteiro:
            roteiro = Roteiro()
        roteiro.nome = request.POST.get('nome', '').strip()
        roteiro.descricao = request.POST.get('descricao', '').strip()
        evento_id = request.POST.get('evento_id')
        roteiro.evento_id = int(evento_id) if evento_id else None
        roteiro.save()
        messages.success(request, 'Roteiro salvo.')
        if return_to:
            return redirect(return_to)
        return redirect('documentos:roteiros')

    return render(request, 'documentos/roteiros/form.html', {
        'roteiro': roteiro, 'eventos': eventos, 'return_to': return_to,
    })


@login_required
def roteiro_excluir(request, pk):
    roteiro = get_object_or_404(Roteiro, pk=pk)
    if request.method == 'POST':
        roteiro.delete()
        messages.success(request, 'Roteiro excluído.')
        return redirect('documentos:roteiros')
    return render(request, 'documentos/roteiros/confirmar_exclusao.html', {'roteiro': roteiro})


# ─── TERMOS ───────────────────────────────────────────────────────────────────

@login_required
def termo_lista(request):
    termos = TermoAutorizacao.objects.all().order_by('-criado_em')
    return render(request, 'documentos/termos/lista.html', {'termos': termos})


@login_required
def termo_form(request, pk=None):
    termo = get_object_or_404(TermoAutorizacao, pk=pk) if pk else None
    return_to = _next_safe(request)

    if request.method == 'POST':
        if not termo:
            termo = TermoAutorizacao()
        termo.numero = request.POST.get('numero', '').strip()
        try:
            termo.ano = int(request.POST.get('ano') or 0) or None
        except (ValueError, TypeError):
            termo.ano = None
        data_criacao = request.POST.get('data_criacao', '').strip()
        if data_criacao:
            try:
                termo.data_criacao = date.fromisoformat(data_criacao)
            except ValueError:
                pass
        termo.titulo = request.POST.get('titulo', '').strip()
        termo.texto = request.POST.get('texto', '').strip()
        termo.observacoes = request.POST.get('observacoes', '').strip()
        oficio_id = request.POST.get('oficio_id')
        termo.oficio_id = int(oficio_id) if oficio_id else None
        evento_id = request.POST.get('evento_id')
        termo.evento_id = int(evento_id) if evento_id else None
        roteiro_id = request.POST.get('roteiro_id')
        termo.roteiro_id = int(roteiro_id) if roteiro_id else None
        viajante_id = request.POST.get('viajante_id')
        termo.viajante_id = int(viajante_id) if viajante_id else None
        acao = request.POST.get('acao', 'rascunho')
        termo.status = 'FINALIZADO' if acao == 'finalizar' else 'RASCUNHO'
        termo.save()
        messages.success(request, 'Termo salvo.')
        if return_to:
            return redirect(return_to)
        return redirect('documentos:termos')

    oficios = Oficio.objects.all().order_by('-criado_em')
    eventos = Evento.objects.all().order_by('nome')
    roteiros = Roteiro.objects.all().order_by('-criado_em')
    viajantes = Viajante.objects.filter(status='FINALIZADO').order_by('nome')
    return render(request, 'documentos/termos/form.html', {
        'termo': termo,
        'oficios': oficios,
        'eventos': eventos,
        'roteiros': roteiros,
        'viajantes': viajantes,
        'return_to': return_to,
    })


@login_required
def termo_excluir(request, pk):
    termo = get_object_or_404(TermoAutorizacao, pk=pk)
    if request.method == 'POST':
        termo.delete()
        messages.success(request, 'Termo excluído.')
        return redirect('documentos:termos')
    return render(request, 'documentos/termos/confirmar_exclusao.html', {'termo': termo})


# ─── JUSTIFICATIVAS ───────────────────────────────────────────────────────────

@login_required
def justificativa_lista(request):
    justificativas = Justificativa.objects.select_related('oficio', 'modelo').order_by('-criado_em')
    return render(request, 'documentos/justificativas/lista.html', {'justificativas': justificativas})


@login_required
def justificativa_form(request, pk=None):
    just = get_object_or_404(Justificativa, pk=pk) if pk else None
    modelos = ModeloJustificativa.objects.all()
    oficios = Oficio.objects.all().order_by('-criado_em')
    return_to = _next_safe(request)

    if request.method == 'POST':
        oficio_id = request.POST.get('oficio_id')
        if not oficio_id:
            messages.error(request, 'O Ofício é obrigatório para uma justificativa.')
            return render(request, 'documentos/justificativas/form.html', {
                'just': just, 'modelos': modelos, 'oficios': oficios, 'return_to': return_to,
            })
        try:
            oficio = Oficio.objects.get(pk=int(oficio_id))
        except (ValueError, Oficio.DoesNotExist):
            messages.error(request, 'Ofício inválido.')
            return render(request, 'documentos/justificativas/form.html', {
                'just': just, 'modelos': modelos, 'oficios': oficios, 'return_to': return_to,
            })
        if not just:
            just = Justificativa(oficio=oficio)
        else:
            just.oficio = oficio
        just.titulo = request.POST.get('titulo', '').strip()
        just.texto = request.POST.get('texto', '').strip()
        just.observacoes = request.POST.get('observacoes', '').strip()
        modelo_id = request.POST.get('modelo_id')
        just.modelo_id = int(modelo_id) if modelo_id else None
        acao = request.POST.get('acao', 'rascunho')
        just.status = 'FINALIZADO' if acao == 'finalizar' else 'RASCUNHO'
        just.save()
        messages.success(request, 'Justificativa salva.')
        if return_to:
            return redirect(return_to)
        return redirect('documentos:justificativas')

    return render(request, 'documentos/justificativas/form.html', {
        'just': just, 'modelos': modelos, 'oficios': oficios, 'return_to': return_to,
    })


@login_required
def justificativa_excluir(request, pk):
    just = get_object_or_404(Justificativa, pk=pk)
    if request.method == 'POST':
        just.delete()
        messages.success(request, 'Justificativa excluída.')
        return redirect('documentos:justificativas')
    return render(request, 'documentos/justificativas/confirmar_exclusao.html', {'just': just})


# ─── PLANOS DE TRABALHO ───────────────────────────────────────────────────────

@login_required
def plano_lista(request):
    planos = PlanoTrabalho.objects.all().order_by('-criado_em')
    return render(request, 'documentos/planos/lista.html', {'planos': planos})


@login_required
def plano_form(request, pk=None):
    plano = get_object_or_404(PlanoTrabalho, pk=pk) if pk else None
    return_to = _next_safe(request)

    if request.method == 'POST':
        if not plano:
            plano = PlanoTrabalho()
        plano.titulo = request.POST.get('titulo', '').strip()
        plano.conteudo = request.POST.get('conteudo', '').strip()
        plano.save()
        messages.success(request, 'Plano de trabalho salvo.')
        if return_to:
            return redirect(return_to)
        return redirect('documentos:planos-trabalho')

    return render(request, 'documentos/planos/form.html', {
        'plano': plano, 'return_to': return_to,
    })


@login_required
def plano_excluir(request, pk):
    plano = get_object_or_404(PlanoTrabalho, pk=pk)
    if request.method == 'POST':
        plano.delete()
        messages.success(request, 'Plano excluído.')
        return redirect('documentos:planos-trabalho')
    return render(request, 'documentos/planos/confirmar_exclusao.html', {'plano': plano})


# ─── ORDENS DE SERVIÇO ────────────────────────────────────────────────────────

@login_required
def ordem_lista(request):
    ordens = OrdemServico.objects.all().order_by('-criado_em')
    return render(request, 'documentos/ordens/lista.html', {'ordens': ordens})


@login_required
def ordem_form(request, pk=None):
    ordem = get_object_or_404(OrdemServico, pk=pk) if pk else None
    return_to = _next_safe(request)

    if request.method == 'POST':
        if not ordem:
            ordem = OrdemServico()
        ordem.titulo = request.POST.get('titulo', '').strip()
        ordem.conteudo = request.POST.get('conteudo', '').strip()
        ordem.save()
        messages.success(request, 'Ordem de serviço salva.')
        if return_to:
            return redirect(return_to)
        return redirect('documentos:ordens-servico')

    return render(request, 'documentos/ordens/form.html', {
        'ordem': ordem, 'return_to': return_to,
    })


@login_required
def ordem_excluir(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    if request.method == 'POST':
        ordem.delete()
        messages.success(request, 'Ordem de serviço excluída.')
        return redirect('documentos:ordens-servico')
    return render(request, 'documentos/ordens/confirmar_exclusao.html', {'ordem': ordem})


# ─── EVENTOS ──────────────────────────────────────────────────────────────────

@login_required
def evento_lista(request):
    eventos = Evento.objects.all().order_by('-criado_em')
    return render(request, 'documentos/eventos/lista.html', {'eventos': eventos})


@login_required
def evento_detalhe(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    oficios = evento.oficios.all()
    roteiros = evento.roteiros.all()
    termos = evento.termos.all()
    return render(request, 'documentos/eventos/detalhe.html', {
        'evento': evento, 'oficios': oficios, 'roteiros': roteiros, 'termos': termos,
    })


@login_required
def evento_form(request, pk=None):
    evento = get_object_or_404(Evento, pk=pk) if pk else None
    return_to = _next_safe(request)

    if request.method == 'POST':
        if not evento:
            evento = Evento()
        evento.nome = request.POST.get('nome', '').strip()
        evento.descricao = request.POST.get('descricao', '').strip()
        data_inicio = request.POST.get('data_inicio', '').strip()
        data_fim = request.POST.get('data_fim', '').strip()
        if data_inicio:
            try:
                evento.data_inicio = date.fromisoformat(data_inicio)
            except ValueError:
                pass
        if data_fim:
            try:
                evento.data_fim = date.fromisoformat(data_fim)
            except ValueError:
                pass
        evento.save()
        messages.success(request, 'Evento salvo.')
        if return_to:
            return redirect(return_to)
        return redirect('documentos:evento-detalhe', pk=evento.pk)

    return render(request, 'documentos/eventos/form.html', {
        'evento': evento, 'return_to': return_to,
    })


@login_required
def evento_excluir(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        evento.delete()
        messages.success(request, 'Evento excluído.')
        return redirect('documentos:eventos')
    return render(request, 'documentos/eventos/confirmar_exclusao.html', {'evento': evento})


# ─── MODELOS DE MOTIVO ────────────────────────────────────────────────────────

@login_required
def modelo_motivo_lista(request):
    modelos = ModeloMotivo.objects.all()
    return render(request, 'documentos/modelos_motivo/lista.html', {'modelos': modelos})


@login_required
def modelo_motivo_form(request, pk=None):
    modelo = get_object_or_404(ModeloMotivo, pk=pk) if pk else None
    if request.method == 'POST':
        if not modelo:
            modelo = ModeloMotivo()
        modelo.nome = request.POST.get('nome', '').strip()
        modelo.texto = request.POST.get('texto', '').strip()
        modelo.is_padrao = bool(request.POST.get('is_padrao'))
        modelo.save()
        messages.success(request, 'Modelo de motivo salvo.')
        return redirect('documentos:modelos-motivo')
    return render(request, 'documentos/modelos_motivo/form.html', {'modelo': modelo})


@login_required
def modelo_motivo_excluir(request, pk):
    modelo = get_object_or_404(ModeloMotivo, pk=pk)
    if request.method == 'POST':
        modelo.delete()
        messages.success(request, 'Modelo excluído.')
        return redirect('documentos:modelos-motivo')
    return render(request, 'documentos/modelos_motivo/confirmar_exclusao.html', {'modelo': modelo})


# ─── MODELOS DE JUSTIFICATIVA ─────────────────────────────────────────────────

@login_required
def modelo_justificativa_lista(request):
    modelos = ModeloJustificativa.objects.all()
    return render(request, 'documentos/modelos_justificativa/lista.html', {'modelos': modelos})


@login_required
def modelo_justificativa_form(request, pk=None):
    modelo = get_object_or_404(ModeloJustificativa, pk=pk) if pk else None
    if request.method == 'POST':
        if not modelo:
            modelo = ModeloJustificativa()
        modelo.nome = request.POST.get('nome', '').strip()
        modelo.texto = request.POST.get('texto', '').strip()
        modelo.is_padrao = bool(request.POST.get('is_padrao'))
        modelo.save()
        messages.success(request, 'Modelo de justificativa salvo.')
        return redirect('documentos:modelos-justificativa')
    return render(request, 'documentos/modelos_justificativa/form.html', {'modelo': modelo})


@login_required
def modelo_justificativa_excluir(request, pk):
    modelo = get_object_or_404(ModeloJustificativa, pk=pk)
    if request.method == 'POST':
        modelo.delete()
        messages.success(request, 'Modelo excluído.')
        return redirect('documentos:modelos-justificativa')
    return render(request, 'documentos/modelos_justificativa/confirmar_exclusao.html', {'modelo': modelo})
