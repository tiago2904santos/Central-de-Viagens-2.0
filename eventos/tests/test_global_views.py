import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

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

    def _extract_oficio_basic_layout_html(self, response, oficio_pk):
        article_html = self._extract_oficio_article_html(response, oficio_pk)
        match = re.search(
            r'<div class="oficio-list-basic-layout">(.*?)<div class="oficio-list-rich-layout">',
            article_html,
            re.S,
        )
        self.assertIsNotNone(match)
        return match.group(1)

    def _extract_oficio_ids_order(self, response):
        return [int(item) for item in re.findall(r'id="oficio-card-(\d+)"', response.content.decode('utf-8'))]

    def _criar_oficio_ordenacao(
        self,
        *,
        numero,
        protocolo,
        data_criacao,
        updated_at,
        data_evento,
        status=Oficio.STATUS_RASCUNHO,
        contexto_evento=False,
    ):
        oficio = Oficio.objects.create(
            evento=self.evento_pt if contexto_evento else None,
            protocolo=protocolo,
            data_criacao=data_criacao,
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=status,
            motivo='ORDTEST',
        )
        oficio.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=data_evento,
            chegada_data=data_evento,
        )
        Oficio.objects.filter(pk=oficio.pk).update(
            numero=numero,
            ano=2026,
            updated_at=updated_at,
            data_criacao=data_criacao,
        )
        oficio.refresh_from_db()
        return oficio

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
        self.assertContains(response, 'name="order_by"', html=False)
        self.assertContains(response, 'name="order_dir"', html=False)
        self.assertNotContains(response, 'name="evento_id"', html=False)
        self.assertNotContains(response, 'name="ano"', html=False)
        self.assertNotContains(response, 'name="numero"', html=False)
        self.assertEqual(content.count('<h1'), 1)

        filtered = self.client.get(reverse('eventos:oficios-global'), {'q': '12.345.678-9'})
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, self.oficio_pt.numero_formatado)
        self.assertNotContains(filtered, self.oficio_os.numero_formatado)

    def test_lista_global_de_oficios_renderiza_toggle_de_visualizacao_com_persistencia_local(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-oficios-view-root', html=False)
        self.assertContains(response, 'data-oficios-view-toggle="rich"', html=False)
        self.assertContains(response, 'data-oficios-view-toggle="basic"', html=False)
        self.assertContains(response, 'js/oficios_list.js', html=False)

        js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'oficios_list.js').read_text(encoding='utf-8')
        self.assertIn("central-viagens.oficios.view-mode", js)
        self.assertIn("data-view-mode", js)
        self.assertIn("data-oficios-view-toggle", js)

    def test_lista_global_de_oficios_modo_basico_mostra_apenas_campos_essenciais_e_acoes_do_oficio(self):
        with patch('eventos.views_global.get_document_generation_status') as mocked_status:
            mocked_status.return_value = {'status': 'available', 'errors': []}
            response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)

        basic_html = self._extract_oficio_basic_layout_html(response, self.oficio_pt.pk)

        self.assertIn('Oficio', basic_html)
        self.assertIn('Protocolo', basic_html)
        self.assertIn('Destino', basic_html)
        self.assertIn('Data', basic_html)
        self.assertIn('Viajantes', basic_html)
        self.assertIn('Abrir', basic_html)
        self.assertIn('Editar', basic_html)
        self.assertIn('PDF', basic_html)
        self.assertIn('DOCX', basic_html)
        self.assertIn('Excluir', basic_html)
        self.assertNotIn('Justificativa', basic_html)
        self.assertNotIn('Termos de autorizacao', basic_html)
        self.assertNotIn('Abrir wizard', basic_html)
        self.assertNotIn('/eventos/documentos/termos/', basic_html)
        self.assertNotIn('/justificativa/', basic_html)

    def test_lista_global_de_oficios_resume_viajantes_no_modo_basico_com_primeiro_nome_e_quantidade_restante(self):
        viajante_extra_1 = Viajante.objects.create(
            nome='YARA RESUMO',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='23921232095',
            telefone='41977770001',
            unidade_lotacao=self.unidade,
            rg='RGRESUMO1',
        )
        viajante_extra_2 = Viajante.objects.create(
            nome='ZULEICA RESUMO',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='29774396047',
            telefone='41977770002',
            unidade_lotacao=self.unidade,
            rg='RGRESUMO2',
        )
        self.oficio_pt.viajantes.add(viajante_extra_1, viajante_extra_2)

        response = self.client.get(reverse('eventos:oficios-global'))
        basic_html = self._extract_oficio_basic_layout_html(response, self.oficio_pt.pk)

        self.assertIn('VIAJANTE GLOBAL +2', basic_html)
        self.assertNotIn('YARA RESUMO', basic_html)
        self.assertNotIn('ZULEICA RESUMO', basic_html)

    def test_lista_global_de_oficios_modo_rico_melhora_bloco_de_transporte_e_viajantes_em_coluna(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        card_html = self._extract_oficio_article_html(response, self.oficio_pt.pk)
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')

        self.assertIn('oficio-list-transport-panel', card_html)
        self.assertIn('oficio-list-transport-panel__hero', card_html)
        self.assertIn('oficio-list-transport-panel__detail', card_html)
        self.assertIn('oficio-list-transport-panel__headline', card_html)
        self.assertIn('oficio-list-traveler-list', card_html)
        self.assertIn('.oficio-list-traveler-list {', css)
        self.assertIn('.oficio-list-transport-panel__headline {', css)
        self.assertIn('display: grid;', css)

    def test_lista_global_de_oficios_exibe_periodo_sem_horario_status_da_viagem_e_dias_relativos(self):
        hoje = timezone.localdate()
        protocolos = ['111111119', '222222228', '333333337']
        datas = [
            (hoje + timedelta(days=5), hoje + timedelta(days=6)),
            (hoje - timedelta(days=1), hoje),
            (hoje - timedelta(days=4), hoje - timedelta(days=2)),
        ]
        created_oficios = []
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
            created_oficios.append(oficio)

        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        future_card = self._extract_oficio_article_html(response, created_oficios[0].pk)
        today_card = self._extract_oficio_article_html(response, created_oficios[1].pk)
        past_card = self._extract_oficio_article_html(response, created_oficios[2].pk)

        self.assertIn('Termina hoje', today_card)
        self.assertNotContains(response, 'Faltam 5 dia(s)')
        self.assertNotContains(response, 'Aconteceu ha 2 dia(s)')
        self.assertNotIn('Em andamento', future_card)
        self.assertNotIn('Em andamento', today_card)
        self.assertNotIn('Em andamento', past_card)
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
        self.assertIn('Data do evento', card_html)
        self.assertIn('Destino', card_html)
        self.assertNotIn('Contexto do oficio', card_html)
        self.assertNotIn('Motivo', card_html)
        self.assertNotIn('Contexto', card_html)
        self.assertIn('Veiculo e motorista', card_html)
        self.assertIn('oficio-list-core-card--transport', card_html)
        self.assertIn('Veiculo', card_html)
        self.assertIn('Motorista', card_html)
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
        basic_html = self._extract_oficio_basic_layout_html(response, self.oficio_pt.pk)
        self.assertEqual(basic_html.count(self.oficio_pt.protocolo_formatado), 1)

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
        self.assertIn('oficio-list-basic-layout', card_html)
        self.assertIn('oficio-list-basic-field', card_html)
        self.assertIn('oficio-list-rich-layout', card_html)
        self.assertEqual(card_html.count('oficio-list-chip oficio-list-chip--meta'), 4)
        self.assertIn('oficio-list-card__header-status', card_html)
        self.assertIn('oficio-list-core-grid', card_html)
        self.assertIn('oficio-list-core-card', card_html)
        self.assertIn('oficio-list-core-card--transport', card_html)
        self.assertIn('oficio-list-transport-panel', card_html)
        self.assertIn('oficio-list-traveler-pill', card_html)
        self.assertNotIn('Contexto do oficio', card_html)
        self.assertIn('Veiculo e motorista', card_html)
        self.assertIn('Motorista Avulso', card_html)
        self.assertIn('Spin', card_html)
        self.assertNotIn('Aconteceu ha 8 dia(s)', card_html)
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
            r'<section class="oficio-list-core-card oficio-list-core-card--travelers">.*?<h3 class="oficio-list-core-card__title">Viajantes</h3>(.*?)</section>',
            card_html,
            re.S,
        )

        self.assertIsNotNone(viajantes_match)
        viajantes_html = viajantes_match.group(1)
        self.assertEqual(viajantes_html.count('class="oficio-list-traveler-pill '), 4)
        self.assertIn('+1 viajante(s)', viajantes_html)

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
            self.assertIn('oficio-list-chip oficio-list-chip--meta', card_html)
            self.assertIn('oficio-list-badge', card_html)
            self.assertNotIn('Documento', card_html)
            self.assertNotIn('Viagem', card_html)
            self.assertNotIn('Em andamento', card_html)

    def test_lista_global_de_oficios_expoe_links_de_download_direto_sem_fluxo_documental_intermediario(self):
        with patch('eventos.views_global.get_document_generation_status') as mocked_status:
            mocked_status.return_value = {'status': 'available', 'errors': []}
            response = self.client.get(reverse('eventos:oficios-global'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn(reverse('eventos:oficio-documento-download', kwargs={
            'pk': self.oficio_pt.pk,
            'tipo_documento': 'oficio',
            'formato': 'pdf',
        }), content)
        self.assertIn(reverse('eventos:oficio-documento-download', kwargs={
            'pk': self.oficio_pt.pk,
            'tipo_documento': 'oficio',
            'formato': 'docx',
        }), content)
        self.assertIn('data-direct-download="true"', content)
        self.assertNotIn(
            f'href="{reverse("eventos:oficio-documentos", kwargs={"pk": self.oficio_pt.pk})}"',
            content,
        )

    def test_lista_global_de_oficios_mantem_chips_com_css_compacto(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')

        self.assertIn('.oficios-filter-topbar {', css)
        self.assertIn('.oficios-sort-panel {', css)
        self.assertIn('.oficios-view-toggle {', css)
        self.assertIn('.oficio-list-basic-layout {', css)
        self.assertIn('.oficio-list-rich-layout {', css)
        self.assertIn('.oficio-list-basic-field {', css)
        self.assertIn('.oficio-list-chip {', css)
        self.assertIn('padding: 0.58rem 0.74rem;', css)
        self.assertIn('.oficio-list-chip__value {', css)
        self.assertIn('font-size: 0.92rem;', css)
        self.assertIn('.oficio-list-core-card {', css)
        self.assertIn('padding: 0.78rem 0.82rem;', css)
        self.assertIn('.oficio-list-transport-panel__headline {', css)
        self.assertIn('[data-view-mode="basic"] .oficio-list-rich-layout {', css)
        self.assertIn('[data-view-mode="basic"] .oficio-list-basic-layout {', css)
        self.assertIn('.oficio-list-traveler-pill {', css)
        self.assertIn('.oficio-list-traveler-list {', css)
        self.assertIn('display: grid;', css)
        self.assertIn('.oficio-list-subcard--justificativa .oficio-list-subcard__actions {', css)
        self.assertIn('margin-top: auto;', css)
        self.assertIn('.oficio-list-term-row {', css)
        self.assertIn('.oficio-list-term-row .btn-doc-action {', css)
        self.assertIn('padding: 0.26rem 0.5rem;', css)

    def test_lista_global_de_oficios_ordena_por_numero_do_oficio(self):
        oficio_b = self._criar_oficio_ordenacao(
            numero=20,
            protocolo='200000001',
            data_criacao=date(2026, 5, 2),
            updated_at=timezone.make_aware(datetime(2026, 5, 2, 12, 0)),
            data_evento=date(2026, 5, 20),
        )
        oficio_a = self._criar_oficio_ordenacao(
            numero=3,
            protocolo='200000002',
            data_criacao=date(2026, 5, 1),
            updated_at=timezone.make_aware(datetime(2026, 5, 1, 12, 0)),
            data_evento=date(2026, 5, 21),
        )

        response = self.client.get(reverse('eventos:oficios-global'), {'q': 'ORDTEST', 'order_by': 'numero', 'order_dir': 'asc'})
        self.assertEqual(self._extract_oficio_ids_order(response)[:2], [oficio_a.pk, oficio_b.pk])

    def test_lista_global_de_oficios_ordena_por_protocolo(self):
        oficio_b = self._criar_oficio_ordenacao(
            numero=4,
            protocolo='900000009',
            data_criacao=date(2026, 5, 2),
            updated_at=timezone.make_aware(datetime(2026, 5, 2, 12, 0)),
            data_evento=date(2026, 5, 20),
        )
        oficio_a = self._criar_oficio_ordenacao(
            numero=5,
            protocolo='100000001',
            data_criacao=date(2026, 5, 1),
            updated_at=timezone.make_aware(datetime(2026, 5, 1, 12, 0)),
            data_evento=date(2026, 5, 21),
        )

        response = self.client.get(reverse('eventos:oficios-global'), {'q': 'ORDTEST', 'order_by': 'protocolo', 'order_dir': 'asc'})
        self.assertEqual(self._extract_oficio_ids_order(response)[:2], [oficio_a.pk, oficio_b.pk])

    def test_lista_global_de_oficios_ordena_por_data_de_criacao(self):
        oficio_b = self._criar_oficio_ordenacao(
            numero=6,
            protocolo='300000006',
            data_criacao=date(2026, 5, 10),
            updated_at=timezone.make_aware(datetime(2026, 5, 12, 12, 0)),
            data_evento=date(2026, 5, 20),
        )
        oficio_a = self._criar_oficio_ordenacao(
            numero=7,
            protocolo='300000007',
            data_criacao=date(2026, 5, 1),
            updated_at=timezone.make_aware(datetime(2026, 5, 11, 12, 0)),
            data_evento=date(2026, 5, 21),
        )

        response = self.client.get(reverse('eventos:oficios-global'), {'q': 'ORDTEST', 'order_by': 'data_criacao', 'order_dir': 'asc'})
        self.assertEqual(self._extract_oficio_ids_order(response)[:2], [oficio_a.pk, oficio_b.pk])

    def test_lista_global_de_oficios_ordena_por_data_de_atualizacao(self):
        oficio_b = self._criar_oficio_ordenacao(
            numero=8,
            protocolo='400000008',
            data_criacao=date(2026, 5, 2),
            updated_at=timezone.make_aware(datetime(2026, 5, 20, 12, 0)),
            data_evento=date(2026, 5, 22),
        )
        oficio_a = self._criar_oficio_ordenacao(
            numero=9,
            protocolo='400000009',
            data_criacao=date(2026, 5, 1),
            updated_at=timezone.make_aware(datetime(2026, 5, 10, 12, 0)),
            data_evento=date(2026, 5, 21),
        )

        response = self.client.get(reverse('eventos:oficios-global'), {'q': 'ORDTEST', 'order_by': 'updated_at', 'order_dir': 'asc'})
        self.assertEqual(self._extract_oficio_ids_order(response)[:2], [oficio_a.pk, oficio_b.pk])

    def test_lista_global_de_oficios_ordena_por_data_do_evento(self):
        oficio_b = self._criar_oficio_ordenacao(
            numero=10,
            protocolo='500000010',
            data_criacao=date(2026, 5, 2),
            updated_at=timezone.make_aware(datetime(2026, 5, 2, 12, 0)),
            data_evento=date(2026, 6, 20),
        )
        oficio_a = self._criar_oficio_ordenacao(
            numero=11,
            protocolo='500000011',
            data_criacao=date(2026, 5, 1),
            updated_at=timezone.make_aware(datetime(2026, 5, 1, 12, 0)),
            data_evento=date(2026, 6, 10),
        )

        response = self.client.get(reverse('eventos:oficios-global'), {'q': 'ORDTEST', 'order_by': 'data_evento', 'order_dir': 'asc'})
        self.assertEqual(self._extract_oficio_ids_order(response)[:2], [oficio_a.pk, oficio_b.pk])

    def test_lista_global_de_oficios_combina_filtros_com_ordenacao_personalizada(self):
        oficio_rascunho = self._criar_oficio_ordenacao(
            numero=12,
            protocolo='600000012',
            data_criacao=date(2026, 5, 2),
            updated_at=timezone.make_aware(datetime(2026, 5, 2, 12, 0)),
            data_evento=date(2026, 7, 20),
            status=Oficio.STATUS_RASCUNHO,
            contexto_evento=True,
        )
        oficio_finalizado = self._criar_oficio_ordenacao(
            numero=13,
            protocolo='100000013',
            data_criacao=date(2026, 5, 1),
            updated_at=timezone.make_aware(datetime(2026, 5, 1, 12, 0)),
            data_evento=date(2026, 7, 10),
            status=Oficio.STATUS_FINALIZADO,
            contexto_evento=True,
        )

        response = self.client.get(
            reverse('eventos:oficios-global'),
            {
                'q': 'ORDTEST',
                'status': [Oficio.STATUS_FINALIZADO],
                'contexto': ['EVENTO'],
                'order_by': 'protocolo',
                'order_dir': 'asc',
            },
        )

        order = self._extract_oficio_ids_order(response)
        self.assertEqual(order[:1], [oficio_finalizado.pk])
        self.assertNotIn(oficio_rascunho.pk, order)

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
