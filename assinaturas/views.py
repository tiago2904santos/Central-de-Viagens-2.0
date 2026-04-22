import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST

from assinaturas.models import AssinaturaDocumento, AssinaturaEtapa
from assinaturas.services.assinatura_estado import EstadoLinkAssinatura, estado_etapa_assinatura, estado_pedido_assinatura
from assinaturas.services.assinatura_flow import criar_pedido_assinatura, processar_assinatura_etapa


def _titulo_documento_para_pedido(assin: AssinaturaDocumento) -> str:
    key = (assin.documento_tipo or "").strip().lower()
    rotulos = {
        "eventos.oficio": "Ofício",
        "eventos.justificativa": "Justificativa",
        "eventos.planotrabalho": "Plano de trabalho",
        "eventos.ordemservico": "Ordem de serviço",
        "eventos.termoautorizacao": "Termo de autorização",
    }
    return rotulos.get(key, assin.documento_tipo or "Documento")


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _resolver_token(token_str: str) -> tuple[str, AssinaturaEtapa | None, AssinaturaDocumento | None]:
    """
    Devolve (estado, etapa ou None, pedido_legado ou None).
    Prioridade: token de AssinaturaEtapa; fallback token em AssinaturaDocumento (legado).
    """
    try:
        u = uuid.UUID(str(token_str).strip())
    except (ValueError, TypeError, AttributeError):
        return EstadoLinkAssinatura.INVALIDO, None, None

    etapa = AssinaturaEtapa.objects.select_related("assinatura").filter(token=u).first()
    if etapa:
        return estado_etapa_assinatura(etapa), etapa, None

    assin = AssinaturaDocumento.objects.filter(token=u).first()
    if assin:
        return estado_pedido_assinatura(assin), None, assin
    return EstadoLinkAssinatura.INVALIDO, None, None


def _render_estado(request, estado: str, assin: AssinaturaDocumento | None, status_code: int = 200):
    return render(
        request,
        "assinaturas/link_estado.html",
        {"estado": estado, "assin": assin},
        status=status_code,
    )


@require_GET
@xframe_options_sameorigin
def assinar_preview_pdf(request, token):
    estado, etapa, assin_legado = _resolver_token(token)
    if estado != EstadoLinkAssinatura.VALIDO:
        raise Http404()
    if etapa:
        assin = etapa.assinatura
        if etapa.ordem == 1:
            fh = assin.arquivo_original.open("rb")
        else:
            anterior = assin.etapas.filter(ordem=etapa.ordem - 1).first()
            if not anterior or not anterior.resultado_pdf.name:
                raise Http404()
            fh = anterior.resultado_pdf.open("rb")
        resp = FileResponse(fh, content_type="application/pdf")
        resp["Content-Disposition"] = 'inline; filename="documento.pdf"'
        return resp
    if assin_legado and assin_legado.arquivo_original.name:
        resp = FileResponse(assin_legado.arquivo_original.open("rb"), content_type="application/pdf")
        resp["Content-Disposition"] = 'inline; filename="documento.pdf"'
        return resp
    raise Http404()


@require_GET
def assinar_documento(request, token):
    estado, etapa, assin_legado = _resolver_token(token)
    if estado == EstadoLinkAssinatura.INVALIDO and not etapa and not assin_legado:
        return _render_estado(request, estado, None, 404)
    if etapa:
        if estado != EstadoLinkAssinatura.VALIDO:
            return _render_estado(request, estado, etapa.assinatura, 200)
        preview_url = reverse("assinaturas:preview_pdf", kwargs={"token": str(etapa.token)})
        return render(
            request,
            "assinaturas/assinar_documento.html",
            {
                "assin": etapa.assinatura,
                "etapa": etapa,
                "preview_url": preview_url,
                "link_token": str(etapa.token),
                "titulo_documento": _titulo_documento_para_pedido(etapa.assinatura),
            },
        )
    if assin_legado:
        if estado == EstadoLinkAssinatura.INVALIDO:
            return _render_estado(request, estado, None, 404)
        if estado != EstadoLinkAssinatura.VALIDO:
            return _render_estado(request, estado, assin_legado, 200)
        preview_url = reverse("assinaturas:preview_pdf", kwargs={"token": str(assin_legado.token)})
        return render(
            request,
            "assinaturas/assinar_documento.html",
            {
                "assin": assin_legado,
                "etapa": None,
                "preview_url": preview_url,
                "link_token": str(assin_legado.token) if assin_legado.token else str(token),
                "titulo_documento": _titulo_documento_para_pedido(assin_legado),
            },
        )
    return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)


@require_GET
def assinar_resultado(request, token):
    estado, etapa, assin_legado = _resolver_token(token)
    if etapa:
        assin = etapa.assinatura
        if estado == EstadoLinkAssinatura.INVALIDO:
            return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)
        if etapa.status != AssinaturaEtapa.Status.ASSINADO:
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(etapa.token)}))
        return render(
            request,
            "assinaturas/assinar_resultado.html",
            {"assin": assin, "etapa": etapa},
        )
    if assin_legado:
        if estado == EstadoLinkAssinatura.INVALIDO:
            return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)
        if estado != EstadoLinkAssinatura.JA_ASSINADO:
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(assin_legado.token)}))
        return render(
            request,
            "assinaturas/assinar_resultado.html",
            {"assin": assin_legado, "etapa": None},
        )
    return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)


@require_POST
def assinar_documento_submit(request, token):
    estado, etapa, assin_legado = _resolver_token(token)
    if etapa:
        if estado == EstadoLinkAssinatura.INVALIDO:
            return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)
        if estado != EstadoLinkAssinatura.VALIDO:
            if estado == EstadoLinkAssinatura.EXPIRADO:
                messages.error(request, "Este link de assinatura expirou.")
            elif estado == EstadoLinkAssinatura.JA_ASSINADO:
                messages.warning(request, "Esta etapa ja foi assinada.")
            else:
                messages.error(request, "Assinatura indisponivel ou fora de ordem.")
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(etapa.token)}))

        nome = (request.POST.get("nome_assinante") or "").strip()
        cpf = (request.POST.get("cpf_assinante") or "").strip()
        sig = (request.POST.get("signature") or "").strip()
        try:
            processar_assinatura_etapa(
                etapa=etapa,
                nome_assinante=nome,
                cpf_digitado=cpf,
                signature_data_url=sig,
                ip=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:2000],
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(etapa.token)}))
        except Exception:
            messages.error(request, "Nao foi possivel concluir a assinatura. Tente novamente.")
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(etapa.token)}))

        messages.success(request, "Assinatura registada com sucesso.")
        return HttpResponseRedirect(
            reverse("assinaturas:resultado", kwargs={"token": str(etapa.token)}),
        )

    if assin_legado:
        from assinaturas.services.assinatura_flow import processar_assinatura

        if assin_legado is None or estado == EstadoLinkAssinatura.INVALIDO:
            return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)
        if estado != EstadoLinkAssinatura.VALIDO:
            if estado == EstadoLinkAssinatura.EXPIRADO:
                messages.error(request, "Este link de assinatura expirou.")
            elif estado == EstadoLinkAssinatura.JA_ASSINADO:
                messages.warning(request, "Este documento ja foi assinado.")
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(token)}))

        nome = (request.POST.get("nome_assinante") or "").strip()
        cpf = (request.POST.get("cpf_assinante") or "").strip()
        sig = (request.POST.get("signature") or "").strip()
        try:
            processar_assinatura(
                assin=assin_legado,
                nome_assinante=nome,
                signature_data_url=sig,
                ip=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:2000],
                cpf_digitado=cpf,
                usuario=request.user if request.user.is_authenticated else None,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(token)}))
        except Exception:
            messages.error(request, "Nao foi possivel concluir a assinatura. Tente novamente.")
            return HttpResponseRedirect(reverse("assinaturas:assinar", kwargs={"token": str(token)}))

        messages.success(request, "Documento assinado com sucesso.")
        return HttpResponseRedirect(
            reverse("assinaturas:resultado", kwargs={"token": str(assin_legado.token)}),
        )

    return _render_estado(request, EstadoLinkAssinatura.INVALIDO, None, 404)


def _safe_internal_redirect(request, candidato: str, fallback: str) -> str:
    path = (candidato or "").strip()
    if path.startswith("/") and not path.startswith("//"):
        return path
    return fallback


@login_required
@require_POST
def pedido_assinatura_criar(request):
    tipo = (request.POST.get("documento_tipo") or "").strip()
    raw_id = request.POST.get("documento_id")
    next_url = _safe_internal_redirect(
        request,
        request.POST.get("next") or "",
        reverse("eventos:oficios-global"),
    )
    try:
        doc_id = int(raw_id)
    except (TypeError, ValueError):
        messages.error(request, "Identificador do documento inválido.")
        return redirect(next_url)
    cpf_chef = (request.POST.get("cpf_esperado_chefia") or "").strip() or None
    try:
        _, primeira, rel = criar_pedido_assinatura(
            documento_tipo=tipo,
            documento_id=doc_id,
            cpf_esperado_chefia=cpf_chef,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(next_url)
    link = request.build_absolute_uri(rel)
    messages.success(request, "Pedido de assinatura criado.")
    if primeira:
        messages.info(request, f"Link do primeiro assinante: {link}")
    return redirect(next_url)


def _estado_pedido_publico(assin: AssinaturaDocumento) -> str:
    st = (assin.status or "").strip().lower()
    if st == AssinaturaDocumento.Status.CONCLUIDO or st == "assinado":
        return "concluido"
    if st == AssinaturaDocumento.Status.PARCIAL:
        return "parcial"
    if st == AssinaturaDocumento.Status.PENDENTE:
        return "pendente"
    if st == AssinaturaDocumento.Status.INVALIDADO_ALTERACAO:
        return "invalidado_alteracao"
    return "invalido"


@require_GET
def verificar_documento_assinado(request, token):
    try:
        u = uuid.UUID(str(token).strip())
    except (ValueError, TypeError, AttributeError):
        raise Http404()
    pedido = (
        AssinaturaDocumento.objects.filter(verificacao_token=u)
        .prefetch_related("etapas")
        .first()
    )
    if not pedido:
        raise Http404()
    etapas = list(pedido.etapas.order_by("ordem"))
    exp = pedido.expires_at
    expirado = bool(exp and exp < timezone.now())
    return render(
        request,
        "assinaturas/verificar.html",
        {
            "pedido": pedido,
            "etapas": etapas,
            "estado_publico": _estado_pedido_publico(pedido),
            "expirado": expirado,
            "titulo_documento": _titulo_documento_para_pedido(pedido),
            "url_pdf_assinado": reverse("assinaturas:verificar_pdf", kwargs={"token": str(pedido.verificacao_token)}),
        },
    )


@require_GET
@xframe_options_sameorigin
def verificar_documento_pdf(request, token):
    try:
        u = uuid.UUID(str(token).strip())
    except (ValueError, TypeError, AttributeError):
        raise Http404()
    pedido = AssinaturaDocumento.objects.filter(verificacao_token=u).first()
    if not pedido or (pedido.status or "").lower() != AssinaturaDocumento.Status.CONCLUIDO:
        raise Http404()
    if not pedido.arquivo_assinado.name:
        raise Http404()
    fh = pedido.arquivo_assinado.open("rb")
    resp = FileResponse(fh, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="documento-assinado.pdf"'
    return resp
