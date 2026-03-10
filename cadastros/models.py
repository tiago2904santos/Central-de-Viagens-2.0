import re

from django.db import models
from django.db.models import Q, UniqueConstraint

from core.utils.masks import (
    RG_NAO_POSSUI_CANONICAL,
    format_masked_display,
    format_rg_display,
)


class Estado(models.Model):
    """Base fixa de referência (IBGE). Importado por CSV; não é cadastro manual."""
    codigo_ibge = models.CharField('Código IBGE', max_length=10, unique=True, db_index=True, null=True, blank=True)
    nome = models.CharField('Nome', max_length=100)
    sigla = models.CharField('Sigla', max_length=2, unique=True)
    ativo = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Estado'
        verbose_name_plural = 'Estados'

    def __str__(self):
        return f'{self.nome} ({self.sigla})'


class Cidade(models.Model):
    """Base fixa de referência (IBGE). Importado por CSV; não é cadastro manual."""
    codigo_ibge = models.CharField('Código IBGE', max_length=10, unique=True, db_index=True, null=True, blank=True)
    nome = models.CharField('Nome', max_length=200)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, related_name='cidades', verbose_name='Estado')
    latitude = models.DecimalField(
        'Latitude', max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Coordenada para estimativa local de distância/tempo entre cidades.'
    )
    longitude = models.DecimalField(
        'Longitude', max_digits=9, decimal_places=6, null=True, blank=True,
        help_text='Coordenada para estimativa local de distância/tempo entre cidades.'
    )
    ativo = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Cidade'
        verbose_name_plural = 'Cidades'

    def __str__(self):
        return f'{self.nome} — {self.estado.sigla}'


class Cargo(models.Model):
    """Cadastro de cargos (usado em Viajante). Apenas um pode ser padrão (is_padrao=True)."""
    nome = models.CharField('Nome', max_length=120, unique=True)
    is_padrao = models.BooleanField('Padrão', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = ' '.join(self.nome.strip().upper().split())
        super().save(*args, **kwargs)
        if self.is_padrao:
            Cargo.objects.exclude(pk=self.pk).update(is_padrao=False)


class UnidadeLotacao(models.Model):
    """Base fixa de unidades de lotação. Importado por CSV (coluna NOME); não é CRUD manual."""
    nome = models.CharField('Nome', max_length=160, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Unidade de lotação'
        verbose_name_plural = 'Unidades de lotação'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = ' '.join(self.nome.strip().upper().split())
        super().save(*args, **kwargs)


class Viajante(models.Model):
    """Cadastro de servidores (viajantes). Usado em assinaturas, termos e ofícios."""
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]
    nome = models.CharField('Nome', max_length=160, blank=True, default='')
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO
    )
    cargo = models.ForeignKey(
        Cargo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='viajantes', verbose_name='Cargo'
    )
    rg = models.CharField('RG', max_length=30, blank=True, default='')
    sem_rg = models.BooleanField('Não possui RG', default=False)
    cpf = models.CharField('CPF', max_length=14, blank=True, default='')
    telefone = models.CharField('Telefone', max_length=20, blank=True, default='')
    unidade_lotacao = models.ForeignKey(
        UnidadeLotacao, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='viajantes', verbose_name='Unidade de lotação'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Viajante'
        verbose_name_plural = 'Viajantes'
        constraints = [
            UniqueConstraint(
                fields=['nome'],
                condition=Q(nome__gt=''),
                name='cadastros_viajante_nome_unique_preenchido',
            ),
            UniqueConstraint(
                fields=['cpf'],
                condition=Q(cpf__gt=''),
                name='cadastros_viajante_cpf_unique',
            ),
            UniqueConstraint(
                fields=['rg'],
                condition=Q(rg__gt='') & ~Q(rg='NAO POSSUI RG'),
                name='cadastros_viajante_rg_unique',
            ),
            UniqueConstraint(
                fields=['telefone'],
                condition=Q(telefone__gt=''),
                name='cadastros_viajante_telefone_unique',
            ),
        ]

    def __str__(self):
        return self.nome or '(Rascunho)'

    @property
    def rg_formatado(self):
        return format_rg_display(self.rg, sem_rg=self.sem_rg)

    @property
    def cpf_formatado(self):
        return format_masked_display('cpf', self.cpf)

    @property
    def telefone_formatado(self):
        return format_masked_display('telefone', self.telefone)

    def esta_completo(self):
        """
        Retorna True se todos os dados obrigatórios estão preenchidos e válidos
        para o viajante poder ser usado no sistema (status FINALIZADO).
        Campos obrigatórios: nome, cargo, cpf, telefone, unidade_lotacao, e (RG preenchido OU sem_rg=True).
        """
        nome = (self.nome or '').strip()
        if not nome:
            return False
        if not self.cargo_id:
            return False
        cpf = (self.cpf or '').strip()
        if len(cpf) != 11 or not cpf.isdigit():
            return False
        tel = (self.telefone or '').strip()
        if len(tel) not in (10, 11) or not tel.isdigit():
            return False
        if not self.unidade_lotacao_id:
            return False
        if self.sem_rg:
            return True
        rg = (self.rg or '').strip()
        if not rg or rg == 'NAO POSSUI RG':
            return False
        return True

    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = ' '.join(self.nome.strip().upper().split())
        if self.sem_rg:
            self.rg = RG_NAO_POSSUI_CANONICAL
        super().save(*args, **kwargs)


class CombustivelVeiculo(models.Model):
    """Combustíveis para veículos. Um pode ser padrão (is_padrao=True)."""
    nome = models.CharField('Nome', max_length=60, unique=True)
    is_padrao = models.BooleanField('Padrão', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Combustível (veículo)'
        verbose_name_plural = 'Combustíveis (veículos)'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = ' '.join(self.nome.strip().upper().split())
        super().save(*args, **kwargs)
        if self.is_padrao:
            CombustivelVeiculo.objects.exclude(pk=self.pk).update(is_padrao=False)


class Veiculo(models.Model):
    TIPO_CARACTERIZADO = 'CARACTERIZADO'
    TIPO_DESCARACTERIZADO = 'DESCARACTERIZADO'
    TIPO_CHOICES = [
        (TIPO_CARACTERIZADO, 'Caracterizado'),
        (TIPO_DESCARACTERIZADO, 'Descaracterizado'),
    ]
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]
    placa = models.CharField('Placa', max_length=10, blank=True, default='')
    modelo = models.CharField('Modelo', max_length=120, blank=True, default='')
    combustivel = models.ForeignKey(
        CombustivelVeiculo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='veiculos', verbose_name='Combustível'
    )
    tipo = models.CharField(
        'Tipo', max_length=20, choices=TIPO_CHOICES, default=TIPO_DESCARACTERIZADO
    )
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Veículo'
        verbose_name_plural = 'Veículos'
        constraints = [
            models.UniqueConstraint(
                fields=['placa'],
                condition=Q(placa__gt=''),
                name='cadastros_veiculo_placa_unique_preenchida',
            ),
        ]

    def __str__(self):
        placa_display = self.placa_formatada
        modelo_display = self.modelo or '—'
        return f'{placa_display} — {modelo_display}'

    @property
    def placa_formatada(self):
        return format_masked_display('placa', self.placa, empty='(Rascunho)')

    def _placa_valida(self):
        """Retorna True se placa preenchida tem 7 caracteres e formato antigo ou mercosul."""
        p = (self.placa or '').strip()
        if not p or len(p) != 7:
            return False
        return bool(
            re.match(r'^[A-Z]{3}[0-9]{4}$', p) or
            re.match(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$', p)
        )

    def esta_completo(self):
        """
        Retorna True se todos os dados obrigatórios estão preenchidos e válidos
        para o veículo poder ser usado no sistema (status FINALIZADO).
        Campos obrigatórios: placa (válida), modelo, combustivel, tipo.
        """
        if not self._placa_valida():
            return False
        modelo = (self.modelo or '').strip()
        if not modelo:
            return False
        if not self.combustivel_id:
            return False
        tipo = (self.tipo or '').strip()
        if tipo not in (self.TIPO_CARACTERIZADO, self.TIPO_DESCARACTERIZADO):
            return False
        return True

    def save(self, *args, **kwargs):
        if self.placa:
            self.placa = re.sub(r'[\s\-]', '', (self.placa or '').strip().upper())
        if self.modelo:
            self.modelo = ' '.join(self.modelo.strip().upper().split())
        super().save(*args, **kwargs)


class ConfiguracaoSistema(models.Model):
    """Singleton: uma única instância para configurações gerais."""
    # Base / órgão
    cidade_sede_padrao = models.ForeignKey(
        Cidade, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Cidade sede padrão'
    )
    prazo_justificativa_dias = models.PositiveIntegerField(
        'Prazo justificativa (dias)', default=10
    )
    nome_orgao = models.CharField('Nome do órgão', max_length=200, blank=True)
    sigla_orgao = models.CharField('Sigla do órgão', max_length=20, blank=True)

    # Cabeçalho (sempre maiúsculo)
    divisao = models.CharField('Divisão', max_length=120, blank=True, default='')
    unidade = models.CharField('Unidade', max_length=120, blank=True, default='')

    # Rodapé: endereço (preenchido via CEP)
    cep = models.CharField('CEP', max_length=9, blank=True, default='')
    logradouro = models.CharField('Logradouro', max_length=160, blank=True, default='')
    bairro = models.CharField('Bairro', max_length=120, blank=True, default='')
    cidade_endereco = models.CharField('Cidade (endereço)', max_length=120, blank=True, default='')
    uf = models.CharField('UF', max_length=2, blank=True, default='')
    numero = models.CharField('Número', max_length=20, blank=True, default='')

    # Contato
    telefone = models.CharField('Telefone', max_length=20, blank=True, default='')
    email = models.EmailField('E-mail', blank=True, default='')

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuração do sistema'
        verbose_name_plural = 'Configurações do sistema'

    def __str__(self):
        return 'Configurações do sistema'

    @property
    def cep_formatado(self):
        return format_masked_display('cep', self.cep)

    @property
    def telefone_formatado(self):
        return format_masked_display('telefone', self.telefone)

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'prazo_justificativa_dias': 10})
        return obj


class AssinaturaConfiguracao(models.Model):
    """Assinaturas por tipo e ordem, vinculadas à configuração do sistema."""
    TIPO_OFICIO = 'OFICIO'
    TIPO_JUSTIFICATIVA = 'JUSTIFICATIVA'
    TIPO_PLANO_TRABALHO = 'PLANO_TRABALHO'
    TIPO_ORDEM_SERVICO = 'ORDEM_SERVICO'
    TIPO_CHOICES = [
        (TIPO_OFICIO, 'Ofício'),
        (TIPO_JUSTIFICATIVA, 'Justificativa'),
        (TIPO_PLANO_TRABALHO, 'Plano de Trabalho'),
        (TIPO_ORDEM_SERVICO, 'Ordem de Serviço'),
    ]

    configuracao = models.ForeignKey(
        ConfiguracaoSistema, on_delete=models.CASCADE, related_name='assinaturas',
        verbose_name='Configuração'
    )
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES)
    ordem = models.PositiveSmallIntegerField('Ordem', default=1)
    viajante = models.ForeignKey(
        Viajante, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Viajante'
    )
    ativo = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Assinatura (configuração)'
        verbose_name_plural = 'Assinaturas (configuração)'
        constraints = [
            UniqueConstraint(
                fields=['configuracao', 'tipo', 'ordem'],
                name='uniq_assinatura_por_tipo_ordem',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} (ordem {self.ordem})'
