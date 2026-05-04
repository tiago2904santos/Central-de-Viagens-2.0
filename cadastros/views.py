from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from .forms import CidadeForm
from .forms import UnidadeForm
from .presenters import apresentar_cidade_card
from .presenters import apresentar_motorista_card
from .presenters import apresentar_servidor_card
from .presenters import apresentar_unidade_card
from .presenters import apresentar_viatura_card
from .selectors import get_cidade_by_id
from .selectors import get_unidade_by_id
from .selectors import listar_cidades
from .selectors import listar_motoristas
from .selectors import listar_servidores
from .selectors import listar_unidades
from .selectors import listar_viaturas
from .services import atualizar_cidade
from .services import atualizar_unidade
from .services import CadastroVinculadoError
from .services import criar_cidade
from .services import criar_unidade
from .services import excluir_cidade
from .services import excluir_unidade


def _render_listagem(request, template_name, context):
    return render(request, template_name, context)


def index(request):
    return render(
        request,
        "cadastros/index.html",
        {
            "page_title": "Cadastros",
            "page_section": "Dados-base",
            "page_description": "Base para servidores, motoristas, viaturas, cidades e unidades.",
            "modules": [
                {
                    "title": "Unidades",
                    "description": "Estruturas administrativas reutilizadas nos documentos.",
                    "href": "unidades/",
                },
                {
                    "title": "Cidades",
                    "description": "Municipios e UFs usados em deslocamentos e documentos.",
                    "href": "cidades/",
                },
                {
                    "title": "Servidores",
                    "description": "Pessoas vinculadas a viagens, autorizacoes e prestacoes.",
                    "href": "servidores/",
                },
                {
                    "title": "Motoristas",
                    "description": "Servidores habilitados para conduzir viaturas.",
                    "href": "motoristas/",
                },
                {
                    "title": "Viaturas",
                    "description": "Veiculos disponiveis para ordens e deslocamentos.",
                    "href": "viaturas/",
                },
            ],
        },
    )


def unidades_index(request):
    q = request.GET.get("q", "").strip()
    unidades = listar_unidades(q=q)
    cards = [
        apresentar_unidade_card(
            unidade,
            edit_url=reverse("cadastros:unidade_update", args=[unidade.pk]),
            delete_url=reverse("cadastros:unidade_delete", args=[unidade.pk]),
        )
        for unidade in unidades
    ]
    return _render_listagem(
        request,
        "cadastros/unidades/index.html",
        {
            "page_title": "Unidades",
            "page_section": "Cadastros",
            "page_description": "Unidades administrativas reutilizadas nos fluxos documentais.",
            "cards": cards,
            "q": q,
        },
    )


def unidade_create(request):
    form = UnidadeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_unidade(form)
        messages.success(request, "Unidade criada com sucesso.")
        return redirect("cadastros:unidades_index")
    return render(
        request,
        "cadastros/unidades/form.html",
        {
            "page_title": "Nova unidade",
            "page_section": "Cadastros",
            "page_description": "Cadastre uma unidade administrativa reutilizavel.",
            "form": form,
            "submit_label": "Criar unidade",
            "back_url": reverse("cadastros:unidades_index"),
        },
    )


def unidade_update(request, pk):
    unidade = get_unidade_by_id(pk)
    form = UnidadeForm(request.POST or None, instance=unidade)
    if request.method == "POST" and form.is_valid():
        atualizar_unidade(unidade, form)
        messages.success(request, "Unidade atualizada com sucesso.")
        return redirect("cadastros:unidades_index")
    return render(
        request,
        "cadastros/unidades/form.html",
        {
            "page_title": "Editar unidade",
            "page_section": "Cadastros",
            "page_description": "Atualize os dados da unidade administrativa.",
            "form": form,
            "submit_label": "Salvar unidade",
            "back_url": reverse("cadastros:unidades_index"),
        },
    )


def unidade_delete(request, pk):
    unidade = get_unidade_by_id(pk)
    if request.method == "POST":
        try:
            excluir_unidade(unidade)
        except CadastroVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            )
            return redirect("cadastros:unidades_index")
        messages.success(request, "Unidade excluída com sucesso.")
        return redirect("cadastros:unidades_index")
    return render(
        request,
        "cadastros/unidades/confirm_delete.html",
        {
            "page_title": "Excluir unidade",
            "page_section": "Cadastros",
            "page_description": "Esta acao exclui o cadastro quando nao houver vinculos impeditivos.",
            "object": unidade,
            "back_url": reverse("cadastros:unidades_index"),
        },
    )


def cidades_index(request):
    q = request.GET.get("q", "").strip()
    cidades = listar_cidades(q=q)
    cards = [
        apresentar_cidade_card(
            cidade,
            edit_url=reverse("cadastros:cidade_update", args=[cidade.pk]),
            delete_url=reverse("cadastros:cidade_delete", args=[cidade.pk]),
        )
        for cidade in cidades
    ]
    return _render_listagem(
        request,
        "cadastros/cidades/index.html",
        {
            "page_title": "Cidades",
            "page_section": "Cadastros",
            "page_description": "Cidades de referencia para destinos, roteiros e documentos.",
            "cards": cards,
            "q": q,
        },
    )


def cidade_create(request):
    form = CidadeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_cidade(form)
        messages.success(request, "Cidade criada com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/form.html",
        {
            "page_title": "Nova cidade",
            "page_section": "Cadastros",
            "page_description": "Cadastre uma cidade de referencia para os fluxos.",
            "form": form,
            "submit_label": "Criar cidade",
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def cidade_update(request, pk):
    cidade = get_cidade_by_id(pk)
    form = CidadeForm(request.POST or None, instance=cidade)
    if request.method == "POST" and form.is_valid():
        atualizar_cidade(cidade, form)
        messages.success(request, "Cidade atualizada com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/form.html",
        {
            "page_title": "Editar cidade",
            "page_section": "Cadastros",
            "page_description": "Atualize os dados da cidade.",
            "form": form,
            "submit_label": "Salvar cidade",
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def cidade_delete(request, pk):
    cidade = get_cidade_by_id(pk)
    if request.method == "POST":
        try:
            excluir_cidade(cidade)
        except CadastroVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            )
            return redirect("cadastros:cidades_index")
        messages.success(request, "Cidade excluída com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/confirm_delete.html",
        {
            "page_title": "Excluir cidade",
            "page_section": "Cadastros",
            "page_description": "Esta acao exclui o cadastro quando nao houver vinculos impeditivos.",
            "object": cidade,
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def servidores_index(request):
    servidores = listar_servidores()
    cards = [apresentar_servidor_card(servidor) for servidor in servidores]
    return _render_listagem(
        request,
        "cadastros/servidores/index.html",
        {
            "page_title": "Servidores",
            "page_section": "Cadastros",
            "page_description": "Servidores que poderao participar dos documentos de viagem.",
            "cards": cards,
        },
    )


def motoristas_index(request):
    motoristas = listar_motoristas()
    cards = [apresentar_motorista_card(motorista) for motorista in motoristas]
    return _render_listagem(
        request,
        "cadastros/motoristas/index.html",
        {
            "page_title": "Motoristas",
            "page_section": "Cadastros",
            "page_description": "Servidores habilitados para conduzir viaturas.",
            "cards": cards,
        },
    )


def viaturas_index(request):
    viaturas = listar_viaturas()
    cards = [apresentar_viatura_card(viatura) for viatura in viaturas]
    return _render_listagem(
        request,
        "cadastros/viaturas/index.html",
        {
            "page_title": "Viaturas",
            "page_section": "Cadastros",
            "page_description": "Veiculos usados em deslocamentos e ordens de servico.",
            "cards": cards,
        },
    )
