from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify
from cadastros.models import Estado, Cidade
from core.utils.masks import EMPTY_MASK_DISPLAY, format_masked_display, format_placa
from .utils import (
    format_protocolo as format_protocolo_visual,
    normalize_protocolo as normalize_protocolo_canonico,
    only_digits,
)


class TipoDemandaEvento(models.Model):
    """Tipos de demanda configuráveis para eventos (Etapa 1)."""
    nome = models.CharField('Nome', max_length=120, unique=True)
    descricao_padrao = models.TextField('Descrição padrão', blank=True, default='')
    ordem = models.PositiveIntegerField('Ordem', default=100)
    ativo = models.BooleanField('Ativo', default=True)
    is_outros = models.BooleanField('É "Outros"', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'Tipo de demanda (evento)'
        verbose_name_plural = 'Tipos de demanda (evento)'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.nome:
            self.nome = self.nome.strip().upper()
        super().save(*args, **kwargs)


class Evento(models.Model):
    TIPO_PCPR = 'PCPR_NA_COMUNIDADE'
    TIPO_OPERACAO = 'OPERACAO_POLICIAL'
    TIPO_PARANA = 'PARANA_EM_ACAO'
    TIPO_OUTRO = 'OUTRO'
    TIPO_CHOICES = [
        (TIPO_PCPR, 'PCPR na Comunidade'),
        (TIPO_OPERACAO, 'Operação Policial'),
        (TIPO_PARANA, 'Paraná em Ação'),
        (TIPO_OUTRO, 'Outro'),
    ]

    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_EM_ANDAMENTO = 'EM_ANDAMENTO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_ARQUIVADO = 'ARQUIVADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_EM_ANDAMENTO, 'Em andamento'),
        (STATUS_FINALIZADO, 'Finalizado'),
        (STATUS_ARQUIVADO, 'Arquivado'),
    ]

    titulo = models.CharField('Título', max_length=200, blank=True)
    tipo_demanda = models.CharField(
        'Tipo de demanda (legado)', max_length=30, choices=TIPO_CHOICES,
        blank=True, null=True
    )
    tipos_demanda = models.ManyToManyField(
        TipoDemandaEvento, related_name='eventos', blank=True,
        verbose_name='Tipos de demanda'
    )
    descricao = models.TextField('Descrição', blank=True)
    data_inicio = models.DateField('Data de início')
    data_fim = models.DateField('Data de término')
    data_unica = models.BooleanField('Evento em um único dia', default=False)
    estado_principal = models.ForeignKey(
        Estado, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_estado_principal', verbose_name='Estado principal'
    )
    cidade_principal = models.ForeignKey(
        Cidade, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_cidade_principal', verbose_name='Cidade principal'
    )
    cidade_base = models.ForeignKey(
        Cidade, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_cidade_base', verbose_name='Cidade base'
    )
    tem_convite_ou_oficio_evento = models.BooleanField(
        'Tem convite/ofício solicitante?', default=False
    )
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO
    )
    # Etapa 3 - Composição da viagem
    veiculo = models.ForeignKey(
        'cadastros.Veiculo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_veiculo', verbose_name='Veículo'
    )
    motorista = models.ForeignKey(
        'cadastros.Viajante', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='eventos_motorista', verbose_name='Motorista'
    )
    observacoes_operacionais = models.TextField(
        'Observações operacionais', blank=True, default=''
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_inicio', '-created_at']
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'

    def __str__(self):
        return self.titulo or '(sem título)'

    def gerar_titulo(self):
        """
        Gera título automaticamente: tipos + destinos + datas.
        Ex: "PCPR NA COMUNIDADE - CURITIBA - 12/03/2026"
        Ex: "OPERAÇÃO POLICIAL / PARANÁ EM AÇÃO - MARINGÁ E LONDRINA - 12/03/2026 A 14/03/2026"
        """
        partes = []
        tipos = list(self.tipos_demanda.filter(ativo=True).order_by('ordem', 'nome').values_list('nome', flat=True))
        if tipos:
            partes.append(' / '.join(tipos))
        destinos = list(
            self.destinos.select_related('estado', 'cidade').order_by('ordem', 'cidade__nome')
        )
        if destinos:
            nomes = [d.cidade.nome if d.cidade else (d.estado.sigla if d.estado else '') for d in destinos if d.cidade or d.estado]
            if len(nomes) == 0:
                pass
            elif len(nomes) == 1:
                partes.append(nomes[0].upper())
            elif len(nomes) == 2:
                partes.append(' e '.join(n.upper() for n in nomes))
            else:
                partes.append(nomes[0].upper() + ' E OUTRAS CIDADES')
        if self.data_inicio:
            from django.utils.dateformat import format as date_format
            data_str = date_format(self.data_inicio, 'd/m/Y')
            if not self.data_unica and self.data_fim and self.data_fim != self.data_inicio:
                data_str += ' A ' + date_format(self.data_fim, 'd/m/Y')
            partes.append(data_str)
        return ' - '.join(partes) if partes else '(sem título)'

    def montar_descricao_padrao(self):
        """
        Concatena descricao_padrao dos tipos de demanda selecionados (exceto is_outros).
        Para is_outros o usuário deve preencher manualmente.
        """
        tipos = self.tipos_demanda.filter(ativo=True, is_outros=False).order_by('ordem', 'nome')
        textos = [t.descricao_padrao.strip() for t in tipos if t.descricao_padrao and t.descricao_padrao.strip()]
        return '\n\n'.join(textos) if textos else ''


class EventoParticipante(models.Model):
    """Viajante participante do evento (Etapa 3 - composição da viagem)."""
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name='participantes',
        verbose_name='Evento'
    )
    viajante = models.ForeignKey(
        'cadastros.Viajante', on_delete=models.CASCADE, related_name='eventos_participacao',
        verbose_name='Viajante'
    )
    ordem = models.PositiveIntegerField('Ordem', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['evento', 'ordem', 'viajante__nome']
        verbose_name = 'Participante do evento'
        verbose_name_plural = 'Participantes do evento'
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'viajante'],
                name='eventos_eventoparticipante_evento_viajante_unique',
            ),
        ]

    def __str__(self):
        return f'{self.evento_id} - {self.viajante}'


class ModeloMotivoViagem(models.Model):
    """
    Modelos reutilizáveis de motivo de viagem.
    """

    codigo = models.CharField('Código', max_length=80, unique=True)
    nome = models.CharField('Nome do modelo', max_length=200)
    texto = models.TextField('Texto do motivo')
    ordem = models.PositiveIntegerField('Ordem', default=0)
    ativo = models.BooleanField('Ativo', default=True)
    padrao = models.BooleanField('Padrão', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Modelo de motivo'
        verbose_name_plural = 'Modelos de motivo'

    def __str__(self):
        return self.nome

    @classmethod
    def build_unique_codigo(cls, nome, exclude_pk=None):
        base = slugify((nome or '').strip()).replace('-', '_')[:80]
        if not base:
            base = f'modelo_{timezone.now().strftime("%Y%m%d%H%M%S")}'
        codigo = base
        idx = 2
        qs = cls.objects.all()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        while qs.filter(codigo=codigo).exists():
            sufixo = f'_{idx}'
            codigo = f'{base[:max(1, 80 - len(sufixo))]}{sufixo}'
            idx += 1
        return codigo

    def save(self, *args, **kwargs):
        self.codigo = (self.codigo or '').strip().lower()
        self.nome = (self.nome or '').strip()
        self.ativo = True
        if not self.codigo:
            self.codigo = self.build_unique_codigo(self.nome, exclude_pk=self.pk)
        if self.padrao:
            ModeloMotivoViagem.objects.exclude(pk=self.pk).update(padrao=False)
        super().save(*args, **kwargs)


class Oficio(models.Model):
    """
    Ofício vinculado a um evento.
    Wizard: Step 1 (dados + viajantes), Step 2 (transporte + motorista),
    Step 3 (trechos) e Step 4 (resumo).
    """
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]

    CUSTEIO_UNIDADE = 'UNIDADE'
    CUSTEIO_OUTRA_INSTITUICAO = 'OUTRA_INSTITUICAO'
    CUSTEIO_ONUS_LIMITADOS = 'ONUS_LIMITADOS'
    CUSTEIO_CHOICES = [
        (CUSTEIO_UNIDADE, 'UNIDADE - DPC (diárias e combustível custeados pela DPC).'),
        (CUSTEIO_OUTRA_INSTITUICAO, 'OUTRA INSTITUIÇÃO'),
        (CUSTEIO_ONUS_LIMITADOS, 'ÔNUS LIMITADOS AOS PRÓPRIOS VENCIMENTOS'),
    ]

    TIPO_DESTINO_INTERIOR = 'INTERIOR'
    TIPO_DESTINO_CAPITAL = 'CAPITAL'
    TIPO_DESTINO_BRASILIA = 'BRASILIA'
    TIPO_DESTINO_CHOICES = [
        (TIPO_DESTINO_INTERIOR, 'Interior'),
        (TIPO_DESTINO_CAPITAL, 'Capital'),
        (TIPO_DESTINO_BRASILIA, 'Brasília'),
    ]

    TIPO_VIATURA_CARACTERIZADA = 'CARACTERIZADA'
    TIPO_VIATURA_DESCARACTERIZADA = 'DESCARACTERIZADA'
    TIPO_VIATURA_CHOICES = [
        (TIPO_VIATURA_CARACTERIZADA, 'Caracterizada'),
        (TIPO_VIATURA_DESCARACTERIZADA, 'Descaracterizada'),
    ]

    # Vínculos
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name='oficios',
        verbose_name='Evento', null=True, blank=True
    )
    viajantes = models.ManyToManyField(
        'cadastros.Viajante', related_name='oficios', blank=True,
        verbose_name='Viajantes'
    )
    veiculo = models.ForeignKey(
        'cadastros.Veiculo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Veículo'
    )
    motorista_viajante = models.ForeignKey(
        'cadastros.Viajante', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios_motorista', verbose_name='Motorista (viajante)'
    )
    carona_oficio_referencia = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios_que_usam_carona', verbose_name='Ofício referência (carona)'
    )

    # Dados gerais (Step 1)
    numero = models.PositiveIntegerField('Número', null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField('Ano', null=True, blank=True, db_index=True)
    protocolo = models.CharField('Protocolo', max_length=80, blank=True, default='')
    data_criacao = models.DateField('Data de criação', null=True, blank=True, db_index=True)
    modelo_motivo = models.ForeignKey(
        ModeloMotivoViagem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='oficios', verbose_name='Modelo de motivo'
    )
    motivo = models.TextField('Motivo', blank=True, default='')
    custeio_tipo = models.CharField(
        'Custeio', max_length=30, choices=CUSTEIO_CHOICES, default=CUSTEIO_UNIDADE, blank=True
    )
    nome_instituicao_custeio = models.CharField(
        'Nome instituição de custeio', max_length=200, blank=True, default=''
    )
    tipo_destino = models.CharField(
        'Tipo destino', max_length=20, choices=TIPO_DESTINO_CHOICES, blank=True, default=''
    )

    # Transporte (Step 2) - texto/cópia além do FK veículo
    placa = models.CharField('Placa', max_length=10, blank=True, default='')
    modelo = models.CharField('Modelo', max_length=120, blank=True, default='')
    combustivel = models.CharField('Combustível', max_length=80, blank=True, default='')
    tipo_viatura = models.CharField(
        'Tipo viatura', max_length=20, choices=TIPO_VIATURA_CHOICES,
        default=TIPO_VIATURA_DESCARACTERIZADA, blank=True
    )

    # Motorista
    motorista = models.CharField('Motorista (nome)', max_length=120, blank=True, default='')
    motorista_carona = models.BooleanField('Motorista carona', default=False)
    motorista_oficio = models.CharField('Ofício do motorista', max_length=80, blank=True, default='')
    motorista_oficio_numero = models.PositiveIntegerField('Nº ofício motorista', null=True, blank=True)
    motorista_oficio_ano = models.PositiveIntegerField('Ano ofício motorista', null=True, blank=True)
    motorista_protocolo = models.CharField('Protocolo motorista', max_length=80, blank=True, default='')

    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Ofício'
        verbose_name_plural = 'Ofícios'
        constraints = [
            models.UniqueConstraint(
                fields=['ano', 'numero'],
                name='eventos_oficio_numero_ano_unique',
            )
        ]

    def __str__(self):
        if self.numero and self.ano:
            return f'Ofício {self.numero_formatado}'
        return f'Ofício #{self.pk} (rascunho)'

    @property
    def numero_formatado(self):
        """Ex.: 01/2026."""
        if self.numero and self.ano:
            return f'{int(self.numero):02d}/{int(self.ano)}'
        return EMPTY_MASK_DISPLAY

    @staticmethod
    def normalize_digits(value):
        return only_digits(value)

    @classmethod
    def normalize_protocolo(cls, value):
        return normalize_protocolo_canonico(value)

    @classmethod
    def format_protocolo(cls, value):
        return format_protocolo_visual(value)

    @property
    def protocolo_formatado(self):
        return self.format_protocolo(self.protocolo)

    @classmethod
    def get_next_available_numero(cls, ano):
        numeros_usados = list(
            cls.objects.select_for_update()
            .filter(ano=int(ano))
            .exclude(numero__isnull=True)
            .order_by('numero')
            .values_list('numero', flat=True)
        )
        proximo = 1
        for numero in numeros_usados:
            if numero != proximo:
                break
            proximo += 1
        return proximo

    @property
    def motorista_protocolo_formatado(self):
        return format_masked_display('protocolo', self.motorista_protocolo)

    @property
    def placa_formatada(self):
        return format_masked_display('placa', self.placa)

    def clean(self):
        super().clean()
        self.protocolo = self.normalize_protocolo(self.protocolo)
        if self.protocolo and len(self.protocolo) != 9:
            raise ValidationError({'protocolo': 'Protocolo deve estar no formato XX.XXX.XXX-X.'})
        if not self.data_criacao:
            self.data_criacao = timezone.localdate()
        if self.numero and not self.ano:
            self.ano = int(self.data_criacao.year)
        if self.custeio_tipo != self.CUSTEIO_OUTRA_INSTITUICAO:
            self.nome_instituicao_custeio = ''
        elif not (self.nome_instituicao_custeio or '').strip():
            raise ValidationError({'nome_instituicao_custeio': 'Informe a instituição de custeio.'})

    def save(self, *args, **kwargs):
        creating = self.pk is None
        self.protocolo = self.normalize_protocolo(self.protocolo)
        if self.protocolo and len(self.protocolo) != 9:
            raise ValidationError({'protocolo': 'Protocolo deve estar no formato XX.XXX.XXX-X.'})
        if not self.data_criacao:
            self.data_criacao = timezone.localdate()
        if self.numero and not self.ano:
            self.ano = int(self.data_criacao.year)
        if self.custeio_tipo != self.CUSTEIO_OUTRA_INSTITUICAO:
            self.nome_instituicao_custeio = ''

        # Numeração anual por menor lacuna disponível, com retry para concorrência.
        if creating and not self.numero:
            ano = int(self.ano or self.data_criacao.year)
            self.ano = ano
            for attempt in range(5):
                try:
                    with transaction.atomic():
                        self.numero = self.get_next_available_numero(ano)
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    if attempt == 4:
                        raise
                    self.numero = None

        super().save(*args, **kwargs)

    @property
    def data_criacao_formatada_br(self):
        if not self.data_criacao:
            return EMPTY_MASK_DISPLAY
        return self.data_criacao.strftime('%d/%m/%Y')


class EventoDestino(models.Model):
    """Destino do evento (estado/cidade). Um evento pode ter 1 ou mais destinos."""
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name='destinos',
        verbose_name='Evento'
    )
    estado = models.ForeignKey(
        Estado, on_delete=models.PROTECT, related_name='evento_destinos',
        verbose_name='Estado'
    )
    cidade = models.ForeignKey(
        Cidade, on_delete=models.PROTECT, related_name='evento_destinos',
        verbose_name='Cidade'
    )
    ordem = models.PositiveIntegerField('Ordem', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['evento', 'ordem', 'cidade__nome']
        verbose_name = 'Destino do evento'
        verbose_name_plural = 'Destinos do evento'

    def __str__(self):
        return f'{self.evento_id}: {self.cidade}'


class RoteiroEventoDestino(models.Model):
    """Um destino do roteiro (ordem na sequência: sede -> dest1 -> dest2 -> ... -> sede)."""
    roteiro = models.ForeignKey(
        'RoteiroEvento', on_delete=models.CASCADE, related_name='destinos',
        verbose_name='Roteiro'
    )
    estado = models.ForeignKey(
        Estado, on_delete=models.PROTECT, related_name='roteiro_destinos',
        verbose_name='Estado'
    )
    cidade = models.ForeignKey(
        Cidade, on_delete=models.PROTECT, related_name='roteiro_destinos',
        verbose_name='Cidade'
    )
    ordem = models.PositiveIntegerField('Ordem', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['roteiro', 'ordem']
        verbose_name = 'Destino do roteiro'
        verbose_name_plural = 'Destinos do roteiro'

    def __str__(self):
        return f'{self.cidade} ({self.estado.sigla})'


class RoteiroEventoTrecho(models.Model):
    """Trecho do roteiro com horários próprios de saída e chegada."""
    TIPO_IDA = 'IDA'
    TIPO_RETORNO = 'RETORNO'
    TIPO_CHOICES = [
        (TIPO_IDA, 'Ida'),
        (TIPO_RETORNO, 'Retorno'),
    ]

    roteiro = models.ForeignKey(
        'RoteiroEvento', on_delete=models.CASCADE, related_name='trechos',
        verbose_name='Roteiro'
    )
    ordem = models.PositiveIntegerField('Ordem', default=0)
    tipo = models.CharField('Tipo', max_length=10, choices=TIPO_CHOICES, default=TIPO_IDA)
    origem_estado = models.ForeignKey(
        Estado, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
        verbose_name='Estado origem'
    )
    origem_cidade = models.ForeignKey(
        Cidade, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
        verbose_name='Cidade origem'
    )
    destino_estado = models.ForeignKey(
        Estado, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
        verbose_name='Estado destino'
    )
    destino_cidade = models.ForeignKey(
        Cidade, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
        verbose_name='Cidade destino'
    )
    saida_dt = models.DateTimeField('Saída', null=True, blank=True)
    chegada_dt = models.DateTimeField('Chegada', null=True, blank=True)
    distancia_km = models.DecimalField(
        'Distância (km)', max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Preenchido manualmente ou via "Estimar km/tempo" (estimativa local).'
    )
    duracao_estimada_min = models.PositiveIntegerField(
        'Duração estimada (min)', null=True, blank=True,
        help_text='tempo_total_final = tempo_cru + tempo_adicional. Mantido para compatibilidade.'
    )
    tempo_cru_estimado_min = models.PositiveIntegerField(
        'Tempo cru estimado (min)', null=True, blank=True,
        help_text='Tempo base da viagem (estimativa local), somente leitura.'
    )
    tempo_adicional_min = models.IntegerField(
        'Tempo adicional (min)', null=True, blank=True, default=0,
        help_text='Folga ajustável pelo usuário (botões ±15 min).'
    )
    rota_fonte = models.CharField(
        'Fonte da rota', max_length=30, blank=True, default='',
        help_text='Ex.: ESTIMATIVA_LOCAL quando calculado pela estimativa local.'
    )
    rota_calculada_em = models.DateTimeField(
        'Rota calculada em', null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['roteiro', 'ordem']
        verbose_name = 'Trecho do roteiro'
        verbose_name_plural = 'Trechos do roteiro'

    @property
    def tempo_total_final_min(self):
        """Tempo total = tempo_cru_estimado + tempo_adicional. Usado para calcular chegada."""
        cru = self.tempo_cru_estimado_min or 0
        adic = self.tempo_adicional_min or 0
        total = cru + adic
        return total if total > 0 else (self.duracao_estimada_min or None)

    def __str__(self):
        orig = self.origem_cidade or self.origem_estado or EMPTY_MASK_DISPLAY
        dest = self.destino_cidade or self.destino_estado or EMPTY_MASK_DISPLAY
        return f'{orig} -> {dest} ({self.get_tipo_display()})'


class RoteiroEvento(models.Model):
    """Roteiro vinculado a um evento (Etapa 2 do fluxo guiado). Sede (origem) + N destinos."""
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]

    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name='roteiros',
        verbose_name='Evento'
    )
    origem_estado = models.ForeignKey(
        Estado, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Estado sede'
    )
    origem_cidade = models.ForeignKey(
        Cidade, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cidade sede'
    )
    saida_dt = models.DateTimeField('Data/hora saída', null=True, blank=True)
    duracao_min = models.PositiveIntegerField('Duração (min)', null=True, blank=True)
    chegada_dt = models.DateTimeField('Data/hora chegada', null=True, blank=True)
    retorno_saida_dt = models.DateTimeField('Retorno - saída', null=True, blank=True)
    retorno_duracao_min = models.PositiveIntegerField('Retorno - duração (min)', null=True, blank=True)
    retorno_chegada_dt = models.DateTimeField('Retorno - chegada', null=True, blank=True)
    observacoes = models.TextField('Observações', blank=True, default='')
    status = models.CharField(
        'Status', max_length=20, choices=STATUS_CHOICES, default=STATUS_RASCUNHO
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Roteiro do evento'
        verbose_name_plural = 'Roteiros do evento'

    def __str__(self):
        orig = self.origem_cidade or self.origem_estado or EMPTY_MASK_DISPLAY
        destinos = list(self.destinos.select_related('cidade', 'estado').order_by('ordem')[:3])
        if not destinos:
            return f'{orig} -> {EMPTY_MASK_DISPLAY}'
        nomes = [d.cidade.nome if d.cidade else d.estado.sigla for d in destinos]
        sufixo = '...' if self.destinos.count() > 3 else ''
        return f'{orig} -> ' + ', '.join(nomes) + sufixo

    def esta_completo(self):
        """
        True se os dados obrigatórios para FINALIZADO estão preenchidos:
        evento, sede (origem), ao menos um destino, saida_dt, chegada_dt.
        Duração é por trecho (cru + adicional); duracao_min do roteiro é legado.
        Retorno é opcional. Não usa self.destinos antes de ter pk.
        """
        if not self.pk:
            return False
        return bool(
            self.evento_id
            and self.origem_estado_id
            and self.origem_cidade_id
            and self.destinos.exists()
            and self.saida_dt is not None
            and self.chegada_dt is not None
        )

    def save(self, *args, **kwargs):
        if self.observacoes:
            self.observacoes = self.observacoes.strip().upper()
        from datetime import timedelta
        # duracao_min é legado; quando preenchido, recalcula chegada.
        if self.saida_dt and self.duracao_min is not None:
            self.chegada_dt = self.saida_dt + timedelta(minutes=self.duracao_min)
        if self.retorno_saida_dt and self.duracao_min is not None:
            self.retorno_chegada_dt = self.retorno_saida_dt + timedelta(minutes=self.duracao_min)
        self.status = self.STATUS_FINALIZADO if self.esta_completo() else self.STATUS_RASCUNHO
        super().save(*args, **kwargs)

