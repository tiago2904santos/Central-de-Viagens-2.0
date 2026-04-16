from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cadastros.models import AssinaturaConfiguracao, Cargo, Cidade, ConfiguracaoSistema, Estado, Viajante
from eventos.forms import OrdemServicoForm
from eventos.forms import TermoAutorizacaoEdicaoForm
from eventos.models import Evento, Justificativa, Oficio, OrdemServico, PlanoTrabalho, TermoAutorizacao
from eventos.services.contexto_evento import build_contexto_ordem_servico_from_evento
from eventos.services.documento_vinculos import resolver_vinculos_evento, resolver_vinculos_oficio, resolver_vinculos_ordem_servico
from eventos.services.documentos.ordem_servico import build_ordem_servico_model_template_context


User = get_user_model()


class PtOsDesacopladoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='ptos', password='ptos123')
        self.client.login(username='ptos', password='ptos123')

        self.evento = Evento.objects.create(
            titulo='Evento PT/OS',
            data_inicio=date(2026, 3, 10),
            data_fim=date(2026, 3, 12),
            status=Evento.STATUS_EM_ANDAMENTO,
        )
        self.oficio = Oficio.objects.create(
            evento=self.evento,
            protocolo='123456789',
            data_criacao=date(2026, 3, 1),
            status=Oficio.STATUS_RASCUNHO,
        )

    def test_criar_pt_sem_evento(self):
        response = self.client.get(reverse('eventos:documentos-planos-trabalho-novo'))
        self.assertEqual(response.status_code, 302)
        plano = PlanoTrabalho.objects.order_by('-pk').first()
        self.assertIsNotNone(plano)
        self.assertIsNone(plano.evento_id)
        self.assertEqual(plano.status, PlanoTrabalho.STATUS_RASCUNHO)

    def test_criar_pt_sem_oficio(self):
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-novo'),
            {'preselected_event_id': self.evento.pk},
        )
        self.assertEqual(response.status_code, 302)
        plano = PlanoTrabalho.objects.order_by('-pk').first()
        self.assertIsNotNone(plano)
        self.assertEqual(plano.evento_id, self.evento.pk)
        self.assertIsNone(plano.oficio_id)

    def test_criar_os_sem_evento(self):
        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'numero': '10',
                'ano': '2026',
                'data_criacao': '2026-03-10',
                'status': OrdemServico.STATUS_RASCUNHO,
                'finalidade': 'OS sem evento',
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OrdemServico.objects.filter(finalidade='OS sem evento', evento__isnull=True).exists())

    def test_criar_os_sem_oficio(self):
        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'numero': '11',
                'ano': '2026',
                'data_criacao': '2026-03-10',
                'status': OrdemServico.STATUS_RASCUNHO,
                'evento': self.evento.pk,
                'finalidade': 'OS sem oficio',
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            OrdemServico.objects.filter(
                finalidade='OS sem oficio',
                evento=self.evento,
                oficio__isnull=True,
            ).exists()
        )

    def test_preselected_event_id_pt(self):
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-novo'),
            {'preselected_event_id': self.evento.pk},
        )
        self.assertEqual(response.status_code, 302)
        plano = PlanoTrabalho.objects.order_by('-pk').first()
        self.assertIsNotNone(plano)
        self.assertEqual(plano.evento_id, self.evento.pk)

    def test_preselected_event_id_os(self):
        response = self.client.get(
            reverse('eventos:documentos-ordens-servico-novo'),
            {'preselected_event_id': self.evento.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('evento'), self.evento.pk)

    def test_preselected_event_id_os_consolida_viajantes_dos_oficios_sem_duplicar(self):
        cargo = Cargo.objects.create(nome='Agente de Polícia Civil')
        viajante_a = Viajante.objects.create(
            nome='ANA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo,
            cpf='12345678901',
            telefone='41999998888',
        )
        viajante_b = Viajante.objects.create(
            nome='BRUNO LIMA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo,
            cpf='98765432100',
            telefone='41999997777',
        )
        oficio_a = Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)
        oficio_a.viajantes.set([viajante_a])
        oficio_b = Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)
        oficio_b.viajantes.set([viajante_a, viajante_b])

        contexto = build_contexto_ordem_servico_from_evento(self.evento)

        self.assertEqual(contexto['viajantes_ids'], [viajante_a.pk, viajante_b.pk])
        self.assertEqual(
            set(Oficio.objects.filter(eventos=self.evento).values_list('pk', flat=True)),
            {self.oficio.pk, oficio_a.pk, oficio_b.pk},
        )

    def test_preselected_oficio_id_pt(self):
        response = self.client.get(
            reverse('eventos:documentos-planos-trabalho-novo'),
            {'preselected_oficio_id': self.oficio.pk},
        )
        self.assertEqual(response.status_code, 302)
        plano = PlanoTrabalho.objects.order_by('-pk').first()
        self.assertIsNotNone(plano)
        self.assertEqual(plano.oficio_id, self.oficio.pk)

    def test_preselected_oficio_id_os(self):
        response = self.client.get(
            reverse('eventos:documentos-ordens-servico-novo'),
            {'preselected_oficio_id': self.oficio.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('oficio'), self.oficio.pk)

    def test_formulario_os_usa_padrao_visual_e_blocos_reaproveitados(self):
        response = self.client.get(reverse('eventos:documentos-ordens-servico-novo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'oficio-stage-panel')
        self.assertContains(response, 'oficio-stage-intro')
        self.assertContains(response, 'Criação')
        self.assertContains(response, 'Vínculos documentais')
        self.assertContains(response, 'Datas')
        self.assertContains(response, 'evento-dataunica-pill')
        self.assertContains(response, 'Oculta a data final')
        self.assertContains(response, 'wrap-data-fim')
        self.assertContains(response, 'Equipe do ofício')
        self.assertContains(response, 'Destinos')
        self.assertContains(response, 'Motivo')
        self.assertNotContains(response, 'ordem-servico-data-choice-group')
        self.assertNotContains(response, 'Leitura documental')
        self.assertNotContains(response, 'Texto institucional')
        self.assertContains(response, 'js/ordem_servico_form.js')

    def test_os_data_unica_permite_periodo_completo(self):
        cargo = Cargo.objects.create(nome='Agente de Polícia Civil')
        viajante = Viajante.objects.create(
            nome='MARIA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo,
            cpf='12345678901',
            telefone='41999998888',
        )
        estado = Estado.objects.create(nome='Paraná', sigla='PR')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado)
        modelo = self._novo_modelo_motivo('OS com período')

        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'data_criacao': '2026-03-10',
                'status': OrdemServico.STATUS_RASCUNHO,
                'data_deslocamento': '2026-03-12',
                'data_deslocamento_fim': '2026-03-14',
                'modelo_motivo': modelo.pk,
                'motivo_texto': 'Apoio operacional em período estendido.',
                'viajantes': [str(viajante.pk)],
                'destinos_payload': (
                    '[{"estado_id": %d, "estado_sigla": "PR", "cidade_id": %d, "cidade_nome": "Curitiba"}]'
                    % (estado.pk, cidade.pk)
                ),
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem = OrdemServico.objects.get(motivo_texto='Apoio operacional em período estendido.')
        self.assertFalse(ordem.data_unica)
        self.assertEqual(ordem.data_deslocamento, date(2026, 3, 12))
        self.assertEqual(ordem.data_deslocamento_fim, date(2026, 3, 14))

    def test_etapa4_guiado_abre_cadastro_real_pt(self):
        response = self.client.get(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('eventos:documentos-planos-trabalho-novo'))

    def test_etapa4_guiado_abre_cadastro_real_os(self):
        response = self.client.get(reverse('eventos:guiado-etapa-4', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('eventos:documentos-ordens-servico-novo'))

    def test_download_pt_usa_model_quando_sem_oficio(self):
        pt = PlanoTrabalho.objects.create(recursos_texto='PT download', status=PlanoTrabalho.STATUS_RASCUNHO)
        with patch('eventos.views_global.render_plano_trabalho_model_docx', return_value=b'docx') as mock_model:
            with patch('eventos.views_global.render_plano_trabalho_docx', return_value=b'oficio-docx') as mock_oficio:
                response = self.client.get(
                    reverse('eventos:documentos-planos-trabalho-download', kwargs={'pk': pt.pk, 'formato': 'docx'})
                )
        self.assertEqual(response.status_code, 200)
        mock_model.assert_called_once()
        mock_oficio.assert_not_called()

    def test_download_pt_pdf_funciona(self):
        pt = PlanoTrabalho.objects.create(recursos_texto='PT download PDF', status=PlanoTrabalho.STATUS_RASCUNHO)
        with patch('eventos.views_global.render_plano_trabalho_model_docx', return_value=b'docx'):
            with patch('eventos.views_global.convert_docx_bytes_to_pdf_bytes', return_value=b'pdf'):
                response = self.client.get(
                    reverse('eventos:documentos-planos-trabalho-download', kwargs={'pk': pt.pk, 'formato': 'pdf'})
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_download_os_usa_model_quando_sem_oficio(self):
        os_obj = OrdemServico.objects.create(finalidade='OS download', status=OrdemServico.STATUS_RASCUNHO)
        with patch('eventos.views_global.render_ordem_servico_model_docx', return_value=b'docx') as mock_model:
            with patch('eventos.views_global.render_ordem_servico_docx', return_value=b'oficio-docx') as mock_oficio:
                response = self.client.get(
                    reverse('eventos:documentos-ordens-servico-download', kwargs={'pk': os_obj.pk, 'formato': 'docx'})
                )
        self.assertEqual(response.status_code, 200)
        mock_model.assert_called_once()
        mock_oficio.assert_not_called()

    def test_model_legado_nao_existe_mais(self):
        import eventos.models as eventos_models

        legacy_name = 'Evento' + 'Fundamentacao'
        self.assertFalse(hasattr(eventos_models, legacy_name))

    def test_formulario_os_nao_reintroduz_campos_legados_removidos(self):
        form = OrdemServicoForm()

        self.assertIn('motivo_texto', form.fields)
        self.assertIn('viajantes', form.fields)
        self.assertNotIn('observacoes', form.fields)
        self.assertNotIn('designacoes', form.fields)
        self.assertNotIn('determinacoes', form.fields)

    def test_criar_os_salva_campos_documentais_e_numero_automatico(self):
        cargo = Cargo.objects.create(nome='Agente de Polícia Civil')
        estado = Estado.objects.create(nome='Paraná', sigla='PR')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado)
        viajante = Viajante.objects.create(
            nome='MARIA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo,
            cpf='12345678901',
            telefone='41999998888',
        )
        modelo = self._novo_modelo_motivo('OS compartilhada')

        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'data_criacao': '2026-03-10',
                'status': OrdemServico.STATUS_RASCUNHO,
                'data_unica': '1',
                'data_deslocamento': '2026-03-12',
                'modelo_motivo': modelo.pk,
                'motivo_texto': 'Apoio operacional em ação integrada.',
                'viajantes': [str(viajante.pk)],
                'destinos_payload': (
                    '[{"estado_id": %d, "estado_sigla": "PR", "cidade_id": %d, "cidade_nome": "Curitiba"}]'
                    % (estado.pk, cidade.pk)
                ),
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem = OrdemServico.objects.get(motivo_texto='Apoio operacional em ação integrada.')
        self.assertEqual(ordem.numero_formatado, '01/2026')
        self.assertEqual(ordem.finalidade, 'Apoio operacional em ação integrada.')
        self.assertEqual(ordem.data_deslocamento, date(2026, 3, 12))
        self.assertEqual(ordem.modelo_motivo, modelo)
        self.assertEqual(ordem.viajantes.count(), 1)
        self.assertEqual(ordem.viajantes.first(), viajante)
        self.assertEqual(ordem.destinos_json[0]['cidade_nome'], 'Curitiba')
        self.assertEqual(ordem.status, OrdemServico.STATUS_FINALIZADO)
        self.assertEqual(ordem.data_criacao, date(2026, 3, 10))

    def test_criar_os_incompleta_fica_rascunho_com_data_automatica(self):
        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-novo'),
            data={
                'status': OrdemServico.STATUS_FINALIZADO,
                'motivo_texto': 'Teste de rascunho automático',
                'destinos_payload': '[]',
                'return_to': reverse('eventos:documentos-ordens-servico'),
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem = OrdemServico.objects.get(motivo_texto='Teste de rascunho automático')
        self.assertEqual(ordem.status, OrdemServico.STATUS_RASCUNHO)
        self.assertEqual(ordem.data_criacao, timezone.localdate())

    def test_autosave_os_cria_rascunho_editavel_e_reutiliza_mesmo_registro(self):
        cargo = Cargo.objects.create(nome='Agente de PolÃ­cia Civil')
        estado = Estado.objects.create(nome='ParanÃ¡', sigla='PR')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado)
        viajante = Viajante.objects.create(
            nome='MARIA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo,
            cpf='12345678901',
            telefone='41999998888',
        )
        modelo = self._novo_modelo_motivo('OS compartilhada')
        create_url = reverse('eventos:documentos-ordens-servico-novo')

        response = self.client.post(
            create_url,
            data={
                'autosave': '1',
                'autosave_obj_id': '',
                'evento': str(self.evento.pk),
                'oficio': str(self.oficio.pk),
                'data_deslocamento': '2026-03-12',
                'modelo_motivo': str(modelo.pk),
                'motivo_texto': 'Primeiro rascunho operacional.',
                'viajantes': [str(viajante.pk)],
                'destinos_payload': (
                    '[{"estado_id": %d, "estado_sigla": "PR", "cidade_id": %d, "cidade_nome": "Curitiba"}]'
                    % (estado.pk, cidade.pk)
                ),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        ordem = OrdemServico.objects.get(pk=payload['id'])
        self.assertEqual(
            payload['edit_url'],
            reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': ordem.pk}),
        )
        self.assertEqual(OrdemServico.objects.count(), 1)
        self.assertEqual(ordem.motivo_texto, 'Primeiro rascunho operacional.')

        response = self.client.post(
            create_url,
            data={
                'autosave': '1',
                'autosave_obj_id': str(ordem.pk),
                'evento': str(self.evento.pk),
                'oficio': str(self.oficio.pk),
                'data_deslocamento': '2026-03-13',
                'modelo_motivo': str(modelo.pk),
                'motivo_texto': 'Rascunho atualizado sem duplicar.',
                'viajantes': [str(viajante.pk)],
                'destinos_payload': (
                    '[{"estado_id": %d, "estado_sigla": "PR", "cidade_id": %d, "cidade_nome": "Curitiba"}]'
                    % (estado.pk, cidade.pk)
                ),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['id'], ordem.pk)
        self.assertEqual(OrdemServico.objects.count(), 1)
        ordem.refresh_from_db()
        self.assertEqual(ordem.motivo_texto, 'Rascunho atualizado sem duplicar.')
        self.assertEqual(ordem.data_deslocamento, date(2026, 3, 13))

    def test_editar_os_preserva_viajantes_e_data_quando_campos_ausentes_no_post(self):
        cargo = Cargo.objects.create(nome='Agente de Polícia Civil')
        viajante = Viajante.objects.create(
            nome='MARIA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo,
            cpf='12345678901',
            telefone='41999998888',
        )
        ordem = OrdemServico.objects.create(
            data_criacao=date(2026, 3, 10),
            data_deslocamento=date(2026, 3, 12),
            status=OrdemServico.STATUS_RASCUNHO,
            motivo_texto='Motivo inicial',
        )
        ordem.viajantes.set([viajante])

        response = self.client.post(
            reverse('eventos:documentos-ordens-servico-editar', kwargs={'pk': ordem.pk}),
            data={
                'status': OrdemServico.STATUS_FINALIZADO,
                'motivo_texto': 'Motivo atualizado',
                'destinos_payload': '[]',
                # Simula formulário sem os campos data_deslocamento/viajantes no payload.
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem.refresh_from_db()
        self.assertEqual(ordem.data_criacao, date(2026, 3, 10))
        self.assertEqual(ordem.data_deslocamento, date(2026, 3, 12))
        self.assertEqual(ordem.viajantes.count(), 1)
        self.assertEqual(ordem.viajantes.first(), viajante)
        self.assertEqual(ordem.motivo_texto, 'Motivo atualizado')

    def test_contexto_template_os_usa_configuracao_e_equipe_agrupada(self):
        config = ConfiguracaoSistema.get_singleton()
        config.divisao = 'Diretoria de Operações'
        config.unidade = 'Unidade Especial'
        config.sigla_orgao = 'UE'
        config.cidade_endereco = 'Curitiba'
        config.email = 'os@pcpr.pr.gov.br'
        config.telefone = '4133334444'
        config.logradouro = 'Rua XV de Novembro'
        config.numero = '100'
        config.save()

        cargo_chefia = Cargo.objects.create(nome='Delegado Chefe')
        chefia = Viajante.objects.create(
            nome='JOAO PEREIRA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=cargo_chefia,
            cpf='11122233344',
            telefone='41911112222',
        )
        AssinaturaConfiguracao.objects.create(
            configuracao=config,
            tipo=AssinaturaConfiguracao.TIPO_ORDEM_SERVICO,
            ordem=1,
            viajante=chefia,
            ativo=True,
        )

        cargo_agente = Cargo.objects.create(nome='Agente')
        cargo_motorista = Cargo.objects.create(nome='Motorista')
        v1 = Viajante.objects.create(nome='ANA SOUZA', status=Viajante.STATUS_FINALIZADO, cargo=cargo_agente)
        v2 = Viajante.objects.create(nome='BRUNO LIMA', status=Viajante.STATUS_FINALIZADO, cargo=cargo_agente)
        v3 = Viajante.objects.create(nome='CARLOS REIS', status=Viajante.STATUS_FINALIZADO, cargo=cargo_motorista)

        ordem = OrdemServico.objects.create(
            data_criacao=date(2026, 4, 3),
            data_deslocamento=date(2026, 4, 3),
            motivo_texto='Cumprimento de missão institucional.',
            status=OrdemServico.STATUS_RASCUNHO,
        )
        ordem.viajantes.set([v1, v2, v3])
        ordem.destinos_json = [
            {'estado_id': None, 'estado_sigla': 'PR', 'cidade_id': 1, 'cidade_nome': 'Curitiba'},
            {'estado_id': None, 'estado_sigla': 'PR', 'cidade_id': 2, 'cidade_nome': 'Londrina'},
        ]
        ordem.save(update_fields=['destinos_json'])

        context = build_ordem_servico_model_template_context(ordem)

        self.assertEqual(context['divisao'], 'DIRETORIA DE OPERAÇÕES')
        self.assertEqual(context['unidade'], 'UNIDADE ESPECIAL')
        self.assertEqual(context['unidade_abreviado'], 'UE')
        self.assertEqual(context['nome_chefia'], 'Joao Pereira')
        self.assertEqual(context['cargo_chefia'], 'Delegado Chefe')
        self.assertEqual(context['destino'], 'Curitiba/PR, Londrina/PR')
        self.assertEqual(context['data_extenso'], '03 de abril de 2026')
        self.assertIn('dos(as) Agentes Ana Souza e Bruno Lima', context['equipe_deslocamento'])
        self.assertIn('do(a) Motorista Carlos Reis', context['equipe_deslocamento'])

    def test_contexto_template_os_agrupa_por_cargo_com_ordem_mista(self):
        cargo_agente = Cargo.objects.create(nome='agente de polícia civil')
        cargo_motorista = Cargo.objects.create(nome='motorista')
        cargo_escrivao = Cargo.objects.create(nome='escrivão')

        v1 = Viajante.objects.create(nome='SERVIDOR 4', status=Viajante.STATUS_FINALIZADO, cargo=cargo_motorista)
        v2 = Viajante.objects.create(nome='SERVIDOR 2', status=Viajante.STATUS_FINALIZADO, cargo=cargo_agente)
        v3 = Viajante.objects.create(nome='SERVIDOR 5', status=Viajante.STATUS_FINALIZADO, cargo=cargo_escrivao)
        v4 = Viajante.objects.create(nome='SERVIDOR 1', status=Viajante.STATUS_FINALIZADO, cargo=cargo_agente)
        v5 = Viajante.objects.create(nome='SERVIDOR 3', status=Viajante.STATUS_FINALIZADO, cargo=cargo_agente)

        ordem = OrdemServico.objects.create(
            data_criacao=date(2026, 4, 3),
            data_deslocamento=date(2026, 4, 3),
            motivo_texto='Apoio em operação integrada.',
            status=OrdemServico.STATUS_RASCUNHO,
        )
        ordem.viajantes.set([v1, v2, v3, v4, v5])

        context = build_ordem_servico_model_template_context(ordem)

        esperado = (
            'dos(as) Agentes de Polícia Civil Servidor 1, Servidor 2 e Servidor 3, '
            'do(a) Escrivão Servidor 5 e do(a) Motorista Servidor 4'
        )
        self.assertEqual(context['equipe_deslocamento'], esperado)

    def test_contexto_template_os_usa_data_criacao(self):
        ordem = OrdemServico.objects.create(
            data_criacao=date(2026, 4, 3),
            data_deslocamento=date(2026, 4, 3),
            motivo_texto='Documento para teste de data.',
            status=OrdemServico.STATUS_RASCUNHO,
        )

        context = build_ordem_servico_model_template_context(ordem)

        self.assertEqual(context['data_atual_extenso'], '03 de abril de 2026')

    def _novo_modelo_motivo(self, texto):
        from eventos.models import ModeloMotivoViagem

        return ModeloMotivoViagem.objects.create(codigo='motivo_os', nome='Motivo OS', texto=texto, ativo=True)

    def test_justificativa_unica_por_oficio(self):
        Justificativa.objects.create(oficio=self.oficio, texto='Primeira')
        with self.assertRaises(Exception):
            Justificativa.objects.create(oficio=self.oficio, texto='Duplicada')

    def test_ordem_servico_herda_oficios_do_evento(self):
        oficio_extra = Oficio.objects.create(
            evento=self.evento,
            protocolo='987650123',
            data_criacao=date(2026, 3, 2),
            status=Oficio.STATUS_RASCUNHO,
        )
        ordem = OrdemServico.objects.create(
            evento=self.evento,
            data_criacao=date(2026, 3, 10),
            data_deslocamento=date(2026, 3, 10),
            motivo_texto='Teste herança',
            status=OrdemServico.STATUS_RASCUNHO,
        )
        vinculos = resolver_vinculos_ordem_servico(ordem)
        herdados_ids = set(vinculos['oficios_herdados_ids'])
        self.assertIn(self.oficio.pk, herdados_ids)
        self.assertIn(oficio_extra.pk, herdados_ids)

    def test_termo_edicao_restringe_a_um_unico_oficio(self):
        termo = TermoAutorizacao.objects.create(destino='Curitiba/PR', data_evento=date(2026, 3, 10))
        oficio_2 = Oficio.objects.create(
            evento=self.evento,
            protocolo='111222333',
            data_criacao=date(2026, 3, 3),
            status=Oficio.STATUS_RASCUNHO,
        )
        form = TermoAutorizacaoEdicaoForm(
            data={
                'evento': self.evento.pk,
                'destino': 'Curitiba/PR',
                'data_evento': '2026-03-10',
                'oficios': [str(self.oficio.pk), str(oficio_2.pk)],
            },
            instance=termo,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('oficios', form.errors)

    def test_resolver_vinculos_oficio_e_evento(self):
        Justificativa.objects.create(oficio=self.oficio, texto='Base')
        TermoAutorizacao.objects.create(oficio=self.oficio, destino='Curitiba/PR', data_evento=date(2026, 3, 10))

        vinculos_oficio = resolver_vinculos_oficio(self.oficio)
        tipos_oficio = {item.tipo for item in vinculos_oficio['diretos']}
        self.assertIn('evento', tipos_oficio)
        self.assertIn('justificativa', tipos_oficio)
        self.assertIn('termo', tipos_oficio)

        vinculos_evento = resolver_vinculos_evento(self.evento)
        self.assertTrue(any(of.pk == self.oficio.pk for of in vinculos_evento['oficios']))
