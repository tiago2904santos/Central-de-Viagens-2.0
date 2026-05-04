from django.shortcuts import render

from .presenters import apresentar_cidade_card
from .presenters import apresentar_motorista_card
from .presenters import apresentar_servidor_card
from .presenters import apresentar_unidade_card
from .presenters import apresentar_viatura_card
from .selectors import listar_cidades
from .selectors import listar_motoristas
from .selectors import listar_servidores
from .selectors import listar_unidades
from .selectors import listar_viaturas


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
    unidades = listar_unidades()
    cards = [apresentar_unidade_card(unidade) for unidade in unidades]
    return _render_listagem(
        request,
        "cadastros/unidades/index.html",
        {
            "page_title": "Unidades",
            "page_section": "Cadastros",
            "page_description": "Unidades administrativas reutilizadas nos fluxos documentais.",
            "cards": cards,
        },
    )


def cidades_index(request):
    cidades = listar_cidades()
    cards = [apresentar_cidade_card(cidade) for cidade in cidades]
    return _render_listagem(
        request,
        "cadastros/cidades/index.html",
        {
            "page_title": "Cidades",
            "page_section": "Cadastros",
            "page_description": "Cidades de referencia para destinos, roteiros e documentos.",
            "cards": cards,
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
