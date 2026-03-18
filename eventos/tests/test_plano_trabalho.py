# -*- coding: utf-8 -*-
"""Testes do módulo de Plano de Trabalho: domínio (atividades/metas), contexto e termo sem assinatura."""
from datetime import date, datetime, time
from decimal import Decimal

from django.test import TestCase

from cadastros.models import Cargo, Cidade, ConfiguracaoSistema, Estado, Viajante
from eventos.models import (
    CoordenadorOperacional,
    EfetivoPlanoTrabalho,
    Evento,
    Oficio,
    PlanoTrabalho,
    SolicitantePlanoTrabalho,
)
from eventos.services.diarias import PeriodMarker, calculate_periodized_diarias
from eventos.services.documentos.context import build_plano_trabalho_document_context
from eventos.services.plano_trabalho_domain import (
    ATIVIDADES_CATALOGO,
    CODIGO_UNIDADE_MOVEL,
    build_atividades_formatada,
    build_metas_formatada,
    get_unidade_movel_text,
    has_unidade_movel,
)


class PlanoTrabalhoDomainTest(TestCase):
    """Atividades, metas e unidade móvel."""

    def test_metas_formatada_vazio_quando_sem_codigos(self):
        self.assertEqual(build_metas_formatada(''), '')
        self.assertEqual(build_metas_formatada(None), '')

    def test_metas_formatada_gera_texto_na_ordem_oficial(self):
        codigos = 'CIN,BO'
        out = build_metas_formatada(codigos)
        self.assertIn('Ampliar o acesso ao documento oficial', out)
        self.assertIn('Possibilitar o atendimento imediato', out)
        self.assertTrue(out.index('Ampliar') < out.index('Possibilitar'))

    def test_atividades_formatada_gera_lista_com_bullets(self):
        out = build_atividades_formatada('CIN,NOC')
        self.assertIn('•', out)
        self.assertIn('Confecção da Carteira', out)
        self.assertIn('Núcleo de Operações com Cães', out)

    def test_unidade_movel_vazio_quando_atividade_nao_selecionada(self):
        self.assertEqual(get_unidade_movel_text('CIN,BO'), '')
        self.assertFalse(has_unidade_movel('CIN'))

    def test_unidade_movel_preenchido_quando_atividade_selecionada(self):
        self.assertTrue(has_unidade_movel('UNIDADE_MOVEL'))
        self.assertTrue(has_unidade_movel('CIN,UNIDADE_MOVEL'))
        text = get_unidade_movel_text('UNIDADE_MOVEL')
        self.assertIn('Unidade móvel da PCPR', text)
        self.assertIn('atendimento e confecção de documentos', text)

    def test_catalogo_tem_11_atividades(self):
        self.assertEqual(len(ATIVIDADES_CATALOGO), 11)
        codigos = [a['codigo'] for a in ATIVIDADES_CATALOGO]
        self.assertIn(CODIGO_UNIDADE_MOVEL, codigos)


class PlanoTrabalhoContextTest(TestCase):
    """Contexto do documento PT: placeholders, diárias, coordenacao."""

    def setUp(self):
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado)
        self.cargo = Cargo.objects.create(nome='ANALISTA', is_padrao=True)
        self.evento = Evento.objects.create(
            titulo='Evento PT',
            data_inicio=date(2026, 3, 15),
            data_fim=date(2026, 3, 18),
        )
        self.oficio = Oficio.objects.create(
            evento=self.evento,
            motivo='Motivo teste',
            estado_sede=self.estado,
            cidade_sede=self.cidade,
            retorno_chegada_data=date(2026, 3, 18),
            retorno_chegada_hora=time(11, 30),
        )

    def test_build_plano_trabalho_context_retorna_chaves_esperadas(self):
        ctx = build_plano_trabalho_document_context(self.oficio)
        for key in (
            'numero_plano_trabalho', 'destino', 'solicitante', 'metas_formatada',
            'atividades_formatada', 'dias_evento_extenso', 'locais_formatado',
            'horario_atendimento', 'quantidade_de_servidores', 'unidade_movel',
            'valor_total', 'valor_total_por_extenso', 'diarias_x', 'valor_unitario',
            'coordenacao_formatada', 'recursos_formatado', 'data_extenso',
        ):
            self.assertIn(key, ctx, msg=f'Falta chave {key}')

    def test_quantidade_de_servidores_vem_do_efetivo_quando_existe(self):
        EfetivoPlanoTrabalho.objects.create(evento=self.evento, cargo=self.cargo, quantidade=5)
        EfetivoPlanoTrabalho.objects.create(
            evento=self.evento,
            cargo=Cargo.objects.create(nome='PAPILOSCOPISTA', is_padrao=False),
            quantidade=3,
        )
        ctx = build_plano_trabalho_document_context(self.oficio)
        self.assertIn('8 servidor', ctx['quantidade_de_servidores'])

    def test_solicitante_outros_no_contexto(self):
        PlanoTrabalho.objects.create(
            evento=self.evento,
            oficio=self.oficio,
            solicitante_outros='Secretaria Municipal X',
            objetivo='Objetivo',
        )
        ctx = build_plano_trabalho_document_context(self.oficio)
        self.assertEqual(ctx['solicitante'], 'Secretaria Municipal X')

    def test_coordenacao_operacional_no_contexto(self):
        coord = CoordenadorOperacional.objects.create(
            nome='João Silva',
            cargo='Delegado',
            cidade='Curitiba',
            ativo=True,
        )
        PlanoTrabalho.objects.create(
            evento=self.evento,
            oficio=self.oficio,
            coordenador_operacional=coord,
            objetivo='Objetivo',
        )
        ctx = build_plano_trabalho_document_context(self.oficio)
        self.assertIn('Coordenador Operacional', ctx['coordenacao_formatada'])
        self.assertIn('João Silva', ctx['coordenacao_formatada'])
        self.assertIn('Delegado', ctx['coordenacao_formatada'])


class TermoNaoExigeAssinaturaTest(TestCase):
    """Termo de autorização não deve exigir chefia/assinatura configurada."""

    def test_termo_context_assinaturas_vazio(self):
        from eventos.services.documentos.context import build_termo_autorizacao_document_context
        estado = Estado.objects.create(nome='Paraná', sigla='PR')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado)
        evento = Evento.objects.create(
            titulo='E',
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 1, 2),
        )
        oficio = Oficio.objects.create(
            evento=evento,
            motivo='M',
            estado_sede=estado,
            cidade_sede=cidade,
        )
        ctx = build_termo_autorizacao_document_context(oficio)
        self.assertEqual(ctx.get('assinaturas'), [], 'Termo não deve exigir assinaturas configuradas')
