from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, QueryDict
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    PrestacaoComprovanteForm,
    PrestacaoContaCreateForm,
    PrestacaoDBForm,
    PrestacaoInformacoesForm,
    RelatorioTecnicoPrestacaoForm,
    TextoPadraoDocumentoForm,
)
from .models import PrestacaoConta, TextoPadraoDocumento
from .services.relatorio_tecnico import gerar_docx_rt, gerar_pdf_rt, obter_ou_criar_rt
from diario_bordo.models import DiarioBordo


def _is_autosave_request(request):
    return request.method == "POST" and request.POST.get("autosave") == "1"


def _autosave_success_response(extra=None):
    payload = {"ok": True, "saved_at": timezone.localtime().strftime("%H:%M:%S")}
    if extra:
        payload.update(extra)
    return JsonResponse(payload)


def _autosave_error_response(message, status=400):
    return JsonResponse({"ok": False, "error": message}, status=status)


def _resumo_viagem(oficio):
    primeiro = oficio.trechos.order_by("ordem", "id").first()
    ultimo = oficio.trechos.order_by("-ordem", "-id").first()
    destino = ""
    periodo = ""
    if ultimo and ultimo.destino_cidade_id:
        destino = ultimo.destino_cidade.nome
    if primeiro and ultimo and primeiro.saida_data and ultimo.chegada_data:
        periodo = f"{primeiro.saida_data:%d/%m/%Y} a {ultimo.chegada_data:%d/%m/%Y}"
    return {"destino": destino or "Nao informado", "periodo": periodo or "Nao informado"}


def _dados_servidor_preview(prestacao):
    servidor = prestacao.servidor
    if servidor:
        return {
            "nome": (servidor.nome or "").strip() or prestacao.nome_servidor,
            "rg": getattr(servidor, "rg_formatado", "") or prestacao.rg_servidor,
            "cpf": getattr(servidor, "cpf_formatado", "") or prestacao.cpf_servidor,
            "cargo": (getattr(servidor.cargo, "nome", "") or "").strip() or prestacao.cargo_servidor,
            "unidade": (getattr(servidor.unidade_lotacao, "nome", "") or "").strip(),
            "incompleto": not bool((servidor.nome or "").strip() and (getattr(servidor, "rg_formatado", "") or "").strip()),
        }
    return {
        "nome": prestacao.nome_servidor,
        "rg": prestacao.rg_servidor,
        "cpf": prestacao.cpf_servidor,
        "cargo": prestacao.cargo_servidor,
        "unidade": "",
        "incompleto": not bool((prestacao.nome_servidor or "").strip() and (prestacao.rg_servidor or "").strip()),
    }


def _status_badge(status):
    css = {
        PrestacaoConta.STATUS_CONCLUIDA: "oficio-list-badge--success",
        PrestacaoConta.STATUS_EM_ANDAMENTO: "oficio-list-badge--warning",
        PrestacaoConta.STATUS_RASCUNHO: "oficio-list-badge--muted",
    }.get(status, "oficio-list-badge--muted")
    return css


def _prestacao_identificacao(prestacao):
    if prestacao.oficio_id:
        return f"Oficio {prestacao.oficio.numero_formatado}"
    return f"Prestacao #{prestacao.pk}"


def _prestacao_descricao(prestacao):
    return (prestacao.descricao_evento or prestacao.oficio.motivo or "").strip() or "Descricao nao informada"


def _build_prestacao_actions(prestacao):
    actions = [
        {
            "label": "Abrir",
            "aria_label": "Abrir prestacao de contas",
            "url": reverse("prestacao_contas:editar", kwargs={"prestacao_id": prestacao.pk}),
            "css_class": "btn-doc-action--primary",
            "icon": "bi-box-arrow-up-right",
            "download": False,
            "icon_only": False,
        },
        {
            "label": "Editar",
            "aria_label": "Editar ou continuar prestacao",
            "url": reverse("prestacao_contas:step", kwargs={"prestacao_id": prestacao.pk, "step": 1}),
            "css_class": "btn-doc-action--secondary",
            "icon": "bi-pencil-square",
            "download": False,
            "icon_only": False,
        },
    ]
    rt = getattr(prestacao, "relatorio_tecnico", None)
    if rt and rt.arquivo_docx:
        actions.append(
            {
                "label": "DOCX",
                "aria_label": "Baixar RT em DOCX",
                "url": rt.arquivo_docx.url,
                "css_class": "btn-doc-action--secondary",
                "icon": "bi-filetype-docx",
                "download": True,
                "icon_only": True,
            }
        )
    if rt and rt.arquivo_pdf:
        actions.append(
            {
                "label": "PDF",
                "aria_label": "Baixar RT em PDF",
                "url": rt.arquivo_pdf.url,
                "css_class": "btn-doc-action--pdf",
                "icon": "bi-filetype-pdf",
                "download": True,
                "icon_only": True,
            }
        )
    actions.append(
        {
            "label": "Excluir",
            "aria_label": "Excluir prestacao",
            "url": reverse("prestacao_contas:excluir", kwargs={"prestacao_id": prestacao.pk}),
            "css_class": "btn-doc-action--danger",
            "icon": "bi-trash3",
            "download": False,
            "icon_only": True,
        }
    )
    return actions


def _build_prestacao_list_item(prestacao):
    rt = getattr(prestacao, "relatorio_tecnico", None)
    return {
        "obj": prestacao,
        "id": prestacao.pk,
        "identificacao": _prestacao_identificacao(prestacao),
        "descricao": _prestacao_descricao(prestacao),
        "servidor": prestacao.nome_servidor or getattr(prestacao.servidor, "nome", "") or "Nao informado",
        "status_label": prestacao.get_status_display(),
        "status_css_class": _status_badge(prestacao.status),
        "status_rt_label": prestacao.get_status_rt_display(),
        "status_db_label": prestacao.get_status_db_display(),
        "created_display": prestacao.created_at.strftime("%d/%m/%Y") if prestacao.created_at else "-",
        "updated_display": prestacao.updated_at.strftime("%d/%m/%Y %H:%M") if prestacao.updated_at else "-",
        "despacho_nome": prestacao.despacho_pdf.name.rsplit("/", 1)[-1] if prestacao.despacho_pdf else "",
        "despacho_url": prestacao.despacho_pdf.url if prestacao.despacho_pdf else "",
        "comprovante_nome": prestacao.comprovante_transferencia.name.rsplit("/", 1)[-1]
        if prestacao.comprovante_transferencia
        else "",
        "comprovante_url": prestacao.comprovante_transferencia.url if prestacao.comprovante_transferencia else "",
        "rt_docx_url": rt.arquivo_docx.url if rt and rt.arquivo_docx else "",
        "rt_pdf_url": rt.arquivo_pdf.url if rt and rt.arquivo_pdf else "",
        "actions": _build_prestacao_actions(prestacao),
    }


def _build_wizard_steps(prestacao, current_key):
    definitions = [
        ("step1", 1, "Informacoes da prestacao", reverse("prestacao_contas:step", kwargs={"prestacao_id": prestacao.pk, "step": 1})),
        ("step2", 2, "Gerador de RT", reverse("prestacao_contas:step", kwargs={"prestacao_id": prestacao.pk, "step": 2})),
        ("step3", 3, "Gerador de DB", reverse("prestacao_contas:step", kwargs={"prestacao_id": prestacao.pk, "step": 3})),
        ("step4", 4, "Comprovante de transferencia", reverse("prestacao_contas:step", kwargs={"prestacao_id": prestacao.pk, "step": 4})),
        ("summary", 5, "Resumo para copiar e colar", reverse("prestacao_contas:resumo", kwargs={"prestacao_id": prestacao.pk})),
    ]
    current_number = next((number for key, number, _label, _url in definitions if key == current_key), 1)
    steps = []
    for key, number, label, url in definitions:
        active = key == current_key
        state = "active" if active else "completed" if number < current_number else "pending"
        steps.append(
            {
                "key": key,
                "number": number,
                "label": label,
                "url": url,
                "active": active,
                "state": state,
                "state_label": {"active": "Etapa atual", "completed": "Concluido", "pending": "Pendente"}[state],
            }
        )
    return steps


def _summary_lines(prestacao, rt=None):
    rt = rt if rt is not None else getattr(prestacao, "relatorio_tecnico", None)
    descricao = _prestacao_descricao(prestacao)
    lines = [
        f"RT DESCRIÇÃO DO EVENTO: {descricao}",
        f"PRESTAÇÃO DESCRIÇÃO DO EVENTO: {descricao}",
        f"PRESTAÇÃO STATUS: {prestacao.get_status_display()}",
    ]
    if rt:
        if rt.diaria:
            lines.append(f"RT DIÁRIA: {rt.diaria}")
        if rt.translado:
            lines.append(f"RT TRANSLADO: {rt.translado}")
        if rt.passagem:
            lines.append(f"RT PASSAGEM: {rt.passagem}")
        if rt.conclusao:
            lines.append(f"RT CONCLUSÃO: {rt.conclusao}")
    dados_db = prestacao.dados_db or {}
    if dados_db.get("db_numero"):
        lines.append(f"DB NÚMERO: {dados_db['db_numero']}")
    if dados_db.get("db_descricao"):
        lines.append(f"DB DESCRIÇÃO: {dados_db['db_descricao']}")
    if dados_db.get("db_observacoes"):
        lines.append(f"DB OBSERVAÇÕES: {dados_db['db_observacoes']}")
    lines.append(f"DESPACHO: {prestacao.despacho_pdf.name.rsplit('/', 1)[-1] if prestacao.despacho_pdf else 'Nao anexado'}")
    lines.append(
        "COMPROVANTE DE TRANSFERÊNCIA: "
        + (prestacao.comprovante_transferencia.name.rsplit("/", 1)[-1] if prestacao.comprovante_transferencia else "Nao anexado")
    )
    return lines


def _wizard_context(prestacao, current_key, **extra):
    context = {
        "hide_page_header": True,
        "prestacao": prestacao,
        "wizard_steps": _build_wizard_steps(prestacao, current_key),
        "wizard_page_title": "Prestacao de contas",
        "wizard_header_title": "Prestacao de contas",
        "return_to_url": reverse("prestacao_contas:lista"),
        "resumo_viagem": _resumo_viagem(prestacao.oficio),
    }
    context.update(extra)
    return context


def _rt_documento_desatualizado(rt, tipo):
    if tipo == "docx" and not rt.arquivo_docx:
        return True
    if tipo == "pdf" and not rt.arquivo_pdf:
        return True
    if rt.status != rt.STATUS_GERADO:
        return True
    if not rt.data_geracao:
        return True
    if rt.updated_at and rt.updated_at > rt.data_geracao:
        return True
    return False


def _build_rt_partial_payload(rt, post_data):
    form_probe = RelatorioTecnicoPrestacaoForm(instance=rt)
    data = QueryDict("", mutable=True)
    saved_codigos = [c.strip() for c in (rt.atividade_codigos or "").split(",") if c.strip()]

    for field_name in form_probe.fields.keys():
        if field_name in post_data:
            data.setlist(field_name, post_data.getlist(field_name))
            continue
        if field_name == "atividades_codigos":
            data.setlist(field_name, saved_codigos)
            continue
        if field_name in {"conclusao_modelo", "medidas_modelo", "info_modelo"}:
            data[field_name] = str(form_probe.initial.get(field_name) or "")
            continue
        if field_name in {"teve_translado", "teve_passagem"}:
            data[field_name] = "1" if getattr(rt, field_name) else "0"
            continue
        current_value = getattr(rt, field_name, "")
        data[field_name] = "" if current_value is None else str(current_value)
    return data


def _parse_bool_field(value):
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "on", "sim", "yes"}


def _parse_decimal_field(value):
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("R$", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    else:
        normalized = normalized.replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_currency_br(value):
    if value is None:
        return "Nao houve"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _autosave_relatorio_tecnico(prestacao, rt, post_data):
    allowed_fields = {
        "teve_translado",
        "valor_translado",
        "teve_passagem",
        "valor_passagem",
        "atividade",
        "conclusao",
        "medidas",
        "informacoes_complementares",
        "atividade_codigos",
        "conclusao_modelo",
        "medidas_modelo",
        "info_modelo",
    }
    incoming = {key for key in post_data.keys() if key in allowed_fields}
    if not incoming:
        return JsonResponse({"ok": True, "status": "ignorado", "documento_status": "desatualizado"})

    update_fields = []
    errors = {}

    if "atividade_codigos" in incoming:
        codigos = [c.strip() for c in post_data.getlist("atividade_codigos") if c.strip()]
        rt.atividade_codigos = ",".join(codigos)
        update_fields.append("atividade_codigos")

    for field in ("atividade", "conclusao", "medidas", "informacoes_complementares"):
        if field in incoming:
            setattr(rt, field, (post_data.get(field) or "").strip())
            update_fields.append(field)

    if "conclusao_modelo" in incoming:
        modelo = TextoPadraoDocumento.objects.filter(pk=post_data.get("conclusao_modelo") or None).first()
        if modelo and "conclusao" not in incoming:
            rt.conclusao = modelo.texto
            update_fields.append("conclusao")
    if "medidas_modelo" in incoming:
        modelo = TextoPadraoDocumento.objects.filter(pk=post_data.get("medidas_modelo") or None).first()
        if modelo and "medidas" not in incoming:
            rt.medidas = modelo.texto
            update_fields.append("medidas")
    if "info_modelo" in incoming:
        modelo = TextoPadraoDocumento.objects.filter(pk=post_data.get("info_modelo") or None).first()
        if modelo and "informacoes_complementares" not in incoming:
            rt.informacoes_complementares = modelo.texto
            update_fields.append("informacoes_complementares")

    if "teve_translado" in incoming:
        valor_bool = _parse_bool_field(post_data.get("teve_translado"))
        rt.teve_translado = bool(valor_bool)
        update_fields.append("teve_translado")
    if "valor_translado" in incoming:
        valor = _parse_decimal_field(post_data.get("valor_translado"))
        if valor is None and rt.teve_translado:
            errors["valor_translado"] = "Informe um valor válido para translado."
        else:
            rt.valor_translado = valor
            update_fields.append("valor_translado")
    if "teve_translado" in incoming or "valor_translado" in incoming:
        if rt.teve_translado:
            if rt.valor_translado is None:
                errors["valor_translado"] = "Informe o valor de translado."
            rt.translado = _format_currency_br(rt.valor_translado) if rt.valor_translado is not None else ""
        else:
            rt.valor_translado = None
            rt.translado = "Nao houve"
            update_fields.extend(["valor_translado"])
        update_fields.append("translado")

    if "teve_passagem" in incoming:
        valor_bool = _parse_bool_field(post_data.get("teve_passagem"))
        rt.teve_passagem = bool(valor_bool)
        update_fields.append("teve_passagem")
    if "valor_passagem" in incoming:
        valor = _parse_decimal_field(post_data.get("valor_passagem"))
        if valor is None and rt.teve_passagem:
            errors["valor_passagem"] = "Informe um valor válido para passagem."
        else:
            rt.valor_passagem = valor
            update_fields.append("valor_passagem")
    if "teve_passagem" in incoming or "valor_passagem" in incoming:
        if rt.teve_passagem:
            if rt.valor_passagem is None:
                errors["valor_passagem"] = "Informe o valor de passagem."
            rt.passagem = _format_currency_br(rt.valor_passagem) if rt.valor_passagem is not None else ""
        else:
            rt.valor_passagem = None
            rt.passagem = "Nao houve"
            update_fields.extend(["valor_passagem"])
        update_fields.append("passagem")

    if errors:
        return JsonResponse({"ok": False, "status": "erro", "errors": errors}, status=400)

    rt.status = rt.STATUS_RASCUNHO
    update_fields.append("status")
    rt.save(update_fields=[*set(update_fields), "updated_at"])
    prestacao.status_rt = PrestacaoConta.STATUS_RT_RASCUNHO
    prestacao.rt_atualizado_em = timezone.now()
    prestacao.save(update_fields=["status_rt", "rt_atualizado_em", "updated_at"])
    return JsonResponse(
        {
            "ok": True,
            "status": "salvo",
            "updated_at": prestacao.updated_at.isoformat(),
            "saved_at": timezone.localtime(prestacao.updated_at).strftime("%H:%M"),
            "documento_status": "desatualizado",
            "documento_desatualizado": True,
        }
    )


@login_required
def prestacao_lista(request):
    prestacoes = PrestacaoConta.objects.select_related("oficio", "servidor").order_by("-updated_at")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if q:
        prestacoes = prestacoes.filter(
            Q(descricao_evento__icontains=q)
            | Q(nome_servidor__icontains=q)
            | Q(oficio__protocolo__icontains=q)
            | Q(oficio__motivo__icontains=q)
        )
    if status:
        prestacoes = prestacoes.filter(status=status)
    items = [_build_prestacao_list_item(prestacao) for prestacao in prestacoes]
    return render(
        request,
        "prestacao_contas/lista.html",
        {
            "object_list": items,
            "prestacoes": prestacoes,
            "filters": {"q": q, "status": status},
            "status_choices": PrestacaoConta.STATUS_CHOICES,
            "clear_filters_url": reverse("prestacao_contas:lista"),
        },
    )


@login_required
def prestacao_nova(request):
    if request.method == "POST":
        form = PrestacaoContaCreateForm(request.POST)
        if form.is_valid():
            prestacao = form.save(commit=False)
            prestacao.status = PrestacaoConta.STATUS_EM_ANDAMENTO
            if prestacao.servidor:
                prestacao.nome_servidor = prestacao.servidor.nome or ""
                prestacao.rg_servidor = getattr(prestacao.servidor, "rg_formatado", "") or ""
                prestacao.cpf_servidor = getattr(prestacao.servidor, "cpf_formatado", "") or ""
                prestacao.cargo_servidor = getattr(getattr(prestacao.servidor, "cargo", None), "nome", "") or ""
            prestacao.save()
            messages.success(request, "Prestacao criada com sucesso.")
            return redirect("prestacao_contas:step", prestacao_id=prestacao.pk, step=1)
    else:
        form = PrestacaoContaCreateForm()
    return render(request, "prestacao_contas/nova.html", {"form": form})


@login_required
def prestacao_detalhe(request, prestacao_id):
    return redirect("prestacao_contas:step", prestacao_id=prestacao_id, step=1)


@login_required
def prestacao_editar(request, prestacao_id):
    return redirect("prestacao_contas:step", prestacao_id=prestacao_id, step=1)


@login_required
def prestacao_step(request, prestacao_id, step):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    if step == 1:
        form = PrestacaoInformacoesForm(request.POST or None, request.FILES or None, instance=prestacao)
        if _is_autosave_request(request):
            form = PrestacaoInformacoesForm(request.POST or None, instance=prestacao)
            if form.is_valid():
                form.save()
                prestacao.status = PrestacaoConta.STATUS_EM_ANDAMENTO
                prestacao.save(update_fields=["status", "updated_at"])
                return _autosave_success_response({"status": "salvo"})
            error = next(iter(form.errors.values()))[0] if form.errors else "Falha no autosave."
            return _autosave_error_response(str(error))
        if request.method == "POST" and form.is_valid():
            form.save()
            prestacao.status = PrestacaoConta.STATUS_EM_ANDAMENTO
            prestacao.save(update_fields=["status", "updated_at"])
            return redirect("prestacao_contas:step" if "avancar" in request.POST else "prestacao_contas:step", prestacao_id=prestacao.pk, step=2 if "avancar" in request.POST else 1)
        return render(request, "prestacao_contas/wizard_step1.html", _wizard_context(prestacao, "step1", form=form))
    if step == 2:
        rt = obter_ou_criar_rt(prestacao, usuario=request.user)
        if prestacao.descricao_evento and rt.motivo != prestacao.descricao_evento:
            rt.motivo = prestacao.descricao_evento
            rt.save(update_fields=["motivo", "updated_at"])
        form = RelatorioTecnicoPrestacaoForm(request.POST or None, instance=rt)
        is_autosave = request.method == "POST" and request.POST.get("autosave") == "1"
        if is_autosave:
            return _autosave_relatorio_tecnico(prestacao, rt, request.POST)
        if request.method == "POST" and form.is_valid():
            rt = form.save(commit=False)
            rt.status = rt.STATUS_RASCUNHO
            rt.save()
            prestacao.status_rt = PrestacaoConta.STATUS_RT_RASCUNHO
            prestacao.rt_atualizado_em = timezone.now()
            prestacao.save(update_fields=["status_rt", "rt_atualizado_em", "updated_at"])
            return redirect("prestacao_contas:step", prestacao_id=prestacao.pk, step=3 if "avancar" in request.POST else 2)
        return render(
            request,
            "prestacao_contas/wizard_step2.html",
            _wizard_context(prestacao, "step2", form=form, rt=rt, dados_servidor=_dados_servidor_preview(prestacao)),
        )
    if step == 3:
        diario = DiarioBordo.objects.filter(prestacao=prestacao).select_related("veiculo", "motorista").prefetch_related("trechos").first()
        if request.method == "POST" and "avancar" in request.POST:
            return redirect("prestacao_contas:step", prestacao_id=prestacao.pk, step=4)
        return render(request, "prestacao_contas/wizard_step3.html", _wizard_context(prestacao, "step3", diario_bordo=diario))
    if step == 4:
        form = PrestacaoComprovanteForm(request.POST or None, request.FILES or None, instance=prestacao)
        if _is_autosave_request(request):
            # Autosave nesta etapa só persiste campos textuais; upload exige submit normal.
            return _autosave_success_response({"status": "ok"})
        if request.method == "POST" and form.is_valid():
            form.save()
            if "avancar" in request.POST:
                return redirect("prestacao_contas:resumo", prestacao_id=prestacao.pk)
            return redirect("prestacao_contas:step", prestacao_id=prestacao.pk, step=4)
        return render(request, "prestacao_contas/wizard_step4.html", _wizard_context(prestacao, "step4", form=form))
    return redirect("prestacao_contas:resumo", prestacao_id=prestacao.pk)


@login_required
def prestacao_resumo(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    rt = getattr(prestacao, "relatorio_tecnico", None)
    return render(
        request,
        "prestacao_contas/wizard_resumo.html",
        _wizard_context(prestacao, "summary", rt=rt, resumo_linhas=_summary_lines(prestacao, rt)),
    )


@login_required
@require_http_methods(["GET", "POST"])
def prestacao_excluir(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta, pk=prestacao_id)
    if request.method == "POST":
        prestacao.delete()
        messages.success(request, "Prestacao excluida com sucesso.")
        return redirect("prestacao_contas:lista")
    return render(request, "prestacao_contas/excluir_confirm.html", {"prestacao": prestacao})


@login_required
def relatorio_tecnico_form(request, prestacao_id):
    return prestacao_step(request, prestacao_id, 2)


@login_required
def relatorio_tecnico_docx(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    rt = obter_ou_criar_rt(prestacao, usuario=request.user)
    if _rt_documento_desatualizado(rt, "docx"):
        docx_bytes, filename = gerar_docx_rt(rt, usuario=request.user)
    else:
        rt.arquivo_docx.open("rb")
        try:
            docx_bytes = rt.arquivo_docx.read()
        finally:
            rt.arquivo_docx.close()
        filename = rt.arquivo_docx.name.rsplit("/", 1)[-1]
    response = HttpResponse(
        docx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def relatorio_tecnico_pdf(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    rt = obter_ou_criar_rt(prestacao, usuario=request.user)
    try:
        if _rt_documento_desatualizado(rt, "pdf"):
            pdf_bytes, filename = gerar_pdf_rt(rt, usuario=request.user)
        else:
            rt.arquivo_pdf.open("rb")
            try:
                pdf_bytes = rt.arquivo_pdf.read()
            finally:
                rt.arquivo_pdf.close()
            filename = rt.arquivo_pdf.name.rsplit("/", 1)[-1]
    except Exception as exc:
        messages.warning(request, str(exc))
        return redirect("prestacao_contas:relatorio-tecnico", prestacao_id=prestacao.id)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(["POST"])
def relatorio_tecnico_autosave(request, prestacao_id):
    return prestacao_step(request, prestacao_id, 2)


@login_required
def texto_padrao_lista(request):
    q = (request.GET.get("q") or "").strip()
    categoria = (request.GET.get("categoria") or "").strip()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    order_by = (request.GET.get("order_by") or "titulo").strip()
    order_dir = (request.GET.get("order_dir") or "asc").strip()

    qs = TextoPadraoDocumento.objects.all()
    if q:
        qs = qs.filter(Q(titulo__icontains=q) | Q(texto__icontains=q))
    if categoria:
        qs = qs.filter(categoria=categoria)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    allowed_order_fields = {
        "titulo": "titulo",
        "categoria": "categoria",
        "ordem": "ordem",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }
    order_field = allowed_order_fields.get(order_by, "titulo")
    if order_dir == "desc":
        order_field = f"-{order_field}"
    qs = qs.order_by(order_field, "titulo")

    order_by_choices = [
        ("titulo", "Titulo"),
        ("categoria", "Categoria"),
        ("ordem", "Ordem"),
        ("created_at", "Data de criacao"),
        ("updated_at", "Ultima atualizacao"),
    ]
    order_dir_choices = [("asc", "Crescente"), ("desc", "Decrescente")]

    return render(
        request,
        "prestacao_contas/textos_padrao_lista.html",
        {
            "object_list": qs,
            "textos": qs,
            "categoria": categoria,
            "categorias": TextoPadraoDocumento.CATEGORIA_CHOICES,
            "filters": {
                "q": q,
                "categoria": categoria,
                "date_from": date_from,
                "date_to": date_to,
                "order_by": order_by if order_by in allowed_order_fields else "titulo",
                "order_dir": order_dir if order_dir in {"asc", "desc"} else "asc",
            },
            "order_by_choices": order_by_choices,
            "order_dir_choices": order_dir_choices,
            "cadastrar_modelo_url": reverse("prestacao_contas:textos-padrao-novo"),
            "clear_filters_url": reverse("prestacao_contas:textos-padrao"),
        },
    )


@login_required
def texto_padrao_form(request, pk=None):
    instance = get_object_or_404(TextoPadraoDocumento, pk=pk) if pk else None
    if request.method == "POST":
        form = TextoPadraoDocumentoForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.criado_por_id:
                obj.criado_por = request.user
            if obj.is_padrao:
                TextoPadraoDocumento.objects.filter(categoria=obj.categoria).exclude(pk=obj.pk).update(is_padrao=False)
            obj.save()
            messages.success(request, "Texto padrao salvo com sucesso.")
            return redirect("prestacao_contas:textos-padrao")
    else:
        form = TextoPadraoDocumentoForm(instance=instance)
    return render(
        request,
        "prestacao_contas/textos_padrao_form.html",
        {"form": form, "obj": instance},
    )
