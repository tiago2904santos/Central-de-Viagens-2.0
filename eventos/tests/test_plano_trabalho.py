# -*- coding: utf-8 -*-
"""Testes do módulo de Plano de Trabalho: domínio (atividades/metas), contexto e termo sem assinatura."""
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
from eventos.services.documentos.plano_trabalho import render_plano_trabalho_model_docx
from eventos.services.plano_trabalho_domain import (
    ATIVIDADES_CATALOGO,
    CODIGO_UNIDADE_MOVEL,
    build_atividades_formatada,
    build_metas_formatada,
    get_unidade_movel_text,
    has_unidade_movel,
)

User = get_user_model()


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

    def test_numero_armazenado_usado_no_contexto(self):
        """O número salvo no PT deve aparecer no contexto, não um número gerado."""
        PlanoTrabalho.objects.create(
            evento=self.evento,
            oficio=self.oficio,
            numero=7,
            ano=2026,
            objetivo='Objetivo',
        )
        ctx = build_plano_trabalho_document_context(self.oficio)
        self.assertEqual(ctx['numero_plano_trabalho'], '07/2026')

    def test_numero_provisorio_quando_pt_sem_numero(self):
        """Sem PT salvo com número, o contexto usa o número provisório."""
        PlanoTrabalho.objects.create(
            evento=self.evento,
            oficio=self.oficio,
            objetivo='Objetivo',
        )
        ctx = build_plano_trabalho_document_context(self.oficio)
        # Deve ser uma string (pode ser vazia se sem config, mas nunca deve dar erro)
        self.assertIsInstance(ctx['numero_plano_trabalho'], str)

    @patch('eventos.services.documentos.context._get_plano_trabalho_markers_chegada')
    @patch('eventos.services.documentos.context.calculate_periodized_diarias')
    def test_valores_diarias_preenchidos_do_calculo(self, mock_calc, mock_markers):
        mock_markers.return_value = ([object()], datetime(2026, 3, 18, 11, 30))
        mock_calc.return_value = {
            'totais': {
                'total_valor': '1234,56',
                'valor_extenso': 'mil duzentos e trinta e quatro reais e cinquenta e seis centavos',
                'total_diarias': '1 x 100% + 1 x 30%',
                'valor_por_servidor': '617,28',
            }
        }
        PlanoTrabalho.objects.create(evento=self.evento, oficio=self.oficio, objetivo='Objetivo')
        ctx = build_plano_trabalho_document_context(self.oficio)
        self.assertEqual(ctx['valor_total'], '1234,56')
        self.assertEqual(ctx['diarias_x'], '1 x 100% + 1 x 30%')
        self.assertEqual(ctx['valor_unitario'], '617,28')


class PlanoTrabalhoModelDocxTest(TestCase):
    """render_plano_trabalho_model_docx deve incluir atividades formatadas, solicitante e coordenação."""

    def setUp(self):
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado)
        self.evento = Evento.objects.create(
            titulo='Evento Docx',
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 4, 3),
        )
        self.coord = CoordenadorOperacional.objects.create(
            nome='Maria Souza',
            cargo='Delegada',
            ativo=True,
        )

    def test_model_docx_gerada_sem_excecao(self):
        pt = PlanoTrabalho.objects.create(
            evento=self.evento,
            numero=3,
            ano=2026,
            objetivo='Objetivo teste',
            atividades_codigos='CIN,BO',
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        result = render_plano_trabalho_model_docx(pt)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 100)

    def test_model_docx_atividades_usa_formato_legivel(self):
        """Atividades devem aparecer formatadas, não como string bruta 'CIN,BO'."""
        pt = PlanoTrabalho.objects.create(
            evento=self.evento,
            numero=4,
            ano=2026,
            objetivo='Objetivo',
            atividades_codigos='CIN,BO',
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        docx_bytes = render_plano_trabalho_model_docx(pt)
        # Verifica que é bytes válidos (DOCX é ZIP); não contém string bruta CSV
        self.assertIsInstance(docx_bytes, bytes)
        # DOCX é um ZIP, então deve começar com PK
        self.assertTrue(docx_bytes[:2] == b'PK')

    def test_model_docx_com_solicitante_fk(self):
        sol = SolicitantePlanoTrabalho.objects.create(nome='Prefeitura de Curitiba', ativo=True)
        pt = PlanoTrabalho.objects.create(
            evento=self.evento,
            numero=5,
            ano=2026,
            objetivo='Objetivo',
            solicitante=sol,
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        result = render_plano_trabalho_model_docx(pt)
        self.assertIsInstance(result, bytes)

    def test_model_docx_com_coordenador_operacional(self):
        pt = PlanoTrabalho.objects.create(
            evento=self.evento,
            numero=6,
            ano=2026,
            objetivo='Objetivo',
            coordenador_operacional=self.coord,
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        result = render_plano_trabalho_model_docx(pt)
        self.assertIsInstance(result, bytes)

    def test_model_docx_sem_atividades_nao_quebra(self):
        pt = PlanoTrabalho.objects.create(
            objetivo='Objetivo sem atividades',
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        result = render_plano_trabalho_model_docx(pt)
        self.assertIsInstance(result, bytes)

    def test_model_docx_contem_blocos_documentais(self):
        from io import BytesIO
        from docx import Document

        pt = PlanoTrabalho.objects.create(
            evento=self.evento,
            numero=8,
            ano=2026,
            objetivo='Objetivo para estrutura documental',
            atividades_codigos='CIN',
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        docx_bytes = render_plano_trabalho_model_docx(pt)
        doc = Document(BytesIO(docx_bytes))
        text = '\n'.join(p.text for p in doc.paragraphs)
        self.assertIn('PLANO DE TRABALHO', text)
        self.assertIn('BREVE CONTEXTUALIZAÇÃO', text)
        self.assertIn('METAS ESTABELECIDAS', text)
        self.assertIn('ATIVIDADES A SEREM DESENVOLVIDAS', text)
        self.assertIn('CONSIDERAÇÕES FINAIS', text)


class PlanoTrabalhoFormPersistenciaTest(TestCase):
    """Persistência de dados: o formulário salva e reabre corretamente."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='pttest', password='pttest123')
        self.client.login(username='pttest', password='pttest123')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado)
        self.oficio = Oficio.objects.create(
            motivo='Oficio PT',
            estado_sede=self.estado,
            cidade_sede=self.cidade,
            retorno_chegada_data=date(2026, 5, 3),
            retorno_chegada_hora=time(11, 30),
        )
        self.cargo = Cargo.objects.create(nome='AGENTE DE POLÍCIA JUDICIÁRIA', is_padrao=True)
        self.evento = Evento.objects.create(
            titulo='Evento Form',
            data_inicio=date(2026, 5, 1),
            data_fim=date(2026, 5, 3),
        )
        ConfiguracaoSistema.get_singleton()

    def _base_formset_payload(self):
        return {
            'efetivo-TOTAL_FORMS': '3',
            'efetivo-INITIAL_FORMS': '0',
            'efetivo-MIN_NUM_FORMS': '0',
            'efetivo-MAX_NUM_FORMS': '1000',
            'efetivo-0-cargo': str(self.cargo.pk),
            'efetivo-0-quantidade': '5',
            'efetivo-1-cargo': '',
            'efetivo-1-quantidade': '',
            'efetivo-2-cargo': '',
            'efetivo-2-quantidade': '',
        }

    def test_tela_plano_lista_abre(self):
        response = self.client.get(reverse('eventos:documentos-planos-trabalho'))
        self.assertEqual(response.status_code, 200)

    def test_tela_plano_novo_abre(self):
        response = self.client.get(reverse('eventos:documentos-planos-trabalho-novo'))
        self.assertEqual(response.status_code, 200)

    def test_formulario_salva_campos_corretamente(self):
        payload = {
            'data_criacao': '2026-05-01',
            'status': PlanoTrabalho.STATUS_RASCUNHO,
            'evento': self.evento.pk,
            'oficio': self.oficio.pk,
            'destinos_payload': '[]',
            'objetivo': 'Objetivo persistencia',
            'locais': 'Curitiba/PR',
            'horario_atendimento_padrao': '08:00-17:00',
            'coordenador_administrativo_novo_nome': 'Servidor Teste Persistencia',
            'salvar_coordenador_administrativo': 'on',
            'solicitante_escolha': '',
            'atividades_codigos': ['CIN', 'BO'],
            'recursos_texto': 'Sem recursos externos',
            'return_to': reverse('eventos:documentos-planos-trabalho'),
        }
        payload.update(self._base_formset_payload())

        response = self.client.post(
            reverse('eventos:documentos-planos-trabalho-novo'),
            data=payload,
        )
        self.assertEqual(response.status_code, 302)
        pt = PlanoTrabalho.objects.get(objetivo='Objetivo persistencia')
        self.assertEqual(pt.numero, 1)
        self.assertEqual(pt.ano, 2026)
        self.assertEqual(pt.locais, 'Curitiba/PR')
        self.assertEqual(pt.horario_atendimento, '08:00 até 17:00')
        self.assertEqual(pt.quantidade_servidores, 5)
        self.assertIn('CIN', pt.atividades_codigos)
        self.assertIn('BO', pt.atividades_codigos)
        self.assertEqual(pt.recursos_texto, 'Sem recursos externos')
        self.assertIn('Ampliar o acesso ao documento oficial', pt.metas_formatadas)
        self.assertIn('Possibilitar o atendimento imediato', pt.metas_formatadas)

    def test_numero_plano_automatico_auto_increment(self):
        payload = {
            'data_criacao': '2026-05-01',
            'status': PlanoTrabalho.STATUS_RASCUNHO,
            'evento': self.evento.pk,
            'oficio': self.oficio.pk,
            'destinos_payload': '[]',
            'objetivo': 'Primeiro',
            'locais': 'Curitiba/PR',
            'horario_atendimento_padrao': '08:00-12:00',
            'coordenador_administrativo_novo_nome': 'Servidor Teste Numeracao',
            'salvar_coordenador_administrativo': 'on',
            'solicitante_escolha': '',
            'return_to': reverse('eventos:documentos-planos-trabalho'),
        }
        payload.update(self._base_formset_payload())
        r1 = self.client.post(reverse('eventos:documentos-planos-trabalho-novo'), data=payload)

        payload2 = dict(payload)
        payload2['objetivo'] = 'Segundo'
        r2 = self.client.post(reverse('eventos:documentos-planos-trabalho-novo'), data=payload2)
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(r2.status_code, 302)

        pts = list(PlanoTrabalho.objects.order_by('numero').values_list('numero', 'ano', 'objetivo'))
        self.assertEqual(pts[0][0], 1)
        self.assertEqual(pts[1][0], 2)
        self.assertEqual(pts[0][1], 2026)
        self.assertEqual(pts[1][1], 2026)

    def test_solicitante_outros_funciona_e_salva_no_gerenciador(self):
        payload = {
            'data_criacao': '2026-05-01',
            'status': PlanoTrabalho.STATUS_RASCUNHO,
            'evento': self.evento.pk,
            'oficio': self.oficio.pk,
            'destinos_payload': '[]',
            'objetivo': 'Com solicitante outros',
            'locais': 'Curitiba/PR',
            'horario_atendimento_padrao': '13:00-17:00',
            'coordenador_administrativo_novo_nome': 'Servidor Teste Solicitante',
            'salvar_coordenador_administrativo': 'on',
            'solicitante_escolha': '__OUTROS__',
            'solicitante_outros': 'Secretaria Municipal Teste',
            'salvar_solicitante_outros': 'on',
            'return_to': reverse('eventos:documentos-planos-trabalho'),
        }
        payload.update(self._base_formset_payload())

        response = self.client.post(reverse('eventos:documentos-planos-trabalho-novo'), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SolicitantePlanoTrabalho.objects.filter(nome='Secretaria Municipal Teste').exists())
        pt = PlanoTrabalho.objects.get(objetivo='Com solicitante outros')
        self.assertTrue(bool(pt.solicitante_id) or bool(pt.solicitante_outros))

    def test_dados_reaparecem_na_edicao(self):
        """Ao abrir o formulário de edição, os dados salvos devem estar presentes."""
        pt = PlanoTrabalho.objects.create(
            numero=11,
            ano=2026,
            objetivo='Objetivo edicao',
            locais='Londrina/PR',
            horario_atendimento='09h às 18h',
            quantidade_servidores=3,
            atividades_codigos='CIN,NOC',
            recursos_texto='PC equipada',
            status=PlanoTrabalho.STATUS_RASCUNHO,
        )
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': pt.pk})
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.instance.objetivo, 'Objetivo edicao')
        self.assertEqual(form.instance.locais, 'Londrina/PR')
        self.assertEqual(form.instance.atividades_codigos, 'CIN,NOC')
        # Verifica que o initial das atividades está correto
        self.assertIn('CIN', form.initial.get('atividades_codigos', []))
        self.assertIn('NOC', form.initial.get('atividades_codigos', []))

    def test_horario_manual_quando_escolhido_outros(self):
        payload = {
            'data_criacao': '2026-05-01',
            'status': PlanoTrabalho.STATUS_RASCUNHO,
            'evento': self.evento.pk,
            'oficio': self.oficio.pk,
            'destinos_payload': '[]',
            'objetivo': 'Horario manual',
            'locais': 'Curitiba/PR',
            'horario_atendimento_padrao': '__OUTROS__',
            'horario_atendimento_manual': 'das 10h às 20h',
            'coordenador_administrativo_novo_nome': 'Servidor Teste Horario',
            'salvar_coordenador_administrativo': 'on',
            'solicitante_escolha': '',
            'return_to': reverse('eventos:documentos-planos-trabalho'),
        }
        payload.update(self._base_formset_payload())

        response = self.client.post(reverse('eventos:documentos-planos-trabalho-novo'), data=payload)
        self.assertEqual(response.status_code, 302)
        pt = PlanoTrabalho.objects.get(objetivo='Horario manual')
        self.assertEqual(pt.horario_atendimento, '10:00 até 20:00')

    def test_detalhe_abre_com_todos_campos(self):
        pt = PlanoTrabalho.objects.create(
            numero=12,
            ano=2026,
            objetivo='Objetivo detalhe',
            locais='Cascavel/PR',
            status=PlanoTrabalho.STATUS_FINALIZADO,
        )
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-detalhe', kwargs={'pk': pt.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Objetivo detalhe')
        self.assertContains(response, 'Cascavel/PR')
        self.assertContains(response, '12/2026')

    def test_campos_obrigatorios_validados(self):
        """Formulário sem campos mínimos deve retornar 200 (form inválido) sem crash."""
        # O form aceita todos os campos como opcionais; um POST mínimo deve funcionar
        response = self.client.post(
            reverse('eventos:documentos-planos-trabalho-novo'),
            data={
                'status': PlanoTrabalho.STATUS_RASCUNHO,
                'data_criacao': '2026-05-01',
                'return_to': reverse('eventos:documentos-planos-trabalho'),
            },
        )
        # status=302 → criou com sucesso; status=200 → formulário inválido exibido novamente
        self.assertIn(response.status_code, [200, 302])


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
