from django.shortcuts import render
from django.urls import reverse

from cadastros.models import Cargo, CombustivelVeiculo, ConfiguracaoSistema, UnidadeLotacao, Viajante, Veiculo
from eventos.models import ModeloJustificativa, ModeloMotivoViagem, TipoDemandaEvento


def cadastros_hub(request):
    cards = [
        {
            'label': 'Viajantes',
            'count': Viajante.objects.count(),
            'description': 'Servidores utilizados em eventos, oficios, termos e assinaturas.',
            'url': reverse('cadastros:viajante-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Veiculos',
            'count': Veiculo.objects.count(),
            'description': 'Frota utilizada nos deslocamentos e no wizard do oficio.',
            'url': reverse('cadastros:veiculo-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Cargos',
            'count': Cargo.objects.count(),
            'description': 'Cargos base para classificacao e assinaturas dos viajantes.',
            'url': reverse('cadastros:cargo-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Unidades',
            'count': UnidadeLotacao.objects.count(),
            'description': 'Unidades de lotacao vinculadas aos viajantes cadastrados.',
            'url': reverse('cadastros:unidade-lotacao-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Combustiveis',
            'count': CombustivelVeiculo.objects.count(),
            'description': 'Base de combustiveis para os cadastros de veiculos.',
            'url': reverse('cadastros:combustivel-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Tipos de demanda',
            'count': TipoDemandaEvento.objects.count(),
            'description': 'Classificacoes usadas na etapa 1 do evento.',
            'url': reverse('eventos:tipos-demanda-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Modelos de motivo',
            'count': ModeloMotivoViagem.objects.count(),
            'description': 'Modelos reutilizaveis para o motivo do oficio.',
            'url': reverse('eventos:modelos-motivo-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Modelos de justificativa',
            'count': ModeloJustificativa.objects.count(),
            'description': 'Textos base para justificativas vinculadas aos oficios.',
            'url': reverse('eventos:modelos-justificativa-lista'),
            'action': 'Abrir lista',
        },
        {
            'label': 'Configuracoes',
            'count': ConfiguracaoSistema.objects.count() or 1,
            'description': 'Parametros gerais, assinaturas ativas e dados institucionais.',
            'url': reverse('cadastros:configuracoes'),
            'action': 'Abrir configuracoes',
        },
    ]
    return render(
        request,
        'cadastros/hub.html',
        {
            'cards': cards,
        },
    )
