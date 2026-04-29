from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import RelatorioTecnicoPrestacaoForm
from .models import PrestacaoConta
from .services.relatorio_tecnico import gerar_docx_rt, gerar_pdf_rt, obter_ou_criar_rt


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


@login_required
def prestacao_lista(request):
    prestacoes = PrestacaoConta.objects.select_related("oficio", "servidor").order_by("-created_at")
    return render(request, "prestacao_contas/lista.html", {"prestacoes": prestacoes})


@login_required
def prestacao_detalhe(request, prestacao_id):
    prestacao = get_object_or_404(
        PrestacaoConta.objects.select_related("oficio", "servidor").prefetch_related("relatorio_tecnico"),
        pk=prestacao_id,
    )
    rt = getattr(prestacao, "relatorio_tecnico", None)
    return render(
        request,
        "prestacao_contas/detalhe.html",
        {"prestacao": prestacao, "rt": rt, "resumo_viagem": _resumo_viagem(prestacao.oficio)},
    )


@login_required
def relatorio_tecnico_form(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    rt = obter_ou_criar_rt(prestacao, usuario=request.user)
    if request.method == "POST":
        form = RelatorioTecnicoPrestacaoForm(request.POST, instance=rt)
        if form.is_valid():
            rt = form.save(commit=False)
            rt.status = rt.STATUS_RASCUNHO
            rt.save()
            prestacao.status_rt = PrestacaoConta.STATUS_RT_RASCUNHO
            prestacao.rt_atualizado_em = timezone.now()
            prestacao.save(update_fields=["status_rt", "rt_atualizado_em", "updated_at"])
            messages.success(request, "Rascunho do RT salvo com sucesso.")
            return redirect("prestacao_contas:relatorio-tecnico", prestacao_id=prestacao.id)
    else:
        form = RelatorioTecnicoPrestacaoForm(instance=rt)
    return render(
        request,
        "prestacao_contas/relatorio_tecnico_form.html",
        {"prestacao": prestacao, "rt": rt, "form": form, "resumo_viagem": _resumo_viagem(prestacao.oficio)},
    )


@login_required
def relatorio_tecnico_docx(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    rt = obter_ou_criar_rt(prestacao, usuario=request.user)
    form = RelatorioTecnicoPrestacaoForm(request.POST or None, instance=rt)
    if request.method == "POST" and form.is_valid():
        rt = form.save()
    docx_bytes, filename = gerar_docx_rt(rt, usuario=request.user)
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
    form = RelatorioTecnicoPrestacaoForm(request.POST or None, instance=rt)
    if request.method == "POST" and form.is_valid():
        rt = form.save()
    try:
        pdf_bytes, filename = gerar_pdf_rt(rt, usuario=request.user)
    except Exception as exc:
        messages.warning(request, str(exc))
        return redirect("prestacao_contas:relatorio-tecnico", prestacao_id=prestacao.id)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
