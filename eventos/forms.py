import uuid
import json
import re
from datetime import datetime

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from cadastros.models import Cargo, Cidade, ConfiguracaoSistema, UnidadeLotacao, Viajante, Veiculo
from eventos.services.oficio_schema import oficio_justificativa_schema_available
from eventos.services.justificativa import get_oficio_justificativa, get_oficio_justificativa_texto
from eventos.termos import build_termo_context, build_termo_preview_payload
from .models import (
    Evento,
    EventoFinalizacao,
    EventoParticipante,
    Justificativa,
    ModeloJustificativa,
    ModeloMotivoViagem,
    OrdemServico,
    Oficio,
    PlanoTrabalho,
    RoteiroEvento,
    SolicitantePlanoTrabalho,
    TermoAutorizacao,
    CoordenadorOperacional,
    TipoDemandaEvento,
)
from .services.plano_trabalho_domain import (
    ATIVIDADES_CATALOGO,
    build_metas_formatada,
    build_recursos_necessarios_formatado,
)
from .services.diarias import PeriodMarker, calculate_periodized_diarias
from core.utils.masks import format_placa, format_protocolo, normalize_placa
from .utils import buscar_veiculo_finalizado_por_placa, mapear_tipo_viatura_para_oficio, normalize_protocolo


LEGACY_SELECT_WIDGET_CLASSES = {
    'custom-select',
    'cv-select-base',
    'form-select',
    'form-select-sm',
    'oficios-sort-select',
    'termo-context-select',
}


def _sanitize_select_widget(widget):
    if not isinstance(widget, forms.Select):
        return

    classes = [
        token
        for token in str(widget.attrs.get('class', '')).split()
        if token not in LEGACY_SELECT_WIDGET_CLASSES
    ]
    if classes:
        widget.attrs['class'] = ' '.join(classes)
    else:
        widget.attrs.pop('class', None)

    widget.attrs.pop('data-searchable-select', None)
    widget.attrs.pop('data-searchable-placeholder', None)
    widget.attrs.pop('style', None)


class FormComErroInvalidMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in getattr(self, 'fields', {}).values():
            _sanitize_select_widget(field.widget)

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                cls = self.fields[name].widget.attrs.get('class', '')
                if 'is-invalid' not in cls:
                    self.fields[name].widget.attrs['class'] = f'{cls} is-invalid'.strip()


class EventoForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            'titulo', 'tipo_demanda', 'descricao', 'data_inicio', 'data_fim',
            'estado_principal', 'cidade_principal', 'cidade_base',
            'tem_convite_ou_oficio_evento', 'status',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_demanda': forms.Select(attrs={'class': ''}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estado_principal': forms.Select(attrs={'class': '', 'data-cidades-target': 'cidade_principal'}),
            'cidade_principal': forms.Select(attrs={'class': ''}),
            'cidade_base': forms.Select(attrs={'class': ''}),
            'tem_convite_ou_oficio_evento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': ''}),
        }

    def clean(self):
        data = super().clean()
        data_inicio = data.get('data_inicio')
        data_fim = data.get('data_fim')
        estado_principal = data.get('estado_principal')
        cidade_principal = data.get('cidade_principal')

        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error('data_fim', 'A data de término não pode ser anterior à data de início.')

        if estado_principal and cidade_principal:
            if cidade_principal.estado_id != estado_principal.id:
                self.add_error(
                    'cidade_principal',
                    'A cidade principal deve pertencer ao estado principal selecionado.'
                )
        return data


class EventoEtapa1Form(FormComErroInvalidMixin, forms.ModelForm):
    """
    Formulário da Etapa 1 do fluxo guiado refatorado.
    Descrição só é exigida quando tipo OUTROS está selecionado (campo exibido apenas nesse caso no template).
    data_fim opcional quando data_unica=True (preenchido no clean).
    """
    class Meta:
        model = Evento
        fields = [
            'tipos_demanda', 'data_unica', 'data_inicio', 'data_fim',
            'descricao', 'tem_convite_ou_oficio_evento',
        ]
        widgets = {
            'tipos_demanda': forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
            'data_unica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'tem_convite_ou_oficio_evento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipos_demanda'].queryset = TipoDemandaEvento.objects.filter(ativo=True).order_by('ordem', 'nome')
        self.fields['tipos_demanda'].required = False  # validamos no clean
        self.fields['data_fim'].required = False  # quando data_unica=True o campo some; preenchemos no clean
        self.fields['descricao'].required = False  # obrigatório só quando OUTROS selecionado (validado no clean)

    def clean(self):
        data = super().clean()
        tipos = data.get('tipos_demanda')
        data_inicio = data.get('data_inicio')
        data_fim = data.get('data_fim')
        data_unica = data.get('data_unica')

        if not tipos or not list(tipos):
            self.add_error('tipos_demanda', 'Selecione pelo menos um tipo de demanda.')

        if data_unica and data_inicio:
            data['data_fim'] = data_inicio
        elif not data_unica and data_inicio and data_fim and data_fim < data_inicio:
            self.add_error('data_fim', 'A data de término não pode ser anterior à data de início.')

        tem_outros = bool(tipos and any(t.is_outros for t in tipos))
        if tem_outros:
            desc = (data.get('descricao') or '').strip()
            if not desc:
                self.add_error('descricao', 'Com o tipo "Outros" selecionado, a descrição é obrigatória.')
        else:
            data['descricao'] = ''  # sem OUTROS: não exigir e limpar ao salvar

        return data


class EventoFinalizacaoForm(FormComErroInvalidMixin, forms.ModelForm):
    """Formulário da Etapa 6 do evento: observações finais (finalizado_em/por são definidos na ação de finalizar)."""
    class Meta:
        model = EventoFinalizacao
        fields = ['observacoes_finais']
        widgets = {
            'observacoes_finais': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Observações finais do evento (opcional).',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['observacoes_finais'].required = False


class CoordenadorOperacionalForm(FormComErroInvalidMixin, forms.ModelForm):
    cargo_base = forms.ModelChoiceField(
        label='Cargo',
        queryset=Cargo.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': ''}),
    )
    lotacao_base = forms.ModelChoiceField(
        label='Lotação',
        queryset=UnidadeLotacao.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': ''}),
    )

    class Meta:
        model = CoordenadorOperacional
        fields = ['nome', 'ativo', 'ordem']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cargo_base'].queryset = Cargo.objects.order_by('nome')
        self.fields['lotacao_base'].queryset = UnidadeLotacao.objects.order_by('nome')
        if self.instance and self.instance.pk:
            cargo_value = (self.instance.cargo or '').strip()
            lotacao_value = (self.instance.unidade or '').strip()
            if cargo_value:
                cargo_obj = Cargo.objects.filter(nome__iexact=cargo_value).first()
                if cargo_obj:
                    self.initial['cargo_base'] = cargo_obj.pk
            if lotacao_value:
                lotacao_obj = UnidadeLotacao.objects.filter(nome__iexact=lotacao_value).first()
                if lotacao_obj:
                    self.initial['lotacao_base'] = lotacao_obj.pk

    def clean_nome(self):
        value = ' '.join((self.cleaned_data.get('nome') or '').strip().upper().split())
        if not value:
            raise forms.ValidationError('Informe o nome completo do coordenador.')
        qs = CoordenadorOperacional.objects.filter(nome=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um coordenador com este nome.')
        return value

    def clean(self):
        cleaned_data = super().clean()
        cargo_obj = cleaned_data.get('cargo_base')
        lotacao_obj = cleaned_data.get('lotacao_base')
        if cargo_obj:
            cleaned_data['cargo'] = cargo_obj.nome
        if lotacao_obj:
            cleaned_data['unidade'] = lotacao_obj.nome
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.cargo = (self.cleaned_data.get('cargo') or '').strip()
        instance.unidade = (self.cleaned_data.get('unidade') or '').strip()
        instance.cidade = ''
        if commit:
            instance.save()
        return instance


class PlanoTrabalhoForm(FormComErroInvalidMixin, forms.ModelForm):
    OUTROS_CHOICE = '__OUTROS__'
    HORARIO_OUTROS = '__OUTROS__'

    atividades_codigos = forms.MultipleChoiceField(
        label='Atividades (PT)',
        choices=[(item['codigo'], item['nome']) for item in ATIVIDADES_CATALOGO],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    solicitante_escolha = forms.ChoiceField(
        label='Solicitante',
        required=False,
        widget=forms.Select(attrs={'class': ''}),
    )
    salvar_solicitante_outros = forms.BooleanField(
        label='Salvar este solicitante no gerenciador',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    horario_atendimento_padrao = forms.ChoiceField(
        label='Horário de atendimento',
        required=False,
        widget=forms.Select(attrs={'class': ''}),
    )
    horario_atendimento_manual = forms.CharField(
        label='Horário de atendimento (manual)',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    oficios_relacionados = forms.ModelMultipleChoiceField(
        label='Ofícios relacionados',
        queryset=Oficio.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': '', 'size': 6}),
    )
    destinos_payload = forms.CharField(required=False, widget=forms.HiddenInput())
    coordenadores_ids = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = PlanoTrabalho
        fields = [
            'data_criacao',
            'evento',
            'oficio',
            'roteiro',
            'solicitante_outros',
            'coordenador_operacional',
            'coordenador_administrativo',
            'destinos_json',
            'evento_data_unica',
            'evento_data_inicio',
            'evento_data_fim',
            'horario_atendimento',
            'quantidade_servidores',
            'metas_formatadas',
            'diarias_quantidade',
            'diarias_valor_total',
            'diarias_valor_unitario',
            'diarias_valor_extenso',
            'recursos_texto',
        ]
        widgets = {
            'data_criacao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'evento': forms.Select(attrs={'class': ''}),
            'oficio': forms.Select(attrs={'class': ''}),
            'roteiro': forms.Select(attrs={'class': ''}),
            'solicitante_outros': forms.TextInput(attrs={'class': 'form-control'}),
            'coordenador_operacional': forms.Select(attrs={'class': ''}),
            'coordenador_administrativo': forms.Select(attrs={'class': ''}),
            'destinos_json': forms.HiddenInput(),
            'evento_data_unica': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'evento_data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'evento_data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'horario_atendimento': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade_servidores': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'metas_formatadas': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'diarias_quantidade': forms.TextInput(attrs={'class': 'form-control'}),
            'diarias_valor_total': forms.TextInput(attrs={'class': 'form-control'}),
            'diarias_valor_unitario': forms.TextInput(attrs={'class': 'form-control'}),
            'diarias_valor_extenso': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'recursos_texto': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['evento'].required = False
        self.fields['oficio'].required = False
        self.fields['roteiro'].required = False
        self.fields['coordenador_operacional'].required = False
        self.fields['coordenador_administrativo'].required = False
        self.fields['quantidade_servidores'].required = False
        self.fields['evento_data_inicio'].required = False
        self.fields['evento_data_fim'].required = False
        self.fields['evento'].queryset = Evento.objects.order_by('-data_inicio', 'titulo')
        self.fields['oficio'].queryset = Oficio.objects.select_related('evento').order_by('-updated_at')
        self.fields['oficios_relacionados'].queryset = Oficio.objects.select_related('evento').order_by('-updated_at')
        self.fields['roteiro'].queryset = RoteiroEvento.objects.select_related('evento').order_by('-updated_at')
        self.fields['coordenador_operacional'].queryset = CoordenadorOperacional.objects.filter(ativo=True).order_by('ordem', 'nome')
        self.fields['coordenador_administrativo'].queryset = Viajante.objects.filter(
            status=Viajante.STATUS_FINALIZADO
        ).select_related('cargo', 'unidade_lotacao').order_by('nome')
        self.fields['metas_formatadas'].widget.attrs['readonly'] = True
        self.fields['recursos_texto'].widget.attrs['readonly'] = True
        self.fields['diarias_quantidade'].widget.attrs['readonly'] = True
        self.fields['diarias_valor_total'].widget.attrs['readonly'] = True
        self.fields['diarias_valor_unitario'].widget.attrs['readonly'] = True
        self.fields['diarias_valor_extenso'].widget.attrs['readonly'] = True

        self.initial.setdefault('data_criacao', timezone.localdate())
        config = ConfiguracaoSistema.objects.order_by('pk').first()
        if config and getattr(config, 'coordenador_adm_plano_trabalho_id', None):
            self.initial.setdefault('coordenador_administrativo', config.coordenador_adm_plano_trabalho_id)

        solicitantes = list(
            SolicitantePlanoTrabalho.objects.filter(ativo=True).order_by('ordem', 'nome').values_list('pk', 'nome')
        )
        self.fields['solicitante_escolha'].choices = [
            ('', 'Selecione...'),
            *[(str(pk), nome) for pk, nome in solicitantes],
            (self.OUTROS_CHOICE, 'Outros'),
        ]

        horarios = [
            ('', 'Selecione...'),
            ('08:00 até 12:00', '08:00 até 12:00'),
            ('13:00 até 17:00', '13:00 até 17:00'),
            ('08:00 até 17:00', '08:00 até 17:00'),
            ('08:00-12:00', '08:00-12:00 (legado)'),
            ('13:00-17:00', '13:00-17:00 (legado)'),
            ('08:00-17:00', '08:00-17:00 (legado)'),
            (self.HORARIO_OUTROS, 'Outro (informar manualmente)'),
        ]
        self.fields['horario_atendimento_padrao'].choices = horarios

        selected_event = None
        if self.is_bound:
            raw_event = (self.data.get('evento') or '').strip()
            if raw_event.isdigit():
                selected_event = Evento.objects.filter(pk=int(raw_event)).first()
        elif self.instance and self.instance.evento_id:
            selected_event = self.instance.evento
        elif self.initial.get('evento'):
            selected_event = Evento.objects.filter(pk=self.initial.get('evento')).first()

        if selected_event:
            self.fields['oficio'].queryset = Oficio.objects.filter(
                Q(evento=selected_event) | Q(evento__isnull=True)
            ).order_by('-updated_at')
            self.fields['oficios_relacionados'].queryset = Oficio.objects.filter(
                Q(evento=selected_event) | Q(evento__isnull=True)
            ).order_by('-updated_at')
            self.fields['roteiro'].queryset = RoteiroEvento.objects.filter(
                Q(evento=selected_event) | Q(evento__isnull=True)
            ).order_by('-updated_at')

        if self.instance and self.instance.pk:
            if self.instance.solicitante_id:
                self.initial['solicitante_escolha'] = str(self.instance.solicitante_id)
            elif self.instance.solicitante_outros:
                self.initial['solicitante_escolha'] = self.OUTROS_CHOICE

            horario_atual = (self.instance.horario_atendimento or '').strip()
            known = {value for value, _label in horarios}
            if horario_atual in known:
                self.initial['horario_atendimento_padrao'] = horario_atual
            elif horario_atual:
                self.initial['horario_atendimento_padrao'] = self.HORARIO_OUTROS
                self.initial['horario_atendimento_manual'] = horario_atual

            related_ids = list(self.instance.oficios.values_list('pk', flat=True))
            if not related_ids and self.instance.oficio_id:
                related_ids = [self.instance.oficio_id]
            self.initial['oficios_relacionados'] = related_ids
            self.initial['destinos_payload'] = json.dumps(self.instance.destinos_json or [])

            # Pre-populate coordenadores_ids from existing M2M
            coord_ids = list(self.instance.coordenadores.values_list('pk', flat=True))
            self.initial['coordenadores_ids'] = ','.join(str(pk) for pk in coord_ids)

        if self.instance and self.instance.pk and self.instance.atividades_codigos:
            self.initial['atividades_codigos'] = [
                codigo.strip()
                for codigo in self.instance.atividades_codigos.split(',')
                if codigo.strip()
            ]

        self.proximo_numero_preview = self._get_next_pt_number_preview()

    def _get_next_pt_number_preview(self):
        ano_atual = timezone.now().year
        with transaction.atomic():
            proximo = PlanoTrabalho.get_next_available_numero(ano_atual)
        return f'{proximo:02d}/{ano_atual}'

    def _build_markers_for_diarias(self, cleaned_data):
        roteiro = cleaned_data.get('roteiro')
        if roteiro:
            trechos = list(roteiro.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'))
            markers = []
            chegada_final = None
            for trecho in trechos:
                if trecho.saida_dt and trecho.destino_cidade_id:
                    markers.append(
                        PeriodMarker(
                            saida=trecho.saida_dt,
                            destino_cidade=trecho.destino_cidade.nome,
                            destino_uf=(trecho.destino_estado.sigla if trecho.destino_estado_id else ''),
                        )
                    )
                if trecho.chegada_dt and (not chegada_final or trecho.chegada_dt > chegada_final):
                    chegada_final = trecho.chegada_dt
            if markers and chegada_final:
                return markers, chegada_final

        oficios = list(cleaned_data.get('oficios_relacionados') or [])
        if not oficios and cleaned_data.get('oficio'):
            oficios = [cleaned_data.get('oficio')]
        for oficio in oficios:
            trechos = list(oficio.trechos.select_related('destino_cidade', 'destino_estado').order_by('ordem', 'pk'))
            if not trechos:
                continue
            markers = []
            for trecho in trechos:
                if not trecho.saida_data or not trecho.saida_hora:
                    markers = []
                    break
                if not trecho.destino_cidade_id:
                    continue
                markers.append(
                    PeriodMarker(
                        saida=datetime.combine(trecho.saida_data, trecho.saida_hora),
                        destino_cidade=trecho.destino_cidade.nome,
                        destino_uf=(trecho.destino_estado.sigla if trecho.destino_estado_id else ''),
                    )
                )
            if not markers:
                continue
            if oficio.retorno_chegada_data and oficio.retorno_chegada_hora:
                return markers, datetime.combine(oficio.retorno_chegada_data, oficio.retorno_chegada_hora)
        return [], None

    def _parse_destinos_payload(self, payload_text):
        payload = []
        if not payload_text:
            return payload
        try:
            raw = json.loads(payload_text)
        except (TypeError, ValueError):
            raise forms.ValidationError('Destinos inválidos. Atualize a tela e tente novamente.')
        if not isinstance(raw, list):
            raise forms.ValidationError('Destinos inválidos. Atualize a tela e tente novamente.')

        cidade_ids = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            cidade_id = item.get('cidade_id')
            if isinstance(cidade_id, str) and cidade_id.isdigit():
                cidade_id = int(cidade_id)
            if isinstance(cidade_id, int) and cidade_id > 0:
                cidade_ids.append(cidade_id)
        cidades_map = {
            cidade.pk: cidade
            for cidade in Cidade.objects.select_related('estado').filter(pk__in=set(cidade_ids), ativo=True)
        }

        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            cidade_id = item.get('cidade_id')
            if isinstance(cidade_id, str) and cidade_id.isdigit():
                cidade_id = int(cidade_id)
            if not isinstance(cidade_id, int):
                continue
            cidade = cidades_map.get(cidade_id)
            if not cidade or cidade_id in seen:
                continue
            seen.add(cidade_id)
            payload.append(
                {
                    'estado_id': cidade.estado_id,
                    'estado_sigla': cidade.estado.sigla,
                    'cidade_id': cidade.pk,
                    'cidade_nome': cidade.nome,
                }
            )
        return payload

    def clean(self):
        cleaned_data = super().clean()

        escolha = (cleaned_data.get('solicitante_escolha') or '').strip()
        solicitante_outros = (cleaned_data.get('solicitante_outros') or '').strip()
        if escolha == self.OUTROS_CHOICE and not solicitante_outros:
            self.add_error('solicitante_outros', 'Informe o solicitante quando selecionar "Outros".')

        horario_padrao = (cleaned_data.get('horario_atendimento_padrao') or '').strip()
        horario_manual = (cleaned_data.get('horario_atendimento_manual') or '').strip()
        if horario_padrao == self.HORARIO_OUTROS:
            if not horario_manual:
                self.add_error('horario_atendimento_manual', 'Informe o horário manual.')
            horario_value = horario_manual
        else:
            horario_value = horario_padrao

        normalized_horario = horario_value
        if horario_value:
            if re.match(r'^\d{2}:\d{2}\s*-\s*\d{2}:\d{2}$', horario_value):
                parts = [p.strip() for p in horario_value.split('-', 1)]
                normalized_horario = f'{parts[0]} até {parts[1]}'
            elif re.match(r'^das\s+\d{1,2}h\s+às\s+\d{1,2}h$', horario_value, flags=re.IGNORECASE):
                hh = re.findall(r'\d{1,2}', horario_value)
                if len(hh) == 2:
                    normalized_horario = f'{int(hh[0]):02d}:00 até {int(hh[1]):02d}:00'
            if not re.match(r'^\d{2}:\d{2}\s+até\s+\d{2}:\d{2}$', normalized_horario):
                self.add_error('horario_atendimento_manual', 'Use o formato 00:00 até 00:00.')
        cleaned_data['horario_atendimento'] = normalized_horario

        evento = cleaned_data.get('evento')
        oficio = cleaned_data.get('oficio')
        roteiro = cleaned_data.get('roteiro')
        oficios_relacionados = list(cleaned_data.get('oficios_relacionados') or [])
        if oficio and oficio not in oficios_relacionados:
            oficios_relacionados.append(oficio)
        cleaned_data['oficios_relacionados'] = oficios_relacionados

        eventos_relacionados = {}
        for of in oficios_relacionados:
            if of.evento_id:
                eventos_relacionados[of.evento_id] = of.evento
        if len(eventos_relacionados) > 1:
            self.add_error(
                'oficios_relacionados',
                'Os ofícios relacionados precisam pertencer ao mesmo evento documental.',
            )
        evento_inferido = next(iter(eventos_relacionados.values()), None)
        if evento and evento_inferido and evento.pk != evento_inferido.pk:
            self.add_error('evento', 'O evento selecionado não corresponde aos ofícios relacionados.')
        elif not evento and evento_inferido:
            evento = evento_inferido
            cleaned_data['evento'] = evento

        if evento and roteiro and roteiro.evento_id and roteiro.evento_id != evento.pk:
            self.add_error('roteiro', 'O roteiro selecionado pertence a outro evento.')

        for of in oficios_relacionados:
            if evento and of.evento_id and of.evento_id != evento.pk:
                self.add_error('oficios_relacionados', 'Um dos ofícios selecionados pertence a outro evento.')
                break

        coord_adm = cleaned_data.get('coordenador_administrativo')
        if not coord_adm:
            config = ConfiguracaoSistema.objects.order_by('pk').first()
            coord_cfg = getattr(config, 'coordenador_adm_plano_trabalho', None) if config else None
            if coord_cfg:
                cleaned_data['coordenador_administrativo'] = coord_cfg

        destinos = []
        try:
            destinos = self._parse_destinos_payload((cleaned_data.get('destinos_payload') or '').strip())
        except forms.ValidationError as exc:
            self.add_error('destinos_payload', exc)

        if not destinos:
            if roteiro:
                destinos = [
                    {
                        'estado_id': d.estado_id,
                        'estado_sigla': (d.estado.sigla if d.estado_id else ''),
                        'cidade_id': d.cidade_id,
                        'cidade_nome': (d.cidade.nome if d.cidade_id else ''),
                    }
                    for d in roteiro.destinos.select_related('cidade', 'estado').order_by('ordem')
                ]
            elif evento:
                destinos = [
                    {
                        'estado_id': d.estado_id,
                        'estado_sigla': (d.estado.sigla if d.estado_id else ''),
                        'cidade_id': d.cidade_id,
                        'cidade_nome': (d.cidade.nome if d.cidade_id else ''),
                    }
                    for d in evento.destinos.select_related('cidade', 'estado').order_by('ordem')
                ]

        if not destinos and not (evento or roteiro or oficios_relacionados):
            self.add_error('destinos_payload', 'Adicione ao menos um destino manual quando não houver vínculo.')

        cleaned_data['destinos_json'] = destinos

        data_unica = bool(cleaned_data.get('evento_data_unica'))
        data_inicio = cleaned_data.get('evento_data_inicio')
        data_fim = cleaned_data.get('evento_data_fim')
        if not data_inicio:
            if evento and evento.data_inicio:
                data_inicio = evento.data_inicio
            elif roteiro and roteiro.saida_dt:
                data_inicio = roteiro.saida_dt.date()
        if not data_fim:
            if evento and evento.data_fim:
                data_fim = evento.data_fim
            elif roteiro and roteiro.chegada_dt:
                data_fim = roteiro.chegada_dt.date()
        if not data_inicio and not (evento or roteiro or oficios_relacionados):
            self.add_error('evento_data_inicio', 'Informe a data inicial do evento.')
        if data_unica and data_inicio:
            data_fim = data_inicio
        elif data_inicio and data_fim and data_fim < data_inicio:
            self.add_error('evento_data_fim', 'A data final não pode ser anterior à inicial.')
        cleaned_data['evento_data_inicio'] = data_inicio
        cleaned_data['evento_data_fim'] = data_fim

        qtd = cleaned_data.get('quantidade_servidores') or 1
        markers, chegada_final = self._build_markers_for_diarias(cleaned_data)
        if markers and chegada_final:
            try:
                result = calculate_periodized_diarias(markers, chegada_final, quantidade_servidores=int(qtd))
                totais = (result or {}).get('totais') or {}
                cleaned_data['diarias_quantidade'] = totais.get('total_diarias', '') or ''
                cleaned_data['diarias_valor_total'] = totais.get('total_valor', '') or ''
                cleaned_data['diarias_valor_unitario'] = totais.get('valor_por_servidor', '') or ''
                cleaned_data['diarias_valor_extenso'] = totais.get('valor_extenso', '') or ''
            except Exception:
                cleaned_data['diarias_quantidade'] = ''
                cleaned_data['diarias_valor_total'] = ''
                cleaned_data['diarias_valor_unitario'] = ''
                cleaned_data['diarias_valor_extenso'] = ''
        else:
            cleaned_data['diarias_quantidade'] = ''
            cleaned_data['diarias_valor_total'] = ''
            cleaned_data['diarias_valor_unitario'] = ''
            cleaned_data['diarias_valor_extenso'] = ''

        codigos = cleaned_data.get('atividades_codigos', [])
        cleaned_data['metas_formatadas'] = build_metas_formatada(','.join(codigos) if codigos else '')
        cleaned_data['recursos_texto'] = build_recursos_necessarios_formatado(','.join(codigos) if codigos else '')
        return cleaned_data

    def _assign_auto_number(self, instance):
        if instance.numero and instance.ano:
            return
        ano_atual = timezone.now().year
        with transaction.atomic():
            instance.numero = PlanoTrabalho.get_next_available_numero(ano_atual)
            instance.ano = ano_atual

    def save(self, commit=True):
        instance = super().save(commit=False)
        escolha = (self.cleaned_data.get('solicitante_escolha') or '').strip()
        instance.solicitante = None
        if escolha and escolha != self.OUTROS_CHOICE and escolha.isdigit():
            instance.solicitante_id = int(escolha)
            instance.solicitante_outros = ''
        elif escolha == self.OUTROS_CHOICE:
            instance.solicitante_outros = (self.cleaned_data.get('solicitante_outros') or '').strip()
            if instance.solicitante_outros and self.cleaned_data.get('salvar_solicitante_outros'):
                solicitante_obj, _ = SolicitantePlanoTrabalho.objects.get_or_create(
                    nome=instance.solicitante_outros,
                    defaults={'ativo': True},
                )
                instance.solicitante = solicitante_obj
                instance.solicitante_outros = ''

        instance.horario_atendimento = (self.cleaned_data.get('horario_atendimento') or '').strip()
        codigos = self.cleaned_data.get('atividades_codigos', [])
        instance.atividades_codigos = ','.join(codigos) if codigos else ''
        instance.metas_formatadas = self.cleaned_data.get('metas_formatadas') or ''
        instance.recursos_texto = self.cleaned_data.get('recursos_texto') or ''
        instance.destinos_json = self.cleaned_data.get('destinos_json') or []
        instance.diarias_quantidade = self.cleaned_data.get('diarias_quantidade') or ''
        instance.diarias_valor_total = self.cleaned_data.get('diarias_valor_total') or ''
        instance.diarias_valor_unitario = self.cleaned_data.get('diarias_valor_unitario') or ''
        instance.diarias_valor_extenso = self.cleaned_data.get('diarias_valor_extenso') or ''
        instance.coordenador_municipal = ''
        instance.observacoes = ''
        instance.status = PlanoTrabalho.STATUS_RASCUNHO

        related_oficios = list(self.cleaned_data.get('oficios_relacionados') or [])
        if instance.oficio_id and instance.oficio not in related_oficios:
            related_oficios.append(instance.oficio)
        if not instance.evento_id:
            related_event_ids = {oficio.evento_id for oficio in related_oficios if oficio.evento_id}
            if len(related_event_ids) == 1:
                instance.evento_id = next(iter(related_event_ids))
        if related_oficios and not instance.oficio_id:
            instance.oficio = related_oficios[0]
        # Parse coordenadores ids from hidden field
        coordenadores_ids_raw = (self.cleaned_data.get('coordenadores_ids') or '').strip()
        coordenadores_ids = []
        if coordenadores_ids_raw:
            for part in coordenadores_ids_raw.split(','):
                part = part.strip()
                if part.isdigit():
                    coordenadores_ids.append(int(part))

        if commit:
            self._assign_auto_number(instance)
            instance.save()
            instance.oficios.set(related_oficios)
            if coordenadores_ids is not None:
                from .models import CoordenadorOperacional as _CO
                instance.coordenadores.set(_CO.objects.filter(pk__in=coordenadores_ids, ativo=True))
        else:
            self._pending_oficios = related_oficios
            self._pending_coordenadores_ids = coordenadores_ids
        return instance


class OrdemServicoForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = [
            'numero',
            'ano',
            'data_criacao',
            'status',
            'evento',
            'oficio',
            'finalidade',
            'responsaveis',
            'designacoes',
            'determinacoes',
            'observacoes',
        ]
        widgets = {
            'numero': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'ano': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
            'data_criacao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': ''}),
            'evento': forms.Select(attrs={'class': ''}),
            'oficio': forms.Select(attrs={'class': ''}),
            'finalidade': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'responsaveis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'designacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'determinacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['evento'].required = False
        self.fields['oficio'].required = False
        self.fields['numero'].required = False
        self.fields['ano'].required = False
        self.fields['evento'].queryset = Evento.objects.order_by('-data_inicio', 'titulo')
        self.fields['oficio'].queryset = Oficio.objects.select_related('evento').order_by('-updated_at')


def _parse_hidden_ids(raw_value):
    ids = []
    seen = set()
    for item in str(raw_value or '').split(','):
        value = item.strip()
        if not value.isdigit() or value in seen:
            continue
        seen.add(value)
        ids.append(int(value))
    return ids


class TermoAutorizacaoForm(FormComErroInvalidMixin, forms.ModelForm):
    oficios = forms.ModelMultipleChoiceField(
        queryset=Oficio.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                'class': '',
                'size': 6,
                'data-preview-source': 'oficios',
            }
        ),
    )
    viajantes_ids = forms.CharField(required=False, widget=forms.HiddenInput())
    veiculo_id = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = TermoAutorizacao
        fields = [
            'evento',
            'roteiro',
            'destino',
            'data_evento',
            'data_evento_fim',
        ]
        widgets = {
            'evento': forms.Select(attrs={'class': '', 'data-preview-source': 'evento'}),
            'roteiro': forms.Select(attrs={'class': '', 'data-preview-source': 'roteiro'}),
            'destino': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Curitiba/PR, Londrina/PR...'}),
            'data_evento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_evento_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cleaned_viajantes = []
        self.cleaned_veiculo = None
        self.cleaned_oficios = []
        self.context_data = build_termo_context()
        self.preview_payload = build_termo_preview_payload(self.context_data)
        self.fields['evento'].required = False
        self.fields['roteiro'].required = False
        self.fields['data_evento_fim'].required = False
        self.fields['evento'].queryset = Evento.objects.order_by('-data_inicio', 'titulo')
        self.fields['roteiro'].queryset = RoteiroEvento.objects.select_related('evento').order_by('-updated_at')
        self.fields['oficios'].queryset = (
            Oficio.objects.select_related('evento', 'roteiro_evento', 'veiculo')
            .prefetch_related('viajantes', 'trechos__destino_cidade', 'trechos__destino_estado')
            .order_by('-updated_at')
        )

    def _resolve_viajantes(self, raw_ids):
        viajantes_ids = _parse_hidden_ids(raw_ids)
        queryset = list(
            Viajante.objects.select_related('cargo', 'unidade_lotacao').filter(
                status=Viajante.STATUS_FINALIZADO,
                pk__in=viajantes_ids,
            )
        )
        viajantes_map = {viajante.pk: viajante for viajante in queryset}
        return [viajantes_map[pk] for pk in viajantes_ids if pk in viajantes_map]

    def _resolve_veiculo(self, raw_id):
        veiculo_id = str(raw_id or '').strip()
        if not veiculo_id.isdigit():
            return None
        return Veiculo.objects.select_related('combustivel').filter(
            status=Veiculo.STATUS_FINALIZADO,
            pk=int(veiculo_id),
        ).first()

    def clean(self):
        data = super().clean()
        self.cleaned_oficios = list(data.get('oficios') or [])
        evento = data.get('evento')
        roteiro = data.get('roteiro')
        self.context_data = build_termo_context(
            evento=evento,
            oficios=self.cleaned_oficios,
            roteiro=roteiro,
        )

        if evento:
            conflitos = [
                oficio.numero_formatado or f'#{oficio.pk}'
                for oficio in self.cleaned_oficios
                if oficio.evento_id and oficio.evento_id != evento.pk
            ]
            if conflitos:
                self.add_error(
                    'oficios',
                    f'Os oficios {", ".join(conflitos)} pertencem a outro evento.',
                )
        if evento and roteiro and roteiro.evento_id and roteiro.evento_id != evento.pk:
            self.add_error('roteiro', 'O roteiro selecionado pertence a outro evento.')

        if not data.get('evento') and self.context_data['evento']:
            data['evento'] = self.context_data['evento']
        if not data.get('roteiro') and self.context_data['roteiro']:
            data['roteiro'] = self.context_data['roteiro']
        if not data.get('destino') and self.context_data['destino']:
            data['destino'] = self.context_data['destino']
        if not data.get('data_evento') and self.context_data['data_evento']:
            data['data_evento'] = self.context_data['data_evento']
        if not data.get('data_evento_fim') and self.context_data['data_evento_fim']:
            data['data_evento_fim'] = self.context_data['data_evento_fim']

        self.cleaned_viajantes = self._resolve_viajantes(data.get('viajantes_ids'))
        if not self.cleaned_viajantes:
            self.cleaned_viajantes = list(self.context_data['viajantes'])
        self.cleaned_veiculo = self._resolve_veiculo(data.get('veiculo_id'))
        if not self.cleaned_veiculo and self.context_data['veiculo_inferido']:
            self.cleaned_veiculo = self.context_data['veiculo_inferido']

        if not data.get('destino'):
            self.add_error('destino', 'Informe o destino do termo.')
        if not data.get('data_evento'):
            self.add_error('data_evento', 'Informe a data do termo.')
        if data.get('data_evento') and data.get('data_evento_fim') and data['data_evento_fim'] < data['data_evento']:
            self.add_error('data_evento_fim', 'A data final nao pode ser anterior a data inicial.')

        self.preview_payload = build_termo_preview_payload(
            self.context_data,
            viajantes=self.cleaned_viajantes,
            veiculo=self.cleaned_veiculo,
        )
        return data

    def save_terms(self, *, user=None):
        cleaned = self.cleaned_data
        oficio_legacy = self.cleaned_oficios[0] if len(self.cleaned_oficios) == 1 else None
        common_kwargs = {
            'evento': cleaned.get('evento') or self.context_data['evento'],
            'roteiro': cleaned.get('roteiro') or self.context_data['roteiro'],
            'oficio': oficio_legacy,
            'destino': cleaned.get('destino') or self.context_data['destino'],
            'data_evento': cleaned.get('data_evento') or self.context_data['data_evento'],
            'data_evento_fim': cleaned.get('data_evento_fim') or self.context_data['data_evento_fim'],
            'criado_por': user,
            'veiculo': self.cleaned_veiculo,
        }
        modo = self.preview_payload['modo_geracao']
        lote_uuid = uuid.uuid4() if modo != TermoAutorizacao.MODO_RAPIDO else None
        termos = []

        if modo == TermoAutorizacao.MODO_RAPIDO:
            termo = TermoAutorizacao(**common_kwargs)
            termo.full_clean()
            termo.save()
            if self.cleaned_oficios:
                termo.oficios.set(self.cleaned_oficios)
            return [termo]

        for viajante in self.cleaned_viajantes:
            termo = TermoAutorizacao(
                **common_kwargs,
                viajante=viajante,
                lote_uuid=lote_uuid,
            )
            termo.full_clean()
            termo.save()
            if self.cleaned_oficios:
                termo.oficios.set(self.cleaned_oficios)
            termos.append(termo)
        return termos


class TermoAutorizacaoEdicaoForm(FormComErroInvalidMixin, forms.ModelForm):
    oficios = forms.ModelMultipleChoiceField(
        queryset=Oficio.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': '', 'size': 6}),
    )

    class Meta:
        model = TermoAutorizacao
        fields = [
            'evento',
            'roteiro',
            'destino',
            'data_evento',
            'data_evento_fim',
        ]
        widgets = {
            'evento': forms.Select(attrs={'class': ''}),
            'roteiro': forms.Select(attrs={'class': ''}),
            'destino': forms.TextInput(attrs={'class': 'form-control'}),
            'data_evento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_evento_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['evento'].required = False
        self.fields['roteiro'].required = False
        self.fields['data_evento_fim'].required = False
        self.fields['evento'].queryset = Evento.objects.order_by('-data_inicio', 'titulo')
        self.fields['roteiro'].queryset = RoteiroEvento.objects.select_related('evento').order_by('-updated_at')
        self.fields['oficios'].queryset = (
            Oficio.objects.select_related('evento', 'veiculo', 'roteiro_evento')
            .prefetch_related('viajantes', 'trechos__destino_cidade', 'trechos__destino_estado')
            .order_by('-updated_at')
        )
        initial_oficios = list(self.instance.oficios.all())
        if not initial_oficios and self.instance.oficio_id:
            initial_oficios = [self.instance.oficio]
        self.initial.setdefault('oficios', [oficio.pk for oficio in initial_oficios])

    def clean(self):
        data = super().clean()
        if not data.get('destino'):
            self.add_error('destino', 'Informe o destino do termo.')
        if not data.get('data_evento'):
            self.add_error('data_evento', 'Informe a data do termo.')
        if data.get('data_evento') and data.get('data_evento_fim') and data['data_evento_fim'] < data['data_evento']:
            self.add_error('data_evento_fim', 'A data final nao pode ser anterior a data inicial.')
        return data

    def save(self, commit=True):
        instance = super().save(commit=False)
        oficios = list(self.cleaned_data.get('oficios') or [])
        instance.oficio = oficios[0] if len(oficios) == 1 else None
        if commit:
            instance.full_clean()
            instance.save()
            instance.oficios.set(oficios)
        return instance

class TipoDemandaEventoForm(FormComErroInvalidMixin, forms.ModelForm):
    """CRUD de tipos de demanda para eventos."""
    class Meta:
        model = TipoDemandaEvento
        fields = ['nome', 'descricao_padrao', 'ordem', 'ativo', 'is_outros']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 120}),
            'descricao_padrao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ordem': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_outros': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ModeloMotivoViagemForm(FormComErroInvalidMixin, forms.ModelForm):
    """CRUD simples de modelos de motivo da viagem (Step 1 do Ofício)."""

    class Meta:
        model = ModeloMotivoViagem
        fields = ['nome', 'texto']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'texto': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        }


class ModeloJustificativaForm(FormComErroInvalidMixin, forms.ModelForm):
    """CRUD simples de modelos de justificativa do ofício."""

    class Meta:
        model = ModeloJustificativa
        fields = ['nome', 'texto']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'texto': forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
        }


class OficioJustificativaForm(FormComErroInvalidMixin, forms.Form):
    """Tela própria da justificativa do ofício."""

    modelo_justificativa = forms.ModelChoiceField(
        queryset=ModeloJustificativa.objects.none(),
        required=False,
        label='Modelo de justificativa',
        empty_label='---------',
        widget=forms.Select(attrs={'class': ''}),
    )
    justificativa_texto = forms.CharField(
        required=False,
        label='Texto final da justificativa',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
    )

    def __init__(self, *args, **kwargs):
        self.oficio = kwargs.pop('oficio')
        super().__init__(*args, **kwargs)
        if not oficio_justificativa_schema_available():
            self.fields['modelo_justificativa'].queryset = ModeloJustificativa.objects.none()
            return
        justificativa = get_oficio_justificativa(self.oficio)
        justificativa_modelo_id = getattr(justificativa, 'modelo_id', None)
        queryset = ModeloJustificativa.objects.filter(
            Q(ativo=True) | Q(pk=justificativa_modelo_id)
        ).order_by('nome').distinct()
        self.fields['modelo_justificativa'].queryset = queryset
        if self.is_bound:
            return

        modelo_inicial = getattr(justificativa, 'modelo', None)
        if not modelo_inicial:
            modelo_inicial = queryset.filter(padrao=True).first()
        if modelo_inicial:
            self.initial.setdefault('modelo_justificativa', modelo_inicial.pk)
        justificativa_texto = get_oficio_justificativa_texto(self.oficio)
        if justificativa_texto:
            self.initial.setdefault('justificativa_texto', justificativa_texto)
        elif modelo_inicial:
            self.initial.setdefault('justificativa_texto', modelo_inicial.texto)

    def clean_justificativa_texto(self):
        return (self.cleaned_data.get('justificativa_texto') or '').strip()

    def clean(self):
        data = super().clean()
        modelo = data.get('modelo_justificativa')
        texto = (data.get('justificativa_texto') or '').strip()
        if modelo and not texto:
            data['justificativa_texto'] = (modelo.texto or '').strip()
        return data


class JustificativaForm(FormComErroInvalidMixin, forms.ModelForm):
    """Formulário independente de Justificativa — com seletor de Ofício."""

    class Meta:
        model = Justificativa
        fields = ['oficio', 'modelo', 'texto']
        widgets = {
            'oficio': forms.Select(attrs={'class': ''}),
            'modelo': forms.Select(attrs={'class': ''}),
            'texto': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }

    def __init__(self, *args, **kwargs):
        preselected_oficio = kwargs.pop('preselected_oficio', None)
        super().__init__(*args, **kwargs)
        self.fields['oficio'].queryset = Oficio.objects.select_related('evento').order_by('-updated_at')
        self.fields['modelo'].required = False
        self.fields['texto'].required = False
        self.fields['modelo'].queryset = ModeloJustificativa.objects.filter(ativo=True).order_by('nome')
        if preselected_oficio and not self.instance.pk:
            self.initial.setdefault('oficio', preselected_oficio.pk)
        elif not self.instance.pk and not self.initial.get('oficio'):
            # Pre-fill from modelo padrão when available
            modelo_padrao = ModeloJustificativa.objects.filter(ativo=True, padrao=True).first()
            if modelo_padrao:
                self.initial.setdefault('modelo', modelo_padrao.pk)
                self.initial.setdefault('texto', modelo_padrao.texto)

    def clean_oficio(self):
        oficio = self.cleaned_data.get('oficio')
        if not oficio:
            raise forms.ValidationError('Selecione o ofício vinculado.')
        if not self.instance.pk:
            if Justificativa.objects.filter(oficio=oficio).exists():
                raise forms.ValidationError(
                    f'Já existe uma justificativa para o ofício {oficio.numero_formatado}. '
                    'Use a opção de editar a existente.'
                )
        return oficio

    def clean(self):
        data = super().clean()
        modelo = data.get('modelo')
        texto = (data.get('texto') or '').strip()
        if modelo and not texto:
            data['texto'] = (modelo.texto or '').strip()
        return data


class RoteiroEventoForm(FormComErroInvalidMixin, forms.ModelForm):
    """Formulário do roteiro (Etapa 2). Sede + destinos dinâmicos. Duração por trecho (cru + adicional + total)."""

    class Meta:
        model = RoteiroEvento
        fields = [
            'origem_estado', 'origem_cidade',
            'saida_dt',
            'retorno_saida_dt',
            'observacoes',
        ]
        widgets = {
            'origem_estado': forms.Select(attrs={'class': ''}),
            'origem_cidade': forms.Select(attrs={'class': ''}),
            'saida_dt': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'retorno_saida_dt': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['saida_dt'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d']
        self.fields['retorno_saida_dt'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d']

    def clean_observacoes(self):
        val = self.cleaned_data.get('observacoes') or ''
        return val.strip().upper()

    def clean(self):
        data = super().clean()
        o_estado = data.get('origem_estado')
        o_cidade = data.get('origem_cidade')
        if o_estado and o_cidade and o_cidade.estado_id != o_estado.id:
            self.add_error('origem_cidade', 'A cidade sede deve pertencer ao estado selecionado.')
        return data


class EventoEtapa3Form(FormComErroInvalidMixin, forms.Form):
    """Etapa 3 — Composição da viagem: veículo, motorista, participantes (apenas finalizados)."""
    veiculo = forms.ModelChoiceField(
        queryset=Veiculo.objects.none(),
        required=True,
        empty_label='---------',
        label='Veículo',
        widget=forms.Select(attrs={'class': ''}),
    )
    motorista = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=True,
        empty_label='---------',
        label='Motorista',
        widget=forms.Select(attrs={'class': ''}),
    )
    viajantes_participantes = forms.ModelMultipleChoiceField(
        queryset=Viajante.objects.none(),
        required=True,
        label='Viajantes participantes',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    observacoes_operacionais = forms.CharField(
        required=False,
        label='Observações operacionais',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs_v = Veiculo.objects.filter(status=Veiculo.STATUS_FINALIZADO).order_by('placa', 'modelo')
        qs_p = Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).order_by('nome')
        self.fields['veiculo'].queryset = qs_v
        self.fields['motorista'].queryset = qs_p
        self.fields['viajantes_participantes'].queryset = qs_p

    def clean(self):
        data = super().clean()
        participantes = list(data.get('viajantes_participantes') or [])
        motorista = data.get('motorista')
        if participantes and motorista and motorista not in participantes:
            self.add_error('motorista', 'O motorista deve ser um dos viajantes participantes selecionados.')
        if not participantes:
            self.add_error('viajantes_participantes', 'Selecione pelo menos um viajante participante.')
        return data


# ---------- Wizard do Ofício (legado) ----------


class OficioStep1Form(FormComErroInvalidMixin, forms.Form):
    """Step 1 — Dados gerais + viajantes com regras legadas de protocolo/custeio."""

    oficio_numero = forms.CharField(
        required=False,
        label='Ofício',
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
    )
    protocolo = forms.CharField(
        required=True,
        max_length=12,
        label='Protocolo',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'data-mask': 'protocolo',
                'inputmode': 'numeric',
                'maxlength': 12,
                'placeholder': '12.345.678-9',
                'autocomplete': 'off',
            }
        ),
    )
    data_criacao = forms.DateField(
        required=False,
        label='Data de criação',
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
    )
    modelo_motivo = forms.ModelChoiceField(
        queryset=ModeloMotivoViagem.objects.none(),
        required=False,
        label='Modelo de motivo',
        empty_label='---------',
        widget=forms.Select(attrs={'class': ''}),
    )
    motivo = forms.CharField(
        required=False,
        label='Motivo da viagem',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
    )
    custeio_tipo = forms.ChoiceField(
        required=True,
        choices=Oficio.CUSTEIO_CHOICES,
        label='Custeio',
        widget=forms.Select(attrs={'class': ''}),
    )
    nome_instituicao_custeio = forms.CharField(
        required=False, max_length=200, label='Nome instituição de custeio',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    viajantes = forms.ModelMultipleChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        label='Viajantes',
        widget=forms.MultipleHiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        selected_viajantes_ids = kwargs.pop('selected_viajantes_ids', None) or []
        super().__init__(*args, **kwargs)
        self.fields['modelo_motivo'].queryset = ModeloMotivoViagem.objects.all().order_by('nome')
        selected_ids = []
        for raw_value in selected_viajantes_ids:
            value = str(raw_value).strip()
            if value.isdigit():
                selected_ids.append(int(value))
        viajantes_qs = Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO)
        if selected_ids:
            viajantes_qs = Viajante.objects.filter(
                Q(status=Viajante.STATUS_FINALIZADO) | Q(pk__in=selected_ids)
            )
        self.fields['viajantes'].queryset = viajantes_qs.select_related('cargo').distinct().order_by('nome')
        if not self.initial.get('custeio_tipo'):
            self.initial['custeio_tipo'] = Oficio.CUSTEIO_UNIDADE
        custeio_value = (
            self.data.get('custeio_tipo')
            if self.is_bound
            else (self.initial.get('custeio_tipo') or Oficio.CUSTEIO_UNIDADE)
        )
        if custeio_value != Oficio.CUSTEIO_OUTRA_INSTITUICAO:
            self.fields['nome_instituicao_custeio'].widget.attrs['disabled'] = 'disabled'
        else:
            self.fields['nome_instituicao_custeio'].widget.attrs.pop('disabled', None)
        data_val = self.initial.get('data_criacao')
        if data_val and hasattr(data_val, 'strftime'):
            self.initial['data_criacao'] = data_val.strftime('%d/%m/%Y')
        protocolo = self.initial.get('protocolo')
        if protocolo and not self.is_bound:
            self.initial['protocolo'] = format_protocolo(protocolo)
        if self.initial.get('oficio_numero'):
            self.fields['oficio_numero'].widget.attrs['readonly'] = 'readonly'

    def clean_protocolo(self):
        protocolo = normalize_protocolo(self.cleaned_data.get('protocolo'))
        if len(protocolo) != 9:
            raise forms.ValidationError('Informe o protocolo no formato XX.XXX.XXX-X.')
        return protocolo

    def clean(self):
        data = super().clean()
        viajantes = list(data.get('viajantes') or [])
        if not viajantes:
            self.add_error('viajantes', 'Selecione ao menos um viajante.')
        custeio = data.get('custeio_tipo') or Oficio.CUSTEIO_UNIDADE
        nome_instituicao = (data.get('nome_instituicao_custeio') or '').strip()
        if custeio == Oficio.CUSTEIO_OUTRA_INSTITUICAO and not nome_instituicao:
            self.add_error('nome_instituicao_custeio', 'Informe a instituição de custeio.')
        if custeio != Oficio.CUSTEIO_OUTRA_INSTITUICAO:
            data['nome_instituicao_custeio'] = ''
        modelo = data.get('modelo_motivo')
        motivo = (data.get('motivo') or '').strip()
        if modelo and not motivo:
            data['motivo'] = modelo.texto
        if not data.get('data_criacao'):
            from django.utils import timezone
            data['data_criacao'] = timezone.localdate()
        return data


class LegacyOficioStep2Form(FormComErroInvalidMixin, forms.Form):
    """Step 2 — Transporte. Regras: placa, modelo e combustível obrigatórios; motorista carona exige ofício e protocolo."""
    placa = forms.CharField(required=False, max_length=10, label='Placa', widget=forms.TextInput(attrs={'class': 'form-control'}))
    modelo = forms.CharField(required=False, max_length=120, label='Modelo', widget=forms.TextInput(attrs={'class': 'form-control'}))
    combustivel = forms.CharField(required=False, max_length=80, label='Combustível', widget=forms.TextInput(attrs={'class': 'form-control'}))
    tipo_viatura = forms.ChoiceField(
        required=False,
        choices=[('', '---------')] + list(Oficio.TIPO_VIATURA_CHOICES),
        label='Tipo viatura',
        widget=forms.Select(attrs={'class': ''}),
    )
    motorista_viajante = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        empty_label='---------',
        label='Motorista (viajante)',
        widget=forms.Select(attrs={'class': ''}),
    )
    motorista_nome = forms.CharField(
        required=False, max_length=120, label='Motorista (nome manual)',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    motorista_carona = forms.BooleanField(required=False, initial=False, label='Motorista carona', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    motorista_oficio_numero = forms.IntegerField(required=False, min_value=1, label='Nº ofício motorista', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    motorista_oficio_ano = forms.IntegerField(required=False, min_value=2000, max_value=2100, label='Ano ofício motorista', widget=forms.NumberInput(attrs={'class': 'form-control'}))
    motorista_protocolo = forms.CharField(
        required=False,
        max_length=12,
        label='Protocolo motorista',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'data-mask': 'protocolo',
                'inputmode': 'numeric',
                'maxlength': 12,
                'placeholder': '12.345.678-9',
                'autocomplete': 'off',
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['motorista_viajante'].queryset = Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).order_by('nome')
        if not self.initial.get('tipo_viatura'):
            self.initial['tipo_viatura'] = Oficio.TIPO_VIATURA_DESCARACTERIZADA
        protocolo = self.initial.get('motorista_protocolo')
        if protocolo and not self.is_bound:
            self.initial['motorista_protocolo'] = format_protocolo(protocolo)

    def clean_motorista_protocolo(self):
        protocolo = normalize_protocolo(self.cleaned_data.get('motorista_protocolo'))
        if protocolo and len(protocolo) != 9:
            raise forms.ValidationError('Informe o protocolo do motorista no formato XX.XXX.XXX-X.')
        return protocolo

    def clean(self):
        data = super().clean()
        placa = (data.get('placa') or '').strip()
        modelo = (data.get('modelo') or '').strip()
        combustivel = (data.get('combustivel') or '').strip()
        if not placa:
            self.add_error('placa', 'Informe a placa.')
        if not modelo:
            self.add_error('modelo', 'Informe o modelo.')
        if not combustivel:
            self.add_error('combustivel', 'Informe o combustível.')
        motorista_carona = data.get('motorista_carona')
        if motorista_carona:
            num = data.get('motorista_oficio_numero')
            ano = data.get('motorista_oficio_ano')
            prot = (data.get('motorista_protocolo') or '').strip()
            if not num:
                self.add_error('motorista_oficio_numero', 'Informe o número do ofício do motorista.')
            if not ano and num:
                self.add_error('motorista_oficio_ano', 'Informe o ano do ofício do motorista.')
            if not prot:
                self.add_error('motorista_protocolo', 'Informe o protocolo do motorista.')
        return data
class OficioStep2Form(FormComErroInvalidMixin, forms.Form):
    """Step 2 — Transporte do ofício."""

    MOTORISTA_SEM_CADASTRO = '__manual__'
    SIM_NAO_CHOICES = [('1', 'Sim'), ('0', 'N\u00e3o')]

    placa = forms.CharField(
        required=False,
        max_length=10,
        label='Placa',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'data-mask': 'placa',
                'maxlength': 8,
                'placeholder': 'ABC-1234 ou ABC1D23',
                'autocomplete': 'off',
            }
        ),
    )
    modelo = forms.CharField(
        required=False,
        max_length=120,
        label='Modelo',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    combustivel = forms.CharField(
        required=False,
        max_length=80,
        label='Combustível',
        widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'combustivel-opcoes'}),
    )
    tipo_viatura = forms.ChoiceField(
        required=False,
        choices=[('', '---------')] + list(Oficio.TIPO_VIATURA_CHOICES),
        label='Tipo viatura',
        widget=forms.Select(attrs={'class': ''}),
    )
    porte_transporte_armas = forms.TypedChoiceField(
        required=False,
        label='Porte/transporte de armas',
        choices=SIM_NAO_CHOICES,
        coerce=lambda value: str(value) == '1',
        empty_value=True,
        widget=forms.Select(attrs={'class': ''}),
    )
    motorista_viajante = forms.ChoiceField(
        required=False,
        label='Motorista',
        choices=(),
        widget=forms.HiddenInput(),
    )
    motorista_nome = forms.CharField(
        required=False,
        max_length=120,
        label='Motorista (nome manual)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': 120}),
    )
    motorista_oficio_numero = forms.IntegerField(
        required=False,
        min_value=1,
        label='Nº ofício motorista',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'inputmode': 'numeric'}),
    )
    motorista_oficio_ano = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    motorista_protocolo = forms.CharField(
        required=False,
        max_length=12,
        label='Protocolo do motorista',
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'data-mask': 'protocolo',
                'inputmode': 'numeric',
                'maxlength': 12,
                'placeholder': '12.345.678-9',
                'autocomplete': 'off',
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.oficio = kwargs.pop('oficio', None)
        super().__init__(*args, **kwargs)
        self.current_year = timezone.localdate().year
        self.oficio_viajante_ids = set()
        if self.oficio:
            self.oficio_viajante_ids = set(self.oficio.viajantes.values_list('pk', flat=True))

        qs_motoristas = Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).order_by('nome')
        if self.oficio and self.oficio.motorista_viajante_id:
            qs_motoristas = (
                Viajante.objects.filter(pk=self.oficio.motorista_viajante_id) | qs_motoristas
            ).distinct().order_by('nome')
        self.motoristas_queryset = qs_motoristas
        self.motoristas_map = {obj.pk: obj for obj in qs_motoristas}

        if not self.initial.get('tipo_viatura'):
            self.initial['tipo_viatura'] = Oficio.TIPO_VIATURA_DESCARACTERIZADA
        porte_inicial = self.initial.get('porte_transporte_armas', True)
        if not self.is_bound:
            self.initial['porte_transporte_armas'] = '1' if bool(porte_inicial) else '0'
        if not self.initial.get('motorista_oficio_ano'):
            self.initial['motorista_oficio_ano'] = self.current_year

        if not self.is_bound:
            placa = self.initial.get('placa')
            protocolo = self.initial.get('motorista_protocolo')
            motorista_viajante = self.initial.get('motorista_viajante')
            if placa:
                self.initial['placa'] = format_placa(placa)
            if protocolo:
                self.initial['motorista_protocolo'] = format_protocolo(protocolo)
            if motorista_viajante:
                self.initial['motorista_viajante'] = str(motorista_viajante)
            elif self.initial.get('motorista_nome'):
                self.initial['motorista_viajante'] = self.MOTORISTA_SEM_CADASTRO

        self.motorista_choices_payload = self._build_motorista_choice_payloads()
        self.fields['motorista_viajante'].choices = self._build_motorista_choices()
        self.selected_motorista_value = self._raw_motorista_value()
        self.selected_motorista_payload = self._build_selected_motorista_payload()
        self.motorista_manual_selected = self._resolve_manual_selected()
        self.motorista_carona_selected = self._resolve_carona_preview()
        self.motorista_oficio_ano_display = self._resolve_motorista_oficio_ano_display()

    def _build_motorista_choice_payloads(self):
        payload = [
            {
                'value': '',
                'label': '---------',
                'nome': '',
                'cpf': '',
                'rg': '',
                'cargo': '',
                'is_carona': False,
            },
            {
                'value': self.MOTORISTA_SEM_CADASTRO,
                'label': 'Motorista sem cadastro',
                'nome': '',
                'cpf': '',
                'rg': '',
                'cargo': '',
                'is_carona': True,
            },
        ]
        for motorista in self.motoristas_queryset:
            is_carona = motorista.pk not in self.oficio_viajante_ids
            label = motorista.nome
            if is_carona:
                label = f'{label} (carona)'
            payload.append(
                {
                    'value': str(motorista.pk),
                    'label': label,
                    'nome': motorista.nome,
                    'cpf': motorista.cpf_formatado,
                    'rg': motorista.rg_formatado,
                    'cargo': motorista.cargo.nome if motorista.cargo_id and motorista.cargo else '',
                    'is_carona': is_carona,
                }
            )
        return payload

    def _build_motorista_choices(self):
        return [
            (item['value'], item['label'])
            for item in getattr(self, 'motorista_choices_payload', self._build_motorista_choice_payloads())
        ]

    def _build_selected_motorista_payload(self):
        selected_value = self._raw_motorista_value()
        if not selected_value or not selected_value.isdigit():
            return None
        for item in getattr(self, 'motorista_choices_payload', []):
            if item.get('value') == selected_value:
                payload = dict(item)
                payload['id'] = int(selected_value)
                return payload
        return None

    def _raw_motorista_value(self):
        if self.is_bound:
            return (self.data.get('motorista_viajante') or '').strip()
        return str(self.initial.get('motorista_viajante') or '').strip()

    def _raw_motorista_nome(self):
        if self.is_bound:
            return (self.data.get('motorista_nome') or '').strip()
        return (self.initial.get('motorista_nome') or '').strip()

    def _resolve_manual_selected(self):
        motorista_value = self._raw_motorista_value()
        if motorista_value == self.MOTORISTA_SEM_CADASTRO:
            return True
        return not motorista_value and bool(self._raw_motorista_nome())

    def _resolve_carona_preview(self):
        motorista_value = self._raw_motorista_value()
        if motorista_value == self.MOTORISTA_SEM_CADASTRO:
            return True
        if motorista_value.isdigit():
            return int(motorista_value) not in self.oficio_viajante_ids
        return bool(self.initial.get('motorista_carona'))

    def _resolve_motorista_oficio_ano_display(self):
        if self.is_bound:
            ano = self.data.get('motorista_oficio_ano')
        else:
            ano = self.initial.get('motorista_oficio_ano')
        try:
            return int(ano)
        except (TypeError, ValueError):
            return self.current_year

    def clean_placa(self):
        return normalize_placa(self.cleaned_data.get('placa'))

    def clean_modelo(self):
        value = (self.cleaned_data.get('modelo') or '').strip()
        return ' '.join(value.upper().split()) if value else ''

    def clean_combustivel(self):
        value = (self.cleaned_data.get('combustivel') or '').strip()
        return ' '.join(value.upper().split()) if value else ''

    def clean_motorista_nome(self):
        value = (self.cleaned_data.get('motorista_nome') or '').strip()
        return ' '.join(value.upper().split()) if value else ''

    def clean_motorista_viajante(self):
        value = (self.cleaned_data.get('motorista_viajante') or '').strip()
        if not value:
            return None
        if value == self.MOTORISTA_SEM_CADASTRO:
            return self.MOTORISTA_SEM_CADASTRO
        if not value.isdigit():
            raise forms.ValidationError('Selecione um motorista válido.')
        motorista = self.motoristas_map.get(int(value))
        if not motorista:
            raise forms.ValidationError('Selecione um motorista válido.')
        return motorista

    def clean_motorista_protocolo(self):
        protocolo = normalize_protocolo(self.cleaned_data.get('motorista_protocolo'))
        if protocolo and len(protocolo) != 9:
            raise forms.ValidationError('Informe o protocolo do motorista no formato XX.XXX.XXX-X.')
        return protocolo

    def clean(self):
        data = super().clean()
        placa = (data.get('placa') or '').strip()
        modelo = (data.get('modelo') or '').strip()
        combustivel = (data.get('combustivel') or '').strip()
        tipo_viatura = data.get('tipo_viatura') or Oficio.TIPO_VIATURA_DESCARACTERIZADA
        porte_transporte_armas = data.get('porte_transporte_armas')
        if porte_transporte_armas in (None, ''):
            porte_transporte_armas = True

        veiculo = buscar_veiculo_finalizado_por_placa(placa)
        if veiculo:
            if not modelo:
                modelo = veiculo.modelo or ''
                data['modelo'] = modelo
            if not combustivel and veiculo.combustivel_id:
                combustivel = veiculo.combustivel.nome or ''
                data['combustivel'] = combustivel
            if not data.get('tipo_viatura'):
                tipo_viatura = mapear_tipo_viatura_para_oficio(veiculo.tipo)
                data['tipo_viatura'] = tipo_viatura
        data['veiculo_cadastrado'] = veiculo
        data['tipo_viatura'] = tipo_viatura
        data['porte_transporte_armas'] = bool(porte_transporte_armas)

        if not placa:
            self.add_error('placa', 'Informe a placa.')
        if not modelo:
            self.add_error('modelo', 'Informe o modelo.')
        if not combustivel:
            self.add_error('combustivel', 'Informe o combustível.')

        motorista_value = data.get('motorista_viajante')
        manual_selected = motorista_value == self.MOTORISTA_SEM_CADASTRO or (
            motorista_value is None and bool(data.get('motorista_nome'))
        )
        motorista_obj = motorista_value if isinstance(motorista_value, Viajante) else None
        motorista_nome = (data.get('motorista_nome') or '').strip()

        if manual_selected and not motorista_nome:
            self.add_error('motorista_nome', 'Informe o nome do motorista sem cadastro.')

        motorista_nome_final = motorista_obj.nome if motorista_obj else motorista_nome
        motorista_carona = bool(manual_selected or (motorista_obj and motorista_obj.pk not in self.oficio_viajante_ids))
        data['motorista_carona'] = motorista_carona
        data['motorista_viajante_obj'] = motorista_obj
        data['motorista_nome_final'] = motorista_nome_final

        if motorista_carona:
            ano = data.get('motorista_oficio_ano') or self.current_year
            protocolo = (data.get('motorista_protocolo') or '').strip()
            numero = data.get('motorista_oficio_numero')
            data['motorista_oficio_ano'] = ano
            if not numero:
                self.add_error('motorista_oficio_numero', 'Informe o número do ofício do motorista.')
            if not protocolo:
                self.add_error('motorista_protocolo', 'Informe o protocolo do motorista.')
            data['motorista_oficio'] = f'{numero}/{ano}' if numero else ''
        else:
            data['motorista_oficio_numero'] = None
            data['motorista_oficio_ano'] = None
            data['motorista_oficio'] = ''
            data['motorista_protocolo'] = ''

        return data
