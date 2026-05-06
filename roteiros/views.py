import json
import logging

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import RoteiroForm
from core.autosave import (
    AutosavePayloadError,
    autosave_json_response,
    filter_allowed_fields,
    parse_autosave_payload,
)
from .services.routing.route_exceptions import (
    RouteAuthenticationError,
    RouteConfigurationError,
    RouteCoordinateError,
    RouteDailyRoundTripBlockedError,
    RouteNotFoundError,
    RouteProviderUnavailable,
    RouteRateLimitError,
    RouteServiceError,
    RouteTimeoutError,
    RouteValidationError,
)
from .services.routing.route_service import calcular_rota_para_roteiro
from .services.routing.route_preview_service import calculate_route_preview

logger = logging.getLogger(__name__)
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
from .services.autosave import (
    ROTEIRO_AUTOSAVE_FIELDS,
    apply_roteiro_autosave,
    build_roteiro_draft,
    has_minimum_roteiro_content,
)
from .services.estimativa_local import ROTA_FONTE_ESTIMATIVA_LOCAL
from .services.routing.trecho_route_service import calcular_rota_trecho


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
    try:
        _, _, validated, resultado = roteiro_logic._build_roteiro_diarias_from_request(request)
    except ValueError as exc:
        return JsonResponse(
            {
                "ok": False,
                "error": str(exc) or "Revise os dados do roteiro antes de calcular as diárias.",
                "errors": [str(exc)] if str(exc) else [],
            },
            status=400,
        )
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
def calcular_rota(request):
    """Calcula rota consolidada via backend (OpenRouteService); nunca expõe chave de API."""
    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        body = {}
    if "openrouteservice_api_key" in body or "api_key" in body:
        logger.warning("calcular_rota: tentativa de enviar chave de API no payload.")
        return JsonResponse(
            {
                "ok": False,
                "message": "Requisição inválida.",
            },
            status=400,
        )
    roteiro_id = body.get("roteiro_id")
    force = bool(body.get("force_recalculate"))
    try:
        rid = int(roteiro_id)
    except (TypeError, ValueError):
        rid = None
    if not rid:
        return JsonResponse(
            {
                "ok": False,
                "message": "Salve o roteiro antes de calcular a rota no mapa.",
            },
            status=400,
        )
    try:
        roteiro = get_roteiro_by_id(rid)
    except Http404:
        return JsonResponse(
            {"ok": False, "message": "Roteiro não encontrado."},
            status=404,
        )
    try:
        payload = calcular_rota_para_roteiro(roteiro, force_recalculate=force)
        return JsonResponse(payload)
    except RouteAuthenticationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=401)
    except RouteConfigurationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=503)
    except RouteCoordinateError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteDailyRoundTripBlockedError as exc:
        return JsonResponse(
            {
                "ok": False,
                "blocked": True,
                "reason": exc.reason,
                "message": exc.user_message,
            },
            status=400,
        )
    except RouteValidationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteTimeoutError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=504)
    except RouteRateLimitError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=429)
    except RouteNotFoundError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=404)
    except RouteProviderUnavailable as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=502)
    except RouteServiceError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except Exception as exc:
        logger.exception("calcular_rota falhou: %s", exc)
        return JsonResponse(
            {
                "ok": False,
                "message": "Não foi possível calcular a rota automaticamente. Você pode preencher a distância e o tempo manualmente.",
            },
            status=500,
        )


@require_http_methods(["POST"])
def trechos_estimar(request):
    """Estima um trecho operacional (origem → destino). Usa OpenRouteService se configurado; senão estimativa local."""
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
                "ors_fallback": False,
                "erro": "Informe origem_cidade_id e destino_cidade_id.",
            }
        )
    raw = calcular_rota_trecho(origem_id, destino_id)
    if not raw.get("ok"):
        return JsonResponse(
            {
                "ok": False,
                "distancia_km": None,
                "duracao_estimada_min": None,
                "duracao_estimada_hhmm": "",
                "tempo_cru_estimado_min": None,
                "tempo_adicional_sugerido_min": None,
                "rota_fonte": raw.get("rota_fonte") or ROTA_FONTE_ESTIMATIVA_LOCAL,
                "ors_fallback": raw.get("ors_fallback", False),
                "erro": raw.get("erro") or "Não foi possível estimar o trecho.",
            }
        )

    dist_km = raw.get("distancia_km")
    return JsonResponse(
        {
            "ok": True,
            "origem": raw.get("origem"),
            "destino": raw.get("destino"),
            "distancia_km": float(dist_km) if dist_km is not None else None,
            "distancia_linha_reta_km": raw.get("distancia_linha_reta_km"),
            "distancia_rodoviaria_km": raw.get("distancia_rodoviaria_km"),
            "duracao_estimada_min": raw.get("duracao_estimada_min"),
            "duracao_estimada_hhmm": raw.get("duracao_estimada_hhmm"),
            "tempo_viagem_estimado_min": raw.get("tempo_viagem_estimado_min"),
            "tempo_viagem_estimado_hhmm": raw.get("tempo_viagem_estimado_hhmm"),
            "buffer_operacional_sugerido_min": raw.get("buffer_operacional_sugerido_min"),
            "tempo_cru_estimado_min": raw.get("tempo_cru_estimado_min"),
            "tempo_adicional_sugerido_min": raw.get("tempo_adicional_sugerido_min"),
            "correcao_final_min": raw.get("correcao_final_min"),
            "velocidade_media_kmh": raw.get("velocidade_media_kmh"),
            "perfil_rota": raw.get("perfil_rota"),
            "corredor": raw.get("corredor"),
            "corredor_macro": raw.get("corredor_macro"),
            "corredor_fino": raw.get("corredor_fino"),
            "rota_fonte": raw.get("rota_fonte"),
            "fallback_usado": raw.get("fallback_usado"),
            "ors_fallback": raw.get("ors_fallback"),
            "confianca_estimativa": raw.get("confianca_estimativa"),
            "refs_predominantes": raw.get("refs_predominantes") or [],
            "pedagio_presente": raw.get("pedagio_presente", False),
            "travessia_urbana_presente": raw.get("travessia_urbana_presente", False),
            "serra_presente": raw.get("serra_presente", False),
            "erro": raw.get("erro") or "",
            "duration_human": raw.get("duration_human"),
        }
    )


@require_http_methods(["POST"])
def calcular_rota_preview(request):
    """
    Preview de rota sem persistência para rascunho de tela (novo roteiro sem salvar).
    """
    try:
        body = json.loads(request.body or "{}")
    except (json.JSONDecodeError, TypeError):
        body = {}
    if "openrouteservice_api_key" in body or "api_key" in body:
        logger.warning("calcular_rota_preview: tentativa de enviar chave de API no payload.")
        return JsonResponse({"ok": False, "message": "Requisição inválida."}, status=400)
    try:
        return JsonResponse(calculate_route_preview(body))
    except RouteAuthenticationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=401)
    except RouteConfigurationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=503)
    except RouteCoordinateError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteDailyRoundTripBlockedError as exc:
        return JsonResponse(
            {
                "ok": False,
                "blocked": True,
                "reason": exc.reason,
                "message": exc.user_message,
            },
            status=400,
        )
    except RouteValidationError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except RouteTimeoutError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=504)
    except RouteRateLimitError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=429)
    except RouteNotFoundError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=404)
    except RouteProviderUnavailable as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=502)
    except RouteServiceError as exc:
        return JsonResponse({"ok": False, "message": exc.user_message}, status=400)
    except Exception as exc:
        logger.exception("calcular_rota_preview falhou: %s", exc)
        return JsonResponse(
            {
                "ok": False,
                "message": "Não foi possível calcular a rota automaticamente. Você pode preencher a distância e o tempo manualmente.",
            },
            status=500,
        )


@require_http_methods(["POST"])
def roteiro_autosave_create(request):
    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    if not has_minimum_roteiro_content(clean_fields, payload.snapshots):
        return autosave_json_response(ok=False, message="Conteúdo insuficiente para criar rascunho.")

    roteiro = build_roteiro_draft()
    version = apply_roteiro_autosave(roteiro, clean_fields, payload.snapshots)
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=True, version=version)


@require_http_methods(["POST"])
def roteiro_autosave(request, pk):
    roteiro = get_roteiro_by_id(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    version = apply_roteiro_autosave(roteiro, clean_fields, payload.snapshots)
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=False, version=version)
