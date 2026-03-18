from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone
from django.utils.text import slugify
from cadastros.models import Cargo, Estado, Cidade
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


class SolicitantePlanoTrabalho(models.Model):
    """Gerenciador de solicitantes para o Plano de Trabalho (cadastro reutilizável)."""
    nome = models.CharField('Nome', max_length=200)
    ativo = models.BooleanField('Ativo', default=True)
    ordem = models.PositiveIntegerField('Ordem', default=100)
    is_padrao = models.BooleanField('Padrão', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'Solicitante (Plano de Trabalho)'
        verbose_name_plural = 'Solicitantes (Plano de Trabalho)'

    def __str__(self):
        return self.nome


class CoordenadorOperacional(models.Model):
    """Banco de coordenadores operacionais para o Plano de Trabalho."""
    nome = models.CharField('Nome', max_length=200)
    cargo = models.CharField('Cargo', max_length=120, blank=True, default='')
    cidade = models.CharField('Cidade', max_length=120, blank=True, default='')
    unidade = models.CharField('Unidade', max_length=160, blank=True, default='')
    ativo = models.BooleanField('Ativo', default=True)
    ordem = models.PositiveIntegerField('Ordem', default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'nome']
        verbose_name = 'Coordenador operacional'
        verbose_name_plural = 'Coordenadores operacionais'

    def __str__(self):
        return f'{self.cargo or "—"} {self.nome}'.strip()


class PlanoTrabalho(models.Model):
    """Documento independente de Plano de Trabalho, com vínculo opcional a evento e ofício."""

    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]

    numero = models.PositiveIntegerField('Número', null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField('Ano', null=True, blank=True, db_index=True)
    data_criacao = models.DateField('Data de criação', default=timezone.localdate, db_index=True)
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RASCUNHO,
        db_index=True,
    )
    evento = models.ForeignKey(
        Evento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planos_trabalho',
        verbose_name='Evento',
    )
    oficio = models.ForeignKey(
        'Oficio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planos_trabalho',
        verbose_name='Ofício',
    )
    solicitante = models.ForeignKey(
        'SolicitantePlanoTrabalho',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planos_trabalho',
        verbose_name='Solicitante',
    )
    solicitante_outros = models.CharField('Solicitante (outros)', max_length=200, blank=True, default='')
    coordenador_operacional = models.ForeignKey(
        'CoordenadorOperacional',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planos_trabalho',
        verbose_name='Coordenador operacional',
    )
    coordenador_administrativo = models.ForeignKey(
        'cadastros.Viajante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planos_trabalho_coord_adm',
        verbose_name='Coordenador administrativo',
    )
    coordenador_municipal = models.CharField('Coordenador municipal', max_length=200, blank=True, default='')
    objetivo = models.TextField('Objetivo/finalidade', blank=True, default='')
    locais = models.TextField('Locais', blank=True, default='')
    horario_atendimento = models.CharField('Horário de atendimento', max_length=120, blank=True, default='')
    quantidade_servidores = models.PositiveIntegerField('Quantidade de servidores', null=True, blank=True)
    atividades_codigos = models.CharField('Atividades (códigos)', max_length=500, blank=True, default='')
    metas_formatadas = models.TextField('Metas formatadas', blank=True, default='')
    efetivo_resumo = models.TextField('Efetivo (resumo)', blank=True, default='')
    recursos_texto = models.TextField('Recursos (texto)', blank=True, default='')
    observacoes = models.TextField('Observações', blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Plano de trabalho'
        verbose_name_plural = 'Planos de trabalho'

    def __str__(self):
        if self.numero and self.ano:
            return f'PT {int(self.numero):02d}/{int(self.ano)}'
        return f'PT #{self.pk} (rascunho)'

    @property
    def numero_formatado(self):
        if self.numero and self.ano:
            return f'{int(self.numero):02d}/{int(self.ano)}'
        return EMPTY_MASK_DISPLAY


class OrdemServico(models.Model):
    """Documento independente de Ordem de Serviço, com vínculo opcional a evento e ofício."""

    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]

    numero = models.PositiveIntegerField('Número', null=True, blank=True, db_index=True)
    ano = models.PositiveIntegerField('Ano', null=True, blank=True, db_index=True)
    data_criacao = models.DateField('Data de criação', default=timezone.localdate, db_index=True)
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RASCUNHO,
        db_index=True,
    )
    evento = models.ForeignKey(
        Evento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordens_servico',
        verbose_name='Evento',
    )
    oficio = models.ForeignKey(
        'Oficio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordens_servico',
        verbose_name='Ofício',
    )
    finalidade = models.TextField('Finalidade', blank=True, default='')
    responsaveis = models.TextField('Responsáveis', blank=True, default='')
    designacoes = models.TextField('Designações', blank=True, default='')
    determinacoes = models.TextField('Determinações', blank=True, default='')
    observacoes = models.TextField('Observações', blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Ordem de serviço'
        verbose_name_plural = 'Ordens de serviço'

    def __str__(self):
        if self.numero and self.ano:
            return f'OS {int(self.numero):02d}/{int(self.ano)}'
        return f'OS #{self.pk} (rascunho)'

    @property
    def numero_formatado(self):
        if self.numero and self.ano:
            return f'{int(self.numero):02d}/{int(self.ano)}'
        return EMPTY_MASK_DISPLAY


class EfetivoPlanoTrabalhoDocumento(models.Model):
    """Composição de efetivo do plano vinculada ao documento PlanoTrabalho."""

    plano_trabalho = models.ForeignKey(
        PlanoTrabalho,
        on_delete=models.CASCADE,
        related_name='efetivos',
        verbose_name='Plano de trabalho',
    )
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        related_name='efetivos_plano_documento',
        verbose_name='Cargo',
    )
    quantidade = models.PositiveIntegerField('Quantidade', default=1)

    class Meta:
        ordering = ['plano_trabalho', 'cargo__nome']
        verbose_name = 'Efetivo do plano de trabalho'
        verbose_name_plural = 'Efetivos do plano de trabalho'
        constraints = [
            models.UniqueConstraint(
                fields=['plano_trabalho', 'cargo'],
                name='eventos_efetivoptdocumento_plano_cargo_unique',
            ),
        ]

    def __str__(self):
        return f'{self.plano_trabalho_id}: {self.quantidade} x {self.cargo}'


class EfetivoPlanoTrabalho(models.Model):
    """Composição de efetivo do Plano de Trabalho por cargo e quantidade (por evento)."""
    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name='efetivo_plano_trabalho',
        verbose_name='Evento',
    )
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        related_name='efetivos_plano',
        verbose_name='Cargo',
    )
    quantidade = models.PositiveIntegerField('Quantidade', default=1)

    class Meta:
        ordering = ['evento', 'cargo__nome']
        verbose_name = 'Efetivo (Plano de Trabalho)'
        verbose_name_plural = 'Efetivos (Plano de Trabalho)'
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'cargo'],
                name='eventos_efetivoplano_evento_cargo_unique',
            ),
        ]

    def __str__(self):
        return f'{self.evento_id}: {self.quantidade} x {self.cargo}'


class EventoTermoParticipante(models.Model):
    """
    Situação do termo (Etapa 5) por participante do evento.
    Participantes = viajantes que constam em algum ofício do evento.
    Um registro por (evento, viajante). Status: pendente, dispensado, gerado ou concluído.
    """
    STATUS_PENDENTE = 'PENDENTE'
    STATUS_DISPENSADO = 'DISPENSADO'
    STATUS_GERADO = 'GERADO'
    STATUS_CONCLUIDO = 'CONCLUIDO'
    STATUS_CHOICES = [
        (STATUS_PENDENTE, 'Pendente'),
        (STATUS_DISPENSADO, 'Dispensado'),
        (STATUS_GERADO, 'Gerado'),
        (STATUS_CONCLUIDO, 'Concluído'),
    ]
    STATUS_FINALIZADORES = {STATUS_DISPENSADO, STATUS_CONCLUIDO}

    MODALIDADE_COMPLETO = 'COMPLETO'
    MODALIDADE_SEMIPREENCHIDO = 'SEMIPREENCHIDO'
    MODALIDADE_CHOICES = [
        (MODALIDADE_COMPLETO, 'Completo'),
        (MODALIDADE_SEMIPREENCHIDO, 'Semipreenchido'),
    ]

    FORMATO_DOCX = 'docx'
    FORMATO_PDF = 'pdf'
    FORMATO_CHOICES = [
        (FORMATO_DOCX, 'DOCX'),
        (FORMATO_PDF, 'PDF'),
    ]

    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name='termos_participantes',
        verbose_name='Evento',
    )
    viajante = models.ForeignKey(
        'cadastros.Viajante',
        on_delete=models.CASCADE,
        related_name='eventos_termo_status',
        verbose_name='Viajante',
    )
    status = models.CharField(
        'Status do termo',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
    )
    modalidade = models.CharField(
        'Modalidade do termo',
        max_length=20,
        choices=MODALIDADE_CHOICES,
        default=MODALIDADE_COMPLETO,
    )
    ultima_geracao_em = models.DateTimeField(
        'Última geração em',
        null=True,
        blank=True,
    )
    ultimo_formato_gerado = models.CharField(
        'Último formato gerado',
        max_length=10,
        choices=FORMATO_CHOICES,
        blank=True,
        default='',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['evento', 'viajante__nome']
        verbose_name = 'Termo do participante (evento)'
        verbose_name_plural = 'Termos dos participantes (evento)'
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'viajante'],
                name='eventos_eventotermoparticipante_evento_viajante_unique',
            ),
        ]

    def __str__(self):
        return (
            f'{self.evento_id} — {self.viajante} — '
            f'{self.get_status_display()} — {self.get_modalidade_display()}'
        )


class EventoFinalizacao(models.Model):
    """
    Dados da Etapa 6 do evento: Finalização.
    Um registro por evento (1:1). Concluído quando finalizado_em estiver preenchido.
    """
    evento = models.OneToOneField(
        Evento,
        on_delete=models.CASCADE,
        related_name='finalizacao',
        verbose_name='Evento',
    )
    observacoes_finais = models.TextField(
        'Observações finais',
        blank=True,
        default='',
    )
    finalizado_em = models.DateTimeField(
        'Finalizado em',
        null=True,
        blank=True,
    )
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_finalizados',
        verbose_name='Finalizado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Finalização do evento'
        verbose_name_plural = 'Finalizações do evento'

    def __str__(self):
        return f'Finalização — {self.evento}'

    @property
    def concluido(self):
        """True quando o evento foi marcado como finalizado (finalizado_em preenchido)."""
        return self.finalizado_em is not None


class DocumentoAvulso(models.Model):
    """Documento criado sem vínculo obrigatório; pode ser vinculado posteriormente."""

    TIPO_OFICIO = 'OFICIO'
    TIPO_TERMO_AUTORIZACAO = 'TERMO_AUTORIZACAO'
    TIPO_JUSTIFICATIVA = 'JUSTIFICATIVA'
    TIPO_PLANO_TRABALHO = 'PLANO_TRABALHO'
    TIPO_ORDEM_SERVICO = 'ORDEM_SERVICO'
    TIPO_OUTRO = 'OUTRO'
    TIPO_CHOICES = [
        (TIPO_OFICIO, 'Ofício avulso'),
        (TIPO_TERMO_AUTORIZACAO, 'Termo de autorização avulso'),
        (TIPO_JUSTIFICATIVA, 'Justificativa avulsa'),
        (TIPO_PLANO_TRABALHO, 'Plano de trabalho avulso'),
        (TIPO_ORDEM_SERVICO, 'Ordem de serviço avulsa'),
        (TIPO_OUTRO, 'Outros modelos avulsos'),
    ]

    CLASSIFICACAO_AVULSO = 'AVULSO'
    CLASSIFICACAO_VINCULADO = 'VINCULADO'
    CLASSIFICACAO_CHOICES = [
        (CLASSIFICACAO_AVULSO, 'Avulso'),
        (CLASSIFICACAO_VINCULADO, 'Vinculado'),
    ]

    TERMO_TEMPLATE_COMPLETO_COM_VIATURA = 'COMPLETO_COM_VIATURA'
    TERMO_TEMPLATE_COMPLETO_SEM_VIATURA = 'COMPLETO_SEM_VIATURA'
    TERMO_TEMPLATE_SEMIPREENCHIDO = 'SEMIPREENCHIDO'
    TERMO_TEMPLATE_CHOICES = [
        (TERMO_TEMPLATE_COMPLETO_COM_VIATURA, 'Termo completo com viatura'),
        (TERMO_TEMPLATE_COMPLETO_SEM_VIATURA, 'Termo completo sem viatura'),
        (TERMO_TEMPLATE_SEMIPREENCHIDO, 'Termo semipreenchido/manual'),
    ]

    titulo = models.CharField('Título', max_length=200)
    tipo_documento = models.CharField('Tipo do documento', max_length=30, choices=TIPO_CHOICES)
    conteudo_texto = models.TextField('Conteúdo livre', blank=True, default='')
    placeholders = models.JSONField('Placeholders', blank=True, default=dict)
    termo_template_variant = models.CharField(
        'Variante do template de termo',
        max_length=30,
        choices=TERMO_TEMPLATE_CHOICES,
        default=TERMO_TEMPLATE_SEMIPREENCHIDO,
    )
    classificacao = models.CharField(
        'Classificação',
        max_length=20,
        choices=CLASSIFICACAO_CHOICES,
        default=CLASSIFICACAO_AVULSO,
        db_index=True,
    )
    evento = models.ForeignKey(
        Evento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_avulsos',
        verbose_name='Evento vinculado',
    )
    roteiro = models.ForeignKey(
        'RoteiroEvento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_avulsos',
        verbose_name='Roteiro vinculado',
    )
    plano_trabalho = models.ForeignKey(
        'PlanoTrabalho',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_avulsos',
        verbose_name='Plano de trabalho vinculado',
    )
    ordem_servico = models.ForeignKey(
        'OrdemServico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_avulsos',
        verbose_name='Ordem de serviço vinculada',
    )
    oficio = models.ForeignKey(
        'Oficio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_avulsos',
        verbose_name='Ofício vinculado',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_avulsos_criados',
        verbose_name='Criado por',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-created_at']
        verbose_name = 'Documento avulso'
        verbose_name_plural = 'Documentos avulsos'

    def __str__(self):
        return f'{self.get_tipo_documento_display()} — {self.titulo}'

    @property
    def is_vinculado(self):
        return bool(
            self.evento_id
            or self.roteiro_id
            or self.plano_trabalho_id
            or self.ordem_servico_id
            or self.oficio_id
        )

    def _sync_classificacao(self):
        self.classificacao = (
            self.CLASSIFICACAO_VINCULADO if self.is_vinculado else self.CLASSIFICACAO_AVULSO
        )

    def save(self, *args, **kwargs):
        self.titulo = (self.titulo or '').strip()
        self.conteudo_texto = (self.conteudo_texto or '').strip()
        if not isinstance(self.placeholders, dict):
            self.placeholders = {}
        self._sync_classificacao()
        super().save(*args, **kwargs)


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


class ModeloJustificativa(models.Model):
    """Modelos reutilizáveis de justificativa do ofício."""

    nome = models.CharField('Nome do modelo', max_length=200)
    texto = models.TextField('Texto da justificativa')
    padrao = models.BooleanField('Padrão', default=False)
    ativo = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Modelo de justificativa'
        verbose_name_plural = 'Modelos de justificativa'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.nome = (self.nome or '').strip()
        if self.padrao:
            ModeloJustificativa.objects.exclude(pk=self.pk).update(padrao=False)
        super().save(*args, **kwargs)


class Oficio(models.Model):
    """
    Ofício, que pode ser avulso ou vinculado a um evento.
    Wizard: Step 1 (dados + viajantes), Step 2 (transporte + motorista),
    Step 3 (trechos) e Step 4 (resumo).
    """
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]

    ORIGEM_AVULSO = 'AVULSO'
    ORIGEM_EVENTO = 'EVENTO'
    ORIGEM_CHOICES = [
        (ORIGEM_AVULSO, 'Avulso'),
        (ORIGEM_EVENTO, 'Vinculado a evento'),
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
    ROTEIRO_MODO_EVENTO = 'EVENTO_EXISTENTE'
    ROTEIRO_MODO_PROPRIO = 'ROTEIRO_PROPRIO'
    ROTEIRO_MODO_CHOICES = [
        (ROTEIRO_MODO_EVENTO, 'Usar roteiro salvo'),
        (ROTEIRO_MODO_PROPRIO, 'Montar roteiro neste ofício'),
    ]

    # Vínculos
    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name='oficios',
        verbose_name='Evento',
        null=True,
        blank=True,
    )
    roteiro_evento = models.ForeignKey(
        'RoteiroEvento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficios',
        verbose_name='Roteiro do evento selecionado',
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

    tipo_origem = models.CharField(
        'Origem',
        max_length=20,
        choices=ORIGEM_CHOICES,
        default=ORIGEM_EVENTO,
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
    justificativa_modelo = models.ForeignKey(
        ModeloJustificativa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficios',
        verbose_name='Modelo de justificativa',
    )
    motivo = models.TextField('Motivo', blank=True, default='')
    justificativa_texto = models.TextField('Justificativa', blank=True, default='')
    gerar_termo_preenchido = models.BooleanField(
        'Gerar termo de autorização preenchido',
        default=False,
    )
    custeio_tipo = models.CharField(
        'Custeio', max_length=30, choices=CUSTEIO_CHOICES, default=CUSTEIO_UNIDADE, blank=True
    )
    nome_instituicao_custeio = models.CharField(
        'Nome instituição de custeio', max_length=200, blank=True, default=''
    )
    tipo_destino = models.CharField(
        'Tipo destino', max_length=20, choices=TIPO_DESTINO_CHOICES, blank=True, default=''
    )
    roteiro_modo = models.CharField(
        'Modo do roteiro',
        max_length=20,
        choices=ROTEIRO_MODO_CHOICES,
        default=ROTEIRO_MODO_PROPRIO,
        blank=True,
    )
    estado_sede = models.ForeignKey(
        Estado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficios_sede',
        verbose_name='Estado sede',
    )
    cidade_sede = models.ForeignKey(
        Cidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficios_sede',
        verbose_name='Cidade sede',
    )

    # Transporte (Step 2) - texto/cópia além do FK veículo
    placa = models.CharField('Placa', max_length=10, blank=True, default='')
    modelo = models.CharField('Modelo', max_length=120, blank=True, default='')
    combustivel = models.CharField('Combustível', max_length=80, blank=True, default='')
    tipo_viatura = models.CharField(
        'Tipo viatura', max_length=20, choices=TIPO_VIATURA_CHOICES,
        default=TIPO_VIATURA_DESCARACTERIZADA, blank=True
    )
    porte_transporte_armas = models.BooleanField('Porte/transporte de armas', default=True)

    # Motorista
    motorista = models.CharField('Motorista (nome)', max_length=120, blank=True, default='')
    motorista_carona = models.BooleanField('Motorista carona', default=False)
    motorista_oficio = models.CharField('Ofício do motorista', max_length=80, blank=True, default='')
    motorista_oficio_numero = models.PositiveIntegerField('Nº ofício motorista', null=True, blank=True)
    motorista_oficio_ano = models.PositiveIntegerField('Ano ofício motorista', null=True, blank=True)
    motorista_protocolo = models.CharField('Protocolo motorista', max_length=80, blank=True, default='')
    retorno_saida_cidade = models.CharField('Retorno - cidade de saída', max_length=120, blank=True, default='')
    retorno_saida_data = models.DateField('Retorno - data de saída', null=True, blank=True)
    retorno_saida_hora = models.TimeField('Retorno - hora de saída', null=True, blank=True)
    retorno_chegada_cidade = models.CharField('Retorno - cidade de chegada', max_length=120, blank=True, default='')
    retorno_chegada_data = models.DateField('Retorno - data de chegada', null=True, blank=True)
    retorno_chegada_hora = models.TimeField('Retorno - hora de chegada', null=True, blank=True)
    retorno_distancia_km = models.DecimalField(
        'Retorno - distancia (km)',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    retorno_duracao_estimada_min = models.PositiveIntegerField(
        'Retorno - duracao estimada (min)',
        null=True,
        blank=True,
    )
    retorno_tempo_cru_estimado_min = models.PositiveIntegerField(
        'Retorno - tempo cru estimado (min)',
        null=True,
        blank=True,
    )
    retorno_tempo_adicional_min = models.IntegerField(
        'Retorno - tempo adicional (min)',
        null=True,
        blank=True,
        default=0,
    )
    retorno_rota_fonte = models.CharField('Retorno - fonte da rota', max_length=30, blank=True, default='')
    retorno_rota_calculada_em = models.DateTimeField('Retorno - rota calculada em', null=True, blank=True)
    quantidade_diarias = models.CharField('Quantidade de diárias', max_length=120, blank=True, default='')
    valor_diarias = models.CharField('Valor das diárias', max_length=80, blank=True, default='')
    valor_diarias_extenso = models.TextField('Valor das diárias por extenso', blank=True, default='')

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

    @property
    def motorista_oficio_formatado(self):
        if self.motorista_oficio_numero and self.motorista_oficio_ano:
            return f'{int(self.motorista_oficio_numero):02d}/{int(self.motorista_oficio_ano)}'
        return self.motorista_oficio or EMPTY_MASK_DISPLAY

    @property
    def retorno_tempo_total_final_min(self):
        cru = self.retorno_tempo_cru_estimado_min or 0
        adicional = self.retorno_tempo_adicional_min or 0
        total = cru + adicional
        return total if total > 0 else (self.retorno_duracao_estimada_min or None)

    def clean(self):
        super().clean()
        self.protocolo = self.normalize_protocolo(self.protocolo)
        if self.protocolo and len(self.protocolo) != 9:
            raise ValidationError({'protocolo': 'Protocolo deve estar no formato XX.XXX.XXX-X.'})
        # Normalizar e validar protocolo do motorista quando motorista carona
        self.motorista_protocolo = self.normalize_protocolo(self.motorista_protocolo)
        if self.motorista_carona:
            if not (self.motorista_protocolo or '').strip():
                raise ValidationError({
                    'motorista_protocolo': 'Informe o protocolo do motorista (formato XX.XXX.XXX-X).',
                })
            if len(self.motorista_protocolo) != 9:
                raise ValidationError({
                    'motorista_protocolo': 'Protocolo do motorista deve ter 9 dígitos (formato XX.XXX.XXX-X).',
                })
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
        self.motorista_protocolo = self.normalize_protocolo(self.motorista_protocolo)
        if self.motorista_carona and self.motorista_protocolo and len(self.motorista_protocolo) != 9:
            raise ValidationError({
                'motorista_protocolo': 'Protocolo do motorista deve ter 9 dígitos (formato XX.XXX.XXX-X).',
            })
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


class OficioTrecho(models.Model):
    """Trecho de ida do ofício. O retorno permanece separado no próprio Ofício."""

    oficio = models.ForeignKey(
        Oficio,
        on_delete=models.CASCADE,
        related_name='trechos',
        verbose_name='Ofício',
    )
    ordem = models.PositiveIntegerField('Ordem', default=0)
    origem_estado = models.ForeignKey(
        Estado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficio_trechos_origem',
        verbose_name='Estado origem',
    )
    origem_cidade = models.ForeignKey(
        Cidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficio_trechos_origem',
        verbose_name='Cidade origem',
    )
    destino_estado = models.ForeignKey(
        Estado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficio_trechos_destino',
        verbose_name='Estado destino',
    )
    destino_cidade = models.ForeignKey(
        Cidade,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='oficio_trechos_destino',
        verbose_name='Cidade destino',
    )
    saida_data = models.DateField('Saída - data', null=True, blank=True)
    saida_hora = models.TimeField('Saída - hora', null=True, blank=True)
    chegada_data = models.DateField('Chegada - data', null=True, blank=True)
    chegada_hora = models.TimeField('Chegada - hora', null=True, blank=True)
    distancia_km = models.DecimalField(
        'Distância (km)',
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    duracao_estimada_min = models.PositiveIntegerField('Duração estimada (min)', null=True, blank=True)
    tempo_cru_estimado_min = models.PositiveIntegerField('Tempo cru estimado (min)', null=True, blank=True)
    tempo_adicional_min = models.IntegerField('Tempo adicional (min)', null=True, blank=True, default=0)
    rota_fonte = models.CharField('Fonte da rota', max_length=30, blank=True, default='')
    rota_calculada_em = models.DateTimeField('Rota calculada em', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Trecho do ofício'
        verbose_name_plural = 'Trechos do ofício'
        constraints = [
            models.UniqueConstraint(
                fields=['oficio', 'ordem'],
                name='eventos_oficiotrecho_oficio_ordem_unique',
            )
        ]

    def __str__(self):
        origem = self.origem_cidade or self.origem_estado or EMPTY_MASK_DISPLAY
        destino = self.destino_cidade or self.destino_estado or EMPTY_MASK_DISPLAY
        return f'Trecho {self.ordem + 1}: {origem} -> {destino}'

    @property
    def tempo_total_final_min(self):
        cru = self.tempo_cru_estimado_min or 0
        adicional = self.tempo_adicional_min or 0
        total = cru + adicional
        return total if total > 0 else (self.duracao_estimada_min or None)


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
    """
    Roteiro vinculado a um evento (Etapa 2 do fluxo guiado) ou avulso.
    Sede (origem) + N destinos.
    """
    STATUS_RASCUNHO = 'RASCUNHO'
    STATUS_FINALIZADO = 'FINALIZADO'
    STATUS_CHOICES = [
        (STATUS_RASCUNHO, 'Rascunho'),
        (STATUS_FINALIZADO, 'Finalizado'),
    ]

    TIPO_EVENTO = 'EVENTO'
    TIPO_AVULSO = 'AVULSO'
    TIPO_CHOICES = [
        (TIPO_EVENTO, 'Vinculado a evento'),
        (TIPO_AVULSO, 'Avulso'),
    ]

    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name='roteiros',
        verbose_name='Evento',
        null=True,
        blank=True,
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
    tipo = models.CharField(
        'Tipo de roteiro',
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_EVENTO,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Roteiro'
        verbose_name_plural = 'Roteiros'

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
        - sede (origem), ao menos um destino, saida_dt, chegada_dt; e
        - quando tipo = EVENTO, requer vínculo com evento.
        Duração é por trecho (cru + adicional); duracao_min do roteiro é legado.
        Retorno é opcional. Não usa self.destinos antes de ter pk.
        """
        if not self.pk:
            return False
        if self.tipo == self.TIPO_EVENTO and not self.evento_id:
            return False
        return bool(
            self.origem_estado_id
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
