import json
from types import SimpleNamespace

from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cadastros.models import Cidade, ConfiguracaoSistema, Estado

from .forms import RoteiroForm
from .models import Roteiro
from . import step3_logic
from .presenters import apresentar_roteiro_card
from .selectors import get_roteiro_by_id, listar_roteiros, listar_trechos_do_roteiro
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
    initial = {}
    config = ConfiguracaoSistema.get_singleton()
    if getattr(config, "cidade_sede_padrao", None):
        initial["origem_cidade"] = config.cidade_sede_padrao_id
        if config.cidade_sede_padrao.estado_id:
            initial["origem_estado"] = config.cidade_sede_padrao.estado_id
    form = RoteiroForm(request.POST or None, initial=initial)
    form.instance.tipo = Roteiro.TIPO_AVULSO
    if request.method != "POST" and initial:
        form.instance.origem_cidade_id = initial.get("origem_cidade")
        form.instance.origem_estado_id = initial.get("origem_estado")
    step3_logic._setup_roteiro_querysets(form, request, None)
    route_options, route_state_map = step3_logic._build_roteiro_avulso_route_options()
    destinos_atuais = [
        {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
    ]
    trechos_list = []
    if request.method == "POST":
        step3_state = step3_logic._build_avulso_step3_state_from_post(
            request, route_state_map=route_state_map
        )
        fake = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
        validated = step3_logic._validate_step3_state(step3_state, oficio=fake)
        _, _, _, diarias_resultado = step3_logic._build_roteiro_diarias_from_request(request)
        if form.is_valid() and validated["ok"]:
            roteiro = form.save(commit=False)
            roteiro.tipo = Roteiro.TIPO_AVULSO
            roteiro.origem_estado = validated.get("sede_estado")
            roteiro.origem_cidade = validated.get("sede_cidade")
            roteiro.save()
            step3_logic._salvar_roteiro_avulso_from_step3_state(
                roteiro, step3_state, validated, diarias_resultado=diarias_resultado
            )
            messages.success(request, "Roteiro cadastrado com sucesso.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais = [
            {
                "estado_id": item.get("estado_id"),
                "cidade_id": item.get("cidade_id"),
                "cidade": None,
                "estado": None,
            }
            for item in (step3_state.get("destinos_atuais") or [])
        ]
        if not destinos_atuais:
            destinos_atuais = [
                {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
            ]
        trechos_list = step3_state.get("trechos", [])
    else:
        step3_state = step3_logic._build_step3_state_from_estrutura(
            trechos_list,
            [{"estado_id": None, "cidade_id": None}],
            initial.get("origem_estado"),
            initial.get("origem_cidade"),
            "",
        )
        step3_state["roteiro_modo"] = "ROTEIRO_PROPRIO"
    context = step3_logic._build_roteiro_form_context(
        evento=None,
        form=form,
        obj=None,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        step3_state=step3_state,
        route_options=route_options,
    )
    return render(
        request,
        "roteiros/form_step3.html",
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
        {
            "page_title": f"Roteiro #{roteiro.pk}",
            "page_description": "Resumo do roteiro, trechos e diárias calculadas.",
            "roteiro": roteiro,
            "trechos": trechos,
            "edit_url": reverse("roteiros:editar", args=[roteiro.pk]),
            "delete_url": reverse("roteiros:excluir", args=[roteiro.pk]),
            "back_url": reverse("roteiros:index"),
        },
    )


def editar(request, pk):
    roteiro = get_object_or_404(
        Roteiro.objects.prefetch_related(
            "destinos",
            "destinos__estado",
            "destinos__cidade",
            "trechos",
            "trechos__origem_estado",
            "trechos__origem_cidade",
            "trechos__destino_estado",
            "trechos__destino_cidade",
        ).select_related("origem_estado", "origem_cidade"),
        pk=pk,
    )
    form = RoteiroForm(request.POST or None, instance=roteiro)
    step3_logic._setup_roteiro_querysets(form, request, roteiro)
    route_options, route_state_map = step3_logic._build_roteiro_avulso_route_options()
    if request.method == "POST":
        step3_state = step3_logic._build_avulso_step3_state_from_post(
            request, route_state_map=route_state_map
        )
        fake = SimpleNamespace(evento_id=None, roteiro_evento_id=None, evento=None)
        validated = step3_logic._validate_step3_state(step3_state, oficio=fake)
        _, _, _, diarias_resultado = step3_logic._build_roteiro_diarias_from_request(
            request, roteiro=roteiro
        )
        if form.is_valid() and validated["ok"]:
            roteiro_salvo = form.save(commit=False)
            roteiro_salvo.tipo = roteiro.tipo or Roteiro.TIPO_AVULSO
            roteiro_salvo.origem_estado = validated.get("sede_estado")
            roteiro_salvo.origem_cidade = validated.get("sede_cidade")
            roteiro_salvo.save()
            step3_logic._salvar_roteiro_avulso_from_step3_state(
                roteiro_salvo, step3_state, validated, diarias_resultado=diarias_resultado
            )
            messages.success(request, "Roteiro atualizado com sucesso.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais = [
            {
                "estado_id": item.get("estado_id"),
                "cidade_id": item.get("cidade_id"),
                "cidade": None,
                "estado": None,
            }
            for item in (step3_state.get("destinos_atuais") or [])
        ]
        if not destinos_atuais:
            destinos_atuais = [
                {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
            ]
        trechos_list = step3_state.get("trechos", [])
    else:
        destinos_atuais = step3_logic._destinos_roteiro_para_template(roteiro)
        if not destinos_atuais:
            destinos_atuais = [
                {"estado_id": None, "cidade_id": None, "cidade": None, "estado": None}
            ]
        destinos_list = [
            (d.get("estado_id"), d.get("cidade_id"))
            for d in destinos_atuais
            if d.get("estado_id") and d.get("cidade_id")
        ]
        trechos_list = (
            step3_logic._estrutura_trechos(roteiro, destinos_list) if destinos_list else []
        )
        step3_state = step3_logic._build_step3_state_from_roteiro_evento(roteiro)
        step3_state["roteiro_modo"] = "ROTEIRO_PROPRIO"
    context = step3_logic._build_roteiro_form_context(
        evento=None,
        form=form,
        obj=roteiro,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        step3_state=step3_state,
        route_options=route_options,
    )
    return render(
        request,
        "roteiros/form_step3.html",
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
        try:
            roteiro.delete()
        except ProtectedError:
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
    cidades = Cidade.objects.filter(estado_id=estado_id).order_by("nome")
    payload = [{"id": c.pk, "nome": str(c.nome)} for c in cidades]
    return JsonResponse(payload, safe=False)


@require_http_methods(["POST"])
def calcular_diarias(request):
    _, _, validated, resultado = step3_logic._build_roteiro_diarias_from_request(request)
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
    origem = Cidade.objects.filter(pk=origem_id).select_related("estado").first()
    destino = Cidade.objects.filter(pk=destino_id).select_related("estado").first()
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
