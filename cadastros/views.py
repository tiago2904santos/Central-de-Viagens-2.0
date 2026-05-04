from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse

from .forms import CargoForm
from .forms import CidadeForm
from .forms import CombustivelForm
from .forms import ServidorForm
from .forms import UnidadeForm
from .forms import ViaturaForm
from .presenters import apresentar_cargo_card
from .presenters import apresentar_cidade_card
from .presenters import apresentar_combustivel_card
from .presenters import apresentar_servidor_card
from .presenters import apresentar_unidade_card
from .presenters import apresentar_viatura_card
from .selectors import get_cargo_by_id
from .selectors import get_cidade_by_id
from .selectors import get_combustivel_by_id
from .selectors import get_servidor_by_id
from .selectors import get_unidade_by_id
from .selectors import get_viatura_by_id
from .selectors import listar_cargos
from .selectors import listar_cidades
from .selectors import listar_combustiveis
from .selectors import listar_servidores
from .selectors import listar_unidades
from .selectors import listar_viaturas
from .services import atualizar_cargo
from .services import atualizar_cidade
from .services import atualizar_combustivel
from .services import atualizar_servidor
from .services import atualizar_unidade
from .services import atualizar_viatura
from .services import CadastroVinculadoError
from .services import criar_cargo
from .services import criar_cidade
from .services import criar_combustivel
from .services import criar_servidor
from .services import criar_unidade
from .services import criar_viatura
from .services import excluir_cargo
from .services import excluir_cidade
from .services import excluir_combustivel
from .services import excluir_servidor
from .services import excluir_unidade
from .services import excluir_viatura


def _render_listagem(request, template_name, context):
    return render(request, template_name, context)


def _vinculo_error(request):
    messages.error(
        request,
        "Não foi possível excluir este cadastro porque ele está vinculado a outros registros.",
    )


def index(request):
    return render(
        request,
        "cadastros/index.html",
        {
            "page_title": "Cadastros",
            "page_section": "Dados-base",
            "page_description": "Base para cidades, unidades, cargos, combustíveis, servidores e viaturas.",
            "modules": [
                {"title": "Unidades", "description": "Estruturas administrativas.", "href": "unidades/"},
                {"title": "Cidades", "description": "Cidades e UFs de referência.", "href": "cidades/"},
                {"title": "Cargos", "description": "Cargos vinculados a servidores.", "href": "cargos/"},
                {"title": "Combustíveis", "description": "Tipos de combustível para viaturas.", "href": "combustiveis/"},
                {"title": "Servidores", "description": "Pessoas vinculadas aos fluxos.", "href": "servidores/"},
                {"title": "Viaturas", "description": "Veículos operacionais cadastrados.", "href": "viaturas/"},
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
            "page_description": "Unidades administrativas reutilizadas nos fluxos.",
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
            "page_description": "Cadastre uma unidade administrativa reutilizável.",
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
            "page_description": "Atualize os dados da unidade.",
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
            _vinculo_error(request)
            return redirect("cadastros:unidades_index")
        messages.success(request, "Unidade excluída com sucesso.")
        return redirect("cadastros:unidades_index")
    return render(
        request,
        "cadastros/unidades/confirm_delete.html",
        {
            "page_title": "Excluir unidade",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
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
            "page_description": "Cidades de referência para os fluxos.",
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
            "page_description": "Cadastre uma cidade de referência.",
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
            _vinculo_error(request)
            return redirect("cadastros:cidades_index")
        messages.success(request, "Cidade excluída com sucesso.")
        return redirect("cadastros:cidades_index")
    return render(
        request,
        "cadastros/cidades/confirm_delete.html",
        {
            "page_title": "Excluir cidade",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": cidade,
            "back_url": reverse("cadastros:cidades_index"),
        },
    )


def cargos_index(request):
    q = request.GET.get("q", "").strip()
    cargos = listar_cargos(q=q)
    cards = [
        apresentar_cargo_card(
            cargo,
            edit_url=reverse("cadastros:cargo_update", args=[cargo.pk]),
            delete_url=reverse("cadastros:cargo_delete", args=[cargo.pk]),
        )
        for cargo in cargos
    ]
    return _render_listagem(
        request,
        "cadastros/cargos/index.html",
        {
            "page_title": "Cargos",
            "page_description": "Cadastre os cargos utilizados em servidores.",
            "cards": cards,
            "q": q,
        },
    )


def cargo_create(request):
    form = CargoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_cargo(form)
        messages.success(request, "Cargo criado com sucesso.")
        return redirect("cadastros:cargos_index")
    return render(
        request,
        "cadastros/cargos/form.html",
        {
            "page_title": "Novo cargo",
            "page_description": "Cadastre um cargo para seleção em servidores.",
            "form": form,
            "submit_label": "Criar cargo",
            "back_url": reverse("cadastros:cargos_index"),
        },
    )


def cargo_update(request, pk):
    cargo = get_cargo_by_id(pk)
    form = CargoForm(request.POST or None, instance=cargo)
    if request.method == "POST" and form.is_valid():
        atualizar_cargo(cargo, form)
        messages.success(request, "Cargo atualizado com sucesso.")
        return redirect("cadastros:cargos_index")
    return render(
        request,
        "cadastros/cargos/form.html",
        {
            "page_title": "Editar cargo",
            "page_description": "Atualize os dados do cargo.",
            "form": form,
            "submit_label": "Salvar cargo",
            "back_url": reverse("cadastros:cargos_index"),
        },
    )


def cargo_delete(request, pk):
    cargo = get_cargo_by_id(pk)
    if request.method == "POST":
        try:
            excluir_cargo(cargo)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:cargos_index")
        messages.success(request, "Cargo excluído com sucesso.")
        return redirect("cadastros:cargos_index")
    return render(
        request,
        "cadastros/cargos/confirm_delete.html",
        {
            "page_title": "Excluir cargo",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": cargo,
            "back_url": reverse("cadastros:cargos_index"),
        },
    )


def combustiveis_index(request):
    q = request.GET.get("q", "").strip()
    combustiveis = listar_combustiveis(q=q)
    cards = [
        apresentar_combustivel_card(
            combustivel,
            edit_url=reverse("cadastros:combustivel_update", args=[combustivel.pk]),
            delete_url=reverse("cadastros:combustivel_delete", args=[combustivel.pk]),
        )
        for combustivel in combustiveis
    ]
    return _render_listagem(
        request,
        "cadastros/combustiveis/index.html",
        {
            "page_title": "Combustíveis",
            "page_description": "Cadastre os combustíveis disponíveis para viaturas.",
            "cards": cards,
            "q": q,
        },
    )


def combustivel_create(request):
    form = CombustivelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_combustivel(form)
        messages.success(request, "Combustível criado com sucesso.")
        return redirect("cadastros:combustiveis_index")
    return render(
        request,
        "cadastros/combustiveis/form.html",
        {
            "page_title": "Novo combustível",
            "page_description": "Cadastre um combustível para seleção em viaturas.",
            "form": form,
            "submit_label": "Criar combustível",
            "back_url": reverse("cadastros:combustiveis_index"),
        },
    )


def combustivel_update(request, pk):
    combustivel = get_combustivel_by_id(pk)
    form = CombustivelForm(request.POST or None, instance=combustivel)
    if request.method == "POST" and form.is_valid():
        atualizar_combustivel(combustivel, form)
        messages.success(request, "Combustível atualizado com sucesso.")
        return redirect("cadastros:combustiveis_index")
    return render(
        request,
        "cadastros/combustiveis/form.html",
        {
            "page_title": "Editar combustível",
            "page_description": "Atualize os dados do combustível.",
            "form": form,
            "submit_label": "Salvar combustível",
            "back_url": reverse("cadastros:combustiveis_index"),
        },
    )


def combustivel_delete(request, pk):
    combustivel = get_combustivel_by_id(pk)
    if request.method == "POST":
        try:
            excluir_combustivel(combustivel)
        except CadastroVinculadoError:
            _vinculo_error(request)
            return redirect("cadastros:combustiveis_index")
        messages.success(request, "Combustível excluído com sucesso.")
        return redirect("cadastros:combustiveis_index")
    return render(
        request,
        "cadastros/combustiveis/confirm_delete.html",
        {
            "page_title": "Excluir combustível",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": combustivel,
            "back_url": reverse("cadastros:combustiveis_index"),
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
            "page_description": "Servidores vinculados aos fluxos documentais.",
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
            "page_description": "Cadastre servidor com cargo, CPF e RG opcional.",
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
            _vinculo_error(request)
            return redirect("cadastros:servidores_index")
        messages.success(request, "Servidor excluído com sucesso.")
        return redirect("cadastros:servidores_index")
    return render(
        request,
        "cadastros/servidores/confirm_delete.html",
        {
            "page_title": "Excluir servidor",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": servidor,
            "back_url": reverse("cadastros:servidores_index"),
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
            "page_description": "Viaturas cadastradas para uso operacional.",
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
            "page_description": "Cadastre placa, modelo, combustível e tipo.",
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
            _vinculo_error(request)
            return redirect("cadastros:viaturas_index")
        messages.success(request, "Viatura excluída com sucesso.")
        return redirect("cadastros:viaturas_index")
    return render(
        request,
        "cadastros/viaturas/confirm_delete.html",
        {
            "page_title": "Excluir viatura",
            "page_description": "Esta ação excluirá o cadastro. Se houver vínculos com outros registros, a exclusão será bloqueada.",
            "object": viatura,
            "back_url": reverse("cadastros:viaturas_index"),
        },
    )
