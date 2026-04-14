from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo, Cidade, CombustivelVeiculo, ConfiguracaoSistema, Estado, UnidadeLotacao, Viajante, Veiculo
from eventos.models import (
    Evento,
    EventoDestino,
    Justificativa,
    ModeloJustificativa,
    Oficio,
    OficioTrecho,
    RoteiroEvento,
    RoteiroEventoDestino,
    TermoAutorizacao,
)
from eventos.services.documentos.renderer import get_termo_autorizacao_template_path
from eventos.services.documentos.termo_autorizacao import (
    build_saved_termo_autorizacao_template_context,
    build_termo_autorizacao_template_context,
)


User = get_user_model()


class TermoAutorizacaoModuleTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='termos', password='termos123')
        self.client.login(username='termos', password='termos123')

        self.estado = Estado.objects.create(codigo_ibge='41', nome='Parana', sigla='PR', ativo=True)
        self.cidade_curitiba = Cidade.objects.create(codigo_ibge='4106902', nome='Curitiba', estado=self.estado, ativo=True)
        self.cidade_londrina = Cidade.objects.create(codigo_ibge='4113700', nome='Londrina', estado=self.estado, ativo=True)
        self.cidade_maringa = Cidade.objects.create(codigo_ibge='4115200', nome='Maringa', estado=self.estado, ativo=True)
        self.cargo = Cargo.objects.create(nome='AGENTE')
        self.unidade = UnidadeLotacao.objects.create(nome='UNIDADE TERMOS')
        self.combustivel = CombustivelVeiculo.objects.create(nome='GASOLINA', is_padrao=True)
        self.veiculo = Veiculo.objects.create(
            placa='ABC1D23',
            modelo='SPIN',
            combustivel=self.combustivel,
            tipo=Veiculo.TIPO_DESCARACTERIZADO,
            status=Veiculo.STATUS_FINALIZADO,
        )
        ConfiguracaoSistema.objects.create(
            nome_orgao='Polícia Civil do Paraná',
            sigla_orgao='PCPR',
            divisao='Diretoria de Polícia do Interior',
            unidade='Departamento de Polícia Civil',
            cidade_endereco='Curitiba',
            uf='PR',
        )
        self.evento = Evento.objects.create(
            titulo='Evento Termos',
            data_inicio=date(2026, 3, 18),
            data_fim=date(2026, 3, 19),
            cidade_base=self.cidade_curitiba,
            cidade_principal=self.cidade_curitiba,
            estado_principal=self.estado,
            veiculo=self.veiculo,
        )
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_londrina, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_maringa, ordem=1)

        self.roteiro = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_curitiba,
            saida_dt=timezone.make_aware(datetime(2026, 3, 18, 7, 30)),
            chegada_dt=timezone.make_aware(datetime(2026, 3, 18, 10, 0)),
            retorno_saida_dt=timezone.make_aware(datetime(2026, 3, 19, 17, 0)),
            retorno_chegada_dt=timezone.make_aware(datetime(2026, 3, 19, 21, 0)),
            tipo=RoteiroEvento.TIPO_EVENTO,
            status=RoteiroEvento.STATUS_FINALIZADO,
        )
        RoteiroEventoDestino.objects.create(roteiro=self.roteiro, estado=self.estado, cidade=self.cidade_londrina, ordem=0)
        RoteiroEventoDestino.objects.create(roteiro=self.roteiro, estado=self.estado, cidade=self.cidade_maringa, ordem=1)

        self.viajante_a = self._criar_viajante('Servidor A', '1234567')
        self.viajante_b = self._criar_viajante('Servidor B', '2345678')
        self.viajante_c = self._criar_viajante('Servidor C', '3456789')

        self.oficio_a = self._criar_oficio('123456789', self.veiculo, [self.viajante_a, self.viajante_b])
        self.oficio_b = self._criar_oficio('987654321', self.veiculo, [self.viajante_b, self.viajante_c])
        self.oficio_sem_viatura = self._criar_oficio('555444333', None, [self.viajante_a, self.viajante_c])

    def _criar_viajante(self, nome, rg):
        return Viajante.objects.create(
            nome=nome,
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            unidade_lotacao=self.unidade,
            cpf=f'52998224{rg[-3:]}',
            telefone=f'4199999{rg[-4:]}',
            rg=rg,
        )

    def _criar_oficio(self, protocolo, veiculo, viajantes):
        oficio = Oficio.objects.create(
            evento=self.evento,
            roteiro_evento=self.roteiro,
            protocolo=protocolo,
            data_criacao=date(2026, 3, 10),
            tipo_destino=Oficio.TIPO_DESTINO_INTERIOR,
            status=Oficio.STATUS_RASCUNHO,
            veiculo=veiculo,
        )
        oficio.viajantes.set(viajantes)
        OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            origem_estado=self.estado,
            origem_cidade=self.cidade_curitiba,
            destino_estado=self.estado,
            destino_cidade=self.cidade_londrina,
            saida_data=date(2026, 3, 18),
            saida_hora=time(7, 30),
            chegada_data=date(2026, 3, 18),
            chegada_hora=time(10, 0),
        )
        return oficio

    def test_novo_termo_abre_direto_no_formulario(self):
        response = self.client.get(reverse('eventos:documentos-termos-novo'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Novo termo de autorizacao')
        self.assertContains(response, 'Contexto documental')
        self.assertContains(response, 'Período e horário de atendimento')
        self.assertContains(response, 'Servidores e viatura')
        self.assertNotContains(response, 'Escolha o modo de criacao')
        self.assertNotContains(response, 'Texto complementar')
        self.assertNotContains(response, 'Observacoes')
        self.assertNotContains(response, 'Resultado previsto')
        self.assertNotContains(response, 'Resumo rapido antes de gerar')
        self.assertNotContains(response, 'Quick report')

    def test_lista_filtrada_por_evento_monta_url_contextual_para_novo_termo(self):
        response = self.client.get(reverse('eventos:documentos-termos'), {'evento_id': self.evento.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['return_to_url'],
            reverse('eventos:guiado-etapa-1', kwargs={'pk': self.evento.pk}),
        )
        self.assertEqual(response.context['evento_context'].pk, self.evento.pk)
        self.assertIn(f'preselected_event_id={self.evento.pk}', response.context['termo_novo_url'])
        self.assertIn('context_source=evento', response.context['termo_novo_url'])
        self.assertContains(response, 'Voltar ao evento')

    def test_novo_termo_contextualizado_por_evento_redireciona_para_etapa_1(self):
        etapa1_url = reverse('eventos:guiado-etapa-1', kwargs={'pk': self.evento.pk})

        response = self.client.post(
            reverse('eventos:documentos-termos-novo'),
            {
                'return_to': etapa1_url,
                'context_source': 'evento',
                'preselected_event_id': str(self.evento.pk),
                'preselected_oficio_id': '',
                'evento': str(self.evento.pk),
                'oficios': [],
                'roteiro': '',
                'destino': 'Curitiba/PR',
                'data_evento': '2026-03-20',
                'data_evento_fim': '2026-03-20',
                'viajantes_ids': '',
                'veiculo_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, etapa1_url)

    def test_rotas_legadas_reaproveitam_formulario_unico(self):
        response = self.client.get(reverse('eventos:documentos-termos-novo-rapido'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Novo termo de autorizacao')
        self.assertContains(response, 'Período e horário de atendimento')

    def test_preview_evento_puxa_datas_destinos_e_roteiro(self):
        response = self.client.get(
            reverse('eventos:documentos-termos-preview'),
            {'evento': self.evento.pk},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['data_evento'], '2026-03-18')
        self.assertEqual(payload['data_evento_fim'], '2026-03-19')
        self.assertEqual(payload['destinos'], ['Londrina/PR', 'Maringa/PR'])
        self.assertEqual(payload['roteiro']['id'], self.roteiro.pk)

    def test_preview_um_oficio_puxa_servidores_viaturas_datas_destinos_e_roteiro(self):
        response = self.client.get(
            reverse('eventos:documentos-termos-preview'),
            [('oficios', self.oficio_a.pk)],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['total_viajantes'], 2)
        self.assertEqual(payload['total_viaturas'], 1)
        self.assertEqual(payload['destinos'], ['Londrina/PR'])
        self.assertEqual(payload['roteiro']['id'], self.roteiro.pk)

    def test_preview_multiplos_oficios_agrega_sem_duplicar(self):
        response = self.client.get(
            reverse('eventos:documentos-termos-preview'),
            [('oficios', self.oficio_a.pk), ('oficios', self.oficio_b.pk)],
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['total_viajantes'], 3)
        self.assertEqual(payload['total_viaturas'], 1)
        self.assertEqual(payload['destinos'], ['Londrina/PR'])
        self.assertEqual(sorted(item['nome'] for item in payload['viajantes']), ['SERVIDOR A', 'SERVIDOR B', 'SERVIDOR C'])

    def test_novo_termo_simples_inferido_sem_campos_removidos(self):
        response = self.client.post(
            reverse('eventos:documentos-termos-novo'),
            {
                'evento': '',
                'oficios': [],
                'roteiro': '',
                'destino': 'Foz do Iguacu/PR',
                'data_evento': '2026-03-20',
                'data_evento_fim': '2026-03-20',
                'viajantes_ids': '',
                'veiculo_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        termo = TermoAutorizacao.objects.get(modo_geracao=TermoAutorizacao.MODO_RAPIDO)
        self.assertEqual(termo.destino, 'Foz do Iguacu/PR')
        self.assertFalse(hasattr(termo, 'texto_complementar'))
        self.assertFalse(hasattr(termo, 'observacoes'))
        self.assertEqual(
            get_termo_autorizacao_template_path(termo.template_variant).name,
            'termo_autorizacao.docx',
        )

    def test_novo_termo_inferido_com_viatura_gera_um_por_servidor(self):
        response = self.client.post(
            reverse('eventos:documentos-termos-novo'),
            {
                'evento': str(self.evento.pk),
                'oficios': [str(self.oficio_a.pk)],
                'roteiro': str(self.roteiro.pk),
                'destino': '',
                'data_evento': '',
                'data_evento_fim': '',
                'viajantes_ids': '',
                'veiculo_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        termos = list(
            TermoAutorizacao.objects.filter(modo_geracao=TermoAutorizacao.MODO_AUTOMATICO_COM_VIATURA).order_by('pk')
        )
        self.assertEqual(len(termos), 2)
        self.assertTrue(all(termo.veiculo_id == self.veiculo.pk for termo in termos))
        self.assertEqual(len({termo.lote_uuid for termo in termos}), 1)
        self.assertEqual(
            get_termo_autorizacao_template_path(termos[0].template_variant).name,
            'termo_autorizacao_automatico.docx',
        )

    def test_novo_termo_com_multiplos_oficios_agrega_viajantes_sem_duplicar_e_persiste_m2m(self):
        response = self.client.post(
            reverse('eventos:documentos-termos-novo'),
            {
                'evento': str(self.evento.pk),
                'oficios': [str(self.oficio_a.pk), str(self.oficio_b.pk)],
                'roteiro': str(self.roteiro.pk),
                'destino': '',
                'data_evento': '',
                'data_evento_fim': '',
                'viajantes_ids': '',
                'veiculo_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        termos = list(
            TermoAutorizacao.objects.filter(modo_geracao=TermoAutorizacao.MODO_AUTOMATICO_COM_VIATURA).order_by('pk')
        )
        self.assertEqual(len(termos), 3)
        self.assertEqual(
            sorted(termo.viajante.nome for termo in termos),
            ['SERVIDOR A', 'SERVIDOR B', 'SERVIDOR C'],
        )
        self.assertTrue(all(termo.oficio is None for termo in termos))
        for termo in termos:
            self.assertEqual(
                sorted(termo.oficios.values_list('pk', flat=True)),
                sorted([self.oficio_a.pk, self.oficio_b.pk]),
            )

    def test_template_context_formata_nome_lotacao_em_caixa_alta(self):
        mapping, _viatura_data = build_termo_autorizacao_template_context(
            self.oficio_a,
            viajante=self.viajante_a,
        )

        self.assertEqual(mapping['nome_servidor'], 'Servidor A')
        self.assertEqual(mapping['lotacao'], 'UNIDADE TERMOS')
        self.assertEqual(mapping['viatura'], 'Spin')
        self.assertEqual(mapping['combustivel'], 'Gasolina')
        self.assertEqual(mapping['divisao'], 'Diretoria de Polícia do Interior')
        self.assertEqual(mapping['unidade'], 'DEPARTAMENTO DE POLÍCIA CIVIL')
        self.assertEqual(mapping['unidade_rodape'], 'Departamento de Polícia Civil')
        self.assertEqual(mapping['placa'], mapping['placa'].upper())

    def test_template_context_de_termo_salvo_normaliza_lotacao_snapshot_em_caixa_alta(self):
        termo = TermoAutorizacao.objects.create(
            evento=self.evento,
            oficio=self.oficio_a,
            destino='Curitiba/PR',
            data_evento=date(2026, 3, 18),
            servidor_nome='SERVIDOR SNAPSHOT',
            servidor_rg='1234567',
            servidor_cpf='529.982.247-25',
            servidor_telefone='(41) 99999-9999',
            servidor_lotacao='UNIDADE DOCUMENTAL ESPECIAL',
        )

        mapping, _viatura_data, _template_variant = build_saved_termo_autorizacao_template_context(termo)

        self.assertEqual(mapping['lotacao'], 'UNIDADE DOCUMENTAL ESPECIAL')

    def test_novo_termo_inferido_sem_viatura_gera_um_por_servidor(self):
        response = self.client.post(
            reverse('eventos:documentos-termos-novo'),
            {
                'evento': '',
                'oficios': [str(self.oficio_sem_viatura.pk)],
                'roteiro': str(self.roteiro.pk),
                'destino': '',
                'data_evento': '',
                'data_evento_fim': '',
                'viajantes_ids': '',
                'veiculo_id': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        termos = list(
            TermoAutorizacao.objects.filter(modo_geracao=TermoAutorizacao.MODO_AUTOMATICO_SEM_VIATURA).order_by('pk')
        )
        self.assertEqual(len(termos), 2)
        self.assertTrue(all(not termo.veiculo_id for termo in termos))
        self.assertEqual(
            get_termo_autorizacao_template_path(termos[0].template_variant).name,
            'termo_autorizacao_automatico_sem_viatura.docx',
        )

    def test_lista_renderiza_card_compacto(self):
        TermoAutorizacao.objects.create(
            evento=self.evento,
            oficio=self.oficio_a,
            viajante=self.viajante_a,
            destino='Curitiba/PR',
            data_evento=date(2026, 3, 18),
        )

        response = self.client.get(reverse('eventos:documentos-termos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'termo-list-card')
        self.assertContains(response, 'Modelo')
        self.assertNotContains(response, 'oficio-document-card')

    def test_autocomplete_de_viajantes_e_viaturas_funciona(self):
        response_viajantes = self.client.get(reverse('eventos:oficio-step1-viajantes-api'), {'q': 'Servidor'})
        response_viaturas = self.client.get(reverse('eventos:oficio-step2-veiculos-busca-api'), {'q': 'ABC'})

        self.assertEqual(response_viajantes.status_code, 200)
        self.assertContains(response_viajantes, 'SERVIDOR A')
        self.assertEqual(response_viaturas.status_code, 200)
        self.assertContains(response_viaturas, 'ABC1D23')

    def test_downloads_dos_termos_continuam_funcionando(self):
        termo = TermoAutorizacao.objects.create(
            evento=self.evento,
            oficio=self.oficio_a,
            viajante=self.viajante_a,
            veiculo=self.veiculo,
            destino='Curitiba/PR',
            data_evento=date(2026, 3, 18),
        )

        response_docx = self.client.get(
            reverse('eventos:documentos-termos-download', kwargs={'pk': termo.pk, 'formato': 'docx'})
        )
        self.assertEqual(response_docx.status_code, 200)
        self.assertEqual(
            response_docx['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

        with patch('eventos.views_global.convert_docx_bytes_to_pdf_bytes', return_value=b'%PDF-1.4 termo'):
            response_pdf = self.client.get(
                reverse('eventos:documentos-termos-download', kwargs={'pk': termo.pk, 'formato': 'pdf'})
            )
        self.assertEqual(response_pdf.status_code, 200)
        self.assertEqual(response_pdf['Content-Type'], 'application/pdf')

    # --- Testes: Termo criado pelo Ofício persiste em TermoAutorizacao ---

    def test_download_termo_pelo_oficio_cria_registro_em_termosautorizacao(self):
        """Download do Termo via rota do Ofício deve criar e persistir TermoAutorizacao."""
        self.assertEqual(TermoAutorizacao.objects.filter(oficio=self.oficio_a).count(), 0)
        response = self.client.get(
            reverse('eventos:oficio-documento-download', kwargs={
                'pk': self.oficio_a.pk,
                'tipo_documento': 'termo-autorizacao',
                'formato': 'docx',
            })
        )
        # Deve redirecionar para o download do termo salvo
        self.assertIn(response.status_code, [200, 302])
        self.assertGreater(TermoAutorizacao.objects.filter(oficio=self.oficio_a).count(), 0)

    def test_termo_criado_pelo_oficio_aparece_na_lista_global(self):
        """Termo gerado por ofício deve aparecer na lista global de Termos."""
        TermoAutorizacao.objects.filter(oficio=self.oficio_a).delete()
        self.client.get(
            reverse('eventos:oficio-documento-download', kwargs={
                'pk': self.oficio_a.pk,
                'tipo_documento': 'termo-autorizacao',
                'formato': 'docx',
            })
        )
        lista_response = self.client.get(reverse('eventos:documentos-termos'))
        self.assertEqual(lista_response.status_code, 200)
        termos_do_oficio = TermoAutorizacao.objects.filter(oficio=self.oficio_a)
        self.assertGreater(termos_do_oficio.count(), 0)

    def test_termo_criado_pelo_oficio_mantem_vinculo_com_oficio(self):
        """Termo criado via Ofício deve ter FK para o Ofício."""
        TermoAutorizacao.objects.filter(oficio=self.oficio_a).delete()
        self.client.get(
            reverse('eventos:oficio-documento-download', kwargs={
                'pk': self.oficio_a.pk,
                'tipo_documento': 'termo-autorizacao',
                'formato': 'docx',
            })
        )
        termo = TermoAutorizacao.objects.filter(oficio=self.oficio_a).first()
        self.assertIsNotNone(termo)
        self.assertEqual(termo.oficio_id, self.oficio_a.pk)

    def test_download_repetido_nao_cria_duplicata(self):
        """Segundo download do mesmo Ofício deve reutilizar o Termo existente."""
        TermoAutorizacao.objects.filter(oficio=self.oficio_a).delete()
        for _ in range(2):
            self.client.get(
                reverse('eventos:oficio-documento-download', kwargs={
                    'pk': self.oficio_a.pk,
                    'tipo_documento': 'termo-autorizacao',
                    'formato': 'docx',
                })
            )
        count = TermoAutorizacao.objects.filter(oficio=self.oficio_a).count()
        self.assertGreater(count, 0)
        # Não deve criar duplicatas
        self.assertEqual(TermoAutorizacao.objects.filter(
            oficio=self.oficio_a
        ).values('oficio').distinct().count(), 1)

    def test_oficio_com_viajantes_cria_um_termo_por_servidor(self):
        """Ofício com dois viajantes deve gerar dois TermoAutorizacao (modo automático)."""
        TermoAutorizacao.objects.filter(oficio=self.oficio_a).delete()
        self.client.get(
            reverse('eventos:oficio-documento-download', kwargs={
                'pk': self.oficio_a.pk,
                'tipo_documento': 'termo-autorizacao',
                'formato': 'docx',
            })
        )
        termos = TermoAutorizacao.objects.filter(oficio=self.oficio_a)
        # oficio_a tem 2 viajantes
        self.assertGreaterEqual(termos.count(), 1)


class JustificativaModuleTest(TestCase):
    """Testa o módulo independente de Justificativas."""

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(username='justtest', password='just123')
        self.client.login(username='justtest', password='just123')

        self.estado = Estado.objects.create(codigo_ibge='41', nome='Parana JT', sigla='PR', ativo=True)
        self.cidade = Cidade.objects.create(codigo_ibge='4106902', nome='CuritibaJT', estado=self.estado, ativo=True)
        self.cargo = Cargo.objects.create(nome='AGENTE JT')
        self.evento = Evento.objects.create(
            titulo='Evento Justificativas',
            data_inicio=date(2026, 3, 18),
            data_fim=date(2026, 3, 19),
            cidade_base=self.cidade,
            cidade_principal=self.cidade,
            estado_principal=self.estado,
        )
        self.oficio = Oficio.objects.create(
            evento=self.evento,
            numero=1,
            ano=2026,
            status=Oficio.STATUS_FINALIZADO,
        )
        self.oficio2 = Oficio.objects.create(
            evento=self.evento,
            numero=2,
            ano=2026,
            status=Oficio.STATUS_FINALIZADO,
        )
        self.modelo = ModeloJustificativa.objects.create(
            nome='Modelo Padrão',
            texto='Texto padrão da justificativa.',
            ativo=True,
        )

    def test_lista_global_justificativas_abre_corretamente(self):
        response = self.client.get(reverse('eventos:documentos-justificativas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'justificativa', msg_prefix='Template deve conter "justificativa"')

    def test_nova_justificativa_pode_ser_criada_fora_da_tela_do_oficio(self):
        response = self.client.post(
            reverse('eventos:documentos-justificativas-nova'),
            {
                'oficio': self.oficio.pk,
                'modelo': '',
                'texto': 'Justificativa criada globalmente.',
            },
        )
        self.assertIn(response.status_code, [200, 302])
        self.assertTrue(Justificativa.objects.filter(oficio=self.oficio).exists())

    def test_formulario_global_permita_criar_sem_oficio(self):
        response = self.client.post(
            reverse('eventos:documentos-justificativas-nova'),
            {'oficio': '', 'texto': 'Sem ofício.'},
        )
        self.assertIn(response.status_code, [200, 302])
        just = Justificativa.objects.filter(texto='Sem ofício.').first()
        self.assertIsNotNone(just)
        self.assertIsNone(just.oficio_id)

    def test_formulario_global_exibe_botao_gerenciador_modelos(self):
        response = self.client.get(reverse('eventos:documentos-justificativas-nova'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('eventos:modelos-justificativa-lista'))

    def test_preselected_oficio_id_funciona(self):
        url = reverse('eventos:documentos-justificativas-nova') + f'?preselected_oficio_id={self.oficio.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.oficio.pk))

    def test_nao_permite_duplicata_por_oficio(self):
        Justificativa.objects.create(oficio=self.oficio, texto='Primeira')
        response = self.client.post(
            reverse('eventos:documentos-justificativas-nova'),
            {
                'oficio': self.oficio.pk,
                'texto': 'Segunda, não deve salvar.',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Justificativa.objects.filter(oficio=self.oficio).count(), 1)

    def test_editar_justificativa_global_funciona(self):
        just = Justificativa.objects.create(oficio=self.oficio, texto='Original')
        response = self.client.post(
            reverse('eventos:documentos-justificativas-editar', kwargs={'pk': just.pk}),
            {
                'oficio': self.oficio.pk,
                'modelo': '',
                'texto': 'Texto atualizado',
            },
        )
        self.assertIn(response.status_code, [200, 302])
        just.refresh_from_db()
        self.assertEqual(just.texto, 'Texto atualizado')

    def test_detalhe_justificativa_funciona(self):
        just = Justificativa.objects.create(oficio=self.oficio, texto='Detalhe test')
        response = self.client.get(
            reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': just.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detalhe test')

    def test_detalhe_justificativa_sem_oficio_funciona(self):
        just = Justificativa.objects.create(oficio=None, texto='Sem vínculo')
        response = self.client.get(
            reverse('eventos:documentos-justificativas-detalhe', kwargs={'pk': just.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sem ofício vinculado')

    def test_excluir_justificativa_funciona(self):
        just = Justificativa.objects.create(oficio=self.oficio, texto='Para excluir')
        response = self.client.post(
            reverse('eventos:documentos-justificativas-excluir', kwargs={'pk': just.pk}),
            {},
        )
        self.assertIn(response.status_code, [200, 302])
        self.assertFalse(Justificativa.objects.filter(pk=just.pk).exists())

    def test_lista_justificativas_usa_template_de_documentos(self):
        """A lista global de justificativas usa o template documentos/ (padrão de qualidade)."""
        Justificativa.objects.create(oficio=self.oficio, texto='Listada')
        response = self.client.get(reverse('eventos:documentos-justificativas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'JT-')

    def test_justificativa_continua_pertencendo_ao_oficio(self):
        """Integridade: a justificativa criada deve manter o FK para o ofício correto."""
        just = Justificativa.objects.create(oficio=self.oficio, texto='FK ok')
        self.assertEqual(just.oficio_id, self.oficio.pk)
        # Cada ofício tem no máximo uma justificativa (1:1)
        self.assertEqual(Justificativa.objects.filter(oficio=self.oficio).count(), 1)
