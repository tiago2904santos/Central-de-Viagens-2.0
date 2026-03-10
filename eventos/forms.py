from django import forms
from cadastros.models import Viajante, Veiculo
from .models import Evento, EventoParticipante, ModeloMotivoViagem, Oficio, RoteiroEvento, TipoDemandaEvento
from core.utils.masks import format_protocolo
from .utils import normalize_protocolo


class FormComErroInvalidMixin:
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
            'tipo_demanda': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'data_fim': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estado_principal': forms.Select(attrs={'class': 'form-select', 'data-cidades-target': 'cidade_principal'}),
            'cidade_principal': forms.Select(attrs={'class': 'form-select'}),
            'cidade_base': forms.Select(attrs={'class': 'form-select'}),
            'tem_convite_ou_oficio_evento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
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
            'origem_estado': forms.Select(attrs={'class': 'form-select'}),
            'origem_cidade': forms.Select(attrs={'class': 'form-select'}),
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
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    motorista = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=True,
        empty_label='---------',
        label='Motorista',
        widget=forms.Select(attrs={'class': 'form-select'}),
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
        max_length=80,
        label='Protocolo',
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'data-mask': 'protocolo', 'inputmode': 'numeric'}
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
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    motivo = forms.CharField(
        required=False,
        label='Motivo da viagem',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
    )
    custeio_tipo = forms.ChoiceField(
        required=True,
        choices=Oficio.CUSTEIO_CHOICES,
        label='Custeio',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    nome_instituicao_custeio = forms.CharField(
        required=False, max_length=200, label='Nome instituição de custeio',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    viajantes = forms.ModelMultipleChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        label='Viajantes',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modelo_motivo'].queryset = ModeloMotivoViagem.objects.all().order_by('nome')
        self.fields['viajantes'].queryset = Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).order_by('nome')
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


class OficioStep2Form(FormComErroInvalidMixin, forms.Form):
    """Step 2 — Transporte. Regras: placa, modelo e combustível obrigatórios; motorista carona exige ofício e protocolo."""
    placa = forms.CharField(required=False, max_length=10, label='Placa', widget=forms.TextInput(attrs={'class': 'form-control'}))
    modelo = forms.CharField(required=False, max_length=120, label='Modelo', widget=forms.TextInput(attrs={'class': 'form-control'}))
    combustivel = forms.CharField(required=False, max_length=80, label='Combustível', widget=forms.TextInput(attrs={'class': 'form-control'}))
    tipo_viatura = forms.ChoiceField(
        required=False,
        choices=[('', '---------')] + list(Oficio.TIPO_VIATURA_CHOICES),
        label='Tipo viatura',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    motorista_viajante = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        empty_label='---------',
        label='Motorista (viajante)',
        widget=forms.Select(attrs={'class': 'form-select'}),
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
        max_length=80,
        label='Protocolo motorista',
        widget=forms.TextInput(attrs={'class': 'form-control', 'data-mask': 'protocolo', 'inputmode': 'numeric'}),
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
