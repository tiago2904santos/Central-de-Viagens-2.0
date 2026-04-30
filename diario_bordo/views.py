from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from cadastros.models import ConfiguracaoSistema
from eventos.models import Oficio, RoteiroEvento
from prestacao_contas.models import PrestacaoConta

from .forms import DiarioAssinadoForm, DiarioIdentificacaoForm, DiarioTrechoFormSet, DiarioVeiculoResponsavelForm
from .models import DiarioBordo
from .services import gerar_pdf_diario, gerar_xlsx_diario, inicializar_trechos_diario_bordo


def _fmt_protocolo(oficio):
    return getattr(oficio, "protocolo_formatado", "") or getattr(oficio, "protocolo", "") or ""


def preencher_diario_por_oficio(diario, oficio):
    diario.oficio = oficio
    diario.numero_oficio = getattr(oficio, "numero_formatado", "") or ""
    diario.e_protocolo = _fmt_protocolo(oficio)
    diario.roteiro = getattr(oficio, "roteiro_evento", None)
    if getattr(oficio, "veiculo_id", None) and not diario.veiculo_id:
        diario.veiculo = oficio.veiculo
    diario.tipo_veiculo = diario.tipo_veiculo or getattr(oficio, "get_tipo_viatura_display", lambda: "")()
    diario.combustivel = diario.combustivel or getattr(oficio, "combustivel", "")
    diario.placa_oficial = diario.placa_oficial or getattr(oficio, "placa", "")
    diario.nome_responsavel = diario.nome_responsavel or getattr(oficio, "motorista", "")
    if getattr(oficio, "motorista_viajante_id", None) and not diario.motorista_id:
        diario.motorista = oficio.motorista_viajante
        diario.nome_responsavel = diario.nome_responsavel or oficio.motorista_viajante.nome
        diario.rg_responsavel = diario.rg_responsavel or getattr(oficio.motorista_viajante, "rg_formatado", "")
    config = ConfiguracaoSistema.get_singleton()
    diario.divisao = diario.divisao or config.divisao
    diario.unidade_cabecalho = diario.unidade_cabecalho or config.unidade
    return diario


def _sync_manual_from_relations(diario):
    if diario.prestacao_id and diario.prestacao and diario.prestacao.oficio_id:
        preencher_diario_por_oficio(diario, diario.prestacao.oficio)
        diario.prestacao = diario.prestacao
    if diario.oficio_id and diario.oficio:
        diario.numero_oficio = diario.numero_oficio or diario.oficio.numero_formatado
        diario.e_protocolo = diario.e_protocolo or _fmt_protocolo(diario.oficio)
    if diario.veiculo_id and diario.veiculo:
        diario.tipo_veiculo = diario.tipo_veiculo or diario.veiculo.get_tipo_display()
        diario.combustivel = diario.combustivel or str(diario.veiculo.combustivel or "")
        diario.placa_oficial = diario.placa_oficial or diario.veiculo.placa_formatada
    if diario.motorista_id and diario.motorista:
        diario.nome_responsavel = diario.nome_responsavel or diario.motorista.nome
        diario.rg_responsavel = diario.rg_responsavel or diario.motorista.rg_formatado


def _build_steps(diario, current_key):
    defs = [
        ("step1", 1, "Identificação", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 1})),
        ("step2", 2, "Veículo e responsável", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 2})),
        ("step3", 3, "Trechos e quilometragem", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 3})),
        ("step4", 4, "Conferência e geração", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 4})),
        ("step5", 5, "Arquivo assinado", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 5})),
    ]
    current_number = next((n for key, n, _label, _url in defs if key == current_key), 1)
    steps = []
    for key, number, label, url in defs:
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
                "state_label": {"active": "Etapa atual", "completed": "Concluído", "pending": "Pendente"}[state],
            }
        )
    return steps


def _wizard_context(diario, current_key, **extra):
    context = {
        "hide_page_header": True,
        "diario": diario,
        "wizard_steps": _build_steps(diario, current_key),
        "wizard_header_title": "Diário de Bordo",
        "return_to_url": reverse("diario_bordo:lista"),
    }
    context.update(extra)
    return context


def _actions(diario):
    actions = [
        ("Abrir", reverse("diario_bordo:editar", kwargs={"pk": diario.pk}), "btn-doc-action--primary", "bi-box-arrow-up-right", False),
        ("Editar", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 1}), "btn-doc-action--secondary", "bi-pencil-square", False),
    ]
    if diario.arquivo_pdf:
        actions.append(("PDF", reverse("diario_bordo:pdf", kwargs={"pk": diario.pk}), "btn-doc-action--pdf", "bi-filetype-pdf", True))
    if diario.arquivo_xlsx:
        actions.append(("XLSX", reverse("diario_bordo:xlsx", kwargs={"pk": diario.pk}), "btn-doc-action--secondary", "bi-filetype-xlsx", True))
    actions.append(("Anexar assinado", reverse("diario_bordo:step", kwargs={"pk": diario.pk, "step": 5}), "btn-doc-action--secondary", "bi-upload", False))
    actions.append(("Excluir", reverse("diario_bordo:excluir", kwargs={"pk": diario.pk}), "btn-doc-action--danger", "bi-trash3", False))
    return [
        {"label": label, "url": url, "css_class": css, "icon": icon, "icon_only": label in {"PDF", "Excluir"}, "download": download}
        for label, url, css, icon, download in actions
    ]


@login_required
def diario_lista(request):
    qs = DiarioBordo.objects.select_related("oficio", "veiculo", "motorista", "prestacao").prefetch_related("trechos")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if q:
        qs = qs.filter(
            Q(numero_oficio__icontains=q)
            | Q(e_protocolo__icontains=q)
            | Q(placa_oficial__icontains=q)
            | Q(nome_responsavel__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    object_list = [
        {
            "obj": item,
            "id": item.pk,
            "oficio": item.numero_oficio or "Avulso",
            "protocolo": item.e_protocolo or "Não informado",
            "veiculo": item.tipo_veiculo or getattr(item.veiculo, "modelo", "") or "Não informado",
            "placa": item.placa_oficial or "Não informada",
            "responsavel": item.nome_responsavel or "Não informado",
            "trechos": item.trechos.count(),
            "status": item.get_status_display(),
            "status_key": item.status,
            "tem_pdf": bool(item.arquivo_pdf),
            "tem_assinado": bool(item.arquivo_assinado),
            "actions": _actions(item),
        }
        for item in qs
    ]
    return render(
        request,
        "diario_bordo/lista.html",
        {
            "object_list": object_list,
            "filters": {"q": q, "status": status},
            "status_choices": DiarioBordo.STATUS_CHOICES,
            "clear_filters_url": reverse("diario_bordo:lista"),
        },
    )


@login_required
def diario_novo(request):
    diario = DiarioBordo.objects.create()
    return redirect("diario_bordo:step", pk=diario.pk, step=1)


@login_required
def diario_novo_oficio(request, oficio_id):
    oficio = get_object_or_404(Oficio, pk=oficio_id)
    diario = DiarioBordo()
    preencher_diario_por_oficio(diario, oficio)
    diario.save()
    inicializar_trechos_diario_bordo(diario, force=False)
    return redirect("diario_bordo:step", pk=diario.pk, step=1)


@login_required
def diario_novo_prestacao(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio"), pk=prestacao_id)
    diario = DiarioBordo(prestacao=prestacao)
    if prestacao.oficio_id:
        preencher_diario_por_oficio(diario, prestacao.oficio)
    diario.save()
    inicializar_trechos_diario_bordo(diario, force=False)
    return redirect("diario_bordo:step", pk=diario.pk, step=1)


@login_required
def diario_editar(request, pk):
    return redirect("diario_bordo:step", pk=pk, step=1)


@login_required
def diario_step(request, pk, step):
    diario = get_object_or_404(DiarioBordo.objects.select_related("oficio", "prestacao", "roteiro", "veiculo", "motorista"), pk=pk)
    if step == 1:
        form = DiarioIdentificacaoForm(request.POST or None, instance=diario)
        if request.method == "POST" and form.is_valid():
            diario = form.save(commit=False)
            _sync_manual_from_relations(diario)
            diario.save()
            inicializar_trechos_diario_bordo(diario, force=False)
            return redirect("diario_bordo:step", pk=diario.pk, step=2 if "avancar" in request.POST else 1)
        return render(request, "diario_bordo/wizard_step1.html", _wizard_context(diario, "step1", form=form))
    if step == 2:
        form = DiarioVeiculoResponsavelForm(request.POST or None, instance=diario)
        if request.method == "POST" and form.is_valid():
            diario = form.save(commit=False)
            _sync_manual_from_relations(diario)
            diario.save()
            return redirect("diario_bordo:step", pk=diario.pk, step=3 if "avancar" in request.POST else 2)
        return render(request, "diario_bordo/wizard_step2.html", _wizard_context(diario, "step2", form=form))
    if step == 3:
        if request.method == "POST" and request.POST.get("reimportar_trechos") == "1":
            _trechos, imported = inicializar_trechos_diario_bordo(diario, force=True)
            if imported:
                messages.success(request, "Datas e destinos reimportados com sucesso.")
            else:
                messages.warning(
                    request,
                    "Nenhum roteiro/data foi encontrado automaticamente. Preencha os trechos manualmente.",
                )
            return redirect("diario_bordo:step", pk=diario.pk, step=3)

        _trechos, imported = inicializar_trechos_diario_bordo(diario, force=False)
        import_warning = not diario.trechos.exists() and not imported
        formset = DiarioTrechoFormSet(request.POST or None, instance=diario, prefix="trechos")
        if request.method == "POST" and formset.is_valid():
            instances = formset.save(commit=False)
            for deleted in formset.deleted_objects:
                deleted.delete()
            for index, item in enumerate(instances):
                item.diario = diario
                item.ordem = index
                item.save()
            return redirect("diario_bordo:step", pk=diario.pk, step=4 if "avancar" in request.POST else 3)
        return render(
            request,
            "diario_bordo/wizard_step3.html",
            _wizard_context(
                diario,
                "step3",
                formset=formset,
                trechos=diario.trechos.all().order_by("ordem", "id"),
                import_warning=import_warning,
            ),
        )
    if step == 4:
        if request.method == "POST" and request.POST.get("gerar_pdf"):
            try:
                gerar_pdf_diario(diario)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                messages.success(request, "PDF do Diário de Bordo gerado com sucesso.")
            return redirect("diario_bordo:step", pk=diario.pk, step=4)
        if request.method == "POST" and request.POST.get("gerar_xlsx"):
            try:
                gerar_xlsx_diario(diario)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                messages.success(request, "XLSX do Diário de Bordo gerado com sucesso.")
            return redirect("diario_bordo:step", pk=diario.pk, step=4)
        return render(
            request,
            "diario_bordo/wizard_step4.html",
            _wizard_context(diario, "step4", trechos=diario.trechos.all().order_by("ordem", "id")),
        )
    if step == 5:
        form = DiarioAssinadoForm(request.POST or None, request.FILES or None, instance=diario)
        if request.method == "POST" and form.is_valid():
            diario = form.save(commit=False)
            if diario.arquivo_assinado:
                diario.status = DiarioBordo.STATUS_ASSINADO
            diario.save()
            messages.success(request, "Arquivo assinado anexado com sucesso.")
            return redirect("diario_bordo:step", pk=diario.pk, step=5)
        return render(request, "diario_bordo/wizard_step5.html", _wizard_context(diario, "step5", form=form))
    return redirect("diario_bordo:step", pk=diario.pk, step=1)


@login_required
def diario_pdf(request, pk):
    diario = get_object_or_404(DiarioBordo, pk=pk)
    if diario.arquivo_pdf:
        diario.arquivo_pdf.open("rb")
        try:
            payload = diario.arquivo_pdf.read()
        finally:
            diario.arquivo_pdf.close()
        filename = diario.arquivo_pdf.name.rsplit("/", 1)[-1]
    else:
        try:
            payload, filename = gerar_pdf_diario(diario)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("diario_bordo:step", pk=diario.pk, step=4)
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def diario_xlsx(request, pk):
    diario = get_object_or_404(DiarioBordo, pk=pk)
    if diario.arquivo_xlsx:
        diario.arquivo_xlsx.open("rb")
        try:
            payload = diario.arquivo_xlsx.read()
        finally:
            diario.arquivo_xlsx.close()
        filename = diario.arquivo_xlsx.name.rsplit("/", 1)[-1]
    else:
        try:
            payload, filename = gerar_xlsx_diario(diario)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("diario_bordo:step", pk=diario.pk, step=4)
    response = HttpResponse(payload, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def diario_excluir(request, pk):
    diario = get_object_or_404(DiarioBordo, pk=pk)
    if request.method == "POST":
        diario.delete()
        messages.success(request, "Diário de Bordo excluído com sucesso.")
        return redirect("diario_bordo:lista")
    return render(request, "diario_bordo/excluir_confirm.html", {"diario": diario})
