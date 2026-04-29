from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import RelatorioTecnicoPrestacaoForm, TextoPadraoDocumentoForm
from .models import PrestacaoConta, TextoPadraoDocumento
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
    dados_servidor = _dados_servidor_preview(prestacao)
    if dados_servidor["incompleto"]:
        messages.warning(request, "Dados incompletos do servidor. Atualize o cadastro ou revise a prestacao.")
    return render(
        request,
        "prestacao_contas/relatorio_tecnico_form.html",
        {
            "prestacao": prestacao,
            "rt": rt,
            "form": form,
            "resumo_viagem": _resumo_viagem(prestacao.oficio),
            "dados_servidor": dados_servidor,
        },
    )


@login_required
def relatorio_tecnico_docx(request, prestacao_id):
    prestacao = get_object_or_404(PrestacaoConta.objects.select_related("oficio", "servidor"), pk=prestacao_id)
    rt = obter_ou_criar_rt(prestacao, usuario=request.user)
    form = RelatorioTecnicoPrestacaoForm(request.POST or None, instance=rt)
    if request.method == "POST":
        if form.is_valid():
            rt = form.save()
        else:
            messages.error(request, "Corrija os campos do RT antes de gerar o DOCX.")
            return render(
                request,
                "prestacao_contas/relatorio_tecnico_form.html",
                {
                    "prestacao": prestacao,
                    "rt": rt,
                    "form": form,
                    "resumo_viagem": _resumo_viagem(prestacao.oficio),
                    "dados_servidor": _dados_servidor_preview(prestacao),
                },
                status=422,
            )
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
    if request.method == "POST":
        if form.is_valid():
            rt = form.save()
        else:
            messages.error(request, "Corrija os campos do RT antes de gerar o PDF.")
            return render(
                request,
                "prestacao_contas/relatorio_tecnico_form.html",
                {
                    "prestacao": prestacao,
                    "rt": rt,
                    "form": form,
                    "resumo_viagem": _resumo_viagem(prestacao.oficio),
                    "dados_servidor": _dados_servidor_preview(prestacao),
                },
                status=422,
            )
    try:
        pdf_bytes, filename = gerar_pdf_rt(rt, usuario=request.user)
    except Exception as exc:
        messages.warning(request, str(exc))
        return redirect("prestacao_contas:relatorio-tecnico", prestacao_id=prestacao.id)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def texto_padrao_lista(request):
    categoria = (request.GET.get("categoria") or "").strip()
    qs = TextoPadraoDocumento.objects.all().order_by("categoria", "ordem", "titulo")
    if categoria:
        qs = qs.filter(categoria=categoria)
    return render(
        request,
        "prestacao_contas/textos_padrao_lista.html",
        {
            "textos": qs,
            "categoria": categoria,
            "categorias": TextoPadraoDocumento.CATEGORIA_CHOICES,
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
