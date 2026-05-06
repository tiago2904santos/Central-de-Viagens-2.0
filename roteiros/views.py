import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import RoteiroForm
from .models import Roteiro
from . import roteiro_logic
from .presenters import (
    apresentar_contexto_formulario_roteiro_avulso,
    apresentar_pagina_detalhe_roteiro,
    apresentar_roteiro_card,
)
from .selectors import (
    get_roteiro_by_id,
    listar_cidades_para_select,
    listar_roteiros,
    listar_trechos_do_roteiro,
    obter_cidades_origem_destino_estimativa,
)
from .services import (
    atualizar_roteiro,
    carregar_opcoes_rotas_avulsas_salvas,
    criar_roteiro,
    excluir_roteiro,
    normalizar_destinos_e_trechos_apos_erro_post,
    obter_initial_roteiro,
    preparar_estado_editor_roteiro_para_get,
    preparar_querysets_formulario_roteiro,
    validar_submissao_editor_roteiro,
)
from .services.estimativa_local import ROTA_FONTE_ESTIMATIVA_LOCAL, estimar_distancia_duracao


def index(request):
    q = request.GET.get("q", "").strip()
    roteiros = listar_roteiros(q=q)
    cards = [apresentar_roteiro_card(roteiro) for roteiro in roteiros]
    return render(
        request,
        "roteiros/index.html",
        {
            "page_title": "Roteiros",
            "page_description": "Monte sede, destinos e trechos com o mesmo fluxo do sistema anterior.",
            "create_url": reverse("roteiros:novo"),
            "cards": cards,
            "q": q,
        },
    )


def novo(request):
    initial = obter_initial_roteiro()
    form = RoteiroForm(request.POST or None, initial=initial)
    form.instance.tipo = Roteiro.TIPO_AVULSO
    if request.method != "POST" and initial:
        form.instance.origem_cidade_id = initial.get("origem_cidade")
        form.instance.origem_estado_id = initial.get("origem_estado")

    preparar_querysets_formulario_roteiro(
        form, method=request.method, post=request.POST, instance=None
    )
    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas()

    if request.method == "POST":
        step3_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=None
        )
        if form.is_valid() and validated["ok"]:
            roteiro = criar_roteiro(form, step3_state, validated, diarias_resultado)
            messages.success(request, "Roteiro cadastrado com sucesso.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(step3_state)
    else:
        destinos_atuais, trechos_list, step3_state = preparar_estado_editor_roteiro_para_get(
            initial=initial
        )

    context = apresentar_contexto_formulario_roteiro_avulso(
        evento=None,
        form=form,
        obj=None,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        step3_state=step3_state,
        route_options=route_options,
    )
    return render(
        request,
        "roteiros/roteiro_form_page.html",
        {
            "page_title": "Novo roteiro",
            "page_description": "Sede, destinos, trechos, retorno e diárias no mesmo fluxo do legacy.",
            "back_url": reverse("roteiros:index"),
            **context,
        },
    )


def detalhe(request, pk):
    roteiro = get_roteiro_by_id(pk)
    trechos = listar_trechos_do_roteiro(roteiro)
    return render(
        request,
        "roteiros/detail.html",
        apresentar_pagina_detalhe_roteiro(roteiro, trechos),
    )


def editar(request, pk):
    roteiro = get_roteiro_by_id(pk)
    form = RoteiroForm(request.POST or None, instance=roteiro)

    preparar_querysets_formulario_roteiro(
        form, method=request.method, post=request.POST, instance=roteiro
    )
    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas()

    if request.method == "POST":
        step3_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=roteiro
        )
        if form.is_valid() and validated["ok"]:
            atualizar_roteiro(roteiro, form, step3_state, validated, diarias_resultado)
            messages.success(request, "Roteiro atualizado com sucesso.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(step3_state)
    else:
        destinos_atuais, trechos_list, step3_state = preparar_estado_editor_roteiro_para_get(
            roteiro=roteiro
        )

    context = apresentar_contexto_formulario_roteiro_avulso(
        evento=None,
        form=form,
        obj=roteiro,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        step3_state=step3_state,
        route_options=route_options,
    )
    return render(
        request,
        "roteiros/roteiro_form_page.html",
        {
            "page_title": "Editar roteiro",
            "page_description": "Ajuste sede, destinos, trechos e retorno.",
            "back_url": reverse("roteiros:detalhe", args=[roteiro.pk]),
            "delete_url": reverse("roteiros:excluir", args=[roteiro.pk]),
            **context,
        },
    )


def excluir(request, pk):
    roteiro = get_roteiro_by_id(pk)
    if request.method == "POST":
        if not excluir_roteiro(roteiro):
            messages.error(request, "Este roteiro possui vínculos e não pode ser excluído.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        messages.success(request, "Roteiro excluído com sucesso.")
        return redirect("roteiros:index")

    return render(
        request,
        "roteiros/confirm_delete.html",
        {
            "page_title": "Excluir roteiro",
            "page_description": "Confirme a exclusão do roteiro selecionado.",
            "object": roteiro,
            "back_url": reverse("roteiros:detalhe", args=[roteiro.pk]),
        },
    )


def api_cidades_por_estado(request, estado_id):
    q = request.GET.get("q", "").strip()
    cidades = listar_cidades_para_select(estado_id=estado_id, q=q or None)
    payload = [{"id": c.pk, "nome": str(c.nome)} for c in cidades]
    return JsonResponse(payload, safe=False)


@require_http_methods(["POST"])
def calcular_diarias(request):
    _, _, validated, resultado = roteiro_logic._build_roteiro_diarias_from_request(request)
    if not validated["ok"]:
        return JsonResponse(
            {
                "ok": False,
                "error": "Revise os dados do roteiro antes de calcular as diárias.",
                "errors": validated["errors"],
            },
            status=400,
        )
    if not resultado:
        return JsonResponse(
            {"ok": False, "error": "Revise os dados do roteiro antes de calcular as diárias."},
            status=400,
        )
    payload = {"ok": True, "quantidade_servidores_fixo": 1, "roteiros_disponiveis": 0}
    payload.update(resultado)
    return JsonResponse(payload)


@require_http_methods(["POST"])
def trechos_estimar(request):
    try:
        body = json.loads(request.body or "{}")
        origem_id = body.get("origem_cidade_id")
        destino_id = body.get("destino_cidade_id")
    except (json.JSONDecodeError, TypeError):
        origem_id = destino_id = None
    if not origem_id or not destino_id:
        return JsonResponse(
            {
                "ok": False,
                "distancia_km": None,
                "duracao_estimada_min": None,
                "duracao_estimada_hhmm": "",
                "tempo_cru_estimado_min": None,
                "tempo_adicional_sugerido_min": None,
                "rota_fonte": ROTA_FONTE_ESTIMATIVA_LOCAL,
                "erro": "Informe origem_cidade_id e destino_cidade_id.",
            }
        )
    origem, destino = obter_cidades_origem_destino_estimativa(origem_id, destino_id)
    if not origem or not destino:
        return JsonResponse(
            {
                "ok": False,
                "erro": "Cidade de origem ou destino não encontrada.",
                "rota_fonte": ROTA_FONTE_ESTIMATIVA_LOCAL,
            }
        )
    if origem.latitude is None or origem.longitude is None:
        return JsonResponse(
            {
                "ok": False,
                "erro": f"Cidade de origem sem coordenadas: {origem.nome}",
                "rota_fonte": ROTA_FONTE_ESTIMATIVA_LOCAL,
            }
        )
    if destino.latitude is None or destino.longitude is None:
        return JsonResponse(
            {
                "ok": False,
                "erro": f"Cidade de destino sem coordenadas: {destino.nome}",
                "rota_fonte": ROTA_FONTE_ESTIMATIVA_LOCAL,
            }
        )
    out = estimar_distancia_duracao(
        origem_lat=origem.latitude,
        origem_lon=origem.longitude,
        destino_lat=destino.latitude,
        destino_lon=destino.longitude,
    )
    return JsonResponse(
        {
            "ok": out["ok"],
            "distancia_km": float(out["distancia_km"]) if out["distancia_km"] is not None else None,
            "distancia_linha_reta_km": out.get("distancia_linha_reta_km"),
            "distancia_rodoviaria_km": out.get("distancia_rodoviaria_km"),
            "duracao_estimada_min": out["duracao_estimada_min"],
            "duracao_estimada_hhmm": out["duracao_estimada_hhmm"],
            "tempo_viagem_estimado_min": out.get("tempo_viagem_estimado_min"),
            "tempo_viagem_estimado_hhmm": out.get("tempo_viagem_estimado_hhmm"),
            "buffer_operacional_sugerido_min": out.get("buffer_operacional_sugerido_min"),
            "tempo_cru_estimado_min": out.get("tempo_cru_estimado_min"),
            "tempo_adicional_sugerido_min": out.get("tempo_adicional_sugerido_min"),
            "correcao_final_min": out.get("correcao_final_min"),
            "velocidade_media_kmh": out.get("velocidade_media_kmh"),
            "perfil_rota": out.get("perfil_rota"),
            "corredor": out.get("corredor"),
            "corredor_macro": out.get("corredor_macro"),
            "corredor_fino": out.get("corredor_fino"),
            "rota_fonte": out.get("rota_fonte", ROTA_FONTE_ESTIMATIVA_LOCAL),
            "fallback_usado": out.get("fallback_usado"),
            "confianca_estimativa": out.get("confianca_estimativa"),
            "refs_predominantes": out.get("refs_predominantes") or [],
            "pedagio_presente": out.get("pedagio_presente", False),
            "travessia_urbana_presente": out.get("travessia_urbana_presente", False),
            "serra_presente": out.get("serra_presente", False),
            "erro": out["erro"],
        }
    )
