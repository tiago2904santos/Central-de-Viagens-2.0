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
            observacoes='Plano global',
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

    def _extract_oficio_table_html(self, response):
        content = response.content.decode('utf-8')
        start = content.find('<table class="table oficios-table mb-0">')
        self.assertNotEqual(start, -1)
        end = content.find('</table>', start)
        self.assertNotEqual(end, -1)
        return content[start:end + len('</table>')]

    def _extract_oficio_row_html(self, response, oficio_pk):
        content = self._extract_oficio_table_html(response)
        start_marker = f'<tr id="oficio-row-{oficio_pk}">'
        start = content.find(start_marker)
        self.assertNotEqual(start, -1)
        next_row = content.find('<tr id="oficio-row-', start + len(start_marker))
        end = next_row if next_row != -1 else len(content)
        return content[start:end]

    def _extract_oficio_card_html(self, response, oficio_pk):
        content = response.content.decode('utf-8')
        anchor = f'id="oficio-card-{oficio_pk}"'
        start = content.find(anchor)
        self.assertNotEqual(start, -1)
        article_start = content.rfind('<article class="oficio-list-card ', 0, start)
        self.assertNotEqual(article_start, -1)
        article_end = content.find('</article>', start)
        self.assertNotEqual(article_end, -1)
        return content[article_start:article_end + len('</article>')]

    def _extract_oficio_ids_order(self, response):
        return [int(item) for item in re.findall(r'id="oficio-row-(\d+)"', response.content.decode('utf-8'))]

    def _extract_evento_card_html(self, response, evento_pk):
        content = response.content.decode('utf-8')
        anchor = f'id="evento-card-{evento_pk}"'
        start = content.find(anchor)
        self.assertNotEqual(start, -1)
        article_start = content.rfind('<article class="oficio-list-card documento-cascade-card ', 0, start)
        self.assertNotEqual(article_start, -1)
        article_end = content.find('</article>', start)
        self.assertNotEqual(article_end, -1)
        return content[article_start:article_end + len('</article>')]

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

    def test_lista_global_de_oficios_renderiza_header_e_filtros_completos_da_lista(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertContains(response, 'Oficios salvos')
        self.assertContains(response, 'Novo oficio')
        self.assertContains(response, 'name="q"', html=False)
        self.assertContains(response, 'Oficio, protocolo, destino ou servidor')
        self.assertContains(response, 'name="status"', html=False)
        self.assertContains(response, 'name="viagem_status"', html=False)
        self.assertContains(response, 'name="justificativa"', html=False)
        self.assertContains(response, 'name="termo"', html=False)
        self.assertContains(response, 'name="order_by"', html=False)
        self.assertContains(response, 'name="order_dir"', html=False)
        self.assertContains(response, 'name="date_scope"', html=False)
        self.assertContains(response, 'name="date_start"', html=False)
        self.assertContains(response, 'name="date_end"', html=False)
        self.assertContains(response, 'system-document-filter__action-btn--submit', html=False)
        self.assertContains(response, 'Limpar')
        self.assertNotContains(response, 'name="contexto"', html=False)
        self.assertNotContains(response, 'name="evento_id"', html=False)
        self.assertNotContains(response, 'name="ano"', html=False)
        self.assertNotContains(response, 'name="numero"', html=False)
        self.assertNotContains(response, 'system-document-filter__summary-pill', html=False)
        self.assertNotContains(response, 'A lista e atualizada automaticamente', html=False)
        self.assertEqual(content.count('<h1'), 1)

        filtered = self.client.get(reverse('eventos:oficios-global'), {'q': '12.345.678-9'})
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, self.oficio_pt.numero_formatado)
        self.assertNotContains(filtered, self.oficio_os.numero_formatado)

    def test_lista_global_de_oficios_renderiza_toggle_com_dois_modos_e_script_de_persistencia(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('data-list-view-root', content)
        self.assertIn('data-view-mode="rich"', content)
        self.assertIn('system-list-view-toggle', content)
        self.assertIn('data-list-view-toggle="rich"', content)
        self.assertIn('data-list-view-toggle="basic"', content)
        self.assertIn('Completa', content)
        self.assertIn('Visualizacao unica', content)
        self.assertIn('<script src="/static/js/list_standard.js"></script>', content)
        self.assertIn('<table class="table oficios-table mb-0">', content)
        self.assertIn('oficio-list-grid', content)
        self.assertIn('oficio-list-card', content)

    def test_lista_global_de_oficios_renderiza_modo_completo_em_cards_com_contexto_rico(self):
        with patch('eventos.views_global.get_document_generation_status') as mocked_status:
            mocked_status.return_value = {'status': 'available', 'errors': []}
            response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)

        self.assertIn('oficio-list-card', card_html)
        self.assertIn('oficio-list-chip', card_html)
        self.assertIn('oficio-list-surface', card_html)
        self.assertIn('oficio-list-surface--panel', card_html)
        self.assertIn('oficio-list-surface--soft', card_html)
        self.assertIn('Servidores', card_html)
        self.assertIn('Veiculo e motorista', card_html)
        self.assertIn('oficio-list-card__footer-actions', card_html)
        self.assertIn(reverse('eventos:oficio-step1', kwargs={'pk': self.oficio_pt.pk}), card_html)
        self.assertNotIn('/guiado/painel/', card_html)
        self.assertIn('VIAJANTE GLOBAL', card_html)
        self.assertIn('aria-label="Excluir oficio"', card_html)
        self.assertIn('is-icon-only', card_html)
        self.assertNotIn('Documentos', card_html)

    def test_lista_global_de_oficios_expoe_hook_de_persistencia_do_modo_no_javascript(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'list_standard.js').read_text(encoding='utf-8')

        self.assertContains(response, 'data-view-storage-key="central-viagens.oficios.view-mode"', html=False)
        self.assertIn('central-viagens.list.view-mode.', js)
        self.assertIn('window.localStorage', js)
        self.assertIn('data-list-view-toggle', js)
        self.assertIn('data-view-mode', js)

    def test_lista_global_de_oficios_mostra_acao_abrir_para_todos_os_oficios_no_wizard_do_proprio_oficio(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)

        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)
        wizard_url = reverse('eventos:oficio-step1', kwargs={'pk': self.oficio_pt.pk})
        pacote_url = '/guiado/painel/'
        self.assertIn('Abrir', row_html)
        self.assertIn('Abrir', card_html)
        self.assertIn(wizard_url, row_html)
        self.assertIn(wizard_url, card_html)
        self.assertNotIn(pacote_url, row_html)
        self.assertNotIn(pacote_url, card_html)

        oficio_avulso = Oficio.objects.create(
            protocolo='123123123',
            data_criacao=date(2026, 4, 2),
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=Oficio.STATUS_RASCUNHO,
        )
        oficio_avulso.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=oficio_avulso,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=date(2026, 4, 2),
            chegada_data=date(2026, 4, 2),
        )
        response_avulso = self.client.get(reverse('eventos:oficios-global'), {'q': '123123123'})
        avulso_row_html = self._extract_oficio_row_html(response_avulso, oficio_avulso.pk)
        avulso_card_html = self._extract_oficio_card_html(response_avulso, oficio_avulso.pk)
        avulso_wizard_url = reverse('eventos:oficio-step1', kwargs={'pk': oficio_avulso.pk})
        self.assertIn('Abrir', avulso_row_html)
        self.assertIn('Abrir', avulso_card_html)
        self.assertIn(avulso_wizard_url, avulso_row_html)
        self.assertIn(avulso_wizard_url, avulso_card_html)

    def test_lista_global_de_oficios_modo_basico_mostra_apenas_campos_essenciais_e_acoes_do_oficio(self):
        with patch('eventos.views_global.get_document_generation_status') as mocked_status:
            mocked_status.return_value = {'status': 'available', 'errors': []}
            response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)

        table_html = self._extract_oficio_table_html(response)
        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)

        self.assertIn('OFICIO', table_html)
        self.assertIn('DATA', table_html)
        self.assertIn('N&deg; PROTOCOLO', table_html)
        self.assertIn('DESTINO', table_html)
        self.assertIn('SERVIDORES', table_html)
        self.assertIn('VEICULO', table_html)
        self.assertIn('STATUS', table_html)
        self.assertIn('ACOES', table_html)
        self.assertIn('data-label="SERVIDORES">VIAJANTE<', row_html)
        self.assertIn('Excluir', row_html)
        self.assertNotIn('Documentos', row_html)
        self.assertNotIn('Justificativa', row_html)
        self.assertNotIn('Termos de autorizacao', row_html)
        self.assertNotIn('/eventos/documentos/termos/', row_html)
        self.assertNotIn('/justificativa/', row_html)
        self.assertNotIn('oficio-list-card', row_html)
        self.assertNotIn('oficio-list-core-card', row_html)

    def test_lista_global_de_oficios_modo_basico_mantem_abrir_textual_e_acoes_secundarias_so_com_icone(self):
        with patch('eventos.views_global.get_document_generation_status') as mocked_status:
            mocked_status.return_value = {'status': 'available', 'errors': []}
            response = self.client.get(reverse('eventos:oficios-global'))

        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)

        self.assertIn('Abrir cadastro do oficio', row_html)
        self.assertIn('Baixar DOCX do oficio', row_html)
        self.assertIn('Baixar PDF do oficio', row_html)
        self.assertIn('Excluir oficio', row_html)
        self.assertIn('btn-doc-action--primary', row_html)
        self.assertIn('btn-doc-action--secondary is-icon-only', row_html)
        self.assertIn('btn-doc-action--pdf is-icon-only', row_html)
        self.assertIn('btn-doc-action--danger is-icon-only', row_html)

    def test_lista_global_de_roteiros_mantem_acao_abrir_nos_modos_basico_e_completo(self):
        response = self.client.get(reverse('eventos:roteiros-global'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        self.assertIn('oficios-view-pane--basic', html)
        self.assertIn('oficios-view-pane--rich', html)
        self.assertIn('Abrir roteiro', html)
        self.assertIn('>Abrir</span>', html)
        self.assertIn('btn-doc-action--primary', html)

        # A acao precisa existir nas duas visoes padronizadas da lista (tabela + card).
        self.assertGreaterEqual(html.count('aria-label="Abrir roteiro"'), 2)

    def test_lista_global_de_roteiros_aponta_edicao_para_o_roteiro_especifico(self):
        roteiro_avulso = RoteiroEvento.objects.create(
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            tipo=RoteiroEvento.TIPO_AVULSO,
            saida_dt=timezone.make_aware(datetime(2026, 5, 1, 7, 30)),
            chegada_dt=timezone.make_aware(datetime(2026, 5, 1, 11, 45)),
            status=RoteiroEvento.STATUS_RASCUNHO,
        )
        RoteiroEventoDestino.objects.create(
            roteiro=roteiro_avulso,
            estado=self.estado,
            cidade=self.cidade_destino,
            ordem=0,
        )

        response = self.client.get(reverse('eventos:roteiros-global'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        evento_editar_url = reverse(
            'eventos:guiado-etapa-2-editar',
            kwargs={'evento_id': self.evento_pt.pk, 'pk': self.roteiro.pk},
        )
        avulso_editar_url = reverse(
            'eventos:roteiro-avulso-editar',
            kwargs={'pk': roteiro_avulso.pk},
        )

        self.assertGreaterEqual(html.count(f'href="{evento_editar_url}"'), 2)
        self.assertGreaterEqual(html.count(f'href="{avulso_editar_url}"'), 2)

    def test_lista_global_de_roteiros_exibe_exclusao_para_evento_e_avulso(self):
        roteiro_avulso = RoteiroEvento.objects.create(
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            tipo=RoteiroEvento.TIPO_AVULSO,
            saida_dt=timezone.make_aware(datetime(2026, 5, 2, 7, 30)),
            chegada_dt=timezone.make_aware(datetime(2026, 5, 2, 11, 45)),
            status=RoteiroEvento.STATUS_RASCUNHO,
        )
        RoteiroEventoDestino.objects.create(
            roteiro=roteiro_avulso,
            estado=self.estado,
            cidade=self.cidade_destino,
            ordem=0,
        )

        response = self.client.get(reverse('eventos:roteiros-global'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        evento_delete_url = reverse(
            'eventos:guiado-etapa-2-excluir',
            kwargs={'evento_id': self.evento_pt.pk, 'pk': self.roteiro.pk},
        )
        avulso_delete_url = reverse(
            'eventos:roteiro-avulso-excluir',
            kwargs={'pk': roteiro_avulso.pk},
        )

        self.assertIn(evento_delete_url, html)
        self.assertIn(avulso_delete_url, html)
        self.assertGreaterEqual(html.count('method="post"'), 2)

    def test_excluir_roteiro_avulso_remove_registro(self):
        roteiro_avulso = RoteiroEvento.objects.create(
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            tipo=RoteiroEvento.TIPO_AVULSO,
            saida_dt=timezone.make_aware(datetime(2026, 5, 3, 7, 30)),
            chegada_dt=timezone.make_aware(datetime(2026, 5, 3, 11, 45)),
            status=RoteiroEvento.STATUS_RASCUNHO,
        )
        RoteiroEventoDestino.objects.create(
            roteiro=roteiro_avulso,
            estado=self.estado,
            cidade=self.cidade_destino,
            ordem=0,
        )

        response = self.client.post(
            reverse('eventos:roteiro-avulso-excluir', kwargs={'pk': roteiro_avulso.pk}),
            {'return_to': reverse('eventos:roteiros-global')},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse('eventos:roteiros-global'),
            fetch_redirect_response=False,
        )
        self.assertFalse(RoteiroEvento.objects.filter(pk=roteiro_avulso.pk).exists())

    def test_excluir_roteiro_do_evento_remove_registro(self):
        response = self.client.post(
            reverse(
                'eventos:guiado-etapa-2-excluir',
                kwargs={'evento_id': self.evento_pt.pk, 'pk': self.roteiro.pk},
            ),
            {'return_to': reverse('eventos:guiado-etapa-2', kwargs={'evento_id': self.evento_pt.pk})},
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse('eventos:guiado-etapa-2', kwargs={'evento_id': self.evento_pt.pk}),
            fetch_redirect_response=False,
        )
        self.assertFalse(RoteiroEvento.objects.filter(pk=self.roteiro.pk).exists())

    def test_lista_global_de_planos_mantem_acao_abrir_nos_modos_basico_e_completo(self):
        response = self.client.get(reverse('eventos:documentos-planos-trabalho'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        self.assertIn('oficios-view-pane--basic', html)
        self.assertIn('oficios-view-pane--rich', html)
        self.assertIn('Abrir plano de trabalho', html)
        self.assertIn('btn-doc-action--primary', html)

        # A mesma acao precisa existir nas duas visoes (tabela + card).
        self.assertGreaterEqual(html.count('aria-label="Abrir plano de trabalho"'), 2)

    def test_lista_global_de_oficios_exibe_todos_os_primeiros_nomes_no_modo_basico_sem_resumo(self):
        viajante_extra_1 = Viajante.objects.create(
            nome='Yara Villela de Barros',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='23921232095',
            telefone='41977770001',
            unidade_lotacao=self.unidade,
            rg='RGRESUMO1',
        )
        viajante_extra_2 = Viajante.objects.create(
            nome='Adilson Jose Domingues',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='29774396047',
            telefone='41977770002',
            unidade_lotacao=self.unidade,
            rg='RGRESUMO2',
        )
        self.oficio_pt.viajantes.add(viajante_extra_1, viajante_extra_2)

        response = self.client.get(reverse('eventos:oficios-global'))
        basic_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)

        self.assertIn('VIAJANTE, YARA, ADILSON', basic_html)
        self.assertNotIn('+2', basic_html)
        self.assertNotIn('GLOBAL', basic_html)
        self.assertNotIn('Villela', basic_html)
        self.assertNotIn('Domingues', basic_html)

    def test_lista_global_de_oficios_abre_justificativa_no_cadastro_do_oficio_e_nao_no_modulo_global(self):
        justificativa = Justificativa.objects.create(
            oficio=self.oficio_pt,
            texto='Justificativa vinculada ao oficio para o teste.',
        )

        response = self.client.get(reverse('eventos:oficios-global'))
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)

        self.assertIn(reverse('eventos:oficio-justificativa', kwargs={'pk': self.oficio_pt.pk}), card_html)
        self.assertNotIn(
            reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': justificativa.pk}),
            card_html,
        )

    def test_lista_global_de_oficios_exibe_veiculo_e_status_em_linha_compacta(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)
        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)

        self.assertIn('data-label="VEICULO"', row_html)
        self.assertIn('class="oficio-list-badge is-rascunho"', row_html)
        self.assertIn('Rascunho', row_html)

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
        future_row = self._extract_oficio_row_html(response, created_oficios[0].pk)
        today_row = self._extract_oficio_row_html(response, created_oficios[1].pk)
        past_row = self._extract_oficio_row_html(response, created_oficios[2].pk)

        self.assertIn(f'{(hoje + timedelta(days=5)):%d/%m/%Y}', future_row)
        self.assertIn(f'{(hoje - timedelta(days=1)):%d/%m/%Y}', today_row)
        self.assertIn(f'{(hoje - timedelta(days=4)):%d/%m/%Y}', past_row)
        self.assertContains(response, 'faltam')
        self.assertContains(response, 'aconteceu ha')
        self.assertTrue(
            any(token in response.content.decode('utf-8') for token in ['acontece hoje', 'termina hoje', 'comecou hoje']),
            "Esperava encontrar um rótulo relativo para viagem no dia atual.",
        )
        self.assertNotIn('Em andamento', future_row)
        self.assertNotIn('Em andamento', today_row)
        self.assertNotIn('Em andamento', past_row)
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
        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)
        self.assertIn('SEGUNDO VIAJANTE', response.content.decode('utf-8'))
        self.assertNotIn('Justificativa', row_html)
        self.assertNotIn('Termos de autorizacao', row_html)
        self.assertNotIn('Contexto do oficio', row_html)
        self.assertNotIn('Motivo', row_html)
        self.assertNotIn('Documentos', row_html)
        self.assertIn('Justificativa', card_html)
        self.assertIn('Termos de autorizacao', card_html)
        self.assertIn('Justificativa extensa de teste', card_html)
        self.assertIn('SEGUNDO VIAJANTE', card_html)
        self.assertEqual(row_html.count(self.oficio_pt.protocolo_formatado), 1)

    def test_lista_global_de_oficios_modo_simples_nao_exibe_blocos_de_justificativa_e_termos(self):
        Justificativa.objects.create(
            oficio=self.oficio_pt,
            texto='Justificativa do modo completo.',
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

        response = self.client.get(reverse('eventos:oficios-global'))
        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)

        self.assertNotIn('Justificativa', row_html)
        self.assertNotIn('Termos de autorizacao', row_html)
        self.assertIn('Justificativa', card_html)
        self.assertIn('Termos de autorizacao', card_html)

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
        content = response.content.decode('utf-8')
        row_html = self._extract_oficio_row_html(response, oficio_avulso.pk)
        card_html = self._extract_oficio_card_html(response, oficio_avulso.pk)

        self.assertIn('oficios-table-panel', content)
        self.assertIn('oficio-list-grid', content)
        self.assertIn('oficios-table', content)
        self.assertIn('Spin', row_html)
        self.assertIn('Spin', card_html)
        self.assertIn('Finalizado', row_html)
        self.assertIn('oficio-list-card', content)
        self.assertNotIn('oficio-list-subcard', row_html)
        self.assertNotIn('Contexto do oficio', content)
        self.assertNotIn('Aconteceu ha 8 dia(s)', content)
        self.assertNotIn('Oficio avulso', content)

    def test_lista_global_de_oficios_resume_servidores_quando_ha_excesso(self):
        extras = [
            Viajante.objects.create(
                nome=f'{primeiro_nome} Extra {indice}',
                status=Viajante.STATUS_FINALIZADO,
                cargo=self.cargo,
                cpf=f'1535094605{indice}',
                telefone=f'4198888777{indice}',
                unidade_lotacao=self.unidade,
                rg=f'RGEXTRA{indice}',
            )
            for indice, primeiro_nome in enumerate(['ALFA', 'BETA', 'GAMA'])
        ]
        self.oficio_pt.viajantes.add(*extras)

        response = self.client.get(reverse('eventos:oficios-global'))
        row_html = self._extract_oficio_row_html(response, self.oficio_pt.pk)

        self.assertIn('VIAJANTE, ALFA, BETA, GAMA', row_html)
        self.assertNotIn('+3', row_html)
        self.assertNotIn('Extra 0', row_html)
        self.assertNotIn('Extra 1', row_html)
        self.assertNotIn('Extra 2', row_html)

    def test_lista_global_de_oficios_aplica_badges_de_status_conforme_situacao(self):
        hoje = timezone.localdate()
        cenarios = [
            ('111111110', Oficio.STATUS_FINALIZADO, hoje - timedelta(days=5), hoje - timedelta(days=3), 'is-finalizado', 'Finalizado'),
            ('222222221', Oficio.STATUS_FINALIZADO, hoje, hoje + timedelta(days=1), 'is-finalizado', 'Finalizado'),
            ('333333332', Oficio.STATUS_FINALIZADO, hoje + timedelta(days=4), hoje + timedelta(days=5), 'is-finalizado', 'Finalizado'),
            ('444444443', Oficio.STATUS_RASCUNHO, hoje + timedelta(days=1), hoje + timedelta(days=2), 'is-rascunho', 'Rascunho'),
            ('555555554', Oficio.STATUS_RASCUNHO, hoje, hoje, 'is-rascunho', 'Rascunho'),
        ]
        oficios = []
        for protocolo, status, inicio, fim, _css_class, _label in cenarios:
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

        for oficio, (_, _, _, _, css_class, label) in zip(oficios, cenarios):
            row_html = self._extract_oficio_row_html(response, oficio.pk)
            self.assertIn(f'class="oficio-list-badge {css_class}"', row_html)
            self.assertIn(label, row_html)
            self.assertNotIn('Documento', row_html)
            self.assertNotIn('Viagem', row_html)
            self.assertNotIn('Em andamento', row_html)

    def test_lista_global_de_oficios_expoe_links_de_download_direto_sem_fluxo_documental_intermediario(self):
        with patch('eventos.views_global.get_document_generation_status') as mocked_status:
            mocked_status.return_value = {'status': 'available', 'errors': []}
            response = self.client.get(reverse('eventos:oficios-global'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertNotIn('Contexto documental', content)
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

    def test_lista_global_de_oficios_mantem_tabela_compacta_com_css_dedicado(self):
        css = (Path(settings.BASE_DIR) / 'static' / 'css' / 'style.css').read_text(encoding='utf-8')

        self.assertIn('.oficios-list-shell {', css)
        self.assertIn('.system-document-top > .page-header-cadastro.system-list-header--standard {', css)
        self.assertIn('.system-document-filter {', css)
        self.assertIn('.system-document-filter__grid {', css)
        self.assertIn('.system-document-filter__action-btn--submit {', css)
        self.assertIn('.system-document-filter__summary-pill {', css)
        self.assertIn('.system-list-view-toggle,', css)
        self.assertIn('.oficios-view-toggle {', css)
        self.assertIn('.oficios-view-pane--rich {', css)
        self.assertIn('[data-view-mode="basic"] .oficios-view-pane--rich {', css)
        self.assertIn('[data-view-mode="rich"] .oficios-view-pane--basic {', css)
        self.assertIn('.oficio-list-driver-carona-grid {', css)
        self.assertIn('.oficios-table-panel {', css)
        self.assertIn('.oficios-table {', css)
        self.assertIn('.oficios-table thead th {', css)
        self.assertIn('.oficios-table tbody td {', css)
        self.assertIn('.oficios-table__actions {', css)
        self.assertIn('.oficio-list-card {', css)
        self.assertIn('.oficio-list-surface {', css)
        self.assertIn('.oficio-list-surface--feature {', css)
        self.assertIn('.oficio-list-surface--panel {', css)
        self.assertIn('.oficio-list-surface--soft {', css)
        self.assertIn('.oficio-list-surface--footer {', css)
        self.assertIn('backdrop-filter: blur(var(--oficio-surface-local-blur));', css)
        self.assertIn('.oficio-list-rich-layout {', css)
        self.assertIn('.oficios-fab {', css)
        self.assertIn('padding-bottom: 6rem;', css)
        self.assertIn('white-space: nowrap;', css)
        self.assertIn('border-radius: 1rem;', css)

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

    def test_lista_global_de_oficios_filtra_por_data_com_presets_e_intervalo(self):
        hoje = timezone.localdate()
        oficio_passado = self._criar_oficio_ordenacao(
            numero=14,
            protocolo='700000014',
            data_criacao=hoje - timedelta(days=10),
            updated_at=timezone.now(),
            data_evento=hoje - timedelta(days=8),
        )
        oficio_futuro = self._criar_oficio_ordenacao(
            numero=15,
            protocolo='700000015',
            data_criacao=hoje,
            updated_at=timezone.now(),
            data_evento=hoje + timedelta(days=4),
        )

        response_scope = self.client.get(reverse('eventos:oficios-global'), {'q': 'ORDTEST', 'date_scope': 'upcoming'})
        order_scope = self._extract_oficio_ids_order(response_scope)
        self.assertIn(oficio_futuro.pk, order_scope)
        self.assertNotIn(oficio_passado.pk, order_scope)

        response_range = self.client.get(
            reverse('eventos:oficios-global'),
            {
                'q': 'ORDTEST',
                'date_start': (hoje - timedelta(days=9)).isoformat(),
                'date_end': (hoje - timedelta(days=7)).isoformat(),
            },
        )
        order_range = self._extract_oficio_ids_order(response_range)
        self.assertIn(oficio_passado.pk, order_range)
        self.assertNotIn(oficio_futuro.pk, order_range)

    def test_lista_global_de_oficios_termos_exibem_pdf_docx_e_sem_resumo(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertEqual(response.status_code, 200)

        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)
        self.assertIn('Termos de autorizacao', card_html)
        self.assertIn('bi-filetype-docx', card_html)
        self.assertIn('bi-filetype-pdf', card_html)
        self.assertNotIn('Resumo', card_html)

    def test_lista_global_de_oficios_renderiza_layout_de_carona_no_bloco_motorista(self):
        self.oficio_pt.motorista = 'MOTORISTA CARONA'
        self.oficio_pt.motorista_oficio_numero = 999
        self.oficio_pt.motorista_protocolo = '556677889'
        self.oficio_pt.save(update_fields=['motorista', 'motorista_oficio_numero', 'motorista_protocolo'])

        response = self.client.get(reverse('eventos:oficios-global'))
        card_html = self._extract_oficio_card_html(response, self.oficio_pt.pk)

        self.assertIn('oficio-list-driver-carona-grid', card_html)
        self.assertIn('Carona', card_html)
        self.assertIn('Oficio do motorista', card_html)
        self.assertIn('556677889', card_html)

    def test_lista_global_de_oficios_expoe_hooks_de_filtro_em_tempo_real(self):
        response = self.client.get(reverse('eventos:oficios-global'))
        self.assertContains(response, 'data-list-autosubmit-form', html=False)
        self.assertContains(response, 'data-list-autosubmit', html=False)

        js = (Path(settings.BASE_DIR) / 'static' / 'js' / 'list_standard.js').read_text(encoding='utf-8')
        self.assertIn('data-list-autosubmit-form', js)
        self.assertIn('data-list-autosubmit', js)
        self.assertIn('scheduleSubmit', js)

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
        self.assertContains(response_pt, 'system-list-view-toggle', html=False)
        self.assertContains(response_pt, 'oficios-view-pane--basic', html=False)
        self.assertContains(response_pt, 'oficios-view-pane--rich', html=False)

        response_os = self.client.get(reverse('eventos:documentos-ordens-servico'))
        self.assertContains(response_os, 'Ordens de servi')
        self.assertContains(response_os, self.evento_os.titulo)
        self.assertContains(response_os, self.oficio_os.numero_formatado)

        response_termos = self.client.get(reverse('eventos:documentos-termos'))
        self.assertContains(response_termos, self.viajante.nome)
        self.assertContains(response_termos, self.evento_pt.titulo)
        self.assertContains(response_termos, 'Novo termo')
        self.assertContains(response_termos, 'Londrina/PR')
        self.assertContains(response_termos, '10/03/2026')
        self.assertContains(response_termos, 'VIAJANTE GLOBAL')
        self.assertContains(response_termos, 'TA-0001')

    def test_listas_documentais_prioritarias_compartilham_topo_e_filtros_padronizados(self):
        casos = [
            reverse('eventos:documentos-planos-trabalho'),
            reverse('eventos:documentos-ordens-servico'),
            reverse('eventos:documentos-justificativas'),
            reverse('eventos:documentos-termos'),
        ]

        for url in casos:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, 'data-list-view-root', html=False)
            self.assertContains(response, 'system-list-view-toggle', html=False)
            self.assertContains(response, 'data-list-view-toggle="rich"', html=False)
            self.assertContains(response, 'data-list-view-toggle="basic"', html=False)
            self.assertNotContains(response, 'system-document-filter__summary-pill', html=False)
            self.assertContains(response, 'system-document-filter__action-btn--submit', html=False)
            self.assertContains(response, 'system-document-filter__action-btn--clear', html=False)
            self.assertContains(response, 'oficios-view-pane--basic', html=False)
            self.assertContains(response, 'oficios-view-pane--rich', html=False)
            self.assertNotContains(response, 'Contexto documental')
            self.assertNotContains(response, 'Documentos vinculados')
            self.assertNotContains(response, 'A lista e atualizada automaticamente', html=False)

    def test_lista_de_planos_de_trabalho_nao_exibe_bloco_de_vinculos_no_card(self):
        oficio_extra = Oficio.objects.create(
            evento=self.evento_pt,
            protocolo='333444555',
            data_criacao=date(2026, 3, 2),
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=Oficio.STATUS_FINALIZADO,
        )
        oficio_extra.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=oficio_extra,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=date(2026, 3, 11),
            chegada_data=date(2026, 3, 11),
        )
        plano = PlanoTrabalho.objects.create(
            observacoes='Plano multi-oficios do evento',
            status=PlanoTrabalho.STATUS_FINALIZADO,
            quantidade_servidores=3,
            diarias_quantidade='2,5',
        )
        plano.oficios.add(self.oficio_pt, oficio_extra)

        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho'),
            {'evento_id': str(self.evento_pt.pk)},
        )
        content = response.content.decode('utf-8')

        self.assertContains(response, f'id="plano-card-{plano.pk}"', html=False)
        self.assertIn(self.oficio_pt.numero_formatado, content)
        self.assertIn(oficio_extra.numero_formatado, content)
        self.assertIn('Contexto do plano', content)
        self.assertIn('Valor por servidor', content)
        self.assertIn('Diarias', content)
        self.assertNotIn('Contexto documental', content)
        self.assertNotIn('Vínculos', content)

    def test_lista_de_eventos_exibe_cascata_documental_com_pt_vinculado_por_oficios(self):
        oficio_extra = Oficio.objects.create(
            evento=self.evento_pt,
            protocolo='444555666',
            data_criacao=date(2026, 3, 3),
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=Oficio.STATUS_FINALIZADO,
        )
        oficio_extra.viajantes.add(self.viajante)
        OficioTrecho.objects.create(
            oficio=oficio_extra,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_origem,
            destino_estado=self.estado,
            destino_cidade=self.cidade_destino,
            saida_data=date(2026, 3, 12),
            chegada_data=date(2026, 3, 12),
        )
        plano = PlanoTrabalho.objects.create(
            observacoes='Plano em cascata documental',
            status=PlanoTrabalho.STATUS_FINALIZADO,
        )
        plano.oficios.add(self.oficio_pt, oficio_extra)
        ordem = OrdemServico.objects.create(
            oficio=self.oficio_pt,
            finalidade='Ordem em cascata documental',
            status=OrdemServico.STATUS_FINALIZADO,
        )

        response = self.client.get(reverse('eventos:lista'))
        card_html = self._extract_evento_card_html(response, self.evento_pt.pk)

        self.assertIn('Planos de trabalho', card_html)
        self.assertIn('Ordens de servico', card_html)
        self.assertIn('Oficios', card_html)
        self.assertIn(f'PT {plano.numero_formatado or f"#{plano.pk}"}', card_html)
        self.assertIn(f'OS {ordem.numero_formatado or f"#{ordem.pk}"}', card_html)
        self.assertIn(f'Oficio {self.oficio_pt.numero_formatado}', card_html)
        self.assertIn(reverse('eventos:documentos-planos-trabalho-editar', kwargs={'pk': plano.pk}), card_html)
        self.assertIn(reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': ordem.pk}), card_html)

    def test_lista_de_eventos_exibe_acao_exportar_drive_no_card(self):
        response = self.client.get(reverse('eventos:lista'))
        self.assertEqual(response.status_code, 200)

        card_html = self._extract_evento_card_html(response, self.evento_pt.pk)
        self.assertIn('Exportar Drive', card_html)
        self.assertIn(
            reverse('eventos:exportar-google-drive', kwargs={'pk': self.evento_pt.pk}),
            card_html,
        )
        self.assertIn('name="formatos" value="docx"', card_html)
        self.assertIn('name="formatos" value="pdf"', card_html)
        self.assertIn('name="return_to"', card_html)

    @patch('eventos.views.ExportacaoEventoGoogleDriveService.exportar_evento')
    def test_exportacao_google_drive_da_lista_redireciona_para_lista(self, mocked_exportar):
        mocked_exportar.return_value = type(
            'ResultadoExportacao',
            (),
            {
                'success': True,
                'folders_created': 2,
                'files_uploaded': 4,
                'missing_documents': [],
                'partial_errors': [],
                'oficios_processados': 1,
            },
        )()

        response = self.client.post(
            reverse('eventos:exportar-google-drive', kwargs={'pk': self.evento_pt.pk}),
            data={
                'formatos': ['docx', 'pdf'],
                'return_to': reverse('eventos:lista'),
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('eventos:lista'), fetch_redirect_response=False)

    def test_detalhe_evento_nao_exibe_bloco_de_exportacao_google_drive(self):
        response = self.client.get(reverse('eventos:detalhe', kwargs={'pk': self.evento_pt.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Exportação para Google Drive')
        self.assertNotContains(response, 'Exportar estrutura completa')

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
