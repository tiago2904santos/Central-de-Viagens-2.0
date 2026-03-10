import os
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, Mock

from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth import get_user_model

from cadastros.models import Estado, Cidade, Cargo, ConfiguracaoSistema, Viajante, AssinaturaConfiguracao, Veiculo, UnidadeLotacao, CombustivelVeiculo

User = get_user_model()


class DatabaseConfigTest(TestCase):
    """Configuração do banco: PostgreSQL quando POSTGRES_DB está definido."""

    def test_sem_postgres_usar_sqlite(self):
        from config.settings import _get_db_config
        orig = os.environ.pop('POSTGRES_DB', None)
        try:
            config = _get_db_config()
            self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')
        finally:
            if orig is not None:
                os.environ['POSTGRES_DB'] = orig

    def test_com_postgres_usar_postgresql(self):
        from config.settings import _get_db_config
        orig = os.environ.get('POSTGRES_DB')
        os.environ['POSTGRES_DB'] = 'test_db'
        try:
            config = _get_db_config()
            self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
            self.assertEqual(config['NAME'], 'test_db')
        finally:
            if orig is not None:
                os.environ['POSTGRES_DB'] = orig
            else:
                os.environ.pop('POSTGRES_DB', None)


class ConfiguracoesViewTest(TestCase):
    """Configurações do sistema: exige login, GET 200, POST atualiza singleton."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_configuracoes_exige_login(self):
        response = self.client.get(reverse('cadastros:configuracoes'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_configuracoes_get_200_autenticado(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:configuracoes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Configurações do sistema')
        self.assertContains(response, 'Parâmetros globais')

    def _post_config_base(self, **extra):
        data = {
            'divisao': '',
            'unidade': '',
            'sigla_orgao': '',
            'cep': '',
            'logradouro': '',
            'bairro': '',
            'cidade_endereco': '',
            'uf': '',
            'numero': '',
            'telefone': '',
            'email': '',
            'assinatura_oficio': '',
            'assinatura_justificativas': '',
            'assinatura_planos_trabalho': '',
            'assinatura_ordens_servico': '',
        }
        data.update(extra)
        return self.client.post(reverse('cadastros:configuracoes'), data)

    def test_configuracoes_post_atualiza_singleton(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_config_base(sigla_orgao='ot')
        self.assertRedirects(response, reverse('cadastros:configuracoes'))
        obj = ConfiguracaoSistema.get_singleton()
        self.assertEqual(obj.sigla_orgao, 'OT')
        self.assertEqual(ConfiguracaoSistema.objects.count(), 1)

    def test_configuracoes_post_divisao_unidade_sigla_maiusculo(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_config_base(
            divisao='divisão teste',
            unidade='unidade teste',
            sigla_orgao='sigla',
        )
        self.assertRedirects(response, reverse('cadastros:configuracoes'))
        obj = ConfiguracaoSistema.get_singleton()
        self.assertEqual(obj.divisao, 'DIVISÃO TESTE')
        self.assertEqual(obj.unidade, 'UNIDADE TESTE')
        self.assertEqual(obj.sigla_orgao, 'SIGLA')

    def test_configuracoes_post_telefone_valido(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_config_base(telefone='41999998888')
        self.assertRedirects(response, reverse('cadastros:configuracoes'))
        obj = ConfiguracaoSistema.get_singleton()
        self.assertEqual(obj.telefone, '41999998888')

    def test_configuracoes_post_cep_valido_salva(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_config_base(cep='80010000')
        self.assertRedirects(response, reverse('cadastros:configuracoes'))
        obj = ConfiguracaoSistema.get_singleton()
        self.assertEqual(obj.cep, '80010-000')

    def test_configuracoes_reabrem_cep_e_telefone_mascarados(self):
        obj = ConfiguracaoSistema.get_singleton()
        obj.cep = '80010000'
        obj.telefone = '41999998888'
        obj.save(update_fields=['cep', 'telefone'])
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:configuracoes'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('80010-000', html)
        self.assertIn('(41) 99999-8888', html)

    def test_configuracoes_post_assinaturas_salvam_em_assinatura_configuracao(self):
        c1 = Cargo.objects.create(nome='Coordenador')
        c2 = Cargo.objects.create(nome='Analista')
        viajante1 = Viajante.objects.create(nome='Fulano Assinante', cargo=c1, status=Viajante.STATUS_FINALIZADO)
        viajante2 = Viajante.objects.create(nome='Beltrano Justificativas', cargo=c2, status=Viajante.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self._post_config_base(
            assinatura_oficio=str(viajante1.pk),
            assinatura_justificativas=str(viajante2.pk),
        )
        self.assertRedirects(response, reverse('cadastros:configuracoes'))
        config = ConfiguracaoSistema.get_singleton()
        rec_oficio = AssinaturaConfiguracao.objects.get(
            configuracao=config, tipo=AssinaturaConfiguracao.TIPO_OFICIO, ordem=1
        )
        rec_just = AssinaturaConfiguracao.objects.get(
            configuracao=config, tipo=AssinaturaConfiguracao.TIPO_JUSTIFICATIVA, ordem=1
        )
        self.assertEqual(rec_oficio.viajante_id, viajante1.pk)
        self.assertEqual(rec_just.viajante_id, viajante2.pk)

    def test_configuracoes_ui_nao_mostra_assinatura_oficios_2(self):
        """Ordem=2 de Ofícios não aparece na tela de configurações (apenas no admin)."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:configuracoes'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('id_assinatura_oficio_2', response.content.decode())
        self.assertIn('id_assinatura_oficio', response.content.decode())

    def test_configuracoes_cidade_sede_padrao_definida_quando_estado_cidade_existem(self):
        estado = Estado.objects.create(codigo_ibge='41', nome='Paraná', sigla='PR', ativo=True)
        cidade = Cidade.objects.create(
            codigo_ibge='4106902', nome='Curitiba', estado=estado, ativo=True
        )
        self.client.login(username='testuser', password='testpass123')
        response = self._post_config_base(
            uf='PR',
            cidade_endereco='Curitiba',
        )
        self.assertRedirects(response, reverse('cadastros:configuracoes'))
        obj = ConfiguracaoSistema.get_singleton()
        self.assertEqual(obj.cidade_sede_padrao_id, cidade.pk)

    def test_configuracoes_cidade_nao_encontrada_nao_quebra_e_gera_warning(self):
        self.client.login(username='testuser', password='testpass123')
        data = {
            'divisao': '', 'unidade': '', 'sigla_orgao': '',
            'cep': '', 'logradouro': '', 'bairro': '',
            'cidade_endereco': 'Cidade Inexistente No Banco',
            'uf': 'PR', 'numero': '', 'telefone': '', 'email': '',
            'assinatura_oficio': '', 'assinatura_justificativas': '',
            'assinatura_planos_trabalho': '', 'assinatura_ordens_servico': '',
        }
        response = self.client.post(
            reverse('cadastros:configuracoes'), data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        obj = ConfiguracaoSistema.get_singleton()
        self.assertIsNone(obj.cidade_sede_padrao_id)
        from django.contrib.messages import get_messages
        messages_list = list(get_messages(response.wsgi_request))
        warning_texts = [str(m) for m in messages_list if 'cidade sede padrão não foi definida' in str(m).lower()]
        self.assertTrue(len(warning_texts) >= 1, 'Deveria existir mensagem de aviso sobre cidade sede não definida')


class CargoViewTest(TestCase):
    """Cargos: CRUD, exclusão bloqueada quando em uso."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_cargo_lista_exige_login(self):
        response = self.client.get(reverse('cadastros:cargo-lista'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_cargo_criar_ok(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:cargo-cadastrar'), {'nome': ' Analista ', 'is_padrao': False})
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))
        self.assertEqual(Cargo.objects.count(), 1)
        c = Cargo.objects.get()
        self.assertEqual(c.nome, 'ANALISTA')

    def test_cargo_criar_padrao_unico(self):
        """Ao criar cargo como padrão, só esse fica padrão."""
        self.client.login(username='testuser', password='testpass123')
        c1 = Cargo.objects.create(nome='PRIMEIRO', is_padrao=True)
        self.assertTrue(c1.is_padrao)
        response = self.client.post(
            reverse('cadastros:cargo-cadastrar'),
            {'nome': 'Segundo Padrão', 'is_padrao': True},
        )
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))
        c1.refresh_from_db()
        c2 = Cargo.objects.get(nome='SEGUNDO PADRÃO')
        self.assertFalse(c1.is_padrao)
        self.assertTrue(c2.is_padrao)

    def test_cargo_definir_padrao_desmarca_outro(self):
        """Definir um cargo como padrão (POST) desmarca o anterior."""
        c1 = Cargo.objects.create(nome='A', is_padrao=True)
        c2 = Cargo.objects.create(nome='B', is_padrao=False)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:cargo-definir-padrao', kwargs={'pk': c2.pk}),
            follow=True,
        )
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_padrao)
        self.assertTrue(c2.is_padrao)

    def test_cargo_editar_ok(self):
        c = Cargo.objects.create(nome='Antes')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:cargo-editar', kwargs={'pk': c.pk}),
            {'nome': 'Depois', 'is_padrao': False},
        )
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))
        c.refresh_from_db()
        self.assertEqual(c.nome, 'DEPOIS')

    def test_cargo_excluir_nao_usado_ok(self):
        c = Cargo.objects.create(nome='Sem Uso')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:cargo-excluir', kwargs={'pk': c.pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Cargo.objects.filter(pk=c.pk).count(), 0)
        self.assertIn('excluído', response.content.decode().lower())

    def test_cargo_excluir_em_uso_impedido(self):
        c = Cargo.objects.create(nome='Em Uso')
        Viajante.objects.create(nome='Fulano', cargo=c)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:cargo-excluir', kwargs={'pk': c.pk}), follow=True)
        self.assertEqual(Cargo.objects.filter(pk=c.pk).count(), 1)
        self.assertIn('em uso', response.content.decode().lower())

    def test_cargo_nome_duplicado_rejeitado(self):
        """Não permite nome duplicado mesmo com minúsculo/espacos diferentes."""
        Cargo.objects.create(nome='ANALISTA')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:cargo-cadastrar'),
            {'nome': '  analista  ', 'is_padrao': False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'nome', 'Já existe um cargo com este nome.')
        response2 = self.client.post(
            reverse('cadastros:cargo-cadastrar'),
            {'nome': 'ANALISTA', 'is_padrao': False},
        )
        self.assertFormError(response2.context['form'], 'nome', 'Já existe um cargo com este nome.')

    def test_cargo_editar_mesmo_nome_nao_acusa_duplicado(self):
        """Ao editar, manter o mesmo nome não acusa duplicidade contra si mesmo."""
        c = Cargo.objects.create(nome='UNICO')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:cargo-editar', kwargs={'pk': c.pk}),
            {'nome': 'UNICO', 'is_padrao': False},
        )
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))


class ViajanteViewTest(TestCase):
    """Viajantes: lista exige login, CRUD com cargo FK, validações CPF/telefone, exclusão, sem_rg, máscaras."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.cargo = Cargo.objects.create(nome='Analista')

    def _post_viajante_base(self, **extra):
        data = {
            'nome': 'Fulano',
            'cargo': str(self.cargo.pk),
            'rg': '',
            'sem_rg': '',
            'cpf': '',
            'telefone': '',
            'unidade_lotacao': '',
        }
        data.update(extra)
        return self.client.post(reverse('cadastros:viajante-cadastrar'), data)

    def test_viajante_lista_exige_login(self):
        response = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_viajante_criar_ok_com_cargo_fk(self):
        """Criar com todos os dados obrigatórios preenchidos resulta em status FINALIZADO."""
        unidade = UnidadeLotacao.objects.create(nome='UNIDADE TESTE')
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(
            nome='Servidor Teste',
            cpf='529.982.247-25',
            telefone='(41) 99999-8888',
            unidade_lotacao=str(unidade.pk),
            sem_rg='on',
        )
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        self.assertEqual(Viajante.objects.count(), 1)
        v = Viajante.objects.get()
        self.assertEqual(v.nome, 'SERVIDOR TESTE')
        self.assertEqual(v.cargo_id, self.cargo.pk)
        self.assertEqual(v.status, Viajante.STATUS_FINALIZADO)

    def test_viajante_editar_ok(self):
        v = Viajante.objects.create(nome='ANTES', cargo=self.cargo)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}),
            {'nome': 'Depois', 'cargo': str(self.cargo.pk), 'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '',
             'unidade_lotacao': ''},
        )
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v.refresh_from_db()
        self.assertEqual(v.nome, 'DEPOIS')

    def test_viajante_excluir(self):
        v = Viajante.objects.create(nome='Para Excluir', cargo=self.cargo)
        pk = v.pk
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:viajante-excluir', kwargs={'pk': pk}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Viajante.objects.filter(pk=pk).count(), 0)
        self.assertIn('excluído', response.content.decode().lower())

    def test_viajante_cpf_invalido_falha(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(cpf='11111111111')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'cpf', 'CPF inválido.')

    def test_viajante_telefone_invalido_falha(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(telefone='123')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'telefone', 'Telefone deve ter 10 ou 11 dígitos.')

    def test_viajante_busca_por_cargo(self):
        Viajante.objects.create(nome='FULANO CARGO', cargo=self.cargo)
        c2 = Cargo.objects.create(nome='Outro')
        Viajante.objects.create(nome='BELTRANO', cargo=c2)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-lista') + '?q=Analista')
        self.assertContains(response, 'FULANO CARGO')
        self.assertNotContains(response, 'BELTRANO')

    def test_viajante_sem_rg_salva_nao_possui_rg(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(sem_rg='on', nome='Sem RG')
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v = Viajante.objects.get(nome='SEM RG')
        self.assertTrue(v.sem_rg)
        self.assertEqual(v.rg, 'NAO POSSUI RG')

    def test_viajante_sem_rg_false_rg_vazio_permitido(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(nome='Com RG vazio', sem_rg='')
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v = Viajante.objects.get(nome='COM RG VAZIO')
        self.assertFalse(v.sem_rg)
        self.assertEqual(v.rg, '')

    def test_viajante_cpf_telefone_salvos_como_digitos(self):
        self.client.login(username='testuser', password='testpass123')
        self._post_viajante_base(cpf='529.982.247-25', telefone='(41) 99999-8888')
        v = Viajante.objects.get()
        self.assertEqual(v.cpf, '52998224725')
        self.assertEqual(v.telefone, '41999998888')

    def test_viajante_rg_salvo_como_digitos_editar_mostra_mascarado(self):
        self.client.login(username='testuser', password='testpass123')
        self._post_viajante_base(nome='Com RG', rg='12.345.678-9')
        v = Viajante.objects.get(nome='COM RG')
        self.assertEqual(v.rg, '123456789')
        response = self.client.get(reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('12.345.678-9', response.content.decode())

    def test_viajante_rg_8_digitos_mascarado_editar_e_lista(self):
        Viajante.objects.create(nome='RG 8', cargo=self.cargo, rg='12345678')
        self.client.login(username='testuser', password='testpass123')
        r_edit = self.client.get(reverse('cadastros:viajante-editar', kwargs={'pk': Viajante.objects.get(nome='RG 8').pk}))
        self.assertIn('1.234.567-8', r_edit.content.decode())
        r_lista = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertIn('1.234.567-8', r_lista.content.decode())

    def test_viajante_lista_mostra_rg_mascarado(self):
        Viajante.objects.create(nome='FULANO RG', cargo=self.cargo, rg='123456789')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertIn('12.345.678-9', response.content.decode())
        self.assertContains(response, 'FULANO RG')

    def test_viajante_sem_rg_lista_mostra_nao_possui_rg(self):
        self.client.login(username='testuser', password='testpass123')
        self._post_viajante_base(sem_rg='on', nome='Sem RG Lista')
        response = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertContains(response, 'NÃO POSSUI RG')
        v = Viajante.objects.get(nome='SEM RG LISTA')
        self.assertEqual(v.rg, 'NAO POSSUI RG')

    def test_viajante_editar_sem_rg_mostra_travado_indicativo(self):
        v = Viajante.objects.create(nome='Sem RG Edit', cargo=self.cargo, sem_rg=True, rg='NAO POSSUI RG')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}))
        html = response.content.decode()
        self.assertIn('NAO POSSUI RG', html)
        self.assertIn('id_sem_rg', html)

    def test_viajante_editar_renderiza_cpf_telefone_mascarados(self):
        v = Viajante.objects.create(nome='Mascara', cargo=self.cargo, cpf='52998224725', telefone='41999998888')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('529.982.247-25', html)
        self.assertIn('(41) 99999-8888', html)

    def test_viajante_lista_cpf_telefone_mascarados(self):
        Viajante.objects.create(nome='Lista Mascara', cargo=self.cargo, cpf='10103532927', telefone='41999998888')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-lista'))
        html = response.content.decode()
        self.assertIn('101.035.329-27', html)
        self.assertIn('(41) 99999-8888', html)

    def test_viajante_nome_salvo_uppercase(self):
        self.client.login(username='testuser', password='testpass123')
        self._post_viajante_base(nome='Fulano Silva', cargo=str(self.cargo.pk))
        v = Viajante.objects.get()
        self.assertEqual(v.nome, 'FULANO SILVA')

    def test_viajante_cadastrar_form_cargo_padrao_pre_selecionado(self):
        """Ao abrir formulário de cadastrar viajante, o select cargo vem com o cargo padrão selecionado."""
        padrao = Cargo.objects.create(nome='CARGO PADRÃO', is_padrao=True)
        Cargo.objects.create(nome='OUTRO', is_padrao=False)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-cadastrar'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(f'value="{padrao.pk}"', html)
        self.assertIn('CARGO PADRÃO', html)
        self.assertIn('selected', html)

    def test_viajante_nome_duplicado_rejeitado(self):
        Viajante.objects.create(nome='JOAO SILVA', cargo=self.cargo)
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(nome='joao silva')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'nome', 'Já existe um cadastro com este nome.')

    def test_viajante_cpf_duplicado_rejeitado(self):
        cpf_valido = '52998224725'
        Viajante.objects.create(nome='PRIMEIRO', cargo=self.cargo, cpf=cpf_valido)
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(nome='Segundo', cpf='529.982.247-25')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'cpf', 'Já existe um cadastro com este CPF.')

    def test_viajante_rg_duplicado_rejeitado(self):
        Viajante.objects.create(nome='PRIMEIRO', cargo=self.cargo, rg='123456789')
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(nome='Segundo', rg='12.345.678-9')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'rg', 'Já existe um cadastro com este RG.')

    def test_viajante_telefone_duplicado_rejeitado(self):
        Viajante.objects.create(nome='PRIMEIRO', cargo=self.cargo, telefone='41999998888')
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(nome='Segundo', telefone='(41) 99999-8888')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'telefone', 'Já existe um cadastro com este telefone.')

    def test_viajante_editar_mesmo_nome_nao_acusa_duplicado(self):
        v = Viajante.objects.create(nome='UNICO NOME', cargo=self.cargo)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}),
            {'nome': 'UNICO NOME', 'cargo': str(self.cargo.pk), 'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '', 'unidade_lotacao': ''},
        )
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))

    def test_viajante_editar_mesmo_cpf_nao_acusa_duplicado(self):
        v = Viajante.objects.create(nome='COM CPF', cargo=self.cargo, cpf='52998224725')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}),
            {'nome': 'COM CPF', 'cargo': str(self.cargo.pk), 'rg': '', 'sem_rg': '', 'cpf': '529.982.247-25', 'telefone': '', 'unidade_lotacao': ''},
        )
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))

    def test_viajante_form_exibe_select_unidade(self):
        """Formulário de viajante exibe select de unidades de lotação (apenas nome)."""
        UnidadeLotacao.objects.create(nome='DEFENSORIA PÚBLICA')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-cadastrar'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('DEFENSORIA PÚBLICA', html)
        self.assertIn('id_unidade_lotacao', html)

    def test_viajante_criar_com_unidade_lotacao(self):
        """Criar viajante com unidade de lotação FK salva corretamente."""
        unidade = UnidadeLotacao.objects.create(nome='CORREGEDORIA GERAL')
        self.client.login(username='testuser', password='testpass123')
        data = {
            'nome': 'Servidor CGJ',
            'cargo': str(self.cargo.pk),
            'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '', 'unidade_lotacao': str(unidade.pk),
        }
        response = self.client.post(reverse('cadastros:viajante-cadastrar'), data)
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v = Viajante.objects.get(nome='SERVIDOR CGJ')
        self.assertEqual(v.unidade_lotacao_id, unidade.pk)

    def test_viajante_lista_e_form_mostram_unidade_pelo_nome(self):
        """Lista e form de viajante exibem unidade de lotação pelo nome (sem sigla)."""
        unidade = UnidadeLotacao.objects.create(nome='NÚCLEO DE APOIO')
        Viajante.objects.create(nome='FULANO', cargo=self.cargo, unidade_lotacao=unidade)
        self.client.login(username='testuser', password='testpass123')
        response_lista = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertContains(response_lista, 'NÚCLEO DE APOIO')
        response_editar = self.client.get(reverse('cadastros:viajante-editar', kwargs={'pk': Viajante.objects.get(nome='FULANO').pk}))
        self.assertContains(response_editar, 'NÚCLEO DE APOIO')

    def test_viajante_gerenciar_cargos_salva_rascunho_no_banco(self):
        """Clicar em Gerenciar Cargos cria viajante RASCUNHO no banco e redireciona para lista de cargos."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:viajante-cadastrar'))
        import re
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        data = {
            'nome': 'RASCUNHO CARGO',
            'cargo': str(self.cargo.pk),
            'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '', 'unidade_lotacao': '',
            'return_url': 'http://testserver/cadastros/viajantes/cadastrar/',
            'csrfmiddlewaretoken': csrf,
        }
        response = self.client.post(reverse('cadastros:viajante-rascunho-ir-cargos'), data, follow=False)
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))
        self.assertEqual(Viajante.objects.count(), 1)
        v = Viajante.objects.get()
        self.assertEqual(v.status, Viajante.STATUS_RASCUNHO)
        self.assertEqual(v.nome, 'RASCUNHO CARGO')
        self.assertIn('viajante_form_return_url', self.client.session)
        self.assertIn(f'/viajantes/{v.pk}/editar/', self.client.session['viajante_form_return_url'])

    def test_viajante_gerenciar_unidades_salva_rascunho_no_banco(self):
        """Clicar em Gerenciar Unidades de Lotação cria viajante RASCUNHO no banco e redireciona."""
        unidade = UnidadeLotacao.objects.create(nome='UNIDADE TESTE')
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:viajante-cadastrar'))
        import re
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        data = {
            'nome': 'RASCUNHO UN',
            'cargo': str(self.cargo.pk),
            'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '',
            'unidade_lotacao': str(unidade.pk),
            'return_url': 'http://testserver/cadastros/viajantes/cadastrar/',
            'csrfmiddlewaretoken': csrf,
        }
        response = self.client.post(reverse('cadastros:viajante-rascunho-ir-unidades'), data, follow=False)
        self.assertRedirects(response, reverse('cadastros:unidade-lotacao-lista'))
        self.assertEqual(Viajante.objects.count(), 1)
        v = Viajante.objects.get()
        self.assertEqual(v.status, Viajante.STATUS_RASCUNHO)
        self.assertIn('viajante_form_return_url', self.client.session)
        self.assertIn(f'/viajantes/{v.pk}/editar/', self.client.session['viajante_form_return_url'])

    def test_viajante_gerenciar_cargos_preserva_next_no_retorno(self):
        """Ao salvar rascunho para gerenciar cargos, o retorno preserva next para voltar ao fluxo de origem."""
        self.client.login(username='testuser', password='testpass123')
        next_url = '/eventos/oficio/123/step1/'
        response = self.client.post(
            reverse('cadastros:viajante-rascunho-ir-cargos'),
            data={
                'nome': 'RASCUNHO NEXT',
                'cargo': str(self.cargo.pk),
                'rg': '',
                'sem_rg': '',
                'cpf': '',
                'telefone': '',
                'unidade_lotacao': '',
                'next': next_url,
            },
        )
        self.assertRedirects(response, reverse('cadastros:cargo-lista'))
        return_url = self.client.session.get('viajante_form_return_url', '')
        self.assertIn('/viajantes/', return_url)
        self.assertIn('/editar/', return_url)
        self.assertIn('next=%2Feventos%2Foficio%2F123%2Fstep1%2F', return_url)

    def test_viajante_form_com_next_exibe_cancelar_para_origem(self):
        """Quando aberto com next, botão Cancelar aponta para a origem em vez da lista de viajantes."""
        self.client.login(username='testuser', password='testpass123')
        next_url = '/eventos/oficio/55/step1/'
        response = self.client.get(f"{reverse('cadastros:viajante-cadastrar')}?next={next_url}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{next_url}"')

    def test_viajante_voltar_edita_mesmo_rascunho(self):
        """Voltar do gerenciador abre a edição do mesmo viajante (rascunho) criado."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:viajante-cadastrar'))
        import re
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        data = {
            'nome': 'RESTAURADO VIAJANTE',
            'cargo': str(self.cargo.pk),
            'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '', 'unidade_lotacao': '',
            'return_url': 'http://testserver/cadastros/viajantes/cadastrar/',
            'csrfmiddlewaretoken': csrf,
        }
        self.client.post(reverse('cadastros:viajante-rascunho-ir-cargos'), data)
        v = Viajante.objects.get(nome='RESTAURADO VIAJANTE')
        return_url = self.client.session.get('viajante_form_return_url')
        self.assertIn(f'/viajantes/{v.pk}/editar/', return_url)
        response = self.client.get(return_url)
        self.assertContains(response, 'RESTAURADO VIAJANTE')

    def test_viajante_form_cargo_e_unidade_campos_separados(self):
        """Formulário exibe Cargo e Unidade de Lotação como campos separados com botões de gerenciamento."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-cadastrar'))
        html = response.content.decode()
        self.assertIn('id_cargo', html)
        self.assertIn('id_unidade_lotacao', html)
        self.assertIn('Gerenciar Cargos', html)
        self.assertIn('Gerenciar Unidades de Lotação', html)

    def test_viajante_cadastrar_abre_vazio_mesmo_com_rascunho_anterior(self):
        """+ Cadastrar abre formulário vazio mesmo existindo viajante em rascunho no banco."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:viajante-cadastrar'))
        m = __import__('re').search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        self.client.post(reverse('cadastros:viajante-rascunho-ir-cargos'), {
            'nome': 'RASCUNHO ANTIGO', 'cargo': str(self.cargo.pk),
            'rg': '', 'sem_rg': '', 'cpf': '', 'telefone': '', 'unidade_lotacao': '',
            'return_url': 'http://testserver/cadastros/viajantes/cadastrar/', 'csrfmiddlewaretoken': csrf,
        })
        self.assertEqual(Viajante.objects.count(), 1)
        response = self.client.get(reverse('cadastros:viajante-cadastrar'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('RASCUNHO ANTIGO', html)
        self.assertNotIn('value="RASCUNHO ANTIGO"', html)

    def test_viajante_rascunho_aparece_na_lista_com_status(self):
        """Viajante em rascunho aparece na lista com badge Rascunho."""
        Viajante.objects.create(nome='', cargo=self.cargo, status=Viajante.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertContains(response, 'Rascunho')
        self.assertContains(response, '(Rascunho)')

    def test_viajante_editar_rascunho_continua_mesmo_registro(self):
        """Editar item rascunho e preencher todos os dados obrigatórios permite finalizar o mesmo registro."""
        unidade = UnidadeLotacao.objects.create(nome='UNIDADE EDIT')
        v = Viajante.objects.create(nome='RASCUNHO EDIT', cargo=self.cargo, status=Viajante.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}))
        self.assertContains(response, 'RASCUNHO EDIT')
        response = self.client.post(
            reverse('cadastros:viajante-editar', kwargs={'pk': v.pk}),
            {
                'nome': 'FINALIZADO AGORA',
                'cargo': str(self.cargo.pk),
                'rg': '',
                'sem_rg': 'on',
                'cpf': '529.982.247-25',
                'telefone': '(41) 99999-8888',
                'unidade_lotacao': str(unidade.pk),
            },
        )
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v.refresh_from_db()
        self.assertEqual(v.status, Viajante.STATUS_FINALIZADO)
        self.assertEqual(v.nome, 'FINALIZADO AGORA')

    def test_viajante_salvar_definitivamente_marca_finalizado(self):
        """Salvar formulário com todos os dados obrigatórios marca viajante como FINALIZADO."""
        unidade = UnidadeLotacao.objects.create(nome='UNIDADE FINAL')
        self.client.login(username='testuser', password='testpass123')
        self._post_viajante_base(
            nome='FINAL VIAJANTE',
            cpf='529.982.247-25',
            telefone='(41) 99999-8888',
            unidade_lotacao=str(unidade.pk),
            sem_rg='on',
        )
        v = Viajante.objects.get(nome='FINAL VIAJANTE')
        self.assertEqual(v.status, Viajante.STATUS_FINALIZADO)

    def test_viajante_lista_mostra_status_corretamente(self):
        """Lista exibe coluna Status com Rascunho e Finalizado."""
        Viajante.objects.create(nome='A RASCUNHO', cargo=self.cargo, status=Viajante.STATUS_RASCUNHO)
        Viajante.objects.create(nome='B FINAL', cargo=self.cargo, status=Viajante.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:viajante-lista'))
        self.assertContains(response, 'Rascunho')
        self.assertContains(response, 'Finalizado')
        self.assertContains(response, 'A RASCUNHO')
        self.assertContains(response, 'B FINAL')

    def test_viajante_salvar_incompleto_status_rascunho(self):
        """Salvar viajante sem todos os dados obrigatórios resulta em status RASCUNHO."""
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(nome='Incompleto')
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v = Viajante.objects.get(nome='INCOMPLETO')
        self.assertEqual(v.status, Viajante.STATUS_RASCUNHO)

    def test_viajante_salvar_completo_status_finalizado(self):
        """Salvar viajante com todos os dados obrigatórios resulta em status FINALIZADO."""
        unidade = UnidadeLotacao.objects.create(nome='UNIDADE OK')
        self.client.login(username='testuser', password='testpass123')
        response = self._post_viajante_base(
            nome='Completo',
            cpf='529.982.247-25',
            telefone='(41) 99999-8888',
            unidade_lotacao=str(unidade.pk),
            sem_rg='on',
        )
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v = Viajante.objects.get(nome='COMPLETO')
        self.assertEqual(v.status, Viajante.STATUS_FINALIZADO)

    def test_viajante_rascunho_nao_aparece_queryset_assinaturas(self):
        """Viajante em RASCUNHO não aparece no queryset de assinaturas (configurações)."""
        Viajante.objects.create(nome='RASCUNHO ASSIN', cargo=self.cargo, status=Viajante.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        from cadastros.forms import ConfiguracaoSistemaForm
        form = ConfiguracaoSistemaForm(instance=ConfiguracaoSistema.get_singleton())
        qs_ids = list(form.fields['assinatura_oficio'].queryset.values_list('pk', flat=True))
        rascunho_pk = Viajante.objects.get(nome='RASCUNHO ASSIN').pk
        self.assertNotIn(rascunho_pk, qs_ids)

    def test_viajante_finalizado_aparece_queryset_assinaturas(self):
        """Viajante FINALIZADO aparece no queryset de assinaturas (configurações)."""
        v = Viajante.objects.create(nome='FINAL ASSIN', cargo=self.cargo, status=Viajante.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        from cadastros.forms import ConfiguracaoSistemaForm
        form = ConfiguracaoSistemaForm(instance=ConfiguracaoSistema.get_singleton())
        qs_ids = list(form.fields['assinatura_oficio'].queryset.values_list('pk', flat=True))
        self.assertIn(v.pk, qs_ids)

    def test_viajante_rg_ou_sem_rg_fecha_completude(self):
        """RG preenchido OU sem_rg=True é obrigatório para status FINALIZADO."""
        unidade = UnidadeLotacao.objects.create(nome='UNIDADE RG')
        self.client.login(username='testuser', password='testpass123')
        data = {
            'nome': 'Sem RG nem preenchido',
            'cargo': str(self.cargo.pk),
            'rg': '',
            'sem_rg': '',
            'cpf': '529.982.247-25',
            'telefone': '(41) 99999-8888',
            'unidade_lotacao': str(unidade.pk),
        }
        response = self.client.post(reverse('cadastros:viajante-cadastrar'), data)
        self.assertRedirects(response, reverse('cadastros:viajante-lista'))
        v = Viajante.objects.get(nome='SEM RG NEM PREENCHIDO')
        self.assertEqual(v.status, Viajante.STATUS_RASCUNHO)
        v.sem_rg = True
        v.save(update_fields=['sem_rg'])
        v.rg = 'NAO POSSUI RG'
        v.save(update_fields=['rg'])
        self.assertTrue(v.esta_completo())


class ImportUnidadesLotacaoTest(TestCase):
    """Importação de unidades de lotação via CSV: idempotente."""

    def test_import_cria_unidades(self):
        """Comando cria unidades a partir do CSV de teste (coluna NOME)."""
        csv_path = Path(__file__).parent / 'fixtures' / 'unidades_lotacao.csv'
        self.assertTrue(csv_path.exists(), f'Fixture {csv_path} deve existir')
        call_command('importar_unidades_lotacao', str(csv_path))
        self.assertEqual(UnidadeLotacao.objects.count(), 3)
        dpe = UnidadeLotacao.objects.get(nome='DEFENSORIA PÚBLICA DO ESTADO')
        self.assertEqual(dpe.nome, 'DEFENSORIA PÚBLICA DO ESTADO')
        ascom = UnidadeLotacao.objects.get(nome='ASSESSORIA DE COMUNICAÇÃO')
        self.assertEqual(ascom.nome, 'ASSESSORIA DE COMUNICAÇÃO')

    def test_import_idempotente(self):
        """Rodar importação 2x não duplica registros."""
        csv_path = Path(__file__).parent / 'fixtures' / 'unidades_lotacao.csv'
        call_command('importar_unidades_lotacao', str(csv_path))
        count1 = UnidadeLotacao.objects.count()
        call_command('importar_unidades_lotacao', str(csv_path))
        count2 = UnidadeLotacao.objects.count()
        self.assertEqual(count1, count2, 'Segunda execução não deve criar duplicatas')

    def test_import_falha_sem_coluna_nome(self):
        """Comando não importa e emite erro quando CSV não tem coluna NOME."""
        import tempfile
        from io import StringIO
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write('SIGLA\nDPE\n')
            bad_path = f.name
        try:
            out = StringIO()
            err = StringIO()
            call_command('importar_unidades_lotacao', bad_path, stdout=out, stderr=err)
            self.assertEqual(UnidadeLotacao.objects.count(), 0, 'Nenhuma unidade deve ser criada')
            self.assertIn('NOME', err.getvalue())
        finally:
            Path(bad_path).unlink(missing_ok=True)


class VeiculoViewTest(TestCase):
    """Veículos: placa antiga/mercosul, único, máscara; combustível FK; tipo."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.combustivel = CombustivelVeiculo.objects.create(nome='GASOLINA')

    def _post_veiculo(self, placa, modelo='FIAT', combustivel=None, tipo='CARACTERIZADO'):
        data = {'placa': placa, 'modelo': modelo, 'tipo': tipo}
        data['combustivel'] = str(combustivel.pk) if combustivel else ''
        return self.client.post(reverse('cadastros:veiculo-cadastrar'), data)

    def test_veiculo_placa_antiga_ok(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_veiculo('ABC1234', combustivel=self.combustivel)
        self.assertRedirects(response, reverse('cadastros:veiculo-lista'))
        v = Veiculo.objects.get(placa='ABC1234')
        self.assertEqual(v.modelo, 'FIAT')
        self.assertEqual(v.status, Veiculo.STATUS_FINALIZADO)

    def test_veiculo_placa_mercosul_ok(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_veiculo('ABC1D23', combustivel=self.combustivel)
        self.assertRedirects(response, reverse('cadastros:veiculo-lista'))
        v = Veiculo.objects.get(placa='ABC1D23')

    def test_veiculo_placa_invalida_falha(self):
        self.client.login(username='testuser', password='testpass123')
        response = self._post_veiculo('INVALIDA', combustivel=self.combustivel)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'placa', 'Placa inválida. Use padrão antigo (ABC-1234) ou Mercosul (ABC1D23).')

    def test_veiculo_placa_duplicada_rejeitada(self):
        Veiculo.objects.create(placa='ABC1D23', modelo='OUTRO', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self._post_veiculo('ABC-1D23', modelo='Outro')
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'placa', 'Já existe um cadastro com esta placa.')
        response2 = self._post_veiculo('abc1d23', modelo='Outro')
        self.assertFormError(response2.context['form'], 'placa', 'Já existe um cadastro com esta placa.')

    def test_veiculo_placa_normalizada_salva(self):
        self.client.login(username='testuser', password='testpass123')
        self._post_veiculo('ABC1D23', modelo='Fiat')
        v = Veiculo.objects.get(placa='ABC1D23')
        self.assertEqual(v.placa, 'ABC1D23')

    def test_veiculo_editar_exibe_placa_mascarada(self):
        """Placa exibida no formulário de edição com máscara visual consistente."""
        v = Veiculo.objects.create(placa='ABC1234', modelo='FIAT', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('ABC-1234', response.content.decode())

    def test_veiculo_lista_exibe_placa_mascarada(self):
        """Placa exibida na lista com máscara visual consistente."""
        Veiculo.objects.create(placa='ABC1234', modelo='FIAT', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-lista'))
        self.assertIn('ABC-1234', response.content.decode())

    def test_veiculo_excluir_remove_do_banco(self):
        v = Veiculo.objects.create(placa='XYZ1234', modelo='FIAT', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:veiculo-excluir', kwargs={'pk': v.pk}), follow=True)
        self.assertEqual(Veiculo.objects.filter(pk=v.pk).count(), 0)
        self.assertIn('excluído', response.content.decode().lower())

    def test_veiculo_editar_mesma_placa_nao_acusa_duplicado(self):
        v = Veiculo.objects.create(placa='XYZ1234', modelo='FIAT', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}),
            {'placa': 'XYZ-1234', 'modelo': 'FIAT', 'combustivel': str(self.combustivel.pk), 'tipo': 'CARACTERIZADO'},
        )
        self.assertRedirects(response, reverse('cadastros:veiculo-lista'))
        v.refresh_from_db()
        self.assertEqual(v.placa, 'XYZ1234')

    def test_veiculo_form_combustivel_padrao_preselecionado(self):
        padrao = CombustivelVeiculo.objects.create(nome='DIESEL', is_padrao=True)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('selected', html)
        self.assertIn('DIESEL', html)

    def test_veiculo_gerenciar_combustiveis_salva_rascunho_no_banco(self):
        """Clicar em Gerenciar Combustíveis cria veículo RASCUNHO no banco e redireciona."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        import re
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        data = {
            'placa': 'XYZ9876',
            'modelo': 'RASCUNHO',
            'combustivel': str(self.combustivel.pk),
            'tipo': 'DESCARACTERIZADO',
            'csrfmiddlewaretoken': csrf,
        }
        response = self.client.post(reverse('cadastros:veiculo-rascunho-ir-combustiveis'), data, follow=False)
        self.assertRedirects(response, reverse('cadastros:combustivel-lista'))
        v = Veiculo.objects.get(modelo='RASCUNHO')
        self.assertEqual(v.status, Veiculo.STATUS_RASCUNHO)
        self.assertEqual(v.placa, 'XYZ9876')
        self.assertIn('veiculo_form_return_url', self.client.session)

    def test_veiculo_voltar_edita_mesmo_rascunho(self):
        """Voltar do gerenciador leva à edição do mesmo veículo rascunho."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        import re
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        data = {
            'placa': 'AAA1122',
            'modelo': 'RESTAURAR',
            'combustivel': str(self.combustivel.pk),
            'tipo': 'CARACTERIZADO',
            'csrfmiddlewaretoken': csrf,
        }
        self.client.post(reverse('cadastros:veiculo-rascunho-ir-combustiveis'), data)
        v = Veiculo.objects.get(modelo='RESTAURAR')
        response = self.client.get(reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}))
        self.assertContains(response, 'RESTAURAR')
        self.assertContains(response, 'AAA-1122')

    def test_veiculo_tipo_editavel(self):
        """Campo tipo (CARACTERIZADO/DESCARACTERIZADO) é editável no formulário."""
        v = Veiculo.objects.create(placa='TIP0123', modelo='M', combustivel=self.combustivel, tipo='CARACTERIZADO', status=Veiculo.STATUS_FINALIZADO)
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}))
        self.assertContains(r, 'CARACTERIZADO')
        self.assertContains(r, 'DESCARACTERIZADO')
        import re
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        response2 = self.client.post(
            reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}),
            {
                'placa': 'TIP0123', 'modelo': 'M', 'combustivel': str(self.combustivel.pk),
                'tipo': 'DESCARACTERIZADO', 'csrfmiddlewaretoken': csrf,
            },
        )
        self.assertRedirects(response2, reverse('cadastros:veiculo-lista'))
        v.refresh_from_db()
        self.assertEqual(v.tipo, 'DESCARACTERIZADO')

    def test_veiculo_cadastrar_abre_vazio_mesmo_com_rascunho_anterior(self):
        """+ Cadastrar sempre abre formulário vazio; não restaura rascunho de sessão."""
        Veiculo.objects.create(placa='', modelo='Rascunho antigo', status=Veiculo.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('Rascunho antigo', html)
        self.assertIn('id_placa', html)

    def test_veiculo_rascunho_aparece_na_lista_com_status(self):
        """Veículo em rascunho aparece na lista com badge RASCUNHO."""
        Veiculo.objects.create(placa='', modelo='Rascunho', status=Veiculo.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-lista'))
        self.assertContains(response, 'RASCUNHO')
        self.assertContains(response, '(Rascunho)')

    def test_veiculo_editar_rascunho_continua_mesmo_registro(self):
        """Editar item rascunho pela lista abre o mesmo registro e permite finalizar."""
        v = Veiculo.objects.create(placa='', modelo='RASCUNHO', status=Veiculo.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}))
        self.assertContains(r, 'RASCUNHO')
        m = __import__('re').search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        self.client.post(
            reverse('cadastros:veiculo-editar', kwargs={'pk': v.pk}),
            {'placa': 'FIM1234', 'modelo': 'RASCUNHO', 'combustivel': str(self.combustivel.pk), 'tipo': 'DESCARACTERIZADO', 'csrfmiddlewaretoken': csrf},
        )
        v.refresh_from_db()
        self.assertEqual(v.status, Veiculo.STATUS_FINALIZADO)
        self.assertEqual(v.placa, 'FIM1234')

    def test_veiculo_cadastro_novo_tipo_padrao_descaracterizado(self):
        """Formulário de cadastro novo tem tipo pré-selecionado DESCARACTERIZADO."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        html = response.content.decode()
        self.assertIn('DESCARACTERIZADO', html)
        self.assertIn('Descaracterizado', html)

    def test_veiculo_lista_mostra_status_corretamente(self):
        """Lista exibe coluna Status com Rascunho e Finalizado (labels padronizados)."""
        Veiculo.objects.create(placa='FIN1234', modelo='F', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        Veiculo.objects.create(placa='', modelo='R', status=Veiculo.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:veiculo-lista'))
        self.assertContains(response, 'Finalizado')
        self.assertContains(response, 'Rascunho')
        self.assertContains(response, 'FIN-1234')
        self.assertContains(response, '(Rascunho)')

    def test_veiculo_salvar_incompleto_status_rascunho(self):
        """Salvar veículo sem todos os dados obrigatórios resulta em status RASCUNHO."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        m = __import__('re').search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        response = self.client.post(reverse('cadastros:veiculo-cadastrar'), {
            'placa': '',
            'modelo': 'Incompleto',
            'combustivel': '',
            'tipo': 'DESCARACTERIZADO',
            'csrfmiddlewaretoken': csrf,
        })
        self.assertRedirects(response, reverse('cadastros:veiculo-lista'))
        v = Veiculo.objects.get(modelo='INCOMPLETO')
        self.assertEqual(v.status, Veiculo.STATUS_RASCUNHO)

    def test_veiculo_salvar_completo_status_finalizado(self):
        """Salvar veículo com placa, modelo, combustível e tipo resulta em status FINALIZADO."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        m = __import__('re').search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        data = {'placa': 'OKA1234', 'modelo': 'Completo', 'combustivel': str(self.combustivel.pk), 'tipo': 'DESCARACTERIZADO', 'csrfmiddlewaretoken': csrf}
        response = self.client.post(reverse('cadastros:veiculo-cadastrar'), data)
        self.assertRedirects(response, reverse('cadastros:veiculo-lista'))
        v = Veiculo.objects.get(placa='OKA1234')
        self.assertEqual(v.status, Veiculo.STATUS_FINALIZADO)

    def test_veiculo_rascunho_nao_aparece_queryset_operacional(self):
        """Veículo em RASCUNHO não aparece no queryset de veículos finalizados (uso operacional)."""
        v_r = Veiculo.objects.create(placa='', modelo='Rascunho', status=Veiculo.STATUS_RASCUNHO)
        self.client.login(username='testuser', password='testpass123')
        from cadastros.forms import _veiculos_operacionais_queryset
        qs_ids = list(_veiculos_operacionais_queryset().values_list('pk', flat=True))
        self.assertNotIn(v_r.pk, qs_ids)

    def test_veiculo_finalizado_aparece_queryset_operacional(self):
        """Veículo FINALIZADO aparece no queryset de veículos finalizados (uso operacional)."""
        v_f = Veiculo.objects.create(placa='OP1234', modelo='F', combustivel=self.combustivel, status=Veiculo.STATUS_FINALIZADO)
        from cadastros.forms import _veiculos_operacionais_queryset
        qs_ids = list(_veiculos_operacionais_queryset().values_list('pk', flat=True))
        self.assertIn(v_f.pk, qs_ids)

    def test_veiculo_tipo_padrao_sozinho_nao_finaliza(self):
        """Tipo padrão DESCARACTERIZADO sozinho não torna o veículo FINALIZADO se faltarem outros campos."""
        self.client.login(username='testuser', password='testpass123')
        r = self.client.get(reverse('cadastros:veiculo-cadastrar'))
        m = __import__('re').search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.content.decode())
        csrf = m.group(1) if m else ''
        response = self.client.post(reverse('cadastros:veiculo-cadastrar'), {
            'placa': '',
            'modelo': '',
            'combustivel': '',
            'tipo': 'DESCARACTERIZADO',
            'csrfmiddlewaretoken': csrf,
        })
        self.assertRedirects(response, reverse('cadastros:veiculo-lista'))
        self.assertEqual(Veiculo.objects.count(), 1)
        v = Veiculo.objects.get()
        self.assertEqual(v.status, Veiculo.STATUS_RASCUNHO)
        self.assertEqual(v.tipo, Veiculo.TIPO_DESCARACTERIZADO)


class CombustivelViewTest(TestCase):
    """Combustíveis: CRUD, um único padrão, bloquear exclusão se em uso."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_combustivel_criar(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:combustivel-cadastrar'),
            {'nome': ' Gasolina ', 'is_padrao': False},
        )
        self.assertRedirects(response, reverse('cadastros:combustivel-lista'))
        c = CombustivelVeiculo.objects.get(nome='GASOLINA')

    def test_combustivel_definir_padrao_unico(self):
        c1 = CombustivelVeiculo.objects.create(nome='A', is_padrao=True)
        c2 = CombustivelVeiculo.objects.create(nome='B', is_padrao=False)
        self.client.login(username='testuser', password='testpass123')
        self.client.post(reverse('cadastros:combustivel-definir-padrao', kwargs={'pk': c2.pk}))
        c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertFalse(c1.is_padrao)
        self.assertTrue(c2.is_padrao)

    def test_combustivel_segundo_padrao_desmarca_primeiro(self):
        CombustivelVeiculo.objects.create(nome='PRIMEIRO', is_padrao=True)
        self.client.login(username='testuser', password='testpass123')
        self.client.post(
            reverse('cadastros:combustivel-cadastrar'),
            {'nome': 'Segundo', 'is_padrao': True},
        )
        primeiro = CombustivelVeiculo.objects.get(nome='PRIMEIRO')
        self.assertFalse(primeiro.is_padrao)
        segundo = CombustivelVeiculo.objects.get(nome='SEGUNDO')
        self.assertTrue(segundo.is_padrao)

    def test_combustivel_excluir_em_uso_impedido(self):
        c = CombustivelVeiculo.objects.create(nome='GASOLINA')
        Veiculo.objects.create(placa='ABC1234', modelo='FIAT', combustivel=c)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:combustivel-excluir', kwargs={'pk': c.pk}), follow=True)
        self.assertEqual(CombustivelVeiculo.objects.filter(pk=c.pk).count(), 1)
        self.assertIn('em uso', response.content.decode().lower())


class UnidadeLotacaoViewTest(TestCase):
    """Unidades de Lotação: CRUD; bloquear exclusão quando em uso por viajante."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_unidade_criar(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:unidade-lotacao-cadastrar'),
            {'nome': '  nova unidade  '},
        )
        self.assertRedirects(response, reverse('cadastros:unidade-lotacao-lista'))
        u = UnidadeLotacao.objects.get(nome='NOVA UNIDADE')

    def test_unidade_editar(self):
        u = UnidadeLotacao.objects.create(nome='ORIGINAL')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('cadastros:unidade-lotacao-editar', kwargs={'pk': u.pk}),
            {'nome': '  editada  '},
        )
        self.assertRedirects(response, reverse('cadastros:unidade-lotacao-lista'))
        u.refresh_from_db()
        self.assertEqual(u.nome, 'EDITADA')

    def test_unidade_excluir_quando_nao_em_uso(self):
        u = UnidadeLotacao.objects.create(nome='SEM VIAJANTE')
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:unidade-lotacao-excluir', kwargs={'pk': u.pk}), follow=True)
        self.assertEqual(UnidadeLotacao.objects.filter(pk=u.pk).count(), 0)
        self.assertIn('excluída', response.content.decode().lower())

    def test_unidade_excluir_em_uso_bloqueado(self):
        u = UnidadeLotacao.objects.create(nome='EM USO')
        Cargo.objects.create(nome='CARGOTEST')
        v = Viajante.objects.create(nome='VIAJANTE UN', unidade_lotacao=u)
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('cadastros:unidade-lotacao-excluir', kwargs={'pk': u.pk}), follow=True)
        self.assertEqual(UnidadeLotacao.objects.filter(pk=u.pk).count(), 1)
        self.assertIn('em uso', response.content.decode().lower())


class ImportEstadosTest(TestCase):
    def test_importar_estados_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            f.write('COD,NOME,SIGLA\n')
            f.write('35,São Paulo,SP\n')
            f.write('33,Rio de Janeiro,RJ\n')
            path = f.name
        try:
            call_command('importar_base_geografica', '--estados', path)
            self.assertEqual(Estado.objects.count(), 2)
            sp = Estado.objects.get(codigo_ibge='35')
            self.assertEqual(sp.nome, 'São Paulo')
            self.assertEqual(sp.sigla, 'SP')
        finally:
            Path(path).unlink(missing_ok=True)

    def test_importar_estados_idempotente(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            f.write('COD,NOME,SIGLA\n')
            f.write('35,São Paulo,SP\n')
            path = f.name
        try:
            call_command('importar_base_geografica', '--estados', path)
            call_command('importar_base_geografica', '--estados', path)
            self.assertEqual(Estado.objects.count(), 1)
            sp = Estado.objects.get(codigo_ibge='35')
            self.assertEqual(sp.nome, 'São Paulo')
        finally:
            Path(path).unlink(missing_ok=True)


class ImportCidadesTest(TestCase):
    def setUp(self):
        Estado.objects.create(codigo_ibge='35', nome='São Paulo', sigla='SP', ativo=True)

    def test_importar_cidades_csv(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            f.write('COD UF,COD,NOME\n')
            f.write('35,3550308,São Paulo\n')
            f.write('35,3509502,Campinas\n')
            path = f.name
        try:
            call_command('importar_base_geografica', '--cidades', path)
            self.assertEqual(Cidade.objects.count(), 2)
            sp = Cidade.objects.get(codigo_ibge='3550308')
            self.assertEqual(sp.nome, 'São Paulo')
            self.assertEqual(sp.estado.codigo_ibge, '35')
        finally:
            Path(path).unlink(missing_ok=True)

    def test_importar_cidades_idempotente(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            f.write('COD UF,COD,NOME\n')
            f.write('35,3550308,São Paulo\n')
            path = f.name
        try:
            call_command('importar_base_geografica', '--cidades', path)
            call_command('importar_base_geografica', '--cidades', path)
            self.assertEqual(Cidade.objects.count(), 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_importar_cidade_estado_inexistente_nao_quebra(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            f.write('COD UF,COD,NOME\n')
            f.write('99,9999999,Fantasia\n')
            path = f.name
        try:
            call_command('importar_base_geografica', '--cidades', path)
            self.assertEqual(Cidade.objects.count(), 0)
        finally:
            Path(path).unlink(missing_ok=True)


class ApiCidadesPorEstadoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.estado = Estado.objects.create(codigo_ibge='35', nome='São Paulo', sigla='SP', ativo=True)
        Cidade.objects.create(codigo_ibge='3550308', nome='São Paulo', estado=self.estado, ativo=True)
        Cidade.objects.create(codigo_ibge='3509502', nome='Campinas', estado=self.estado, ativo=True)

    def test_api_requer_login(self):
        response = self.client.get(reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': self.estado.pk}))
        self.assertEqual(response.status_code, 302)

    def test_api_retorna_json_ordenado(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cadastros:api-cidades-por-estado', kwargs={'estado_id': self.estado.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertEqual(len(data), 2)
        nomes = [c['nome'] for c in data]
        self.assertEqual(nomes, ['Campinas', 'São Paulo'])


class ApiConsultaCepTest(TestCase):
    """API de consulta CEP: mock de ViaCEP; 400 inválido, 404 não encontrado, 200 OK."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

    def test_api_cep_requer_login(self):
        client = Client()
        response = client.get(reverse('cadastros:api-consulta-cep', kwargs={'cep': '80010000'}))
        self.assertEqual(response.status_code, 302)

    @patch('cadastros.views.api.requests.get')
    def test_api_cep_invalido_retorna_400(self, mock_get):
        response = self.client.get(reverse('cadastros:api-consulta-cep', kwargs={'cep': '123'}))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('erro', data)
        mock_get.assert_not_called()

    @patch('cadastros.views.api.requests.get')
    def test_api_cep_nao_encontrado_retorna_404(self, mock_get):
        mock_resp = Mock()
        mock_resp.json.return_value = {'erro': True}
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        response = self.client.get(reverse('cadastros:api-consulta-cep', kwargs={'cep': '00000000'}))
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('erro', data)
        self.assertIn('não encontrado', data['erro'].lower())

    @patch('cadastros.views.api.requests.get')
    def test_api_cep_valido_retorna_200_json(self, mock_get):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            'cep': '80010-000',
            'logradouro': 'Rua XV',
            'bairro': 'Centro',
            'localidade': 'Curitiba',
            'uf': 'PR',
        }
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp
        response = self.client.get(reverse('cadastros:api-consulta-cep', kwargs={'cep': '80010000'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = response.json()
        self.assertEqual(data.get('cep'), '80010-000')
        self.assertEqual(data.get('logradouro'), 'Rua XV')
        self.assertEqual(data.get('bairro'), 'Centro')
        self.assertEqual(data.get('cidade'), 'Curitiba')
        self.assertEqual(data.get('uf'), 'PR')


class ImportCoordenadasCidadesTest(TestCase):
    """Testes do comando importar_coordenadas_cidades (atualiza lat/lon por CSV ;)."""

    def setUp(self):
        self.estado_sp = Estado.objects.create(codigo_ibge='35', nome='São Paulo', sigla='SP', ativo=True)
        self.estado_pr = Estado.objects.create(codigo_ibge='41', nome='Paraná', sigla='PR', ativo=True)

    def _csv_path(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='')
        f.write(content)
        f.close()
        return f.name

    def test_importar_coordenadas_atualiza_cidade_existente(self):
        Cidade.objects.create(
            codigo_ibge='3550308', nome='São Paulo', estado=self.estado_sp, ativo=True
        )
        csv_content = 'id_municipio;uf;municipio;longitude;latitude\n'
        csv_content += '3550308;SP;São Paulo;-46.633308;-23.550520\n'
        path = self._csv_path(csv_content)
        try:
            call_command('importar_coordenadas_cidades', '--arquivo', path)
            cidade = Cidade.objects.get(codigo_ibge='3550308')
            self.assertIsNotNone(cidade.latitude)
            self.assertIsNotNone(cidade.longitude)
            self.assertEqual(cidade.latitude, Decimal('-23.550520'))
            self.assertEqual(cidade.longitude, Decimal('-46.633308'))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_nao_cria_cidade_nova_se_nao_encontrar(self):
        Cidade.objects.create(
            codigo_ibge='3550308', nome='São Paulo', estado=self.estado_sp, ativo=True
        )
        csv_content = 'id_municipio;uf;municipio;longitude;latitude\n'
        csv_content += '9999999;SP;Cidade Inexistente;-46.0;-23.0\n'
        path = self._csv_path(csv_content)
        try:
            call_command('importar_coordenadas_cidades', '--arquivo', path)
            self.assertEqual(Cidade.objects.count(), 1)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_match_ignora_acento_e_caixa(self):
        Cidade.objects.create(
            codigo_ibge='3550308', nome='São Paulo', estado=self.estado_sp, ativo=True
        )
        csv_content = 'id_municipio;uf;municipio;longitude;latitude\n'
        csv_content += '3550308;SP;SAO PAULO;-46.633308;-23.550520\n'
        path = self._csv_path(csv_content)
        try:
            call_command('importar_coordenadas_cidades', '--arquivo', path)
            cidade = Cidade.objects.get(codigo_ibge='3550308')
            self.assertEqual(cidade.latitude, Decimal('-23.550520'))
            self.assertEqual(cidade.longitude, Decimal('-46.633308'))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_linha_invalida_nao_quebra_importacao(self):
        Cidade.objects.create(
            codigo_ibge='3550308', nome='São Paulo', estado=self.estado_sp, ativo=True
        )
        csv_content = 'id_municipio;uf;municipio;longitude;latitude\n'
        csv_content += '3550308;SP;São Paulo;abc;xyz\n'
        csv_content += '3550308;SP;São Paulo;-46.633308;-23.550520\n'
        path = self._csv_path(csv_content)
        try:
            call_command('importar_coordenadas_cidades', '--arquivo', path)
            cidade = Cidade.objects.get(codigo_ibge='3550308')
            self.assertEqual(cidade.latitude, Decimal('-23.550520'))
            self.assertEqual(cidade.longitude, Decimal('-46.633308'))
        finally:
            Path(path).unlink(missing_ok=True)

    def test_arquivo_inexistente_retorna_erro(self):
        from io import StringIO
        out, err = StringIO(), StringIO()
        call_command('importar_coordenadas_cidades', '--arquivo', 'arquivo_que_nao_existe.csv', stdout=out, stderr=err)
        err_content = err.getvalue()
        self.assertIn('não encontrado', err_content.lower())

    def test_le_csv_com_delimiter_ponto_virgula(self):
        Cidade.objects.create(
            codigo_ibge='4106902', nome='Curitiba', estado=self.estado_pr, ativo=True
        )
        csv_content = 'id_municipio;uf;municipio;longitude;latitude\n'
        csv_content += '4106902;PR;Curitiba;-49.2733;-25.4284\n'
        path = self._csv_path(csv_content)
        try:
            call_command('importar_coordenadas_cidades', '--arquivo', path)
            cidade = Cidade.objects.get(codigo_ibge='4106902')
            self.assertAlmostEqual(float(cidade.latitude), -25.4284, places=4)
            self.assertAlmostEqual(float(cidade.longitude), -49.2733, places=4)
        finally:
            Path(path).unlink(missing_ok=True)


class SidebarSemEstadosCidadesTest(TestCase):
    """Estados e Cidades não aparecem como itens do menu cadastros."""

    def setUp(self):
        from core.navigation import get_sidebar_config
        self.config = get_sidebar_config()

    def test_cadastros_nao_tem_estados_nem_cidades(self):
        cadastros_group = next((g for g in self.config if g['id'] == 'cadastros'), None)
        self.assertIsNotNone(cadastros_group)
        ids = [item['id'] for item in cadastros_group['items']]
        self.assertNotIn('estados', ids)
        self.assertNotIn('cidades', ids)
        self.assertIn('configuracoes', ids)
