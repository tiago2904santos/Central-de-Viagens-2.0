from django.db import models
from django.utils import timezone


STATUS_RASCUNHO = 'RASCUNHO'
STATUS_FINALIZADO = 'FINALIZADO'
STATUS_CHOICES = [
    (STATUS_RASCUNHO, 'Rascunho'),
    (STATUS_FINALIZADO, 'Finalizado'),
]

CUSTEIO_PROPRIO = 'PROPRIO'
CUSTEIO_EXTERNO = 'EXTERNO'
CUSTEIO_CHOICES = [
    (CUSTEIO_PROPRIO, 'Próprio'),
    (CUSTEIO_EXTERNO, 'Externo'),
]

DESTINO_NACIONAL = 'NACIONAL'
DESTINO_INTERNACIONAL = 'INTERNACIONAL'
DESTINO_CHOICES = [
    (DESTINO_NACIONAL, 'Nacional'),
    (DESTINO_INTERNACIONAL, 'Internacional'),
]


class ModeloMotivo(models.Model):
    """Modelos de motivo para ofícios."""
    nome = models.CharField('Nome', max_length=160)
    texto = models.TextField('Texto do motivo', blank=True, default='')
    is_padrao = models.BooleanField('Padrão', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Modelo de motivo'
        verbose_name_plural = 'Modelos de motivo'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_padrao:
            ModeloMotivo.objects.exclude(pk=self.pk).update(is_padrao=False)


class ModeloJustificativa(models.Model):
    """Modelos de justificativa para ofícios."""
    nome = models.CharField('Nome', max_length=160)
    texto = models.TextField('Texto da justificativa', blank=True, default='')
    is_padrao = models.BooleanField('Padrão', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Modelo de justificativa'
        verbose_name_plural = 'Modelos de justificativa'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_padrao:
            ModeloJustificativa.objects.exclude(pk=self.pk).update(is_padrao=False)


class Evento(models.Model):
    """Agrupador opcional de documentos. Não é entidade-mãe obrigatória."""
    nome = models.CharField('Nome', max_length=200)
    descricao = models.TextField('Descrição', blank=True, default='')
    data_inicio = models.DateField('Data de início', null=True, blank=True)
    data_fim = models.DateField('Data de fim', null=True, blank=True)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

    def __str__(self):
        return self.nome


class Roteiro(models.Model):
    """Roteiro de viagem — entidade independente, opcionalmente vinculada a ofício e/ou evento."""
    nome = models.CharField('Nome / identificação', max_length=200, blank=True, default='')
    descricao = models.TextField('Descrição', blank=True, default='')
    evento = models.ForeignKey(
        Evento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='roteiros', verbose_name='Evento (opcional)',
    )
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Roteiro'
        verbose_name_plural = 'Roteiros'

    def __str__(self):
        return self.nome or f'Roteiro #{self.pk}'


class RoteiroTrecho(models.Model):
    """Trecho de um roteiro."""
    roteiro = models.ForeignKey(Roteiro, on_delete=models.CASCADE, related_name='trechos', verbose_name='Roteiro')
    ordem = models.PositiveSmallIntegerField('Ordem', default=1)
    origem = models.ForeignKey(
        'cadastros.Cidade', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Origem',
    )
    destino = models.ForeignKey(
        'cadastros.Cidade', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Destino',
    )
    data_saida = models.DateField('Data de saída', null=True, blank=True)
    data_chegada = models.DateField('Data de chegada', null=True, blank=True)
    distancia_km = models.DecimalField('Distância (km)', max_digits=9, decimal_places=2, null=True, blank=True)
    duracao_minutos = models.PositiveIntegerField('Duração estimada (min)', null=True, blank=True)
    is_retorno = models.BooleanField('Trecho de retorno', default=False)
    observacoes = models.TextField('Observações', blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['roteiro', 'ordem']
        verbose_name = 'Trecho do roteiro'
        verbose_name_plural = 'Trechos do roteiro'

    def __str__(self):
        return f'Trecho {self.ordem} — {self.roteiro}'


class Oficio(models.Model):
    """Ofício de missão — entidade principal e independente."""
    numero = models.CharField('Número', max_length=20, blank=True, default='')
    ano = models.PositiveSmallIntegerField('Ano', null=True, blank=True)
    protocolo = models.CharField('Protocolo', max_length=30, blank=True, default='')
    data_criacao = models.DateField('Data de criação', default=timezone.now)

    motivo = models.TextField('Motivo', blank=True, default='')
    modelo_motivo = models.ForeignKey(
        ModeloMotivo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Modelo de motivo',
    )

    custeio_tipo = models.CharField('Tipo de custeio', max_length=20, choices=CUSTEIO_CHOICES, default=CUSTEIO_PROPRIO)
    nome_instituicao_custeio = models.CharField('Instituição custeante', max_length=200, blank=True, default='')
    tipo_destino = models.CharField('Tipo de destino', max_length=20, choices=DESTINO_CHOICES, default=DESTINO_NACIONAL)

    veiculo = models.ForeignKey(
        'cadastros.Veiculo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Veículo',
    )
    placa = models.CharField('Placa (snapshot)', max_length=10, blank=True, default='')
    modelo_veiculo = models.CharField('Modelo (snapshot)', max_length=120, blank=True, default='')
    combustivel_snapshot = models.CharField('Combustível (snapshot)', max_length=60, blank=True, default='')
    tipo_viatura = models.CharField('Tipo de viatura', max_length=30, blank=True, default='')
    porte_transporte_armas = models.BooleanField('Porte/transporte de armas', default=False)

    motorista = models.ForeignKey(
        'cadastros.Viajante', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios_como_motorista', verbose_name='Motorista',
    )
    motorista_carona = models.BooleanField('Motorista como carona', default=False)
    motorista_oficio_numero = models.CharField('Número do ofício do motorista', max_length=20, blank=True, default='')
    motorista_oficio_ano = models.PositiveSmallIntegerField('Ano do ofício do motorista', null=True, blank=True)
    motorista_protocolo = models.CharField('Protocolo do motorista', max_length=30, blank=True, default='')

    quantidade_diarias = models.DecimalField('Quantidade de diárias', max_digits=5, decimal_places=1, null=True, blank=True)
    valor_diarias = models.DecimalField('Valor das diárias', max_digits=10, decimal_places=2, null=True, blank=True)
    valor_diarias_extenso = models.CharField('Valor por extenso', max_length=300, blank=True, default='')

    justificativa_texto = models.TextField('Justificativa', blank=True, default='')
    modelo_justificativa = models.ForeignKey(
        ModeloJustificativa, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Modelo de justificativa',
    )
    gerar_termo_preenchido = models.BooleanField('Gerar termo preenchido', default=False)

    roteiro = models.ForeignKey(
        Roteiro, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Roteiro (opcional)',
    )

    evento = models.ForeignKey(
        Evento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Evento (opcional)',
    )

    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Ofício'
        verbose_name_plural = 'Ofícios'

    def __str__(self):
        if self.numero and self.ano:
            return f'Ofício {self.numero}/{self.ano}'
        return f'Ofício #{self.pk} (rascunho)'

    @property
    def identificacao(self):
        if self.numero and self.ano:
            return f'{self.numero}/{self.ano}'
        if self.protocolo:
            return self.protocolo
        return f'#{self.pk}'


class OficioViajante(models.Model):
    """Viajantes vinculados a um ofício."""
    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name='viajantes', verbose_name='Ofício')
    viajante = models.ForeignKey(
        'cadastros.Viajante', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='participacoes', verbose_name='Viajante',
    )
    nome_snapshot = models.CharField('Nome (snapshot)', max_length=160, blank=True, default='')
    cargo_snapshot = models.CharField('Cargo (snapshot)', max_length=120, blank=True, default='')
    unidade_snapshot = models.CharField('Unidade (snapshot)', max_length=160, blank=True, default='')
    ordem = models.PositiveSmallIntegerField('Ordem', default=1)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['oficio', 'ordem']
        verbose_name = 'Viajante do ofício'
        verbose_name_plural = 'Viajantes do ofício'

    def __str__(self):
        return f'{self.nome_snapshot or (self.viajante and str(self.viajante)) or "?"} — {self.oficio}'

    def save(self, *args, **kwargs):
        if self.viajante and not self.nome_snapshot:
            self.nome_snapshot = self.viajante.nome or ''
        if self.viajante and self.viajante.cargo and not self.cargo_snapshot:
            self.cargo_snapshot = str(self.viajante.cargo)
        if self.viajante and self.viajante.unidade_lotacao and not self.unidade_snapshot:
            self.unidade_snapshot = str(self.viajante.unidade_lotacao)
        super().save(*args, **kwargs)


class OficioTrecho(models.Model):
    """Trechos reais do ofício."""
    oficio = models.ForeignKey(Oficio, on_delete=models.CASCADE, related_name='trechos', verbose_name='Ofício')
    ordem = models.PositiveSmallIntegerField('Ordem', default=1)
    origem = models.ForeignKey(
        'cadastros.Cidade', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Origem',
    )
    origem_nome = models.CharField('Origem (texto)', max_length=200, blank=True, default='')
    destino = models.ForeignKey(
        'cadastros.Cidade', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Destino',
    )
    destino_nome = models.CharField('Destino (texto)', max_length=200, blank=True, default='')
    data_saida = models.DateField('Data de saída', null=True, blank=True)
    hora_saida = models.TimeField('Hora de saída', null=True, blank=True)
    data_chegada = models.DateField('Data de chegada', null=True, blank=True)
    hora_chegada = models.TimeField('Hora de chegada', null=True, blank=True)
    distancia_km = models.DecimalField('Distância (km)', max_digits=9, decimal_places=2, null=True, blank=True)
    duracao_minutos = models.PositiveIntegerField('Duração estimada (min)', null=True, blank=True)
    tempo_extra_minutos = models.PositiveIntegerField('Tempo extra (min)', null=True, blank=True)
    is_retorno = models.BooleanField('Trecho de retorno', default=False)
    observacoes = models.TextField('Observações', blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['oficio', 'ordem']
        verbose_name = 'Trecho do ofício'
        verbose_name_plural = 'Trechos do ofício'

    def __str__(self):
        return f'Trecho {self.ordem} — {self.oficio}'


class TermoAutorizacao(models.Model):
    """Termo de autorização — entidade documental própria e independente."""
    numero = models.CharField('Número', max_length=20, blank=True, default='')
    ano = models.PositiveSmallIntegerField('Ano', null=True, blank=True)
    data_criacao = models.DateField('Data de criação', default=timezone.now)
    titulo = models.CharField('Título', max_length=200, blank=True, default='')
    texto = models.TextField('Texto do termo', blank=True, default='')
    observacoes = models.TextField('Observações', blank=True, default='')
    oficio = models.ForeignKey(
        Oficio, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='termos', verbose_name='Ofício (opcional)',
    )
    evento = models.ForeignKey(
        Evento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='termos', verbose_name='Evento (opcional)',
    )
    roteiro = models.ForeignKey(
        Roteiro, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='termos', verbose_name='Roteiro (opcional)',
    )
    viajante = models.ForeignKey(
        'cadastros.Viajante', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='termos', verbose_name='Viajante (opcional)',
    )
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Termo de autorização'
        verbose_name_plural = 'Termos de autorização'

    def __str__(self):
        if self.numero and self.ano:
            return f'Termo {self.numero}/{self.ano}'
        return self.titulo or f'Termo #{self.pk}'


class Justificativa(models.Model):
    """Justificativa — entidade documental satélite do Ofício."""
    oficio = models.ForeignKey(
        Oficio, on_delete=models.CASCADE, null=False, blank=False,
        related_name='justificativas', verbose_name='Ofício',
    )
    titulo = models.CharField('Título / assunto', max_length=200, blank=True, default='')
    modelo = models.ForeignKey(
        ModeloJustificativa, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='justificativas', verbose_name='Modelo (opcional)',
    )
    texto = models.TextField('Texto', blank=True, default='')
    observacoes = models.TextField('Observações', blank=True, default='')
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Justificativa'
        verbose_name_plural = 'Justificativas'

    def __str__(self):
        return self.titulo or f'Justificativa #{self.pk} — {self.oficio}'


class PlanoTrabalho(models.Model):
    """Plano de Trabalho — entidade independente."""
    titulo = models.CharField('Título', max_length=200, blank=True, default='')
    conteudo = models.TextField('Conteúdo', blank=True, default='')
    evento = models.ForeignKey(
        Evento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='planos_trabalho', verbose_name='Evento (opcional)',
    )
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Plano de trabalho'
        verbose_name_plural = 'Planos de trabalho'

    def __str__(self):
        return self.titulo or f'Plano de Trabalho #{self.pk}'


class OrdemServico(models.Model):
    """Ordem de Serviço — entidade independente."""
    titulo = models.CharField('Título', max_length=200, blank=True, default='')
    conteudo = models.TextField('Conteúdo', blank=True, default='')
    oficio = models.ForeignKey(
        Oficio, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_servico', verbose_name='Ofício (opcional)',
    )
    evento = models.ForeignKey(
        Evento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ordens_servico', verbose_name='Evento (opcional)',
    )
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Ordem de serviço'
        verbose_name_plural = 'Ordens de serviço'

    def __str__(self):
        return self.titulo or f'Ordem de Serviço #{self.pk}'
