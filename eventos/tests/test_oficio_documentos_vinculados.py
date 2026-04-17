from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from cadastros.models import Cargo, Cidade, CombustivelVeiculo, Estado, UnidadeLotacao, Veiculo, Viajante
from eventos.models import (
    Evento,
    Justificativa,
    Oficio,
    OficioDocumentoVinculo,
    OficioTrecho,
    OrdemServico,
    PlanoTrabalho,
    RoteiroEvento,
    RoteiroEventoDestino,
    TermoAutorizacao,
)
from eventos.services.documentos.vinculos import vincular_documento_ao_oficio


User = get_user_model()


class OficioDocumentosVinculadosTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='oficio-links', password='oficio-links')
        self.client.login(username='oficio-links', password='oficio-links')

        self.estado_pr = Estado.objects.create(nome='Paraná', sigla='PR')
        self.estado_sp = Estado.objects.create(nome='São Paulo', sigla='SP')
        self.cidade_curitiba = Cidade.objects.create(nome='Curitiba', estado=self.estado_pr)
        self.cidade_londrina = Cidade.objects.create(nome='Londrina', estado=self.estado_pr)
        self.cidade_sp = Cidade.objects.create(nome='São Paulo', estado=self.estado_sp)

        self.cargo = Cargo.objects.create(nome='Agente de Polícia Civil')
        self.unidade = UnidadeLotacao.objects.create(nome='DIRETORIA OPERACIONAL')
        self.viajante_1 = Viajante.objects.create(
            nome='ANA SILVA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            sem_rg=True,
            cpf='11111111111',
            telefone='41999990001',
            unidade_lotacao=self.unidade,
        )
        self.viajante_2 = Viajante.objects.create(
            nome='BRUNO LIMA',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            sem_rg=True,
            cpf='22222222222',
            telefone='41999990002',
            unidade_lotacao=self.unidade,
        )

        combustivel = CombustivelVeiculo.objects.create(nome='Gasolina', is_padrao=True)
        self.veiculo = Veiculo.objects.create(
            placa='ABC1234',
            modelo='Corolla',
            combustivel=combustivel,
            tipo=Veiculo.TIPO_DESCARACTERIZADO,
            status=Veiculo.STATUS_FINALIZADO,
        )

        self.evento = Evento.objects.create(
            titulo='Evento base',
            data_inicio=date(2026, 4, 10),
            data_fim=date(2026, 4, 12),
            status=Evento.STATUS_RASCUNHO,
        )

    def _make_oficio(self, *, motivo='Motivo base', data_criacao=date(2026, 4, 1), with_event=True):
        oficio = Oficio.objects.create(
            protocolo='123456789',
            data_criacao=data_criacao,
            motivo=motivo,
            status=Oficio.STATUS_RASCUNHO,
        )
        if with_event:
            oficio.eventos.add(self.evento)
        return oficio

    def _add_trecho(self, oficio, cidade, estado, *, saida_data, saida_hora, chegada_data=None, chegada_hora=None):
        return OficioTrecho.objects.create(
            oficio=oficio,
            ordem=0,
            destino_cidade=cidade,
            destino_estado=estado,
            saida_data=saida_data,
            saida_hora=saida_hora,
            chegada_data=chegada_data,
            chegada_hora=chegada_hora,
        )

    def test_endpoint_vincula_justificativa_e_herda_motivo(self):
        oficio = self._make_oficio(motivo='Motivo institucional')
        justificativa = Justificativa.objects.create(texto='')

        response = self.client.post(
            reverse('eventos:oficio-documento-vincular', kwargs={'pk': oficio.pk}),
            data={
                'tipo_documento': 'justificativa',
                'documento_id': justificativa.pk,
                'return_to': reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
            },
        )

        self.assertEqual(response.status_code, 302)
        justificativa.refresh_from_db()
        self.assertEqual(justificativa.oficio_id, oficio.pk)
        self.assertEqual(justificativa.texto, 'Motivo institucional')
        vinculo = OficioDocumentoVinculo.objects.get(oficio=oficio, object_id=justificativa.pk)
        self.assertEqual(vinculo.tipo_documento, 'justificativa')
        self.assertIn('texto', vinculo.campos_herdados_documento)

    def test_termo_herda_viajante_e_veiculo(self):
        oficio = self._make_oficio(with_event=False)
        oficio.viajantes.set([self.viajante_1])
        oficio.veiculo = self.veiculo
        oficio.placa = self.veiculo.placa
        oficio.modelo = self.veiculo.modelo
        oficio.combustivel = self.veiculo.combustivel.nome
        oficio.save(update_fields=['veiculo', 'placa', 'modelo', 'combustivel'])

        termo = TermoAutorizacao.objects.create(destino='')

        resultado = vincular_documento_ao_oficio(oficio, termo)

        self.assertTrue(resultado['ok'])
        termo.refresh_from_db()
        self.assertEqual(termo.oficio_id, oficio.pk)
        self.assertEqual(termo.viajante_id, self.viajante_1.pk)
        self.assertEqual(termo.veiculo_id, self.veiculo.pk)
        self.assertTrue(termo.servidor_nome)
        self.assertTrue(termo.veiculo_placa)

    def test_plano_e_ordem_herdam_destinos_e_participantes(self):
        oficio = self._make_oficio()
        oficio.viajantes.set([self.viajante_1, self.viajante_2])
        self._add_trecho(
            oficio,
            self.cidade_curitiba,
            self.estado_pr,
            saida_data=date(2026, 4, 10),
            saida_hora=time(8, 30),
            chegada_data=date(2026, 4, 10),
            chegada_hora=time(10, 0),
        )
        oficio.retorno_saida_data = date(2026, 4, 11)
        oficio.retorno_chegada_data = date(2026, 4, 11)
        oficio.save(update_fields=['retorno_saida_data', 'retorno_chegada_data'])

        plano = PlanoTrabalho.objects.create()
        resultado_plano = vincular_documento_ao_oficio(oficio, plano)
        self.assertTrue(resultado_plano['ok'])
        plano.refresh_from_db()
        self.assertEqual(plano.oficio_id, oficio.pk)
        self.assertEqual(plano.quantidade_servidores, 2)
        self.assertTrue(plano.destinos_json)
        self.assertEqual(plano.destinos_json[0]['cidade_nome'], 'CURITIBA')

        ordem = OrdemServico.objects.create()
        resultado_ordem = vincular_documento_ao_oficio(oficio, ordem)
        self.assertTrue(resultado_ordem['ok'])
        ordem.refresh_from_db()
        self.assertEqual(ordem.oficio_id, oficio.pk)
        self.assertEqual(ordem.viajantes.count(), 2)
        self.assertTrue(ordem.destinos_json)
        self.assertEqual(ordem.finalidade, 'Motivo base')
        self.assertEqual(ordem.motivo_texto, 'Motivo base')

    def test_roteiro_compativel_herda_evento_e_datas(self):
        oficio = self._make_oficio()
        self._add_trecho(
            oficio,
            self.cidade_curitiba,
            self.estado_pr,
            saida_data=date(2026, 4, 10),
            saida_hora=time(7, 15),
            chegada_data=date(2026, 4, 10),
            chegada_hora=time(8, 45),
        )
        oficio.retorno_saida_data = date(2026, 4, 10)
        oficio.retorno_chegada_data = date(2026, 4, 10)
        oficio.save(update_fields=['retorno_saida_data', 'retorno_chegada_data'])

        roteiro = RoteiroEvento.objects.create(status=RoteiroEvento.STATUS_RASCUNHO)
        RoteiroEventoDestino.objects.create(roteiro=roteiro, cidade=self.cidade_curitiba, estado=self.estado_pr, ordem=0)

        resultado = vincular_documento_ao_oficio(oficio, roteiro)

        self.assertTrue(resultado['ok'])
        roteiro.refresh_from_db()
        self.assertEqual(roteiro.evento_id, self.evento.pk)
        self.assertIsNotNone(roteiro.saida_dt)
        self.assertIsNotNone(roteiro.chegada_dt)
        self.assertTrue(OficioDocumentoVinculo.objects.filter(oficio=oficio, object_id=roteiro.pk).exists())

    def test_conflito_de_datas_bloqueia_vinculo(self):
        oficio = self._make_oficio()
        self._add_trecho(
            oficio,
            self.cidade_londrina,
            self.estado_pr,
            saida_data=date(2026, 4, 10),
            saida_hora=time(8, 0),
            chegada_data=date(2026, 4, 10),
            chegada_hora=time(10, 0),
        )

        ordem = OrdemServico.objects.create(
            data_deslocamento=date(2026, 4, 12),
            finalidade='Finalidade divergente',
        )

        resultado = vincular_documento_ao_oficio(oficio, ordem)

        self.assertFalse(resultado['ok'])
        conflitos = resultado['compatibilidade']['conflitos']
        self.assertTrue(any(conflito['campo'] == 'periodo' for conflito in conflitos))
        self.assertFalse(OficioDocumentoVinculo.objects.filter(oficio=oficio, object_id=ordem.pk).exists())

    def test_step1_exibe_bloco_documentos_vinculados(self):
        oficio = self._make_oficio()
        justificativa = Justificativa.objects.create(texto='')
        vincular_documento_ao_oficio(oficio, justificativa)

        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertIn('documentos_vinculados_block', response.context)
        block = response.context['documentos_vinculados_block']
        self.assertTrue(block['items'])
        self.assertContains(response, 'Documentos vinculados')
        self.assertContains(response, 'Justificativa')
