from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from .forms import CidadeForm
from .forms import MotoristaForm
from .forms import ServidorForm
from .forms import UnidadeForm
from .forms import ViaturaForm
from .presenters import apresentar_cidade_card
from .presenters import apresentar_motorista_card
from .presenters import apresentar_servidor_card
from .presenters import apresentar_unidade_card
from .presenters import apresentar_viatura_card
from .selectors import get_cidade_by_id
from .selectors import get_motorista_by_id
from .selectors import get_servidor_by_id
from .selectors import get_unidade_by_id
from .selectors import get_viatura_by_id
from .selectors import listar_cidades
from .selectors import listar_motoristas
from .selectors import listar_servidores
from .selectors import listar_unidades
from .selectors import listar_viaturas
from .services import atualizar_cidade
from .services import atualizar_motorista
from .services import atualizar_servidor
from .services import atualizar_unidade
from .services import atualizar_viatura
from .services import CadastroVinculadoError
from .services import criar_cidade
from .services import criar_motorista
from .services import criar_servidor
from .services import criar_unidade
from .services import criar_viatura
from .services import excluir_cidade
from .services import excluir_motorista
from .services import excluir_servidor
from .services import excluir_unidade
from .services import excluir_viatura


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
    q = request.GET.get("q", "").strip()
    servidores = listar_servidores(q=q)
    cards = [
        apresentar_servidor_card(
            servidor,
            edit_url=reverse("cadastros:servidor_update", args=[servidor.pk]),
            delete_url=reverse("cadastros:servidor_delete", args=[servidor.pk]),
        )
        for servidor in servidores
    ]
    return _render_listagem(
        request,
        "cadastros/servidores/index.html",
        {
            "page_title": "Servidores",
            "page_section": "Cadastros",
            "page_description": "Servidores que poderao participar dos documentos de viagem.",
            "cards": cards,
            "q": q,
        },
    )


def servidor_create(request):
    form = ServidorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_servidor(form)
        messages.success(request, "Servidor criado com sucesso.")
        return redirect("cadastros:servidores_index")
    return render(
        request,
        "cadastros/servidores/form.html",
        {
            "page_title": "Novo servidor",
            "page_section": "Cadastros",
            "page_description": "Cadastre um servidor para uso nos fluxos documentais.",
            "form": form,
            "submit_label": "Criar servidor",
            "back_url": reverse("cadastros:servidores_index"),
        },
    )


def servidor_update(request, pk):
    servidor = get_servidor_by_id(pk)
    form = ServidorForm(request.POST or None, instance=servidor)
    if request.method == "POST" and form.is_valid():
        atualizar_servidor(servidor, form)
        messages.success(request, "Servidor atualizado com sucesso.")
        return redirect("cadastros:servidores_index")
    return render(
        request,
        "cadastros/servidores/form.html",
        {
            "page_title": "Editar servidor",
            "page_section": "Cadastros",
            "page_description": "Atualize os dados do servidor.",
            "form": form,
            "submit_label": "Salvar servidor",
            "back_url": reverse("cadastros:servidores_index"),
        },
    )


def servidor_delete(request, pk):
    servidor = get_servidor_by_id(pk)
    if request.method == "POST":
        try:
            excluir_servidor(servidor)
        except CadastroVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            )
            return redirect("cadastros:servidores_index")
        messages.success(request, "Servidor excluído com sucesso.")
        return redirect("cadastros:servidores_index")
    return render(
        request,
        "cadastros/servidores/confirm_delete.html",
        {
            "page_title": "Excluir servidor",
            "page_section": "Cadastros",
            "page_description": "Confirme a exclusao fisica do cadastro.",
            "object": servidor,
            "back_url": reverse("cadastros:servidores_index"),
        },
    )


def motoristas_index(request):
    q = request.GET.get("q", "").strip()
    motoristas = listar_motoristas(q=q)
    cards = [
        apresentar_motorista_card(
            motorista,
            edit_url=reverse("cadastros:motorista_update", args=[motorista.pk]),
            delete_url=reverse("cadastros:motorista_delete", args=[motorista.pk]),
        )
        for motorista in motoristas
    ]
    return _render_listagem(
        request,
        "cadastros/motoristas/index.html",
        {
            "page_title": "Motoristas",
            "page_section": "Cadastros",
            "page_description": "Servidores habilitados para conduzir viaturas.",
            "cards": cards,
            "q": q,
        },
    )


def motorista_create(request):
    form = MotoristaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_motorista(form)
        messages.success(request, "Motorista criado com sucesso.")
        return redirect("cadastros:motoristas_index")
    return render(
        request,
        "cadastros/motoristas/form.html",
        {
            "page_title": "Novo motorista",
            "page_section": "Cadastros",
            "page_description": "Vincule um servidor como motorista habilitado.",
            "form": form,
            "submit_label": "Criar motorista",
            "back_url": reverse("cadastros:motoristas_index"),
        },
    )


def motorista_update(request, pk):
    motorista = get_motorista_by_id(pk)
    form = MotoristaForm(request.POST or None, instance=motorista)
    if request.method == "POST" and form.is_valid():
        atualizar_motorista(motorista, form)
        messages.success(request, "Motorista atualizado com sucesso.")
        return redirect("cadastros:motoristas_index")
    return render(
        request,
        "cadastros/motoristas/form.html",
        {
            "page_title": "Editar motorista",
            "page_section": "Cadastros",
            "page_description": "Atualize os dados do motorista.",
            "form": form,
            "submit_label": "Salvar motorista",
            "back_url": reverse("cadastros:motoristas_index"),
        },
    )


def motorista_delete(request, pk):
    motorista = get_motorista_by_id(pk)
    if request.method == "POST":
        try:
            excluir_motorista(motorista)
        except CadastroVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            )
            return redirect("cadastros:motoristas_index")
        messages.success(request, "Motorista excluído com sucesso.")
        return redirect("cadastros:motoristas_index")
    return render(
        request,
        "cadastros/motoristas/confirm_delete.html",
        {
            "page_title": "Excluir motorista",
            "page_section": "Cadastros",
            "page_description": "Confirme a exclusao fisica do cadastro.",
            "object": motorista,
            "back_url": reverse("cadastros:motoristas_index"),
        },
    )


def viaturas_index(request):
    q = request.GET.get("q", "").strip()
    viaturas = listar_viaturas(q=q)
    cards = [
        apresentar_viatura_card(
            viatura,
            edit_url=reverse("cadastros:viatura_update", args=[viatura.pk]),
            delete_url=reverse("cadastros:viatura_delete", args=[viatura.pk]),
        )
        for viatura in viaturas
    ]
    return _render_listagem(
        request,
        "cadastros/viaturas/index.html",
        {
            "page_title": "Viaturas",
            "page_section": "Cadastros",
            "page_description": "Veiculos usados em deslocamentos e ordens de servico.",
            "cards": cards,
            "q": q,
        },
    )


def viatura_create(request):
    form = ViaturaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_viatura(form)
        messages.success(request, "Viatura criada com sucesso.")
        return redirect("cadastros:viaturas_index")
    return render(
        request,
        "cadastros/viaturas/form.html",
        {
            "page_title": "Nova viatura",
            "page_section": "Cadastros",
            "page_description": "Cadastre um veiculo para deslocamentos e ordens de servico.",
            "form": form,
            "submit_label": "Criar viatura",
            "back_url": reverse("cadastros:viaturas_index"),
        },
    )


def viatura_update(request, pk):
    viatura = get_viatura_by_id(pk)
    form = ViaturaForm(request.POST or None, instance=viatura)
    if request.method == "POST" and form.is_valid():
        atualizar_viatura(viatura, form)
        messages.success(request, "Viatura atualizada com sucesso.")
        return redirect("cadastros:viaturas_index")
    return render(
        request,
        "cadastros/viaturas/form.html",
        {
            "page_title": "Editar viatura",
            "page_section": "Cadastros",
            "page_description": "Atualize os dados da viatura.",
            "form": form,
            "submit_label": "Salvar viatura",
            "back_url": reverse("cadastros:viaturas_index"),
        },
    )


def viatura_delete(request, pk):
    viatura = get_viatura_by_id(pk)
    if request.method == "POST":
        try:
            excluir_viatura(viatura)
        except CadastroVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
            )
            return redirect("cadastros:viaturas_index")
        messages.success(request, "Viatura excluída com sucesso.")
        return redirect("cadastros:viaturas_index")
    return render(
        request,
        "cadastros/viaturas/confirm_delete.html",
        {
            "page_title": "Excluir viatura",
            "page_section": "Cadastros",
            "page_description": "Confirme a exclusao fisica do cadastro.",
            "object": viatura,
            "back_url": reverse("cadastros:viaturas_index"),
        },
    )
