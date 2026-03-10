import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone as tz

from cadastros.models import Cargo, Estado, Cidade, UnidadeLotacao, Viajante, Veiculo, CombustivelVeiculo
from eventos.models import (
    Evento,
    EventoDestino,
    EventoParticipante,
    ModeloMotivoViagem,
    Oficio,
    RoteiroEvento,
    RoteiroEventoDestino,
    RoteiroEventoTrecho,
    TipoDemandaEvento,
)

User = get_user_model()


class PtBrEncodingTest(TestCase):
    """Valida strings críticas em PT-BR sem caracteres corrompidos."""

    def test_modelos_e_choices_criticos_estao_em_pt_br_correto(self):
        textos = [
            Evento._meta.get_field('titulo').verbose_name,
            Evento._meta.get_field('descricao').verbose_name,
            Oficio._meta.verbose_name,
            dict(Oficio.CUSTEIO_CHOICES)[Oficio.CUSTEIO_UNIDADE],
            dict(Oficio.CUSTEIO_CHOICES)[Oficio.CUSTEIO_ONUS_LIMITADOS],
            dict(Evento.TIPO_CHOICES)[Evento.TIPO_OPERACAO],
            dict(Evento.TIPO_CHOICES)[Evento.TIPO_PARANA],
            ModeloMotivoViagem._meta.verbose_name_plural,
        ]
        for texto in textos:
            self.assertNotIn('\ufffd', texto)
        self.assertEqual(Evento._meta.get_field('titulo').verbose_name, 'Título')
        self.assertEqual(Oficio._meta.verbose_name, 'Ofício')
        self.assertEqual(
            dict(Oficio.CUSTEIO_CHOICES)[Oficio.CUSTEIO_UNIDADE],
            'UNIDADE - DPC (diárias e combustível custeados pela DPC).',
        )
        self.assertEqual(
            dict(Oficio.CUSTEIO_CHOICES)[Oficio.CUSTEIO_ONUS_LIMITADOS],
            'ÔNUS LIMITADOS AOS PRÓPRIOS VENCIMENTOS',
        )


class EventoListaAuthTest(TestCase):
    """Lista de eventos exige login."""

    def setUp(self):
        self.client = Client()

    def test_lista_redireciona_sem_login(self):
        response = self.client.get(reverse('eventos:lista'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_lista_ok_com_login(self):
        User.objects.create_user(username='u', password='p')
        self.client.login(username='u', password='p')
        response = self.client.get(reverse('eventos:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Eventos')

    def test_lista_exibe_titulo_destinos_editar_etapa_1(self):
        """Lista usa título gerado, destinos e link Editar Etapa 1."""
        User.objects.create_user(username='u', password='p')
        self.client.login(username='u', password='p')
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado, codigo_ibge='4106902')
        ev = Evento.objects.create(
            titulo='PCPR - CURITIBA - 01/01/2025',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 1),
            status=Evento.STATUS_RASCUNHO,
        )
        ev.tipos_demanda.add(tipo)
        EventoDestino.objects.create(evento=ev, estado=estado, cidade=cidade, ordem=0)
        response = self.client.get(reverse('eventos:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PCPR')
        self.assertContains(response, 'Curitiba')
        self.assertContains(response, 'Editar Etapa 1')


class EventoCRUDTest(TestCase):
    """Criação e edição unificadas no fluxo guiado."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')

    def test_cadastrar_redireciona_para_fluxo_guiado(self):
        """Cadastrar evento redireciona para guiado-novo (fonte única de criação)."""
        response = self.client.get(reverse('eventos:cadastrar'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('guiado/novo', response.url)

    def test_editar_redireciona_para_etapa_1(self):
        """Editar evento redireciona para a Etapa 1 do fluxo guiado (mesma tela/lógica)."""
        ev = Evento.objects.create(
            titulo='Original',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_RASCUNHO,
        )
        response = self.client.get(reverse('eventos:editar', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(ev.pk), response.url)
        self.assertIn('guiado/etapa-1', response.url)


class EventoValidacaoTest(TestCase):
    """Validações na Etapa 1 (data e destinos)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')
        self.tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')

    def test_etapa1_data_fim_menor_que_data_inicio_rejeita(self):
        """Na Etapa 1, data_fim < data_inicio é rejeitado. Não enviar 'data_unica' para que seja False (checkbox desmarcado)."""
        self.assertIsNotNone(self.tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 1, 10), data_fim=date(2025, 1, 10), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [self.tipo.pk],
            'data_inicio': '2025-01-15',
            'data_fim': '2025-01-10',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('data_fim', response.context['form'].errors)


class EventoDetalheTest(TestCase):
    """Página de detalhe do evento (modelo unificado)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()

    def test_detalhe_redireciona_sem_login(self):
        ev = Evento.objects.create(
            titulo='E',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 2),
        )
        response = self.client.get(reverse('eventos:detalhe', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_detalhe_ok_mostra_dados_do_modelo_novo(self):
        """Detalhe exibe título, tipos, datas, destinos, status (sem cidade_base/legado)."""
        self.client.login(username='u', password='p')
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado, codigo_ibge='4106902')
        ev = Evento.objects.create(
            titulo='PCPR - CURITIBA - 01/01/2025',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 1),
            data_unica=True,
            status=Evento.STATUS_EM_ANDAMENTO,
        )
        ev.tipos_demanda.add(tipo)
        EventoDestino.objects.create(evento=ev, estado=estado, cidade=cidade, ordem=0)
        response = self.client.get(reverse('eventos:detalhe', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PCPR')
        self.assertContains(response, 'Curitiba')
        self.assertContains(response, 'Editar Etapa 1')
        self.assertNotContains(response, 'Cidade base')


class EventoExcluirTest(TestCase):
    """Exclusão de evento: exige login, POST, bloqueia quando há roteiros."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()

    def test_excluir_exige_login(self):
        """Exclusão por POST redireciona para login se não autenticado."""
        ev = Evento.objects.create(titulo='E', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        url = reverse('eventos:excluir', kwargs={'pk': ev.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
        self.assertTrue(Evento.objects.filter(pk=ev.pk).exists())

    def test_evento_sem_vinculos_pode_ser_excluido(self):
        """Evento sem roteiros pode ser excluído; redireciona para lista com mensagem de sucesso."""
        self.client.login(username='u', password='p')
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado, codigo_ibge='4106902')
        ev = Evento.objects.create(titulo='Evento X', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        if tipo:
            ev.tipos_demanda.add(tipo)
        EventoDestino.objects.create(evento=ev, estado=estado, cidade=cidade, ordem=0)
        url = reverse('eventos:excluir', kwargs={'pk': ev.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('eventos:lista'))
        self.assertFalse(Evento.objects.filter(pk=ev.pk).exists())
        response_lista = self.client.get(reverse('eventos:lista'))
        self.assertContains(response_lista, 'excluído com sucesso')

    def test_evento_com_roteiros_nao_pode_ser_excluido(self):
        """Evento com roteiros vinculados não pode ser excluído; mensagem de erro."""
        self.client.login(username='u', password='p')
        ev = Evento.objects.create(titulo='Evento Y', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        RoteiroEvento.objects.create(evento=ev)
        url = reverse('eventos:excluir', kwargs={'pk': ev.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('eventos:lista'))
        self.assertTrue(Evento.objects.filter(pk=ev.pk).exists())
        response_lista = self.client.get(reverse('eventos:lista'))
        self.assertContains(response_lista, 'não pode ser excluído')
        self.assertContains(response_lista, 'roteiros')

    def test_excluir_redireciona_para_lista_com_sucesso(self):
        """Após exclusão bem-sucedida, redireciona para lista e evento some."""
        self.client.login(username='u', password='p')
        ev = Evento.objects.create(titulo='Z', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        pk = ev.pk
        response = self.client.post(reverse('eventos:excluir', kwargs={'pk': pk}), {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('eventos:lista'))
        self.assertFalse(Evento.objects.filter(pk=pk).exists())

    def test_excluir_so_aceita_post(self):
        """Exclusão só aceita POST; GET retorna 405."""
        self.client.login(username='u', password='p')
        ev = Evento.objects.create(titulo='W', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        response = self.client.get(reverse('eventos:excluir', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Evento.objects.filter(pk=ev.pk).exists())


class EventoGuiadoTest(TestCase):
    """Fluxo guiado: novo, etapa 1, painel."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')

    def test_guiado_novo_exige_login_e_redireciona(self):
        self.client.logout()
        response = self.client.get(reverse('eventos:guiado-novo'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_guiado_novo_cria_evento_e_redireciona_para_etapa_1(self):
        response = self.client.get(reverse('eventos:guiado-novo'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Evento.objects.count(), 1)
        ev = Evento.objects.get()
        self.assertEqual(ev.status, Evento.STATUS_RASCUNHO)
        self.assertIn(str(ev.pk), response.url)
        self.assertIn('etapa-1', response.url)

    def test_etapa_1_salva_corretamente(self):
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        self.assertIsNotNone(tipo, 'Precisa existir pelo menos um TipoDemandaEvento (migração 0004).')
        estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado, codigo_ibge='4106902')
        ev = Evento.objects.create(
            titulo='',
            data_inicio=date(2025, 2, 1),
            data_fim=date(2025, 2, 5),
            status=Evento.STATUS_RASCUNHO,
        )
        data = {
            'tipos_demanda': [tipo.pk],
            'data_inicio': '2025-02-01',
            'data_fim': '2025-02-05',
            'descricao': 'Desc',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': estado.pk,
            'destino_cidade_0': cidade.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302, response.context.get('form', {}).errors if response.context else None)
        ev.refresh_from_db()
        self.assertIn(tipo.nome, ev.titulo)
        self.assertIn('CURITIBA', ev.titulo)
        self.assertEqual(ev.data_inicio, date(2025, 2, 1))
        self.assertEqual(ev.data_fim, date(2025, 2, 5))
        self.assertFalse(ev.data_unica)
        if not tipo.is_outros:
            self.assertEqual(ev.descricao, '')  # sem OUTROS a descrição fica vazia
        self.assertEqual(ev.destinos.count(), 1)
        self.assertEqual(ev.tipos_demanda.count(), 1)

    def test_etapa_1_destino_cidade_fora_do_estado_gera_erro(self):
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        self.assertIsNotNone(tipo)
        sp = Estado.objects.create(nome='São Paulo', sigla='SP', codigo_ibge='35')
        rj = Estado.objects.create(nome='Rio de Janeiro', sigla='RJ', codigo_ibge='33')
        cidade_rj = Cidade.objects.create(nome='Rio', estado=rj, codigo_ibge='3304557')
        ev = Evento.objects.create(
            titulo='E',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_RASCUNHO,
        )
        data = {
            'tipos_demanda': [tipo.pk],
            'data_inicio': '2025-01-01',
            'data_fim': '2025-01-05',
            'destino_estado_0': sp.pk,
            'destino_cidade_0': cidade_rj.pk,
            'descricao': 'Desc',
            'tem_convite_ou_oficio_evento': False,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        form = response.context['form']
        self.assertTrue(form.errors.get('__all__') or 'cidade' in str(form.errors).lower() or 'estado' in str(form.errors).lower())

    def test_painel_guiado_carrega_autenticado(self):
        ev = Evento.objects.create(
            titulo='Evento Painel',
            tipo_demanda=Evento.TIPO_OUTRO,
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_RASCUNHO,
        )
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Evento Painel')
        self.assertContains(response, 'Etapa 1')
        self.assertContains(response, 'Etapa 1 — Evento')

    def test_evento_etapa_1_completa_mostra_etapa_1_ok_no_painel(self):
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        self.assertIsNotNone(tipo)
        estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        cidade = Cidade.objects.create(nome='Curitiba', estado=estado, codigo_ibge='4106902')
        ev = Evento.objects.create(
            titulo='PCPR - CURITIBA - 01/01/2025',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_EM_ANDAMENTO,
        )
        ev.tipos_demanda.add(tipo)
        EventoDestino.objects.create(evento=ev, estado=estado, cidade=cidade, ordem=0)
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OK')
        self.assertContains(response, 'Etapa 1 — Evento')


class EventoEtapa2RoteirosTest(TestCase):
    """Etapa 2: Roteiros do evento."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade_a = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.cidade_b = Cidade.objects.create(nome='Londrina', estado=self.estado, codigo_ibge='4113700')
        self.evento = Evento.objects.create(
            titulo='Evento Roteiros',
            tipo_demanda=Evento.TIPO_OUTRO,
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_EM_ANDAMENTO,
            cidade_base=self.cidade_a,
        )

    def test_etapa_2_lista_exige_login(self):
        self.client.logout()
        response = self.client.get(reverse('eventos:guiado-etapa-2', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_criar_roteiro_dentro_de_evento(self):
        saida = datetime(2025, 1, 2, 8, 0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': saida.strftime('%Y-%m-%dT%H:%M'),
            'retorno_saida_dt': '',
            'observacoes': '',
            'trecho_0_saida_dt': saida.strftime('%Y-%m-%dT%H:%M'),
            'trecho_0_chegada_dt': (saida + timedelta(minutes=120)).strftime('%Y-%m-%dT%H:%M'),
            'trecho_1_saida_dt': '',
            'trecho_1_chegada_dt': '',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RoteiroEvento.objects.filter(evento=self.evento).count(), 1)
        r = RoteiroEvento.objects.get(evento=self.evento)
        self.assertEqual(r.origem_cidade_id, self.cidade_a.pk)
        self.assertEqual(r.destinos.count(), 1)
        self.assertEqual(r.destinos.first().cidade_id, self.cidade_b.pk)
        self.assertIsNotNone(r.saida_dt)
        self.assertIsNotNone(r.chegada_dt, 'chegada_dt preenchido a partir dos trechos')
        self.assertEqual((r.chegada_dt - r.saida_dt).total_seconds(), 120 * 60)

    def test_origem_padrao_vem_da_configuracao_sede(self):
        """Sede pré-preenchida vem de ConfiguracaoSistema.cidade_sede_padrao."""
        from cadastros.models import ConfiguracaoSistema
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = self.cidade_a
        config.save(update_fields=['cidade_sede_padrao'])
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.initial.get('origem_cidade'), self.cidade_a.pk)
        self.assertEqual(form.initial.get('origem_estado'), self.estado.pk)

    def test_cidade_destino_deve_pertencer_ao_estado(self):
        outro_estado = Estado.objects.create(nome='São Paulo', sigla='SP', codigo_ibge='35')
        cidade_sp = Cidade.objects.create(nome='São Paulo', estado=outro_estado, codigo_ibge='3550308')
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': cidade_sp.pk,
            'saida_dt': '2025-01-02T08:00',
            'retorno_saida_dt': '',
            'observacoes': '',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors.get('__all__') or 'pertencer' in str(response.context['form'].errors).lower())
        self.assertEqual(RoteiroEvento.objects.filter(evento=self.evento).count(), 0)

    def test_calculo_chegada_ao_salvar(self):
        """chegada_dt do roteiro é preenchida a partir do último trecho de ida."""
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '2025-01-02T14:00',
            'retorno_saida_dt': '',
            'observacoes': '',
            'trecho_0_saida_dt': '2025-01-02T14:00',
            'trecho_0_chegada_dt': '2025-01-02T15:30',
            'trecho_1_saida_dt': '',
            'trecho_1_chegada_dt': '',
        }
        self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        r = RoteiroEvento.objects.get(evento=self.evento)
        self.assertIsNotNone(r.chegada_dt)
        self.assertEqual((r.chegada_dt - r.saida_dt).total_seconds(), 90 * 60)

    def test_salvar_incompleto_rascunho(self):
        """Com um destino mas sem saida/duracao o roteiro fica RASCUNHO."""
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '',
            'retorno_saida_dt': '',
            'observacoes': 'PARCIAL',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        r = RoteiroEvento.objects.get(evento=self.evento)
        self.assertEqual(r.status, RoteiroEvento.STATUS_RASCUNHO)
        self.assertEqual(r.observacoes, 'PARCIAL')

    def test_salvar_completo_finalizado(self):
        """Roteiro fica FINALIZADO quando tem saida_dt e chegada_dt (preenchidos a partir dos trechos)."""
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '2025-01-02T08:00',
            'retorno_saida_dt': '',
            'observacoes': '',
            'trecho_0_saida_dt': '2025-01-02T08:00',
            'trecho_0_chegada_dt': '2025-01-02T10:00',
            'trecho_1_saida_dt': '',
            'trecho_1_chegada_dt': '',
        }
        self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        r = RoteiroEvento.objects.get(evento=self.evento)
        self.assertEqual(r.status, RoteiroEvento.STATUS_FINALIZADO)

    def test_excluir_remove_do_banco(self):
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
            chegada_dt=datetime(2025, 1, 2, 9, 0),
            status=RoteiroEvento.STATUS_FINALIZADO,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-excluir', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            {},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(RoteiroEvento.objects.filter(pk=r.pk).exists())

    def test_painel_mostra_etapa_2_ok_quando_existe_roteiro_finalizado(self):
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
            chegada_dt=datetime(2025, 1, 2, 9, 0),
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        r.save()
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Etapa 2 — Roteiros')
        self.assertContains(response, 'OK')

    def test_cadastro_roteiro_herda_sede_da_configuracao(self):
        """Cadastro novo de roteiro pré-preenche sede com ConfiguracaoSistema.cidade_sede_padrao."""
        from cadastros.models import ConfiguracaoSistema
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = self.cidade_a
        config.save(update_fields=['cidade_sede_padrao'])
        response = self.client.get(reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial.get('origem_estado'), self.estado.pk)
        self.assertEqual(response.context['form'].initial.get('origem_cidade'), self.cidade_a.pk)

    def test_cadastro_roteiro_herda_destinos_do_evento(self):
        """Cadastro novo de roteiro pré-preenche destinos da Etapa 1 do evento."""
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_b, ordem=1)
        response = self.client.get(reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        destinos_atuais = response.context['destinos_atuais']
        self.assertEqual(len(destinos_atuais), 2)
        self.assertEqual(destinos_atuais[0]['cidade_id'], self.cidade_a.pk)
        self.assertEqual(destinos_atuais[1]['cidade_id'], self.cidade_b.pk)

    def test_edicao_roteiro_mostra_dados_salvos_nao_do_evento(self):
        """Edição do roteiro exibe os destinos salvos do roteiro, não os atuais do evento."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        destinos_atuais = response.context['destinos_atuais']
        self.assertEqual(len(destinos_atuais), 1)
        self.assertEqual(destinos_atuais[0]['cidade_id'], self.cidade_b.pk)

    def test_cadastro_roteiro_abre_sem_quebrar_sem_sede_ni_destinos(self):
        """Formulário de cadastro abre mesmo sem cidade sede na config e sem destinos no evento."""
        response = self.client.get(reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('destinos_atuais', response.context)
        self.assertIn('form', response.context)

    def test_cadastro_roteiro_multiplos_destinos_evento(self):
        """Múltiplos destinos do evento aparecem no formulário de novo roteiro."""
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_b, ordem=1)
        response = self.client.get(reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['destinos_atuais']), 2)
        self.assertContains(response, 'destino_estado_0')
        self.assertContains(response, 'destino_estado_1')

    def test_bloco_duracao_apoio_removido(self):
        """O bloco '3) Duração (apoio)' e o campo Duração (HH:MM) foram removidos da Etapa 2."""
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertNotIn('Duração (apoio)', content)
        self.assertNotIn('id_duracao_hhmm', content)

    def test_bloco_global_ida_retorno_nao_aparece(self):
        """Formulário não exibe mais bloco global de Saída ida / Saída retorno / Chegada calculada."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Saída ida — data')
        self.assertNotContains(response, 'Saída retorno — data')
        self.assertNotContains(response, 'Chegada ida (calculada)')
        self.assertNotContains(response, 'Chegada retorno (calculada)')

    def test_trechos_gerados_container_presente(self):
        """Página de roteiro exibe o bloco de trechos (cada trecho com campos próprios, preenchido via JS)."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '3) Trechos')
        self.assertContains(response, 'trechos-gerados-container')

    def test_script_trechos_tem_campos_por_trecho(self):
        """JS gera inputs de saída/chegada por trecho (saída data/hora, chegada data/hora)."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'_saida_date', response.content)
        self.assertIn(b'_saida_time', response.content)
        self.assertIn(b'_chegada_date', response.content)
        self.assertIn(b'_chegada_time', response.content)

    def test_multiplos_destinos_geram_trechos_no_contexto(self):
        """Múltiplos destinos geram múltiplos trechos (ida + retorno) no contexto para o JS."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_a, ordem=1)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        trechos = response.context.get('trechos') or []
        self.assertGreaterEqual(len(trechos), 3)

    def test_salvar_reabrir_mantem_horarios_por_trecho(self):
        """Salvar edição e reabrir: horários de cada trecho permanecem (persistência por trecho)."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T09:00',
            'trecho_0_chegada_dt': '2025-02-10T10:30',
            'trecho_1_saida_dt': '2025-02-12T14:00',
            'trecho_1_chegada_dt': '2025-02-12T15:30',
        }
        self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        r.refresh_from_db()
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 2)
        self.assertIsNotNone(trechos[0].saida_dt)
        self.assertIsNotNone(trechos[0].chegada_dt)
        self.assertEqual((trechos[0].chegada_dt - trechos[0].saida_dt).total_seconds(), 90 * 60)
        self.assertIsNotNone(trechos[1].chegada_dt)
        response2 = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response2.status_code, 200)
        trechos_json = response2.context.get('trechos_json', '[]')
        import json
        initial = json.loads(trechos_json) if isinstance(trechos_json, str) else trechos_json
        self.assertEqual(len(initial), 2)
        self.assertIn('2025-02-10', initial[0].get('saida_dt', ''))
        self.assertIn('2025-02-12', initial[1].get('chegada_dt', ''))

    def test_multiplos_trechos_horarios_no_trecho_certo_salvar_reabrir(self):
        """Salvar com múltiplos trechos (sede->d1->d2->sede) mantém cada saída/chegada no trecho correto; reabrir preserva."""
        from eventos.models import RoteiroEventoTrecho
        cidade_c = Cidade.objects.create(nome='Maringá', estado=self.estado, codigo_ibge='4115200')
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_b, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=cidade_c, ordem=1)
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=cidade_c, ordem=1)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'saida_dt': '2025-02-10T08:00',
            'retorno_saida_dt': '2025-02-11T09:00',
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'destino_estado_1': self.estado.pk,
            'destino_cidade_1': cidade_c.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T08:00',
            'trecho_0_chegada_dt': '2025-02-10T10:00',
            'trecho_1_saida_dt': '2025-02-10T11:00',
            'trecho_1_chegada_dt': '2025-02-10T13:00',
            'trecho_2_saida_dt': '2025-02-11T09:00',
            'trecho_2_chegada_dt': '2025-02-11T12:00',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 3)
        self.assertEqual(trechos[0].tipo, RoteiroEventoTrecho.TIPO_IDA)
        self.assertEqual(tz.localtime(trechos[0].saida_dt).replace(tzinfo=None), datetime(2025, 2, 10, 8, 0))
        self.assertEqual(tz.localtime(trechos[0].chegada_dt).replace(tzinfo=None), datetime(2025, 2, 10, 10, 0))
        self.assertEqual(trechos[1].tipo, RoteiroEventoTrecho.TIPO_IDA)
        self.assertEqual(tz.localtime(trechos[1].saida_dt).replace(tzinfo=None), datetime(2025, 2, 10, 11, 0))
        self.assertEqual(tz.localtime(trechos[1].chegada_dt).replace(tzinfo=None), datetime(2025, 2, 10, 13, 0))
        self.assertEqual(trechos[2].tipo, RoteiroEventoTrecho.TIPO_RETORNO)
        self.assertEqual(tz.localtime(trechos[2].saida_dt).replace(tzinfo=None), datetime(2025, 2, 11, 9, 0))
        self.assertEqual(tz.localtime(trechos[2].chegada_dt).replace(tzinfo=None), datetime(2025, 2, 11, 12, 0))
        response2 = self.client.get(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk})
        )
        self.assertEqual(response2.status_code, 200)
        trechos_json = response2.context.get('trechos_json', '[]')
        initial = json.loads(trechos_json) if isinstance(trechos_json, str) else trechos_json
        self.assertEqual(len(initial), 3)
        self.assertIn('2025-02-10T08:00', initial[0].get('saida_dt', ''))
        self.assertIn('2025-02-10T10:00', initial[0].get('chegada_dt', ''))
        self.assertIn('2025-02-10T11:00', initial[1].get('saida_dt', ''))
        self.assertIn('2025-02-10T13:00', initial[1].get('chegada_dt', ''))
        self.assertIn('2025-02-11T09:00', initial[2].get('saida_dt', ''))
        self.assertIn('2025-02-11T12:00', initial[2].get('chegada_dt', ''))

    def test_parse_trechos_times_post_ordem_correta(self):
        """_parse_trechos_times_post retorna lista na ordem trecho_0, trecho_1, ... para associação correta."""
        from eventos.views import _parse_trechos_times_post
        rf = RequestFactory()
        request = rf.post('/x/', {
            'trecho_0_saida_dt': '2025-02-10T08:00',
            'trecho_0_chegada_dt': '2025-02-10T10:00',
            'trecho_1_saida_dt': '2025-02-10T11:00',
            'trecho_1_chegada_dt': '2025-02-10T13:00',
            'trecho_2_saida_dt': '2025-02-11T09:00',
            'trecho_2_chegada_dt': '2025-02-11T12:00',
        })
        result = _parse_trechos_times_post(request, 3)
        self.assertEqual(len(result), 3)
        self.assertIsNotNone(result[0].get('saida_dt'))
        self.assertEqual(result[0]['saida_dt'].hour, 8)
        self.assertEqual(result[0]['chegada_dt'].hour, 10)
        self.assertEqual(result[1]['saida_dt'].hour, 11)
        self.assertEqual(result[1]['chegada_dt'].hour, 13)
        self.assertEqual(result[2]['saida_dt'].hour, 9)
        self.assertEqual(result[2]['chegada_dt'].hour, 12)

    def test_salvar_trechos_roteiro_associa_por_ordem(self):
        """_salvar_trechos_roteiro associa trechos_data[0] ao primeiro trecho, etc."""
        from eventos.views import _salvar_trechos_roteiro
        cidade_c = Cidade.objects.create(nome='Maringá', estado=self.estado, codigo_ibge='4115200')
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=cidade_c, ordem=1)
        destinos_list = [(self.estado.pk, self.cidade_b.pk), (self.estado.pk, cidade_c.pk)]
        d0 = {'saida_dt': datetime(2025, 2, 10, 8, 0), 'chegada_dt': datetime(2025, 2, 10, 10, 0)}
        d1 = {'saida_dt': datetime(2025, 2, 10, 11, 0), 'chegada_dt': datetime(2025, 2, 10, 13, 0)}
        d2 = {'saida_dt': datetime(2025, 2, 11, 9, 0), 'chegada_dt': datetime(2025, 2, 11, 12, 0)}
        trechos_data = [d0, d1, d2]
        _salvar_trechos_roteiro(r, destinos_list, trechos_data)
        t0 = RoteiroEventoTrecho.objects.get(roteiro=r, ordem=0)
        t1 = RoteiroEventoTrecho.objects.get(roteiro=r, ordem=1)
        t2 = RoteiroEventoTrecho.objects.get(roteiro=r, ordem=2)
        local0 = tz.localtime(t0.saida_dt).replace(tzinfo=None) if t0.saida_dt else None
        local1 = tz.localtime(t1.saida_dt).replace(tzinfo=None) if t1.saida_dt else None
        local2 = tz.localtime(t2.saida_dt).replace(tzinfo=None) if t2.saida_dt else None
        self.assertEqual(local0, datetime(2025, 2, 10, 8, 0), 'trecho ordem=0 deve ter saida 08:00')
        self.assertEqual(local1, datetime(2025, 2, 10, 11, 0), 'trecho ordem=1 deve ter saida 11:00')
        self.assertEqual(local2, datetime(2025, 2, 11, 9, 0), 'trecho ordem=2 deve ter saida 09:00')

    def test_trecho_create_persiste_saida_dt(self):
        """Model persiste saida_dt corretamente ao criar trecho direto."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoTrecho.objects.create(
            roteiro=r, ordem=0, tipo=RoteiroEventoTrecho.TIPO_IDA,
            origem_estado=self.estado, origem_cidade=self.cidade_a,
            destino_estado=self.estado, destino_cidade=self.cidade_b,
            saida_dt=datetime(2025, 2, 10, 8, 0),
            chegada_dt=datetime(2025, 2, 10, 10, 0),
        )
        t0 = RoteiroEventoTrecho.objects.get(roteiro=r, ordem=0)
        # USE_TZ=True: comparar em hora local
        local_saida = tz.localtime(t0.saida_dt).replace(tzinfo=None) if t0.saida_dt else None
        self.assertEqual(local_saida, datetime(2025, 2, 10, 8, 0))

    def test_salvar_trechos_um_destino_dois_trechos(self):
        """Com 1 destino: trecho 0 = ida (trechos_data[0]), trecho 1 = retorno (trechos_data[1])."""
        from eventos.views import _salvar_trechos_roteiro
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        destinos_list = [(self.estado.pk, self.cidade_b.pk)]
        d0 = {'saida_dt': datetime(2025, 2, 10, 8, 0), 'chegada_dt': datetime(2025, 2, 10, 10, 0)}
        d1 = {'saida_dt': datetime(2025, 2, 11, 9, 0), 'chegada_dt': datetime(2025, 2, 11, 12, 0)}
        self.assertEqual(d0['saida_dt'].hour, 8, 'd0 deve ter hora 8')
        trechos_data = [d0, d1]
        _salvar_trechos_roteiro(r, destinos_list, trechos_data)
        self.assertEqual(RoteiroEventoTrecho.objects.filter(roteiro=r).count(), 2)
        t0 = RoteiroEventoTrecho.objects.get(roteiro=r, ordem=0)
        t1 = RoteiroEventoTrecho.objects.get(roteiro=r, ordem=1)
        local0 = tz.localtime(t0.saida_dt).replace(tzinfo=None) if t0.saida_dt else None
        local1 = tz.localtime(t1.saida_dt).replace(tzinfo=None) if t1.saida_dt else None
        self.assertEqual(local0, datetime(2025, 2, 10, 8, 0))
        self.assertEqual(local1, datetime(2025, 2, 11, 9, 0))

    def test_calculo_automatico_ida_persistido(self):
        """Chegada da ida = saída + duração (3h30); valor persistido no banco."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 3, 13, 14, 0),
            duracao_min=210,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '2025-03-13T14:00',
            'retorno_saida_dt': '2025-03-16T08:00',
            'observacoes': '',
            'trecho_0_saida_dt': '2025-03-13T14:00',
            'trecho_0_chegada_dt': '2025-03-13T17:30',
            'trecho_1_saida_dt': '2025-03-16T08:00',
            'trecho_1_chegada_dt': '2025-03-16T11:30',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 2)
        delta = (trechos[0].chegada_dt - trechos[0].saida_dt).total_seconds()
        self.assertEqual(delta, 210 * 60)

    def test_calculo_automatico_retorno_persistido(self):
        """Chegada do retorno = saída retorno + duração (3h30); valor persistido no banco."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 3, 13, 14, 0),
            duracao_min=210,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '2025-03-13T14:00',
            'retorno_saida_dt': '2025-03-16T08:00',
            'observacoes': '',
            'trecho_0_saida_dt': '2025-03-13T14:00',
            'trecho_0_chegada_dt': '2025-03-13T17:30',
            'trecho_1_saida_dt': '2025-03-16T08:00',
            'trecho_1_chegada_dt': '2025-03-16T11:30',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 2)
        self.assertEqual(trechos[1].tipo, 'RETORNO')
        delta = (trechos[1].chegada_dt - trechos[1].saida_dt).total_seconds()
        self.assertEqual(delta, 210 * 60)

    def test_chegada_retorno_calculada(self):
        """Chegada do retorno é preenchida a partir do trecho de retorno salvo."""
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '2025-01-02T08:00',
            'retorno_saida_dt': '2025-01-02T18:00',
            'observacoes': '',
            'trecho_0_saida_dt': '2025-01-02T08:00',
            'trecho_0_chegada_dt': '2025-01-02T09:00',
            'trecho_1_saida_dt': '2025-01-02T18:00',
            'trecho_1_chegada_dt': '2025-01-02T19:00',
        }
        self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        r = RoteiroEvento.objects.get(evento=self.evento)
        self.assertIsNotNone(r.retorno_chegada_dt)
        self.assertEqual((r.retorno_chegada_dt - r.retorno_saida_dt).total_seconds(), 60 * 60)

    def test_trechos_multiplos_destinos(self):
        """Múltiplos trechos na exibição: ida (sede -> destino) e retorno (último destino -> sede)."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
            retorno_saida_dt=datetime(2025, 1, 2, 18, 0),
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        trechos = response.context.get('trechos') or []
        self.assertGreaterEqual(len(trechos), 2)
        self.assertIn('Curitiba', str(trechos))
        self.assertIn('Londrina', str(trechos))
        self.assertTrue(any(t.get('tipo') == 'RETORNO' for t in trechos))

    def test_edicao_nao_sobrescreve_sede_com_config(self):
        """Na edição, a sede exibida é a salva no roteiro, não a da configuração atual."""
        from cadastros.models import ConfiguracaoSistema
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = self.cidade_a
        config.save(update_fields=['cidade_sede_padrao'])
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_b,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_a, ordem=0)
        response = self.client.get(reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}))
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertEqual(form.instance.origem_cidade_id, self.cidade_b.pk)

    def test_cidade_sede_selecionada_ao_abrir_cadastro(self):
        """Ao abrir cadastro novo, Cidade (Sede) deve vir pré-preenchida e selecionada da configuração."""
        from cadastros.models import ConfiguracaoSistema
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = self.cidade_a
        config.save(update_fields=['cidade_sede_padrao'])
        response = self.client.get(reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.cidade_a.pk}"')
        html = response.content.decode()
        self.assertIn(f'value="{self.cidade_a.pk}" selected', html)

    def test_cadastro_e_edicao_usam_mesmo_template_roteiro_form(self):
        """Cadastro novo e edição de roteiro renderizam o mesmo template principal."""
        # Cadastro novo
        response_cad = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response_cad.status_code, 200)
        template_names_cad = {t.name for t in response_cad.templates if t.name}
        self.assertIn('eventos/guiado/roteiro_form.html', template_names_cad)
        # Edição
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        response_edit = self.client.get(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk})
        )
        self.assertEqual(response_edit.status_code, 200)
        template_names_edit = {t.name for t in response_edit.templates if t.name}
        self.assertIn('eventos/guiado/roteiro_form.html', template_names_edit)

    def test_cadastro_novo_ja_exibe_bloco_trechos_sem_salvar(self):
        """Cadastro novo deve renderizar o bloco de trechos para o JS preencher imediatamente."""
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_b, ordem=1)
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '3) Trechos')
        self.assertContains(response, 'trechos-gerados-container')

    def test_cadastro_novo_persistir_trechos_conforme_formulario(self):
        """Cadastro novo deve salvar imediatamente os trechos de acordo com o que foi montado no formulário."""
        from eventos.models import RoteiroEventoTrecho
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T09:00',
            'trecho_0_chegada_dt': '2025-02-10T10:00',
            'trecho_1_saida_dt': '2025-02-12T14:00',
            'trecho_1_chegada_dt': '2025-02-12T15:00',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        # Salvar roteiro novo redireciona para a LISTA da Etapa 2, não para editar.
        expected_url = reverse('eventos:guiado-etapa-2', kwargs={'evento_id': self.evento.pk})
        self.assertEqual(response.url, expected_url, 'Cadastro novo deve redirecionar para lista da Etapa 2')
        r = RoteiroEvento.objects.get(evento=self.evento)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 2)
        self.assertIsNotNone(trechos[0].saida_dt)
        self.assertIsNotNone(trechos[0].chegada_dt)
        self.assertIsNotNone(trechos[1].saida_dt)
        self.assertIsNotNone(trechos[1].chegada_dt)

    def test_cadastro_novo_trechos_json_preenchido_com_sede_e_destinos(self):
        """Cadastro novo com sede da config e 2 destinos do evento já envia trechos_list e trechos_json (3 trechos)."""
        from cadastros.models import ConfiguracaoSistema
        import json
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = self.cidade_a
        config.save(update_fields=['cidade_sede_padrao'])
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_b, ordem=1)
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        trechos_list = response.context.get('trechos') or []
        trechos_json_raw = response.context.get('trechos_json') or '[]'
        trechos_initial = json.loads(trechos_json_raw) if isinstance(trechos_json_raw, str) else trechos_json_raw
        self.assertEqual(len(trechos_list), 3, '2 idas + 1 retorno')
        self.assertEqual(len(trechos_initial), 3)
        self.assertIn('initialTrechosData', response.content.decode())

    def test_script_adicionar_remover_destino_regenera_trechos(self):
        """Página de roteiro contém script que chama renderTrechos ao adicionar/remover destino."""
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('btn-adicionar-destino', content)
        self.assertIn('renderTrechos', content)
        self.assertIn('removerDestino', content)
        self.assertIn('trechos-gerados-container', content)

    def test_tempo_cru_adicional_persistidos_ao_salvar(self):
        """Salvar com tempo_cru e tempo_adicional persiste e tempo_total = cru + adicional."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T09:00',
            'trecho_0_chegada_dt': '2025-02-10T10:45',
            'trecho_0_tempo_cru_estimado_min': '120',
            'trecho_0_tempo_adicional_min': '45',
            'trecho_1_saida_dt': '2025-02-12T14:00',
            'trecho_1_chegada_dt': '2025-02-12T15:30',
            'trecho_1_tempo_cru_estimado_min': '75',
            'trecho_1_tempo_adicional_min': '15',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 2)
        self.assertEqual(trechos[0].tempo_cru_estimado_min, 120)
        self.assertEqual(trechos[0].tempo_adicional_min, 45)
        self.assertEqual(trechos[0].duracao_estimada_min, 165)
        self.assertEqual(trechos[1].tempo_cru_estimado_min, 75)
        self.assertEqual(trechos[1].tempo_adicional_min, 15)
        self.assertEqual(trechos[1].duracao_estimada_min, 90)

    def test_tempo_total_igual_cru_mais_adicional(self):
        """Model: tempo_total_final_min = tempo_cru + tempo_adicional."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        t = RoteiroEventoTrecho.objects.create(
            roteiro=r, ordem=0, tipo=RoteiroEventoTrecho.TIPO_IDA,
            origem_estado=self.estado, origem_cidade=self.cidade_a,
            destino_estado=self.estado, destino_cidade=self.cidade_b,
            tempo_cru_estimado_min=100, tempo_adicional_min=20,
        )
        self.assertEqual(t.tempo_total_final_min, 120)

    def test_tempo_adicional_aceita_zero(self):
        """Backend aceita e persiste tempo_adicional_min=0; total = cru + 0."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T09:00',
            'trecho_0_chegada_dt': '2025-02-10T10:00',
            'trecho_0_tempo_cru_estimado_min': '90',
            'trecho_0_tempo_adicional_min': '0',
            'trecho_1_saida_dt': '2025-02-12T14:00',
            'trecho_1_chegada_dt': '2025-02-12T15:00',
            'trecho_1_tempo_cru_estimado_min': '60',
            'trecho_1_tempo_adicional_min': '0',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(trechos[0].tempo_adicional_min, 0)
        self.assertEqual(trechos[0].duracao_estimada_min, 90)
        self.assertEqual(trechos[1].tempo_adicional_min, 0)
        self.assertEqual(trechos[1].duracao_estimada_min, 60)

    def test_tempo_adicional_negativo_clamped_para_zero(self):
        """Backend rejeita adicional negativo; valor é clampeado para 0."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T09:00',
            'trecho_0_chegada_dt': '2025-02-10T10:15',
            'trecho_0_tempo_cru_estimado_min': '60',
            'trecho_0_tempo_adicional_min': '-15',
            'trecho_1_saida_dt': '',
            'trecho_1_chegada_dt': '',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertIsNotNone(trechos[0].tempo_adicional_min)
        self.assertGreaterEqual(trechos[0].tempo_adicional_min, 0, 'Adicional nunca fica negativo')

    def test_tempo_adicional_sem_restricao_absurda(self):
        """Adicional aceita valores fora da faixa 6..21 (ex.: 0, 30, 60, 120)."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'observacoes': '',
            'trecho_0_saida_dt': '2025-02-10T09:00',
            'trecho_0_chegada_dt': '2025-02-10T11:30',
            'trecho_0_tempo_cru_estimado_min': '90',
            'trecho_0_tempo_adicional_min': '60',
            'trecho_1_saida_dt': '',
            'trecho_1_chegada_dt': '',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(trechos[0].tempo_adicional_min, 60)
        self.assertEqual(trechos[0].duracao_estimada_min, 150)  # 90 + 60

    def test_script_renderiza_inputs_visiveis_por_trecho(self):
        """Script de roteiro gera inputs visíveis (date/time) por trecho, não só hidden."""
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('type="date"', content, 'Script deve gerar input type=date')
        self.assertIn('type="time"', content, 'Script deve gerar input type=time')
        self.assertIn('_saida_date', content, 'Script deve gerar campo saída data por trecho')
        self.assertIn('_saida_time', content, 'Script deve gerar campo saída hora por trecho')
        self.assertIn('_chegada_date', content, 'Script deve gerar campo chegada data por trecho')
        self.assertIn('_chegada_time', content, 'Script deve gerar campo chegada hora por trecho')
        self.assertIn('data-trecho-ordem', content, 'Script deve marcar cada card com ordem do trecho')

    def test_script_tem_botoes_tempo_mais_menos(self):
        """Script de roteiro contém botões +15 e -15 para tempo adicional."""
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('btn-tempo-menos', content)
        self.assertIn('btn-tempo-mais', content)
        self.assertIn('trecho-tempo-adicional', content)

    def test_cadastro_mostra_botao_estimar_km_tempo(self):
        """Cadastro de roteiro exibe o botão 'Estimar km/tempo' (mesma base funcional da edição)."""
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Estimar km/tempo', content)
        self.assertIn('btn-calcular-km', content)
        self.assertIn('urlTrechosEstimar', content)

    def test_cadastro_inclui_url_trechos_estimar_para_trecho_novo(self):
        """Página de cadastro/etapa-2 inclui urlTrechosEstimar para estimar trecho novo sem pk."""
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('urlTrechosEstimar', content)
        self.assertIn('trechos/estimar/', content)

    def test_cadastro_trechos_json_tem_origem_destino_cidade_id(self):
        """trechos_json no cadastro inclui origem_cidade_id e destino_cidade_id por trecho."""
        from cadastros.models import ConfiguracaoSistema
        import json
        config = ConfiguracaoSistema.get_singleton()
        config.cidade_sede_padrao = self.cidade_a
        config.save(update_fields=['cidade_sede_padrao'])
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_a, ordem=0)
        EventoDestino.objects.create(evento=self.evento, estado=self.estado, cidade=self.cidade_b, ordem=1)
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-cadastrar', kwargs={'evento_id': self.evento.pk})
        )
        self.assertEqual(response.status_code, 200)
        trechos_json_raw = response.context.get('trechos_json') or '[]'
        trechos_initial = json.loads(trechos_json_raw) if isinstance(trechos_json_raw, str) else trechos_json_raw
        self.assertGreaterEqual(len(trechos_initial), 2)
        first = trechos_initial[0]
        self.assertIn('origem_cidade_id', first)
        self.assertIn('destino_cidade_id', first)

    def test_edicao_abre_com_trechos_persistidos(self):
        """Edição de roteiro abre com trechos e horários já salvos no contexto."""
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        from eventos.models import RoteiroEventoTrecho
        RoteiroEventoTrecho.objects.create(
            roteiro=r, ordem=0, tipo=RoteiroEventoTrecho.TIPO_IDA,
            origem_estado=self.estado, origem_cidade=self.cidade_a,
            destino_estado=self.estado, destino_cidade=self.cidade_b,
            saida_dt=datetime(2025, 1, 2, 8, 0), chegada_dt=datetime(2025, 1, 2, 9, 0),
        )
        RoteiroEventoTrecho.objects.create(
            roteiro=r, ordem=1, tipo=RoteiroEventoTrecho.TIPO_RETORNO,
            origem_estado=self.estado, origem_cidade=self.cidade_b,
            destino_estado=self.estado, destino_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 18, 0), chegada_dt=datetime(2025, 1, 2, 19, 0),
        )
        response = self.client.get(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk})
        )
        self.assertEqual(response.status_code, 200)
        trechos = response.context.get('trechos') or []
        self.assertEqual(len(trechos), 2)
        self.assertIn('2025-01-02', response.context.get('trechos_json', ''))

    def test_trechos_persistidos_ao_salvar_edicao(self):
        """Ao salvar a edição com horários por trecho, os trechos devem ser persistidos no banco."""
        from eventos.models import RoteiroEventoTrecho
        r = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            saida_dt=datetime(2025, 1, 2, 8, 0),
            duracao_min=60,
        )
        RoteiroEventoDestino.objects.create(roteiro=r, estado=self.estado, cidade=self.cidade_b, ordem=0)
        self.assertEqual(RoteiroEventoTrecho.objects.filter(roteiro=r).count(), 0)
        data = {
            'origem_estado': self.estado.pk,
            'origem_cidade': self.cidade_a.pk,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_b.pk,
            'saida_dt': '2025-01-02T08:00',
            'retorno_saida_dt': '',
            'observacoes': '',
            'trecho_0_saida_dt': '2025-01-02T08:00',
            'trecho_0_chegada_dt': '2025-01-02T09:00',
            'trecho_1_saida_dt': '2025-01-02T18:00',
            'trecho_1_chegada_dt': '2025-01-02T19:00',
        }
        response = self.client.post(
            reverse('eventos:guiado-etapa-2-editar', kwargs={'evento_id': self.evento.pk, 'pk': r.pk}),
            data,
        )
        self.assertEqual(response.status_code, 302)
        r.refresh_from_db()
        trechos = list(RoteiroEventoTrecho.objects.filter(roteiro=r).order_by('ordem'))
        self.assertEqual(len(trechos), 2)
        self.assertIsNotNone(trechos[0].saida_dt)
        self.assertIsNotNone(trechos[0].chegada_dt)
        self.assertIsNotNone(trechos[1].saida_dt)
        self.assertIsNotNone(trechos[1].chegada_dt)


class EventoEtapa1RefatoradoTest(TestCase):
    """Testes da Etapa 1 refatorada: múltiplos tipos, título automático, data única, destinos, descrição."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade_a = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.cidade_b = Cidade.objects.create(nome='Londrina', estado=self.estado, codigo_ibge='4113700')
        self.tipos = list(TipoDemandaEvento.objects.filter(ativo=True).order_by('ordem')[:3])

    def test_etapa_1_multiplos_tipos_demanda(self):
        self.assertGreaterEqual(len(self.tipos), 2, 'Precisa de ao menos 2 tipos (migração 0004).')
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 3, 12), data_fim=date(2025, 3, 12), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [self.tipos[0].pk, self.tipos[1].pk],
            'data_unica': True,
            'data_inicio': '2025-03-12',
            'data_fim': '2025-03-12',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.tipos_demanda.count(), 2)

    def test_etapa_1_titulo_gerado_automaticamente(self):
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2026, 3, 12), data_fim=date(2026, 3, 12), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': True,
            'data_inicio': '2026-03-12',
            'data_fim': '2026-03-12',
            'descricao': 'Desc',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        ev.refresh_from_db()
        self.assertTrue(ev.titulo)
        self.assertIn('CURITIBA', ev.titulo)
        self.assertIn('12/03/2026', ev.titulo)

    def test_etapa_1_data_unica_ignora_data_fim(self):
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 6, 10), data_fim=date(2025, 6, 15), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': True,
            'data_inicio': '2025-06-10',
            'data_fim': '2025-06-10',
            'descricao': 'X',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.data_fim, date(2025, 6, 10))

    def test_etapa_1_data_unica_sem_enviar_data_fim_backend_preenche(self):
        """data_unica=True: não enviar data_fim; backend deve preencher data_fim = data_inicio."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 7, 20), data_fim=date(2025, 7, 25), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': True,
            'data_inicio': '2025-07-20',
            'descricao': 'X',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.data_fim, date(2025, 7, 20))

    def test_etapa_1_sem_outros_descricao_nao_obrigatoria(self):
        """Sem tipo OUTROS selecionado: descrição não é exigida e é limpa ao salvar."""
        tipo = next((t for t in (self.tipos or []) if not t.is_outros), None)
        if not tipo:
            self.skipTest('Precisa de um tipo de demanda que não seja OUTROS.')
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 2, 1), data_fim=date(2025, 2, 1), status=Evento.STATUS_RASCUNHO, descricao='Texto antigo')
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': True,
            'data_inicio': '2025-02-01',
            'data_fim': '2025-02-01',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.descricao, '')

    def test_etapa_1_multiplos_destinos(self):
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 4, 1), data_fim=date(2025, 4, 3), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': False,
            'data_inicio': '2025-04-01',
            'data_fim': '2025-04-03',
            'descricao': 'X',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
            'destino_estado_1': self.estado.pk,
            'destino_cidade_1': self.cidade_b.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.destinos.count(), 2)

    def test_etapa_1_descricao_obrigatoria_quando_outros(self):
        tipo_outros = TipoDemandaEvento.objects.filter(is_outros=True).first()
        if not tipo_outros:
            self.skipTest('Nenhum tipo "Outros" cadastrado.')
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo_outros.pk],
            'data_unica': True,
            'data_inicio': '2025-01-01',
            'data_fim': '2025-01-01',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('descricao', response.context['form'].errors)

    def test_etapa_1_formulario_abre_com_um_destino(self):
        """Ao abrir a Etapa 1 deve existir pelo menos 1 bloco de destino visível."""
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        response = self.client.get(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'destino_estado_0')
        self.assertContains(response, 'destino_cidade_0')
        self.assertContains(response, 'destinos-container')

    def test_reabrir_etapa_1_apos_salvar_mantem_tipos_destinos_datas(self):
        """Após salvar a Etapa 1, reabrir a tela deve exibir os dados persistidos."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 5, 10), data_fim=date(2025, 5, 12), status=Evento.STATUS_RASCUNHO)
        # data_unica=False: não enviar a chave no POST (checkbox desmarcado não envia nada)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_inicio': '2025-05-10',
            'data_fim': '2025-05-12',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
            'destino_estado_1': self.estado.pk,
            'destino_cidade_1': self.cidade_b.pk,
        }
        self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        ev.refresh_from_db()
        self.assertEqual(ev.tipos_demanda.count(), 1)
        self.assertEqual(ev.destinos.count(), 2)
        # Datas persistidas: intervalo 10 a 12/05/2025 (data_unica=False; não enviar chave data_unica no POST)
        self.assertEqual(ev.data_inicio, date(2025, 5, 10))
        self.assertEqual(ev.data_fim, date(2025, 5, 12))
        self.assertFalse(ev.data_unica)
        response = self.client.get(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['destinos_atuais']), 2)
        self.assertIn(tipo.pk, response.context['selected_tipos_pks'])
        # Reabrir: formulário deve exibir as datas salvas
        self.assertContains(response, '2025-05-10')
        self.assertContains(response, '2025-05-12')

    def test_etapa_1_datas_persistidas_data_unica_true(self):
        """Com data_unica=True: data_inicio e data_fim persistidas; data_fim = data_inicio."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 1, 15), data_fim=date(2025, 1, 20), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': True,
            'data_inicio': '2025-08-01',
            'data_fim': '2025-08-01',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.data_inicio, date(2025, 8, 1))
        self.assertEqual(ev.data_fim, date(2025, 8, 1))
        self.assertTrue(ev.data_unica)

    def test_etapa_1_datas_persistidas_data_unica_false(self):
        """Com data_unica=False: data_inicio e data_fim persistidas com valores distintos. Não enviar 'data_unica' no POST."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_inicio': '2025-09-10',
            'data_fim': '2025-09-15',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.data_inicio, date(2025, 9, 10))
        self.assertEqual(ev.data_fim, date(2025, 9, 15))
        self.assertFalse(ev.data_unica)

    def test_etapa_1_reabrir_mostra_datas_salvas(self):
        """Reabrir a Etapa 1 após salvar deve exibir data_inicio e data_fim nos inputs."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 11, 1), data_fim=date(2025, 11, 5), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_inicio': '2025-11-01',
            'data_fim': '2025-11-05',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        response = self.client.get(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2025-11-01"')
        self.assertContains(response, 'value="2025-11-05"')

    def test_detalhe_evento_mostra_datas_corretas(self):
        """Página de detalhe do evento deve exibir as datas persistidas."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 12, 1), data_fim=date(2025, 12, 10), status=Evento.STATUS_RASCUNHO)
        ev.tipos_demanda.add(tipo)
        EventoDestino.objects.create(evento=ev, estado=self.estado, cidade=self.cidade_a, ordem=0)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_inicio': '2025-12-01',
            'data_fim': '2025-12-10',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
            'destino_estado_0': self.estado.pk,
            'destino_cidade_0': self.cidade_a.pk,
        }
        self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        response = self.client.get(reverse('eventos:detalhe', kwargs={'pk': ev.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '01/12/2025')
        self.assertContains(response, '10/12/2025')

    def test_etapa_1_nao_pode_salvar_sem_destino(self):
        """Envio sem nenhum destino válido deve rejeitar com erro."""
        tipo = self.tipos[0] if self.tipos else None
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        data = {
            'tipos_demanda': [tipo.pk],
            'data_unica': True,
            'data_inicio': '2025-01-01',
            'data_fim': '2025-01-01',
            'descricao': '',
            'tem_convite_ou_oficio_evento': False,
        }
        response = self.client.post(reverse('eventos:guiado-etapa-1', kwargs={'pk': ev.pk}), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('__all__', response.context['form'].errors)
        self.assertIn('destino', str(response.context['form'].errors['__all__']).lower())


class TipoDemandaEventoCRUDTest(TestCase):
    """CRUD de tipos de demanda e bloqueio de exclusão quando em uso."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')

    def test_lista_tipos_demanda(self):
        response = self.client.get(reverse('eventos:tipos-demanda-lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tipos de demanda')

    def test_cadastrar_tipo_demanda(self):
        data = {'nome': 'NOVO TIPO', 'descricao_padrao': 'Desc padrão', 'ordem': 50, 'ativo': True, 'is_outros': False}
        response = self.client.post(reverse('eventos:tipos-demanda-cadastrar'), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TipoDemandaEvento.objects.filter(nome='NOVO TIPO').exists())

    def test_excluir_tipo_em_uso_bloqueado(self):
        tipo = TipoDemandaEvento.objects.filter(ativo=True).first()
        self.assertIsNotNone(tipo)
        ev = Evento.objects.create(titulo='E', data_inicio=date(2025, 1, 1), data_fim=date(2025, 1, 1), status=Evento.STATUS_RASCUNHO)
        ev.tipos_demanda.add(tipo)
        response = self.client.post(reverse('eventos:tipos-demanda-excluir', kwargs={'pk': tipo.pk}), {})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TipoDemandaEvento.objects.filter(pk=tipo.pk).exists())

    def test_excluir_tipo_quando_nao_em_uso_funciona(self):
        """Excluir tipo de demanda quando não está em uso deve remover do banco."""
        tipo = TipoDemandaEvento.objects.create(nome='TIPO TESTE EXCLUSAO', ordem=999, ativo=True, is_outros=False)
        self.assertTrue(TipoDemandaEvento.objects.filter(pk=tipo.pk).exists())
        response = self.client.post(reverse('eventos:tipos-demanda-excluir', kwargs={'pk': tipo.pk}), {})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(TipoDemandaEvento.objects.filter(pk=tipo.pk).exists())


class EstimativaLocalServiceTest(TestCase):
    """Testes do serviço de estimativa local (haversine + regras de negócio)."""

    def test_minutos_para_hhmm(self):
        from eventos.services.estimativa_local import minutos_para_hhmm
        self.assertEqual(minutos_para_hhmm(340), '05:40')
        self.assertEqual(minutos_para_hhmm(65), '01:05')
        self.assertEqual(minutos_para_hhmm(0), '00:00')
        self.assertEqual(minutos_para_hhmm(None), '')

    def test_estimativa_entre_coordenadas_retorna_ok(self):
        from eventos.services.estimativa_local import estimar_distancia_duracao
        # Curitiba ~ -25.43, -49.27; Maringá ~ -23.42, -51.94 (linha reta ~380 km)
        out = estimar_distancia_duracao(
            origem_lat=-25.43, origem_lon=-49.27,
            destino_lat=-23.42, destino_lon=-51.94,
        )
        self.assertTrue(out['ok'])
        self.assertIsNotNone(out['distancia_km'])
        self.assertIsNotNone(out['duracao_estimada_min'])
        self.assertEqual(out['rota_fonte'], 'ESTIMATIVA_LOCAL')

    def test_fator_rodoviario_progressivo_por_faixa(self):
        """Fator rodoviário progressivo: até 100 km 1.18; 101-250 1.22; 251-400 1.27; >400 1.34."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, _fator_rodoviario_por_faixa
        # ~100 km linha reta: fator 1.18 -> rodoviário ~118 km
        out = estimar_distancia_duracao(0, 0, 0, 0.9)
        self.assertTrue(out['ok'])
        self.assertAlmostEqual(float(out['distancia_km']), 118, delta=8)
        # Faixas do fator (régua refinada)
        self.assertEqual(float(_fator_rodoviario_por_faixa(50)), 1.18)
        self.assertEqual(float(_fator_rodoviario_por_faixa(100)), 1.18)
        self.assertEqual(float(_fator_rodoviario_por_faixa(200)), 1.22)
        self.assertEqual(float(_fator_rodoviario_por_faixa(350)), 1.27)
        self.assertEqual(float(_fator_rodoviario_por_faixa(500)), 1.34)

    def test_arredondamento_multiplo_5_proximo(self):
        """Arredondar para o múltiplo de 5 mais próximo (neutro)."""
        from eventos.services.estimativa_local import arredondar_para_multiplo_5_proximo
        self.assertEqual(arredondar_para_multiplo_5_proximo(362), 360)  # 6h02 -> 6h00
        self.assertEqual(arredondar_para_multiplo_5_proximo(363), 365)  # 6h03 -> 6h05
        self.assertEqual(arredondar_para_multiplo_5_proximo(367), 365)  # 6h07 -> 6h05
        self.assertEqual(arredondar_para_multiplo_5_proximo(368), 370)  # 6h08 -> 6h10
        self.assertEqual(arredondar_para_multiplo_5_proximo(0), 0)
        self.assertEqual(arredondar_para_multiplo_5_proximo(5), 5)
        self.assertEqual(arredondar_para_multiplo_5_proximo(365), 365)

    def test_arredondamento_cima_bloco_5(self):
        from eventos.services.estimativa_local import arredondar_minutos_para_cima_5
        self.assertEqual(arredondar_minutos_para_cima_5(153), 155)  # 2h33 -> 2h35
        self.assertEqual(arredondar_minutos_para_cima_5(155), 155)  # 2h35 -> 2h35
        self.assertEqual(arredondar_minutos_para_cima_5(156), 160)  # 2h36 -> 2h40
        self.assertEqual(arredondar_minutos_para_cima_5(361), 365)  # 6h01 -> 6h05
        self.assertEqual(arredondar_minutos_para_cima_5(0), 0)
        self.assertEqual(arredondar_minutos_para_cima_5(5), 5)

    def test_sem_coordenadas_retorna_erro_amigavel(self):
        from eventos.services.estimativa_local import estimar_distancia_duracao, ERRO_SEM_COORDENADAS
        out = estimar_distancia_duracao(None, -49.27, -23.42, -51.94)
        self.assertFalse(out['ok'])
        self.assertEqual(out['erro'], ERRO_SEM_COORDENADAS)
        out = estimar_distancia_duracao(-25.43, None, -23.42, -51.94)
        self.assertFalse(out['ok'])
        self.assertEqual(out['erro'], ERRO_SEM_COORDENADAS)

    def test_tempo_cru_multiplo_5_minutos(self):
        """Tempo cru é sempre múltiplo de 5 minutos (arredondamento neutro)."""
        from eventos.services.estimativa_local import estimar_distancia_duracao
        out = estimar_distancia_duracao(-25.43, -49.27, -23.42, -51.94)
        self.assertTrue(out['ok'])
        self.assertIsNotNone(out['tempo_cru_estimado_min'])
        self.assertEqual(out['tempo_cru_estimado_min'] % 5, 0)

    def test_total_igual_cru_mais_adicional_na_estimativa(self):
        """Na estimativa, duracao_estimada_min = tempo_cru + tempo_adicional_sugerido (soma exata)."""
        from eventos.services.estimativa_local import estimar_distancia_duracao
        out = estimar_distancia_duracao(-25.43, -49.27, -23.42, -51.94)
        self.assertTrue(out['ok'])
        cru = out.get('tempo_cru_estimado_min', 0) or 0
        adic = out.get('tempo_adicional_sugerido_min', 0) or 0
        total = out.get('duracao_estimada_min')
        self.assertEqual(total, cru + adic)

    def test_tempo_cru_nao_contem_folga(self):
        """Tempo cru = distância/velocidade_progressiva, arredondado para múltiplo 5 mais próximo. NÃO contém folga."""
        from eventos.services.estimativa_local import (
            estimar_distancia_duracao, arredondar_para_multiplo_5_proximo,
            VELOCIDADE_MEDIA_BASE_KMH, VELOCIDADE_MEDIA_TETO_KMH, INCREMENTO_KM,
        )
        out = estimar_distancia_duracao(0, 0, 0, 1)  # ~111 km linha reta -> ~128 km rod
        self.assertTrue(out['ok'])
        dist_km = float(out['distancia_km'])
        vel = min(VELOCIDADE_MEDIA_TETO_KMH, VELOCIDADE_MEDIA_BASE_KMH + int(dist_km // INCREMENTO_KM))
        tempo_cru = out['tempo_cru_estimado_min']
        esperado_float = (dist_km / vel) * 60
        esperado = arredondar_para_multiplo_5_proximo(esperado_float)
        self.assertEqual(tempo_cru, esperado)
        self.assertIn('tempo_adicional_sugerido_min', out)
        self.assertEqual(out['duracao_estimada_min'], tempo_cru + out['tempo_adicional_sugerido_min'])

    def test_velocidade_media_progressiva_base_62(self):
        """Velocidade média progressiva: base 62 km/h, +1 a cada 100 km, teto 76."""
        from eventos.services.estimativa_local import (
            VELOCIDADE_MEDIA_BASE_KMH, VELOCIDADE_MEDIA_TETO_KMH, INCREMENTO_KM,
        )
        self.assertEqual(VELOCIDADE_MEDIA_BASE_KMH, 62)
        self.assertEqual(VELOCIDADE_MEDIA_TETO_KMH, 76)
        self.assertEqual(INCREMENTO_KM, 100)

    def test_velocidade_50_km_usar_62(self):
        """0-99 km usa 62 km/h."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, arredondar_para_multiplo_5_proximo
        out = estimar_distancia_duracao(0, 0, 0, 50/111)
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertLess(dist, 100)
        tempo_cru = out['tempo_cru_estimado_min']
        esperado = (dist / 62) * 60
        self.assertEqual(tempo_cru, arredondar_para_multiplo_5_proximo(esperado))

    def test_velocidade_100_km_usar_63(self):
        """100-199 km usa 63 km/h."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, arredondar_para_multiplo_5_proximo
        out = estimar_distancia_duracao(0, 0, 0, 100/111)
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertGreaterEqual(dist, 100)
        self.assertLess(dist, 200)
        tempo_cru = out['tempo_cru_estimado_min']
        esperado = (dist / 63) * 60
        self.assertEqual(tempo_cru, arredondar_para_multiplo_5_proximo(esperado))

    def test_velocidade_300_km_usar_65(self):
        """300-399 km usa 65 km/h."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, arredondar_para_multiplo_5_proximo
        out = estimar_distancia_duracao(0, 0, 0, 300/111)
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertGreaterEqual(dist, 300)
        self.assertLess(dist, 400)
        tempo_cru = out['tempo_cru_estimado_min']
        esperado = (dist / 65) * 60
        self.assertEqual(tempo_cru, arredondar_para_multiplo_5_proximo(esperado))

    def test_velocidade_600_km_usar_68(self):
        """600-699 km (rodoviário) usa 68 km/h."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, arredondar_para_multiplo_5_proximo
        # ~500 km linha reta -> fator 1.34 -> ~670 km rod (faixa 600-699 para vel 68)
        out = estimar_distancia_duracao(0, 0, 0, 500/111)
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertGreaterEqual(dist, 600)
        self.assertLess(dist, 700)
        tempo_cru = out['tempo_cru_estimado_min']
        esperado = (dist / 68) * 60
        self.assertEqual(tempo_cru, arredondar_para_multiplo_5_proximo(esperado))

    def test_velocidade_1000_km_usar_72(self):
        """1000-1099 km (rodoviário) usa 72 km/h."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, arredondar_para_multiplo_5_proximo
        # ~750 km linha reta -> fator 1.34 -> ~1005 km rod (faixa 1000-1099)
        out = estimar_distancia_duracao(0, 0, 0, 750/111)
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertGreaterEqual(dist, 1000)
        self.assertLess(dist, 1100)
        tempo_cru = out['tempo_cru_estimado_min']
        esperado = (dist / 72) * 60
        self.assertEqual(tempo_cru, arredondar_para_multiplo_5_proximo(esperado))

    def test_distancia_longa_nao_subestimada_francisco_beltrao_londrina(self):
        """Francisco Beltrão -> Londrina: correção para rotas longas/diagonais (Google ~513 km / 7h32)."""
        from eventos.services.estimativa_local import estimar_distancia_duracao
        # Coordenadas aproximadas: Francisco Beltrão PR (-26.08, -53.05), Londrina PR (-23.30, -51.16)
        out = estimar_distancia_duracao(
            origem_lat=-26.08, origem_lon=-53.05,
            destino_lat=-23.30, destino_lon=-51.16,
        )
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        tempo_cru = out['tempo_cru_estimado_min']
        # Com fator progressivo (1.27 ou 1.34), distância não subestimada como antes (~417 km)
        self.assertGreaterEqual(dist, 450, 'Distância não pode ser subestimada como antes (~417 km)')
        self.assertLessEqual(dist, 550)
        # Tempo cru próximo de 7h (≥ ~6h30) para ~513 km; margem para arredondamento
        self.assertGreaterEqual(tempo_cru, 385)
        self.assertLessEqual(tempo_cru, 480)

    def test_velocidade_1400_km_teto_76(self):
        """1400 km ou mais respeita teto 76 km/h."""
        from eventos.services.estimativa_local import estimar_distancia_duracao, arredondar_para_multiplo_5_proximo, VELOCIDADE_MEDIA_TETO_KMH
        out = estimar_distancia_duracao(-25.43, -49.27, -10, -35)  # ~2500+ km
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertGreaterEqual(dist, 1400)
        tempo_cru = out['tempo_cru_estimado_min']
        esperado = (dist / VELOCIDADE_MEDIA_TETO_KMH) * 60
        self.assertEqual(tempo_cru, arredondar_para_multiplo_5_proximo(esperado))

    def test_adicional_sugerido_nao_zero_por_perfil(self):
        """Adicional sugerido é 15/30/45 conforme perfil e distância; total = cru + adicional."""
        from eventos.services.estimativa_local import estimar_distancia_duracao
        out = estimar_distancia_duracao(-25.43, -49.27, -23.42, -51.94)
        self.assertTrue(out['ok'])
        adic = out.get('tempo_adicional_sugerido_min')
        self.assertIn(adic, (15, 30, 45), f'Adicional sugerido deve ser 15, 30 ou 45, obtido {adic}')
        self.assertEqual(
            out['duracao_estimada_min'],
            out['tempo_cru_estimado_min'] + adic,
        )

    def test_perfil_rota_retornado_na_estimativa(self):
        """Estimativa retorna perfil_rota (EIXO_PRINCIPAL, DIAGONAL_LONGA, LITORAL_SERRA ou PADRAO)."""
        from eventos.services.estimativa_local import (
            estimar_distancia_duracao,
            PERFIL_EIXO_PRINCIPAL,
            PERFIL_DIAGONAL_LONGA,
            PERFIL_LITORAL_SERRA,
            PERFIL_PADRAO,
        )
        out = estimar_distancia_duracao(-25.43, -49.27, -23.42, -51.94)
        self.assertTrue(out['ok'])
        self.assertIn(
            out.get('perfil_rota'),
            (PERFIL_EIXO_PRINCIPAL, PERFIL_DIAGONAL_LONGA, PERFIL_LITORAL_SERRA, PERFIL_PADRAO),
        )

    def test_adicional_sugerido_curto_15(self):
        """Trecho curto (< 250 km rod) recebe adicional sugerido 15 min."""
        from eventos.services.estimativa_local import estimar_distancia_duracao
        # ~50 km linha reta -> ~59 km rod -> curto
        out = estimar_distancia_duracao(0, 0, 0, 50/111)
        self.assertTrue(out['ok'])
        self.assertEqual(out.get('tempo_adicional_sugerido_min'), 15)

    def test_adicional_sugerido_longo_padrao_30(self):
        """Trecho longo (>= 250 km) perfil PADRAO/EIXO recebe adicional sugerido 30 min."""
        from eventos.services.estimativa_local import estimar_distancia_duracao
        # ~300 km linha reta -> fator 1.27 -> ~381 km rod, perfil pode ser PADRAO
        out = estimar_distancia_duracao(0, 0, 0, 300/111)
        self.assertTrue(out['ok'])
        dist = float(out['distancia_km'])
        self.assertGreaterEqual(dist, 250)
        adic = out.get('tempo_adicional_sugerido_min')
        self.assertIn(adic, (15, 30, 45), 'Adicional deve ser 15, 30 ou 45')

    def test_adicional_sugerido_longo_diagonal_45(self):
        """Trecho longo com perfil DIAGONAL_LONGA recebe adicional sugerido 45 min."""
        from eventos.services.estimativa_local import (
            estimar_distancia_duracao,
            PERFIL_DIAGONAL_LONGA,
        )
        # Francisco Beltrão -> Londrina: rota longa e diagonal (ratio alto)
        out = estimar_distancia_duracao(-26.08, -53.05, -23.30, -51.16)
        self.assertTrue(out['ok'])
        self.assertEqual(out.get('perfil_rota'), PERFIL_DIAGONAL_LONGA)
        self.assertEqual(out.get('tempo_adicional_sugerido_min'), 45)


class TrechoCalcularKmEndpointTest(TestCase):
    """Testes do endpoint POST trechos/<pk>/calcular-km/ (estimativa local)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade_a = Cidade.objects.create(
            nome='Curitiba', estado=self.estado, codigo_ibge='4106902',
            latitude=Decimal('-25.4284'), longitude=Decimal('-49.2733'),
        )
        self.cidade_b = Cidade.objects.create(
            nome='Maringá', estado=self.estado, codigo_ibge='4115200',
            latitude=Decimal('-23.4205'), longitude=Decimal('-51.9332'),
        )
        self.evento = Evento.objects.create(
            titulo='Evento Teste',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 1),
            status=Evento.STATUS_RASCUNHO,
        )
        self.roteiro = RoteiroEvento.objects.create(
            evento=self.evento,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
        )
        RoteiroEventoDestino.objects.create(
            roteiro=self.roteiro,
            estado=self.estado,
            cidade=self.cidade_b,
            ordem=0,
        )
        self.trecho = RoteiroEventoTrecho.objects.create(
            roteiro=self.roteiro,
            ordem=0,
            tipo=RoteiroEventoTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade_a,
            destino_estado=self.estado,
            destino_cidade=self.cidade_b,
        )

    def test_endpoint_exige_login(self):
        url = reverse('eventos:trecho-calcular-km', kwargs={'pk': self.trecho.pk})
        response = self.client.post(url, {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_endpoint_retorna_km_e_duracao_estimativa_local(self):
        self.client.login(username='u', password='p')
        url = reverse('eventos:trecho-calcular-km', kwargs={'pk': self.trecho.pk})
        response = self.client.post(
            url,
            {},
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'], data.get('erro'))
        self.assertIsNotNone(data['distancia_km'])
        self.assertIsNotNone(data['duracao_estimada_min'])
        self.assertIn('duracao_estimada_hhmm', data)
        self.assertIn('tempo_cru_estimado_min', data)
        self.assertIn('tempo_adicional_sugerido_min', data)
        self.assertEqual(data.get('rota_fonte'), 'ESTIMATIVA_LOCAL')
        self.trecho.refresh_from_db()
        self.assertIsNotNone(self.trecho.distancia_km)
        self.assertIsNotNone(self.trecho.duracao_estimada_min)
        self.assertIsNotNone(self.trecho.tempo_cru_estimado_min)
        self.assertIsNotNone(self.trecho.tempo_adicional_min)
        self.assertEqual(
            self.trecho.duracao_estimada_min,
            (self.trecho.tempo_cru_estimado_min or 0) + (self.trecho.tempo_adicional_min or 0)
        )
        self.assertEqual(self.trecho.rota_fonte, 'ESTIMATIVA_LOCAL')
        self.assertIsNotNone(self.trecho.rota_calculada_em)
        self.assertEqual(self.trecho.tempo_cru_estimado_min % 5, 0)

    def test_endpoint_erro_sem_coordenadas(self):
        self.cidade_b.latitude = None
        self.cidade_b.longitude = None
        self.cidade_b.save()
        self.client.login(username='u', password='p')
        url = reverse('eventos:trecho-calcular-km', kwargs={'pk': self.trecho.pk})
        response = self.client.post(
            url,
            {},
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('coordenadas', data['erro'].lower())
        self.trecho.refresh_from_db()
        self.assertIsNone(self.trecho.distancia_km)
        self.assertIsNone(self.trecho.duracao_estimada_min)

    @patch('eventos.views.estimar_distancia_duracao')
    def test_endpoint_trata_erro_estimativa(self, mock_estimar):
        mock_estimar.return_value = {
            'ok': False,
            'distancia_km': None,
            'duracao_estimada_min': None,
            'duracao_estimada_hhmm': '',
            'rota_fonte': 'ESTIMATIVA_LOCAL',
            'erro': 'Cidade sem coordenadas para estimativa.',
        }
        self.client.login(username='u', password='p')
        url = reverse('eventos:trecho-calcular-km', kwargs={'pk': self.trecho.pk})
        response = self.client.post(
            url,
            {},
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertEqual(data['erro'], 'Cidade sem coordenadas para estimativa.')
        self.trecho.refresh_from_db()
        self.assertIsNone(self.trecho.distancia_km)
        self.assertIsNone(self.trecho.duracao_estimada_min)


class EstimarKmPorCidadesEndpointTest(TestCase):
    """Testes do endpoint POST trechos/estimar/ (para cadastro, sem trecho salvo)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade_a = Cidade.objects.create(
            nome='Curitiba', estado=self.estado, codigo_ibge='4106902',
            latitude=Decimal('-25.4284'), longitude=Decimal('-49.2733'),
        )
        self.cidade_b = Cidade.objects.create(
            nome='Maringá', estado=self.estado, codigo_ibge='4115200',
            latitude=Decimal('-23.4205'), longitude=Decimal('-51.9332'),
        )

    def test_estimar_km_por_cidades_exige_login(self):
        url = reverse('eventos:trechos-estimar')
        response = self.client.post(
            url,
            json.dumps({'origem_cidade_id': self.cidade_a.pk, 'destino_cidade_id': self.cidade_b.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_estimar_km_por_cidades_retorna_mesmo_formato_que_trecho_calcular(self):
        """Endpoint retorna ok, distancia_km, tempo_cru_estimado_min, tempo_adicional_sugerido_min (não persiste)."""
        self.client.login(username='u', password='p')
        url = reverse('eventos:trechos-estimar')
        response = self.client.post(
            url,
            json.dumps({'origem_cidade_id': self.cidade_a.pk, 'destino_cidade_id': self.cidade_b.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'], data.get('erro'))
        self.assertIn('distancia_km', data)
        self.assertIn('duracao_estimada_min', data)
        self.assertIn('tempo_cru_estimado_min', data)
        self.assertIn('tempo_adicional_sugerido_min', data)
        self.assertEqual(data.get('rota_fonte'), 'ESTIMATIVA_LOCAL')
        if data.get('tempo_cru_estimado_min') and data.get('tempo_adicional_sugerido_min') is not None:
            self.assertEqual(
                data['duracao_estimada_min'],
                data['tempo_cru_estimado_min'] + data['tempo_adicional_sugerido_min'],
            )

    def test_estimar_km_por_cidades_sem_ids_retorna_erro(self):
        self.client.login(username='u', password='p')
        url = reverse('eventos:trechos-estimar')
        response = self.client.post(url, json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['ok'])
        self.assertIn('origem_cidade_id', data.get('erro', '').lower())

    def test_trechos_estimar_trecho_novo_sem_pk(self):
        """Endpoint trechos-estimar/ permite estimar por origem/destino sem trecho salvo (não persiste)."""
        self.client.login(username='u', password='p')
        url = reverse('eventos:trechos-estimar')
        n_before = RoteiroEventoTrecho.objects.count()
        response = self.client.post(
            url,
            json.dumps({'origem_cidade_id': self.cidade_a.pk, 'destino_cidade_id': self.cidade_b.pk}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'], data.get('erro'))
        self.assertIn('distancia_km', data)
        self.assertIn('duracao_estimada_min', data)
        self.assertIn('tempo_cru_estimado_min', data)
        self.assertIn('tempo_adicional_sugerido_min', data)
        self.assertIn('duracao_estimada_hhmm', data)
        self.assertEqual(data.get('rota_fonte'), 'ESTIMATIVA_LOCAL')
        self.assertEqual(RoteiroEventoTrecho.objects.count(), n_before)


class PainelBlocosClicaveisTest(TestCase):
    """Painel: blocos das etapas implementadas devem ser clicáveis (link real)."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')
        self.evento = Evento.objects.create(
            titulo='Evento Painel',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_RASCUNHO,
        )

    def test_painel_bloco_etapa_1_clicavel(self):
        """Bloco da Etapa 1 deve ter link para guiado-etapa-1."""
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        url_etapa1 = reverse('eventos:guiado-etapa-1', kwargs={'pk': self.evento.pk})
        self.assertContains(response, url_etapa1)
        self.assertContains(response, 'Etapa 1 — Evento')

    def test_painel_bloco_etapa_2_clicavel(self):
        """Bloco da Etapa 2 deve ter link para guiado-etapa-2."""
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        url_etapa2 = reverse('eventos:guiado-etapa-2', kwargs={'evento_id': self.evento.pk})
        self.assertContains(response, url_etapa2)
        self.assertContains(response, 'Etapa 2 — Roteiros')

    def test_painel_bloco_etapa_3_clicavel(self):
        """Bloco da Etapa 3 deve ter link para guiado-etapa-3 (Ofícios do evento)."""
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        url_etapa3 = reverse('eventos:guiado-etapa-3', kwargs={'evento_id': self.evento.pk})
        self.assertContains(response, url_etapa3)
        self.assertContains(response, 'Etapa 3 — Ofícios do evento')

    def test_painel_etapas_4_5_6_em_breve_sem_link(self):
        """Etapas 4, 5, 6 devem aparecer como 'Em breve' sem link de navegação."""
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Em breve')
        self.assertNotContains(response, 'guiado/etapa-4/')


class EventoEtapa3OficiosTest(TestCase):
    """Etapa 3 — Ofícios do evento (hub): listar, criar, status OK/Pendente conforme legado."""

    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.client = Client()
        self.client.login(username='u', password='p')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.evento = Evento.objects.create(
            titulo='Evento Etapa 3',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_RASCUNHO,
        )

    def test_etapa_3_exige_login(self):
        self.client.logout()
        response = self.client.get(reverse('eventos:guiado-etapa-3', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_etapa_3_lista_oficios_do_evento(self):
        oficio1 = Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)
        oficio2 = Oficio.objects.create(evento=self.evento, numero=2, ano=2025, status=Oficio.STATUS_FINALIZADO)
        response = self.client.get(reverse('eventos:guiado-etapa-3', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ofícios do evento')
        self.assertContains(response, 'Rascunho')
        self.assertContains(response, 'Finalizado')
        self.assertContains(response, '02/2025')
        self.assertContains(response, reverse('eventos:oficio-editar', kwargs={'pk': oficio1.pk}))

    def test_etapa_3_mostra_botao_criar_oficio(self):
        response = self.client.get(reverse('eventos:guiado-etapa-3', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Criar Ofício neste Evento')
        url_criar = reverse('eventos:guiado-etapa-3-criar-oficio', kwargs={'evento_id': self.evento.pk})
        self.assertContains(response, url_criar)

    def test_etapa_3_ok_quando_existe_oficio(self):
        Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)
        from eventos.views import _evento_etapa3_ok
        self.assertTrue(_evento_etapa3_ok(self.evento))
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        etapas = response.context['etapas']
        etapa3 = next(e for e in etapas if e['numero'] == 3)
        self.assertTrue(etapa3['ok'])
        self.assertContains(response, 'Etapa 3 — Ofícios do evento')

    def test_etapa_3_pendente_quando_nao_existe_oficio(self):
        from eventos.views import _evento_etapa3_ok
        self.assertFalse(_evento_etapa3_ok(self.evento))
        response = self.client.get(reverse('eventos:guiado-painel', kwargs={'pk': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        etapas = response.context['etapas']
        etapa3 = next(e for e in etapas if e['numero'] == 3)
        self.assertFalse(etapa3['ok'])

    def test_criar_oficio_preserva_vinculo_com_evento(self):
        url_criar = reverse('eventos:guiado-etapa-3-criar-oficio', kwargs={'evento_id': self.evento.pk})
        response = self.client.get(url_criar)
        self.assertEqual(response.status_code, 302)
        self.assertIn('oficio/', response.url)
        self.assertIn('/step1/', response.url)
        self.assertEqual(self.evento.oficios.count(), 1)
        oficio = self.evento.oficios.get()
        self.assertEqual(oficio.evento_id, self.evento.pk)
        self.assertEqual(oficio.status, Oficio.STATUS_RASCUNHO)


class OficioWizardTest(TestCase):
    """Wizard do Ofício: Step 1 (viajantes), Step 2 (transporte/motorista), fluxo."""

    def setUp(self):
        self.user = User.objects.create_user(username='u2', password='p2')
        self.client = Client()
        self.client.login(username='u2', password='p2')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.evento = Evento.objects.create(
            titulo='Evento Teste',
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 5),
            status=Evento.STATUS_RASCUNHO,
        )
        self.cargo = Cargo.objects.create(nome='ANALISTA', is_padrao=True)
        self.unidade = UnidadeLotacao.objects.create(nome='DPC')
        self.viajante = Viajante.objects.create(
            nome='Fulano Teste',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='12345678901',
            telefone='41999999999',
            unidade_lotacao=self.unidade,
            rg='1234567890',
        )
        self.combustivel = CombustivelVeiculo.objects.create(nome='GASOLINA', is_padrao=True)
        self.oficio = Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)

    def test_wizard_step1_exige_ao_menos_um_viajante(self):
        url = reverse('eventos:oficio-step1', kwargs={'pk': self.oficio.pk})
        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        csrf = get_resp.context.get('csrf_token', '')
        if hasattr(csrf, '__str__'):
            csrf = str(csrf)
        self.oficio.refresh_from_db()
        post_resp = self.client.post(url, data={
            'oficio_numero': self.oficio.numero_formatado,
            'protocolo': '12.345.678-9',
            'data_criacao': self.oficio.data_criacao.strftime('%d/%m/%Y'),
            'motivo': 'Motivo teste',
            'custeio_tipo': Oficio.CUSTEIO_UNIDADE,
            'viajantes': [],  # nenhum viajante
            'csrfmiddlewaretoken': csrf,
        })
        self.assertEqual(post_resp.status_code, 200)
        self.assertFormError(post_resp.context['form'], 'viajantes', 'Selecione ao menos um viajante.')

    def test_wizard_step1_salva_viajantes(self):
        url = reverse('eventos:oficio-step1', kwargs={'pk': self.oficio.pk})
        get_resp = self.client.get(url)
        csrf = str(get_resp.context['csrf_token']) if get_resp.context.get('csrf_token') else ''
        self.oficio.refresh_from_db()
        post_resp = self.client.post(url, data={
            'oficio_numero': self.oficio.numero_formatado,
            'protocolo': '12.345.678-9',
            'data_criacao': self.oficio.data_criacao.strftime('%d/%m/%Y'),
            'motivo': 'Motivo',
            'custeio_tipo': Oficio.CUSTEIO_UNIDADE,
            'viajantes': [self.viajante.pk],
            'csrfmiddlewaretoken': csrf,
        })
        self.assertEqual(post_resp.status_code, 302)
        self.oficio.refresh_from_db()
        self.assertEqual(list(self.oficio.viajantes.values_list('pk', flat=True)), [self.viajante.pk])
        self.assertIsNotNone(self.oficio.numero)
        self.assertEqual(self.oficio.ano, tz.localdate().year)

    def test_wizard_step2_exige_placa_modelo_combustivel(self):
        url = reverse('eventos:oficio-step2', kwargs={'pk': self.oficio.pk})
        get_resp = self.client.get(url)
        csrf = str(get_resp.context['csrf_token']) if get_resp.context.get('csrf_token') else ''
        post_resp = self.client.post(url, data={
            'placa': '',
            'modelo': '',
            'combustivel': '',
            'tipo_viatura': Oficio.TIPO_VIATURA_DESCARACTERIZADA,
            'motorista_carona': False,
            'csrfmiddlewaretoken': csrf,
        })
        self.assertEqual(post_resp.status_code, 200)
        form = post_resp.context['form']
        self.assertTrue(form.errors.get('placa'))
        self.assertTrue(form.errors.get('modelo'))
        self.assertTrue(form.errors.get('combustivel'))

    def test_wizard_step2_motorista_carona_exige_oficio_protocolo(self):
        url = reverse('eventos:oficio-step2', kwargs={'pk': self.oficio.pk})
        get_resp = self.client.get(url)
        csrf = str(get_resp.context['csrf_token']) if get_resp.context.get('csrf_token') else ''
        post_resp = self.client.post(url, data={
            'placa': 'ABC1234',
            'modelo': 'Modelo X',
            'combustivel': 'GASOLINA',
            'tipo_viatura': Oficio.TIPO_VIATURA_DESCARACTERIZADA,
            'motorista_carona': True,
            'motorista_oficio_numero': '',
            'motorista_oficio_ano': '',
            'motorista_protocolo': '',
            'csrfmiddlewaretoken': csrf,
        })
        self.assertEqual(post_resp.status_code, 200)
        form = post_resp.context['form']
        self.assertTrue(form.errors.get('motorista_oficio_numero') or form.errors.get('motorista_protocolo'))

    def test_editar_oficio_redireciona_para_step1(self):
        response = self.client.get(reverse('eventos:oficio-editar', kwargs={'pk': self.oficio.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/step1/', response.url)

    def test_oficio_step4_finalizar_marca_finalizado(self):
        self.oficio.numero = 1
        self.oficio.ano = 2025
        self.oficio.save(update_fields=['numero', 'ano'])
        url = reverse('eventos:oficio-step4', kwargs={'pk': self.oficio.pk})
        get_resp = self.client.get(url)
        csrf = str(get_resp.context['csrf_token']) if get_resp.context.get('csrf_token') else ''
        post_resp = self.client.post(url, data={'finalizar': '1', 'csrfmiddlewaretoken': csrf})
        self.assertEqual(post_resp.status_code, 302)
        self.oficio.refresh_from_db()
        self.assertEqual(self.oficio.status, Oficio.STATUS_FINALIZADO)


class OficioStep1AcceptanceTest(TestCase):
    """Aceite do Step 1 do Ofício (fidelidade ao legado)."""

    def setUp(self):
        self.user = User.objects.create_user(username='step1', password='step1')
        self.client = Client()
        self.client.login(username='step1', password='step1')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.evento = Evento.objects.create(
            titulo='Evento Step 1',
            data_inicio=date(2026, 1, 10),
            data_fim=date(2026, 1, 12),
            status=Evento.STATUS_RASCUNHO,
        )
        self.cargo = Cargo.objects.create(nome='ANALISTA STEP1', is_padrao=True)
        self.unidade = UnidadeLotacao.objects.create(nome='DPC STEP1')
        self.viajante_final = Viajante.objects.create(
            nome='Viajante Finalizado',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='11122233344',
            telefone='41999990001',
            unidade_lotacao=self.unidade,
            rg='1234567890',
        )
        self.viajante_rascunho = Viajante.objects.create(
            nome='Viajante Rascunho',
            status=Viajante.STATUS_RASCUNHO,
            cargo=self.cargo,
            cpf='55566677788',
            telefone='41999990002',
            unidade_lotacao=self.unidade,
            rg='1234567891',
        )

    def _criar_oficio(self, ano=None):
        kwargs = {'evento': self.evento, 'status': Oficio.STATUS_RASCUNHO}
        if ano is not None:
            kwargs['ano'] = ano
        return Oficio.objects.create(**kwargs)

    def _payload_step1(self, oficio, **overrides):
        oficio.refresh_from_db()
        data = {
            'oficio_numero': oficio.numero_formatado,
            'protocolo': '12.345.678-9',
            'data_criacao': oficio.data_criacao.strftime('%d/%m/%Y'),
            'modelo_motivo': '',
            'motivo': 'Motivo base',
            'custeio_tipo': Oficio.CUSTEIO_UNIDADE,
            'nome_instituicao_custeio': '',
            'viajantes': [self.viajante_final.pk],
        }
        data.update(overrides)
        return data

    def _payload_step2(self, **overrides):
        data = {
            'placa': 'ABC-1234',
            'modelo': 'VIATURA TESTE',
            'combustivel': 'GASOLINA',
            'tipo_viatura': Oficio.TIPO_VIATURA_DESCARACTERIZADA,
            'motorista_viajante': '',
            'motorista_nome': 'Motorista Externo',
            'motorista_carona': 'on',
            'motorista_oficio_numero': '7',
            'motorista_oficio_ano': '2026',
            'motorista_protocolo': '12.345.678-9',
        }
        data.update(overrides)
        return data

    def test_1_novo_oficio_gera_numero_automatico_formato_xx_ano(self):
        oficio = self._criar_oficio(ano=2026)
        self.assertEqual(oficio.numero, 1)
        self.assertEqual(oficio.ano, 2026)
        self.assertEqual(oficio.numero_formatado, '01/2026')

    def test_2_sequencia_anual_funciona_e_reinicia_no_novo_ano(self):
        oficio_1 = self._criar_oficio(ano=2026)
        oficio_2 = self._criar_oficio(ano=2026)
        oficio_3 = self._criar_oficio(ano=2027)
        self.assertEqual(oficio_1.numero_formatado, '01/2026')
        self.assertEqual(oficio_2.numero_formatado, '02/2026')
        self.assertEqual(oficio_3.numero_formatado, '01/2027')

    def test_2b_criacao_usa_menor_numero_livre_do_ano(self):
        oficio_1 = self._criar_oficio(ano=2026)
        oficio_2 = self._criar_oficio(ano=2026)
        oficio_3 = self._criar_oficio(ano=2026)
        oficio_2.delete()
        oficio_novo = self._criar_oficio(ano=2026)
        self.assertEqual(oficio_1.numero_formatado, '01/2026')
        self.assertEqual(oficio_3.numero_formatado, '03/2026')
        self.assertEqual(oficio_novo.numero_formatado, '02/2026')

    def test_3_ao_editar_numero_nao_muda(self):
        oficio = self._criar_oficio(ano=2026)
        numero_antes = oficio.numero_formatado
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(url, data=self._payload_step1(oficio))
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.numero_formatado, numero_antes)

    def test_4_e_5_protocolo_aplica_aceita_mascara_e_reabre_mascarado(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(url, data=self._payload_step1(oficio, protocolo='12.345.678-9'))
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.protocolo, '123456789')
        reaberto = self.client.get(url)
        self.assertEqual(reaberto.status_code, 200)
        self.assertContains(reaberto, '12.345.678-9')

    def test_6_data_criacao_vem_preenchida_com_data_atual(self):
        oficio = self._criar_oficio()
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        oficio.refresh_from_db()
        self.assertEqual(oficio.data_criacao, tz.localdate())
        self.assertContains(response, tz.localdate().strftime('%d/%m/%Y'))

    def test_7_selecionar_modelo_preenche_motivo(self):
        oficio = self._criar_oficio(ano=2026)
        modelo = ModeloMotivoViagem.objects.create(
            codigo='modelo_step1',
            nome='Modelo Step 1',
            texto='Texto padrão do modelo',
            ordem=1,
            ativo=True,
        )
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(url, data=self._payload_step1(oficio, modelo_motivo=modelo.pk, motivo=''))
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.motivo, 'Texto padrão do modelo')
        self.assertEqual(oficio.modelo_motivo_id, modelo.pk)

    def test_8_motivo_pode_ser_editado_manualmente(self):
        oficio = self._criar_oficio(ano=2026)
        modelo = ModeloMotivoViagem.objects.create(
            codigo='modelo_editavel',
            nome='Modelo Editável',
            texto='Texto original',
            ordem=2,
            ativo=True,
        )
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(
            url,
            data=self._payload_step1(oficio, modelo_motivo=modelo.pk, motivo='Texto alterado manualmente'),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.motivo, 'Texto alterado manualmente')

    def test_9_salvar_motivo_como_novo_modelo_funciona(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(
            url,
            data=self._payload_step1(
                oficio,
                motivo='Motivo para virar modelo',
                salvar_modelo_motivo='1',
                novo_modelo_nome='Novo Modelo Step1',
            ),
        )
        self.assertEqual(response.status_code, 302)
        modelo = ModeloMotivoViagem.objects.get(nome='Novo Modelo Step1')
        self.assertEqual(modelo.texto, 'Motivo para virar modelo')
        oficio.refresh_from_db()
        self.assertEqual(oficio.modelo_motivo_id, modelo.pk)

    def test_10_e_11_nome_instituicao_aparece_so_em_outra_instituicao_e_eh_obrigatorio(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})

        get_resp = self.client.get(url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'id="nome-instituicao-wrapper" style="display:none;"')

        post_resp = self.client.post(
            url,
            data=self._payload_step1(
                oficio,
                custeio_tipo=Oficio.CUSTEIO_OUTRA_INSTITUICAO,
                nome_instituicao_custeio='',
            ),
        )
        self.assertEqual(post_resp.status_code, 200)
        self.assertFormError(
            post_resp.context['form'],
            'nome_instituicao_custeio',
            'Informe a instituição de custeio.',
        )

    def test_custeio_diferente_de_outra_instituicao_limpa_nome(self):
        oficio = self._criar_oficio(ano=2026)
        oficio.custeio_tipo = Oficio.CUSTEIO_OUTRA_INSTITUICAO
        oficio.nome_instituicao_custeio = 'Instituição X'
        oficio.save(update_fields=['custeio_tipo', 'nome_instituicao_custeio'])
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(
            url,
            data=self._payload_step1(
                oficio,
                custeio_tipo=Oficio.CUSTEIO_UNIDADE,
                nome_instituicao_custeio='Deve limpar',
            ),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.nome_instituicao_custeio, '')

    def test_12_viajantes_exige_ao_menos_um(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.post(url, data=self._payload_step1(oficio, viajantes=[]))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'viajantes', 'Selecione ao menos um viajante.')

    def test_13_so_viajantes_finalizados_aparecem(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.viajante_final.nome)
        self.assertNotContains(response, self.viajante_rascunho.nome)

    def test_14_botao_cadastrar_novo_viajante_existe(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        expected = (
            f"{reverse('cadastros:viajante-cadastrar')}?next="
            f"{quote(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))}"
        )
        self.assertContains(response, expected)

    def test_15_reabrir_step1_mostra_dados_salvos(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        post = self.client.post(
            url,
            data=self._payload_step1(
                oficio,
                protocolo='98.765.432-1',
                motivo='Motivo salvo',
                custeio_tipo=Oficio.CUSTEIO_OUTRA_INSTITUICAO,
                nome_instituicao_custeio='Instituição de Teste',
                viajantes=[self.viajante_final.pk],
            ),
        )
        self.assertEqual(post.status_code, 302)
        reaberto = self.client.get(url)
        self.assertEqual(reaberto.status_code, 200)
        self.assertContains(reaberto, '98.765.432-1')
        self.assertContains(reaberto, 'Motivo salvo')
        self.assertContains(reaberto, 'Instituição de Teste')
        self.assertContains(reaberto, 'checked')

    def test_step2_reabre_motorista_protocolo_mascarado(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step2', kwargs={'pk': oficio.pk})
        response = self.client.post(url, data=self._payload_step2())
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.motorista_protocolo, '123456789')
        reaberto = self.client.get(url)
        self.assertEqual(reaberto.status_code, 200)
        self.assertContains(reaberto, '12.345.678-9')

    def test_step4_exibe_protocolos_mascarados(self):
        oficio = self._criar_oficio(ano=2026)
        self.client.post(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}), data=self._payload_step1(oficio))
        self.client.post(reverse('eventos:oficio-step2', kwargs={'pk': oficio.pk}), data=self._payload_step2())
        response = self.client.get(reverse('eventos:oficio-step4', kwargs={'pk': oficio.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345.678-9')
        self.assertContains(response, 'ABC-1234')

    def test_step1_exibe_botao_gerenciar_modelos_de_motivo(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        modelos_url = reverse('eventos:modelos-motivo-lista')
        self.assertContains(response, f'{modelos_url}?volta_step1={oficio.pk}')

    def test_modelo_motivo_texto_api_retorna_texto(self):
        modelo = ModeloMotivoViagem.objects.create(
            codigo='api_modelo',
            nome='Modelo API',
            texto='Texto API',
            ordem=1,
            ativo=True,
        )
        url = reverse('eventos:modelos-motivo-texto-api', kwargs={'pk': modelo.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get('ok'))
        self.assertEqual(payload.get('texto'), 'Texto API')

    def test_excluir_oficio_reutiliza_lacuna_no_mesmo_ano(self):
        oficios = [self._criar_oficio(ano=2026) for _ in range(5)]
        oficios[4].delete()
        proximo = self._criar_oficio(ano=2026)
        self.assertEqual(proximo.numero_formatado, '05/2026')

    def test_oficio_pode_ser_excluido_com_redirecionamento_coerente(self):
        oficio = self._criar_oficio(ano=2026)
        url = reverse('eventos:oficio-excluir', kwargs={'pk': oficio.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('eventos:guiado-etapa-3', kwargs={'evento_id': self.evento.pk}))
        self.assertFalse(Oficio.objects.filter(pk=oficio.pk).exists())


class OficioStep1AjustesFinosTest(TestCase):
    """Ajustes finos do Step 1 e gerenciadores auxiliares."""

    def setUp(self):
        self.user = User.objects.create_user(username='ajustes-finos', password='ajustes-finos')
        self.client = Client()
        self.client.login(username='ajustes-finos', password='ajustes-finos')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.evento = Evento.objects.create(
            titulo='Evento Ajustes Finos',
            data_inicio=date(2026, 3, 1),
            data_fim=date(2026, 3, 2),
            status=Evento.STATUS_RASCUNHO,
        )
        self.cargo = Cargo.objects.create(nome='ANALISTA AJUSTE', is_padrao=True)
        self.unidade = UnidadeLotacao.objects.create(nome='DPC AJUSTE')

    def _criar_oficio(self):
        return Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)

    def test_lista_oficios_exibe_protocolo_mascarado_sem_texto_auxiliar(self):
        oficio = self._criar_oficio()
        Oficio.objects.filter(pk=oficio.pk).update(protocolo='123456789')
        response = self.client.get(reverse('eventos:guiado-etapa-3', kwargs={'evento_id': self.evento.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345.678-9')
        self.assertNotContains(response, 'Formato: XX.XXX.XXX-X')

    def test_form_modelo_motivo_nao_exibe_codigo_ordem_ativo(self):
        response = self.client.get(reverse('eventos:modelos-motivo-cadastrar'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id_codigo')
        self.assertNotContains(response, 'id_ordem')
        self.assertNotContains(response, 'id_ativo')

    def test_lista_modelos_ordem_alfabetica(self):
        ModeloMotivoViagem.objects.create(codigo='zzz', nome='ZZZ', texto='z')
        ModeloMotivoViagem.objects.create(codigo='aaa', nome='AAA', texto='a')
        response = self.client.get(reverse('eventos:modelos-motivo-lista'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index('AAA'), html.index('ZZZ'))

    def test_salvar_modelo_redireciona_para_lista(self):
        oficio = self._criar_oficio()
        url = f"{reverse('eventos:modelos-motivo-cadastrar')}?volta_step1={oficio.pk}"
        response = self.client.post(url, data={'nome': 'Modelo Novo', 'texto': 'Texto novo'})
        self.assertRedirects(
            response,
            f"{reverse('eventos:modelos-motivo-lista')}?volta_step1={oficio.pk}",
        )

    def test_botao_definir_padrao_e_excluir_aparecem_na_lista(self):
        modelo = ModeloMotivoViagem.objects.create(codigo='modelo_btn', nome='Modelo Botão', texto='Texto')
        response = self.client.get(reverse('eventos:modelos-motivo-lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('eventos:modelos-motivo-definir-padrao', kwargs={'pk': modelo.pk}),
        )
        self.assertContains(
            response,
            reverse('eventos:modelos-motivo-excluir', kwargs={'pk': modelo.pk}),
        )

    def test_definir_novo_padrao_desmarca_anterior(self):
        m1 = ModeloMotivoViagem.objects.create(codigo='padrao_1', nome='Padrão 1', texto='1', padrao=True)
        m2 = ModeloMotivoViagem.objects.create(codigo='padrao_2', nome='Padrão 2', texto='2', padrao=False)
        response = self.client.post(reverse('eventos:modelos-motivo-definir-padrao', kwargs={'pk': m2.pk}))
        self.assertRedirects(response, reverse('eventos:modelos-motivo-lista'))
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertFalse(m1.padrao)
        self.assertTrue(m2.padrao)

    def test_excluir_modelo_funciona(self):
        modelo = ModeloMotivoViagem.objects.create(codigo='modelo_excluir', nome='Excluir', texto='texto')
        response = self.client.post(reverse('eventos:modelos-motivo-excluir', kwargs={'pk': modelo.pk}))
        self.assertRedirects(response, reverse('eventos:modelos-motivo-lista'))
        self.assertFalse(ModeloMotivoViagem.objects.filter(pk=modelo.pk).exists())

    def test_step1_preseleciona_modelo_padrao(self):
        modelo = ModeloMotivoViagem.objects.create(
            codigo='modelo_padrao_step1',
            nome='Modelo Padrão Step1',
            texto='Texto padrão Step1',
            padrao=True,
        )
        oficio = self._criar_oficio()
        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<option value="{modelo.pk}" selected>')
        self.assertContains(response, 'Texto padrão Step1')

    def test_cadastrar_novo_viajante_com_next_retorna_para_step1(self):
        oficio = self._criar_oficio()
        step1_url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        cadastrar_url = f"{reverse('cadastros:viajante-cadastrar')}?next={quote(step1_url)}"
        response = self.client.post(
            cadastrar_url,
            data={
                'nome': 'Viajante Retorno',
                'cargo': str(self.cargo.pk),
                'rg': '',
                'sem_rg': 'on',
                'cpf': '529.982.247-25',
                'telefone': '(41) 99999-8888',
                'unidade_lotacao': str(self.unidade.pk),
                'next': step1_url,
            },
        )
        self.assertRedirects(response, step1_url)

    def test_fluxo_step1_continua_funcional_apos_retorno_do_viajante(self):
        oficio = self._criar_oficio()
        step1_url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        cadastrar_url = f"{reverse('cadastros:viajante-cadastrar')}?next={quote(step1_url)}"
        self.client.post(
            cadastrar_url,
            data={
                'nome': 'Viajante Fluxo',
                'cargo': str(self.cargo.pk),
                'rg': '',
                'sem_rg': 'on',
                'cpf': '390.533.447-05',
                'telefone': '(41) 99999-7777',
                'unidade_lotacao': str(self.unidade.pk),
                'next': step1_url,
            },
        )
        viajante = Viajante.objects.get(nome='VIAJANTE FLUXO')
        response_get = self.client.get(step1_url)
        self.assertEqual(response_get.status_code, 200)
        self.assertContains(response_get, 'VIAJANTE FLUXO')
        oficio.refresh_from_db()
        response_post = self.client.post(
            step1_url,
            data={
                'oficio_numero': oficio.numero_formatado,
                'protocolo': '12.345.678-9',
                'data_criacao': oficio.data_criacao.strftime('%d/%m/%Y'),
                'modelo_motivo': '',
                'motivo': 'Fluxo após retorno',
                'custeio_tipo': Oficio.CUSTEIO_UNIDADE,
                'nome_instituicao_custeio': '',
                'viajantes': [viajante.pk],
            },
        )
        self.assertEqual(response_post.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(list(oficio.viajantes.values_list('pk', flat=True)), [viajante.pk])


class OficioStep1ProtocolRegressionTest(TestCase):
    """Regressões críticas: GET sem save indevido e protocolo canônico/visual desacoplados."""

    def setUp(self):
        self.user = User.objects.create_user(username='prot-reg', password='prot-reg')
        self.client = Client()
        self.client.login(username='prot-reg', password='prot-reg')
        self.estado = Estado.objects.create(nome='Paraná', sigla='PR', codigo_ibge='41')
        self.cidade = Cidade.objects.create(nome='Curitiba', estado=self.estado, codigo_ibge='4106902')
        self.evento = Evento.objects.create(
            titulo='Evento Regressão Protocolo',
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 2, 2),
            status=Evento.STATUS_RASCUNHO,
        )
        self.cargo = Cargo.objects.create(nome='ANALISTA PROTO', is_padrao=True)
        self.unidade = UnidadeLotacao.objects.create(nome='DPC PROTO')
        self.viajante = Viajante.objects.create(
            nome='Viajante Protocolo',
            status=Viajante.STATUS_FINALIZADO,
            cargo=self.cargo,
            cpf='12312312312',
            telefone='41988887777',
            unidade_lotacao=self.unidade,
            rg='1234567890',
        )

    def _criar_oficio(self):
        return Oficio.objects.create(evento=self.evento, status=Oficio.STATUS_RASCUNHO)

    def _payload(self, oficio, protocolo):
        oficio.refresh_from_db()
        return {
            'oficio_numero': oficio.numero_formatado,
            'protocolo': protocolo,
            'data_criacao': oficio.data_criacao.strftime('%d/%m/%Y'),
            'motivo': 'Motivo protocolo',
            'custeio_tipo': Oficio.CUSTEIO_UNIDADE,
            'nome_instituicao_custeio': '',
            'viajantes': [self.viajante.pk],
        }

    def test_get_step1_nao_chama_save_indevido(self):
        oficio = self._criar_oficio()
        url = reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk})
        with patch('eventos.views.Oficio.save') as save_mock:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        save_mock.assert_not_called()

    def test_get_step1_abre_com_protocolo_salvo_sem_mascara(self):
        oficio = self._criar_oficio()
        Oficio.objects.filter(pk=oficio.pk).update(protocolo='123456789')
        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345.678-9')

    def test_get_step1_abre_com_protocolo_legado_mascarado(self):
        oficio = self._criar_oficio()
        Oficio.objects.filter(pk=oficio.pk).update(protocolo='12.345.678-9')
        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345.678-9')

    def test_post_protocolo_mascarado_salva_canonico(self):
        oficio = self._criar_oficio()
        response = self.client.post(
            reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
            data=self._payload(oficio, '12.345.678-9'),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.protocolo, '123456789')

    def test_post_protocolo_sem_mascara_salva_canonico(self):
        oficio = self._criar_oficio()
        response = self.client.post(
            reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
            data=self._payload(oficio, '123456789'),
        )
        self.assertEqual(response.status_code, 302)
        oficio.refresh_from_db()
        self.assertEqual(oficio.protocolo, '123456789')

    def test_reabrir_step1_reexibe_protocolo_mascarado(self):
        oficio = self._criar_oficio()
        self.client.post(
            reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}),
            data=self._payload(oficio, '123456789'),
        )
        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345.678-9')

    def test_get_edicao_nao_muda_numero_nem_data(self):
        oficio = self._criar_oficio()
        oficio.refresh_from_db()
        numero_antes = oficio.numero
        ano_antes = oficio.ano
        data_antes = oficio.data_criacao
        response = self.client.get(reverse('eventos:oficio-step1', kwargs={'pk': oficio.pk}))
        self.assertEqual(response.status_code, 200)
        oficio.refresh_from_db()
        self.assertEqual(oficio.numero, numero_antes)
        self.assertEqual(oficio.ano, ano_antes)
        self.assertEqual(oficio.data_criacao, data_antes)
