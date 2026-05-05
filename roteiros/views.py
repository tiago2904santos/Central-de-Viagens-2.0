from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from .forms import RoteiroForm
from .presenters import apresentar_roteiro_card
from .selectors import get_roteiro_by_id
from .selectors import listar_roteiros
from .selectors import listar_trechos_do_roteiro


def index(request):
    q = request.GET.get("q", "").strip()
    roteiros = listar_roteiros(q=q)
    cards = [apresentar_roteiro_card(roteiro) for roteiro in roteiros]
    return render(
        request,
        "roteiros/index.html",
        {
            "page_title": "Roteiros",
            "page_description": "Cadastre, consulte e reutilize trajetos oficiais nos documentos de viagem.",
            "create_url": reverse("roteiros:novo"),
            "cards": cards,
            "q": q,
        },
    )


def novo(request):
    if request.method == "POST":
        form = RoteiroForm(request.POST)
        if form.is_valid():
            roteiro = form.save()
            messages.success(request, "Roteiro cadastrado com sucesso.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
    else:
        form = RoteiroForm()

    return render(
        request,
        "roteiros/form.html",
        {
            "page_title": "Novo roteiro",
            "page_description": "Cadastre um trajeto oficial para reutilização nos fluxos de viagem.",
            "form": form,
            "submit_label": "Salvar roteiro",
            "back_url": reverse("roteiros:index"),
            "is_edit": False,
        },
    )


def detalhe(request, pk):
    roteiro = get_roteiro_by_id(pk)
    trechos = listar_trechos_do_roteiro(roteiro)
    return render(
        request,
        "roteiros/detail.html",
        {
            "page_title": roteiro.nome,
            "page_description": "Consulte os dados cadastrados para este roteiro.",
            "roteiro": roteiro,
            "trechos": trechos,
            "edit_url": reverse("roteiros:editar", args=[roteiro.pk]),
            "delete_url": reverse("roteiros:excluir", args=[roteiro.pk]),
            "back_url": reverse("roteiros:index"),
        },
    )


def editar(request, pk):
    roteiro = get_roteiro_by_id(pk)
    if request.method == "POST":
        form = RoteiroForm(request.POST, instance=roteiro)
        if form.is_valid():
            roteiro = form.save()
            messages.success(request, "Roteiro atualizado com sucesso.")
            return redirect("roteiros:detalhe", pk=roteiro.pk)
    else:
        form = RoteiroForm(instance=roteiro)

    return render(
        request,
        "roteiros/form.html",
        {
            "page_title": "Editar roteiro",
            "page_description": "Atualize os dados cadastrais do trajeto oficial.",
            "form": form,
            "submit_label": "Salvar roteiro",
            "back_url": reverse("roteiros:detalhe", args=[roteiro.pk]),
            "delete_url": reverse("roteiros:excluir", args=[roteiro.pk]),
            "is_edit": True,
            "roteiro": roteiro,
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
