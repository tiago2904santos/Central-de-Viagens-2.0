import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo, Cidade, Estado, UnidadeLotacao, Viajante
from eventos.models import (
    Evento,
    Justificativa,
    Oficio,
    OficioTrecho,
    OrdemServico,
    PlanoTrabalho,
    RoteiroEvento,
    RoteiroEventoDestino,
    TermoAutorizacao,
)


User = get_user_model()


class GlobalViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='global', password='global123')
        self.client.login(username='global', password='global123')

        self.estado = Estado.objects.create(codigo_ibge='41', nome='Parana', sigla='PR', ativo=True)
        self.cidade_origem = Cidade.objects.create(codigo_ibge='4106902', nome='Curitiba', estado=self.estado, ativo=True)
        self.cidade_destino = Cidade.objects.create(codigo_ibge='4113700', nome='Londrina', estado=self.estado, ativo=True)
        self.cargo = Cargo.objects.create(nome='ANALISTA GLOBAL')
        self.unidade = UnidadeLotacao.objects.create(nome='UNIDADE GLOBAL')
        self.viajante = Viajante.objects.create(
            nome='VIAJANTE GLOBAL',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='52998224725',
            telefone='41999998888',
            unidade_lotacao=self.unidade,
            rg='123456789',
        )

        self.evento_pt = Evento.objects.create(
            titulo='Evento PT',
            data_inicio=date(2026, 3, 10),
            data_fim=date(2026, 3, 12),
            status=Evento.STATUS_EM_ANDAMENTO,
            cidade_base=self.cidade_origem,
        )
        self.evento_os = Evento.objects.create(
            titulo='Evento OS',
            data_inicio=date(2026, 4, 10),
            data_fim=date(2026, 4, 12),
            status=Evento.STATUS_EM_ANDAMENTO,
            cidade_base=self.cidade_origem,
        )
        self.oficio_pt = Oficio.objects.create(
            evento=self.evento_pt,
            protocolo='123456789',
            data_criacao=date(2026, 3, 1),
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=Oficio.STATUS_RASCUNHO,
        )
        self.oficio_pt.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=self.oficio_pt,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=date(2026, 3, 10),
            saida_hora=time(8, 0),
            chegada_data=date(2026, 3, 10),
            chegada_hora=time(12, 0),
        )

        self.oficio_os = Oficio.objects.create(
            evento=self.evento_os,
            protocolo='987654321',
            data_criacao=date(2026, 4, 1),
            tipo_destino=Oficio.TIPO_DESTINO_CAPITAL,
            status=Oficio.STATUS_RASCUNHO,
        )
        self.oficio_os.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=self.oficio_os,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=date(2026, 4, 10),
            saida_hora=time(9, 0),
            chegada_data=date(2026, 4, 10),
            chegada_hora=time(13, 0),
        )

        PlanoTrabalho.objects.create(
            evento=self.evento_pt,
            oficio=self.oficio_pt,
            objetivo='Plano global',
            status=PlanoTrabalho.STATUS_FINALIZADO,
        )
        OrdemServico.objects.create(
            evento=self.evento_os,
            oficio=self.oficio_os,
            finalidade='Ordem global',
            status=OrdemServico.STATUS_FINALIZADO,
        )

        self.roteiro = RoteiroEvento.objects.create(
            evento=self.evento_pt,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            saida_dt=timezone.make_aware(datetime(2026, 3, 10, 8, 0)),
            chegada_dt=timezone.make_aware(datetime(2026, 3, 10, 12, 0)),
            status=RoteiroEvento.STATUS_FINALIZADO,
        )
        RoteiroEventoDestino.objects.create(
            roteiro=self.roteiro,
            estado=self.estado,
            cidade=self.cidade_destino,
            ordem=0,
        )

        TermoAutorizacao.objects.create(
            evento=self.evento_pt,
            oficio=self.oficio_pt,
            modo_geracao=TermoAutorizacao.MODO_AUTOMATICO_SEM_VIATURA,
            status=TermoAutorizacao.STATUS_GERADO,
            viajante=self.viajante,
            destino='Londrina/PR',
            data_evento=date(2026, 3, 10),
        )

    def _extract_oficio_card_html(self, response, oficio_pk):
        content = response.content.decode('utf-8')
        match = re.search(
            rf'<article class="oficio-list-card[^"]*" id="oficio-card-{oficio_pk}">(.*?)</article>',
            content,
            re.S,
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def _extract_oficio_article_html(self, response, oficio_pk):
        content = response.content.decode('utf-8')
        match = re.search(
            rf'(<article class="oficio-list-card[^"]*" id="oficio-card-{oficio_pk}">.*?</article>)',
            content,
            re.S,
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def _extract_oficio_terms_html(self, response, oficio_pk):
        article_html = self._extract_oficio_article_html(response, oficio_pk)
        match = re.search(
            r'<section class="oficio-list-subcard">\s*<div class="oficio-list-subcard__header">\s*<div>\s*<h3 class="oficio-list-subcard__title">Termos de autorizacao</h3>(.*?)</section>',
            article_html,
            re.S,
        )
        self.assertIsNotNone(match)
        return match.group(0)

    def test_lista_global_de_oficios_renderiza_header_unico_filtros_enxutos_e_busca_ampla(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertContains(response, 'Lista de oficios')
        self.assertContains(response, 'Novo oficio')
        self.assertContains(response, 'name="q"', html=False)
        self.assertContains(response, 'name="contexto"', html=False)
        self.assertContains(response, 'name="viagem_status"', html=False)
        self.assertContains(response, 'name="justificativa"', html=False)
        self.assertContains(response, 'name="termo"', html=False)
        self.assertNotContains(response, 'name="evento_id"', html=False)
        self.assertNotContains(response, 'name="ano"', html=False)
        self.assertNotContains(response, 'name="numero"', html=False)
        self.assertEqual(content.count('<h1'), 1)

        filtered = self.client.get(reverse('eventos:oficios-global'), {'q': '12.345.678-9'})
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, self.oficio_pt.numero_formatado)
        self.assertNotContains(filtered, self.oficio_os.numero_formatado)

    def test_lista_global_de_oficios_exibe_periodo_sem_horario_status_da_viagem_e_dias_relativos(self):
        hoje = timezone.localdate()
        protocolos = ['111111119', '222222228', '333333337']
        datas = [
            (hoje + timedelta(days=5), hoje + timedelta(days=6)),
            (hoje - timedelta(days=1), hoje + timedelta(days=1)),
            (hoje - timedelta(days=4), hoje - timedelta(days=2)),
        ]
        for protocolo, (inicio, fim) in zip(protocolos, datas):
            oficio = Oficio.objects.create(
                protocolo=protocolo,
                data_criacao=hoje,
                tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
                status=Oficio.STATUS_RASCUNHO,
            )
            oficio.viajantes.add(self.viajante)
            OficioTrecho.objects.create(
                oficio=oficio,
                ordem=0,
                origem_estado=self.estado,
                origem_cidade=self.cidade_origem,
                destino_estado=self.estado,
                destino_cidade=self.cidade_destino,
                saida_data=inicio,
                saida_hora=time(8, 0),
                chegada_data=fim,
                chegada_hora=time(12, 0),
            )

        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vai acontecer')
        self.assertContains(response, 'Faltam 5 dia(s)')
        self.assertContains(response, 'Em andamento')
        self.assertContains(response, 'Ja aconteceu')
        self.assertContains(response, 'Aconteceu ha 2 dia(s)')
        self.assertNotContains(response, '08:00')
        self.assertNotContains(response, '09:00')
        self.assertNotContains(response, '12:00')
        self.assertNotContains(response, '13:00')

    def test_lista_global_de_oficios_remove_repeticoes_em_justificativa_e_termos(self):
        segundo_viajante = Viajante.objects.create(
            nome='SEGUNDO VIAJANTE',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='15350946056',
            telefone='41988887777',
            unidade_lotacao=self.unidade,
            rg='987654321',
        )
        self.oficio_pt.viajantes.add(segundo_viajante)
        Justificativa.objects.create(
            oficio=self.oficio_pt,
            texto='Justificativa extensa de teste para validar a exibicao resumida sem repetir contexto do oficio.',
        )
        TermoAutorizacao.objects.create(
            evento=self.evento_pt,
            oficio=self.oficio_pt,
            modo_geracao=TermoAutorizacao.MODO_AUTOMATICO_SEM_VIATURA,
            status=TermoAutorizacao.STATUS_GERADO,
            viajante=segundo_viajante,
            destino='Londrina/PR',
            data_evento=date(2026, 3, 10),
        )

        response = self.client.get(reverse('eventos:oficios-global'))

        self.assertEqual(response.status_code, 200)
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)
        termos_html = self._extract_oficio_terms_html(response, self.oficio_pt.pk)
        self.assertIn('Justificativa', card_html)
        self.assertIn('Termos de autorizacao', card_html)
        self.assertIn('SEGUNDO VIAJANTE', card_html)
        self.assertEqual(card_html.count(self.oficio_pt.protocolo_formatado), 1)
        self.assertNotIn('Primeira saida', card_html)
        self.assertIn('Periodo', card_html)
        self.assertIn('Veiculo', card_html)
        self.assertIn('class="oficio-list-term-row"', termos_html)
        self.assertIn('class="oficio-list-term-row__name"', termos_html)
        self.assertIn('class="oficio-list-term-row__actions"', termos_html)
        self.assertIn('Abrir', termos_html)
        self.assertIn('PDF', termos_html)
        self.assertNotIn('Londrina/PR', termos_html)
        self.assertNotIn('10/03/2026', termos_html)
        self.assertNotIn('Termo de autorizacao,', termos_html)
        self.assertNotIn('Protocolo', termos_html)
        self.assertNotIn('Documentos', card_html)
        self.assertEqual(termos_html.count('class="oficio-list-term-row"'), 2)
        self.assertContains(response, 'Abrir wizard')

    def test_lista_global_de_oficios_aplica_linguagem_visual_compacta_e_contexto_sem_repeticao(self):
        hoje = timezone.localdate()
        oficio_avulso = Oficio.objects.create(
            protocolo='333222111',
            data_criacao=hoje - timedelta(days=12),
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=Oficio.STATUS_FINALIZADO,
            modelo='Spin',
            motorista='Motorista Avulso',
        )
        oficio_avulso.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=oficio_avulso,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=hoje - timedelta(days=9),
            chegada_data=hoje - timedelta(days=8),
        )

        response = self.client.get(reverse('eventos:oficios-global'))
        card_html = self._extract_oficio_article_html(response, oficio_avulso.pk)

        self.assertIn('oficio-list-card is-tone-green', card_html)
        self.assertIn('Concluido', card_html)
        self.assertIn('oficio-list-chip-list--status', card_html)
        self.assertIn('oficio-list-info-grid', card_html)
        self.assertIn('oficio-list-info-block', card_html)
        self.assertIn('oficio-list-info-row', card_html)
        self.assertIn('class="oficio-list-chip', card_html)
        self.assertIn('Contexto do oficio', card_html)
        self.assertIn('Viajantes', card_html)
        self.assertIn('Veiculo e motorista', card_html)
        self.assertIn('Motorista Avulso', card_html)
        self.assertIn('Contexto', card_html)
        self.assertIn('Avulso', card_html)
        self.assertIn('Veiculo', card_html)
        self.assertNotIn('oficio-list-meta-group', card_html)
        self.assertNotIn('Oficio avulso', card_html)

    def test_lista_global_de_oficios_limita_chips_de_viajantes_quando_ha_excesso(self):
        extras = [
            Viajante.objects.create(
                nome=f'VIAJANTE EXTRA {indice}',
                status=Viajante.STATUS_FINALIZADO,
                cargo=self.cargo,
                cpf=f'1535094605{indice}',
                telefone=f'4198888777{indice}',
                unidade_lotacao=self.unidade,
                rg=f'RGEXTRA{indice}',
            )
            for indice in range(3)
        ]
        self.oficio_pt.viajantes.add(*extras)

        response = self.client.get(reverse('eventos:oficios-global'))
        card_html = self._extract_oficio_article_html(response, self.oficio_pt.pk)
        viajantes_match = re.search(
            r'<section class="oficio-list-info-block is-soft">.*?<span class="oficio-list-info-block__title">Viajantes</span>(.*?)</section>',
            card_html,
            re.S,
        )

        self.assertIsNotNone(viajantes_match)
        viajantes_html = viajantes_match.group(1)
        self.assertEqual(viajantes_html.count('class="oficio-list-chip '), 3)
        self.assertIn('+2', viajantes_html)

    def test_lista_global_de_oficios_aplica_cores_combinadas_e_chips_conforme_tema(self):
        hoje = timezone.localdate()
        cenarios = [
            ('111111110', Oficio.STATUS_FINALIZADO, hoje - timedelta(days=5), hoje - timedelta(days=3), 'is-tone-green'),
            ('222222221', Oficio.STATUS_FINALIZADO, hoje, hoje + timedelta(days=1), 'is-tone-orange'),
            ('333333332', Oficio.STATUS_FINALIZADO, hoje + timedelta(days=4), hoje + timedelta(days=5), 'is-tone-blue'),
            ('444444443', Oficio.STATUS_RASCUNHO, hoje + timedelta(days=1), hoje + timedelta(days=2), 'is-tone-yellow'),
            ('555555554', Oficio.STATUS_RASCUNHO, hoje, hoje, 'is-tone-red'),
        ]
        oficios = []
        for protocolo, status, inicio, fim, _theme in cenarios:
            oficio = Oficio.objects.create(
                protocolo=protocolo,
                data_criacao=hoje,
                tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
                status=status,
            )
            oficio.viajantes.add(self.viajante)
            OficioTrecho.objects.create(
                oficio=oficio,
                ordem=0,
                origem_estado=self.estado,
                origem_cidade=self.cidade_origem,
                destino_estado=self.estado,
                destino_cidade=self.cidade_destino,
                saida_data=inicio,
                chegada_data=fim,
            )
            oficios.append(oficio)

        response = self.client.get(reverse('eventos:oficios-global'))

        for oficio, (_, _, _, _, theme_css_class) in zip(oficios, cenarios):
            card_html = self._extract_oficio_article_html(response, oficio.pk)
            self.assertIn(theme_css_class, card_html)
            self.assertIn('oficio-list-chip', card_html)
            self.assertIn('Documento', card_html)
            self.assertIn('Viagem', card_html)

    def test_lista_global_de_oficios_mantem_chips_com_css_compacto(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')

        self.assertIn('.oficio-list-chip {', css)
        self.assertIn('padding: 0.1rem 0.28rem;', css)
        self.assertIn('font-size: 0.63rem;', css)
        self.assertIn('border-radius: 0.52rem;', css)
        self.assertIn('.oficio-list-info-block {', css)
        self.assertIn('padding: 0.44rem 0.5rem;', css)
        self.assertIn('.oficio-list-term-row {', css)
        self.assertIn('.oficio-list-term-row .btn-doc-action {', css)
        self.assertIn('padding: 0.2rem 0.42rem;', css)

    def test_hubs_globais_principais_respondem_200(self):
        urls = [
            reverse('eventos:roteiros-global'),
            reverse('eventos:documentos-hub'),
            reverse('eventos:documentos-planos-trabalho'),
            reverse('eventos:documentos-ordens-servico'),
            reverse('eventos:documentos-justificativas'),
            reverse('eventos:documentos-termos'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_hubs_documentais_renderizam_contexto_real(self):
        response_pt = self.client.get(reverse('eventos:documentos-planos-trabalho'))
        self.assertContains(response_pt, 'Planos de trabalho')
        self.assertContains(response_pt, self.evento_pt.titulo)
        self.assertContains(response_pt, self.oficio_pt.numero_formatado)

        response_os = self.client.get(reverse('eventos:documentos-ordens-servico'))
        self.assertContains(response_os, 'Ordens de servi')
        self.assertContains(response_os, self.evento_os.titulo)
        self.assertContains(response_os, self.oficio_os.numero_formatado)

        response_termos = self.client.get(reverse('eventos:documentos-termos'))
        self.assertContains(response_termos, self.viajante.nome)
        self.assertContains(response_termos, self.evento_pt.titulo)
        self.assertContains(response_termos, 'Novo termo')
        self.assertContains(response_termos, 'Termo de autorizacao, Londrina/PR, 10/03/2026, VIAJANTE GLOBAL')
        self.assertNotContains(response_termos, 'TA-000')

    def test_simulacao_global_calcula_valor(self):
        response = self.client.post(
            reverse('eventos:simulacao-diarias'),
            data={
                'period_count': '1',
                'quantidade_servidores': '2',
                'saida_data_0': '2026-03-10',
                'saida_hora_0': '08:00',
                'destino_cidade_0': 'Londrina',
                'destino_uf_0': 'PR',
                'chegada_final_data': '2026-03-11',
                'chegada_final_hora': '12:00',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resultado')
        self.assertContains(response, 'Valor por servidor')
