import re
from django import forms
from .models import Viajante, Veiculo, ConfiguracaoSistema, Estado, Cidade, Cargo, AssinaturaConfiguracao, UnidadeLotacao, CombustivelVeiculo
from core.utils.masks import (
    RG_NAO_POSSUI_CANONICAL,
    format_cep,
    format_cpf,
    format_placa,
    format_rg,
    format_telefone,
    only_digits,
)


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


def _validar_cpf_digitos(cpf_11):
    """Valida CPF (11 dígitos) com dígitos verificadores. Retorna True se válido."""
    if len(cpf_11) != 11 or not cpf_11.isdigit():
        return False
    if cpf_11 == cpf_11[0] * 11:  # todos iguais
        return False
    # Primeiro dígito verificador
    soma = sum(int(cpf_11[i]) * (10 - i) for i in range(9))
    d1 = (soma * 10 % 11) % 10
    if int(cpf_11[9]) != d1:
        return False
    # Segundo dígito verificador
    soma = sum(int(cpf_11[i]) * (11 - i) for i in range(10))
    d2 = (soma * 10 % 11) % 10
    if int(cpf_11[10]) != d2:
        return False
    return True


class CargoForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = Cargo
        fields = ['nome', 'is_padrao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 120}),
            'is_padrao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nome(self):
        value = (self.cleaned_data.get('nome') or '').strip().upper()
        value = ' '.join(value.split())
        if not value:
            raise forms.ValidationError('Nome do cargo é obrigatório.')
        qs = Cargo.objects.filter(nome=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um cargo com este nome.')
        return value


class UnidadeLotacaoForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = UnidadeLotacao
        fields = ['nome']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 160}),
        }

    def clean_nome(self):
        value = (self.cleaned_data.get('nome') or '').strip().upper()
        value = ' '.join(value.split())
        if not value:
            raise forms.ValidationError('Nome da unidade é obrigatório.')
        qs = UnidadeLotacao.objects.filter(nome=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe uma unidade com este nome.')
        return value


class ViajanteForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = Viajante
        fields = [
            'nome', 'cargo', 'rg', 'sem_rg', 'cpf', 'telefone',
            'unidade_lotacao',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 160}),
            'cargo': forms.Select(attrs={'class': ''}),
            'rg': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 30, 'placeholder': 'Número do RG'}),
            'sem_rg': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_sem_rg'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 14, 'placeholder': '000.000.000-00', 'data-mask': 'cpf', 'inputmode': 'numeric'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 20, 'placeholder': '(00) 00000-0000', 'data-mask': 'telefone', 'inputmode': 'numeric'}),
            'unidade_lotacao': forms.Select(attrs={'class': ''}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sem_rg'].label = 'Não possui RG'
        self.fields['cargo'].queryset = Cargo.objects.all().order_by('nome')
        self.fields['cargo'].required = False
        self.fields['cargo'].empty_label = '---------'
        self.fields['unidade_lotacao'].queryset = UnidadeLotacao.objects.all().order_by('nome')
        self.fields['unidade_lotacao'].required = False
        self.fields['unidade_lotacao'].empty_label = '---------'
        rascunho = kwargs.get('initial')
        if (not self.instance.pk or self.instance.cargo_id is None) and not self.data and not rascunho:
            padrao = Cargo.objects.filter(is_padrao=True).first()
            if padrao:
                self.initial['cargo'] = padrao.pk
        if self.instance and self.instance.pk and not self.data and not rascunho:
            if self.instance.cpf:
                self.initial['cpf'] = format_cpf(self.instance.cpf)
            if self.instance.telefone:
                self.initial['telefone'] = format_telefone(self.instance.telefone)
            if self.instance.sem_rg or self.instance.rg == RG_NAO_POSSUI_CANONICAL:
                self.initial['rg'] = RG_NAO_POSSUI_CANONICAL
            elif self.instance.rg and self.instance.rg.isdigit():
                self.initial['rg'] = format_rg(self.instance.rg)
        self.fields['rg'].widget.attrs['data-mask'] = 'rg'

    def clean_nome(self):
        """Nome opcional no formulário; quando preenchido deve ser único e normalizado."""
        value = (self.cleaned_data.get('nome') or '').strip()
        if not value:
            return ''
        value = ' '.join(value.split()).upper()
        qs = Viajante.objects.filter(nome=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um cadastro com este nome.')
        return value

    def clean_rg(self):
        sem_rg = self.data.get('sem_rg')
        if sem_rg:
            return RG_NAO_POSSUI_CANONICAL
        value = (self.cleaned_data.get('rg') or '').strip()
        value = only_digits(value) or ''
        if value:
            qs = Viajante.objects.filter(rg=value)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Já existe um cadastro com este RG.')
        return value

    def clean_cpf(self):
        value = self.cleaned_data.get('cpf') or ''
        digits = re.sub(r'\D', '', value)
        if not digits:
            return ''
        if len(digits) != 11:
            raise forms.ValidationError('CPF deve ter 11 dígitos.')
        if not _validar_cpf_digitos(digits):
            raise forms.ValidationError('CPF inválido.')
        qs = Viajante.objects.filter(cpf=digits)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um cadastro com este CPF.')
        return digits

    def clean_telefone(self):
        value = self.cleaned_data.get('telefone') or ''
        digits = re.sub(r'\D', '', value)
        if not digits:
            return ''
        if len(digits) not in (10, 11):
            raise forms.ValidationError('Telefone deve ter 10 ou 11 dígitos.')
        qs = Viajante.objects.filter(telefone=digits)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um cadastro com este telefone.')
        return digits

    def clean(self):
        return super().clean()


from .utils.masks import _normalizar_placa

# Regex: antiga 3 letras + 4 dígitos; mercosul 3 letras + 1 dígito + 1 letra + 2 dígitos
PLACA_ANTIGA_RE = re.compile(r'^[A-Z]{3}[0-9]{4}$')
PLACA_MERCOSUL_RE = re.compile(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$')


def _placa_valida(normalizada):
    """Retorna True se placa normalizada (7 chars) é antiga ou mercosul."""
    if not normalizada or len(normalizada) != 7:
        return False
    return bool(PLACA_ANTIGA_RE.match(normalizada) or PLACA_MERCOSUL_RE.match(normalizada))


class CombustivelVeiculoForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = CombustivelVeiculo
        fields = ['nome', 'is_padrao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 60}),
            'is_padrao': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nome(self):
        value = (self.cleaned_data.get('nome') or '').strip().upper()
        value = ' '.join(value.split())
        if not value:
            raise forms.ValidationError('Nome do combustível é obrigatório.')
        qs = CombustivelVeiculo.objects.filter(nome=value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um combustível com este nome.')
        return value


class VeiculoForm(FormComErroInvalidMixin, forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = ['placa', 'modelo', 'combustivel', 'tipo']
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 7, 'placeholder': 'ABC1234 ou ABC1D23'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 120}),
            'combustivel': forms.Select(attrs={'class': ''}),
            'tipo': forms.Select(attrs={'class': ''}),
        }

    def __init__(self, *args, **kwargs):
        rascunho = kwargs.get('initial')
        super().__init__(*args, **kwargs)
        self.fields['combustivel'].queryset = CombustivelVeiculo.objects.all().order_by('nome')
        self.fields['combustivel'].required = False
        self.fields['combustivel'].empty_label = '---------'
        if (not self.instance.pk or self.instance.combustivel_id is None) and not self.data and not rascunho:
            padrao = CombustivelVeiculo.objects.filter(is_padrao=True).first()
            if padrao:
                self.initial['combustivel'] = padrao.pk
        if self.instance and self.instance.pk and not self.data and not rascunho and self.instance.placa:
            self.initial['placa'] = format_placa(self.instance.placa)
        if not self.instance.pk and not self.data and not rascunho:
            self.initial['tipo'] = Veiculo.TIPO_DESCARACTERIZADO
        self.fields['placa'].widget.attrs['data-mask'] = 'placa'

    def clean_placa(self):
        """Placa opcional no formulário; quando preenchida deve ser válida e única."""
        value = (self.cleaned_data.get('placa') or '').strip()
        placa_norm = _normalizar_placa(value)
        if not placa_norm:
            return ''
        if not _placa_valida(placa_norm):
            raise forms.ValidationError(
                'Placa inválida. Use padrão antigo (ABC-1234) ou Mercosul (ABC1D23).'
            )
        qs = Veiculo.objects.filter(placa=placa_norm)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um cadastro com esta placa.')
        return placa_norm

    def clean_modelo(self):
        """Modelo opcional no formulário; quando preenchido é normalizado em maiúsculas."""
        value = (self.cleaned_data.get('modelo') or '').strip()
        if not value:
            return ''
        return ' '.join(value.split()).upper()


def _viajantes_operacionais_queryset():
    """Viajantes finalizados para uso operacional (assinaturas, configurações, ofícios, etc.)."""
    return Viajante.objects.filter(status=Viajante.STATUS_FINALIZADO).order_by('nome')


def _veiculos_operacionais_queryset():
    """Veículos finalizados para uso operacional (ofícios, termos, documentos, configurações)."""
    return Veiculo.objects.filter(status=Veiculo.STATUS_FINALIZADO).order_by('placa', 'modelo')


class ConfiguracaoSistemaForm(FormComErroInvalidMixin, forms.ModelForm):
    """
    Formulário do singleton ConfiguracaoSistema.
    Cabeçalho: divisao, unidade, sigla_orgao (todos upper).
    Rodapé: CEP + endereço; cidade_sede_padrao é definida no backend a partir do endereço.
    Assinaturas: editadas via AssinaturaConfiguracao (ordem=1 por tipo); campos extras não ligados ao model.
    """
    assinatura_oficio = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        empty_label='---------',
        label='Assinatura (Ofícios)',
        widget=forms.Select(attrs={'class': ''}),
    )
    assinatura_justificativas = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        empty_label='---------',
        label='Assinatura (Justificativas)',
        widget=forms.Select(attrs={'class': ''}),
    )
    assinatura_planos_trabalho = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        empty_label='---------',
        label='Assinatura (Planos de Trabalho)',
        widget=forms.Select(attrs={'class': ''}),
    )
    assinatura_ordens_servico = forms.ModelChoiceField(
        queryset=Viajante.objects.none(),
        required=False,
        empty_label='---------',
        label='Assinatura (Ordem de Serviço)',
        widget=forms.Select(attrs={'class': ''}),
    )

    class Meta:
        model = ConfiguracaoSistema
        fields = [
            'divisao', 'unidade', 'sigla_orgao',
            'sede', 'nome_chefia', 'cargo_chefia',
            'coordenador_adm_plano_trabalho',
            'cep', 'logradouro', 'bairro', 'cidade_endereco', 'uf', 'numero',
            'telefone', 'email',
        ]
        widgets = {
            'divisao': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_divisao', 'maxlength': 120}),
            'unidade': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_unidade', 'maxlength': 120}),
            'sigla_orgao': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_sigla_orgao', 'maxlength': 20}),
            'sede': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_sede', 'maxlength': 200, 'placeholder': 'Ex.: Curitiba/PR'}),
            'nome_chefia': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_nome_chefia', 'maxlength': 120}),
            'cargo_chefia': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_cargo_chefia', 'maxlength': 120}),
            'coordenador_adm_plano_trabalho': forms.Select(attrs={'class': '', 'id': 'id_coordenador_adm_plano_trabalho'}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_cep', 'maxlength': 9, 'placeholder': '00000-000', 'data-mask': 'cep', 'inputmode': 'numeric'}),
            'logradouro': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_logradouro'}),
            'bairro': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_bairro'}),
            'cidade_endereco': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_cidade_endereco'}),
            'uf': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_uf', 'maxlength': 2, 'placeholder': 'PR'}),
            'numero': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_numero'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_telefone', 'data-mask': 'telefone', 'inputmode': 'numeric'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'id': 'id_email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = _viajantes_operacionais_queryset()
        self.fields['assinatura_oficio'].queryset = qs
        self.fields['assinatura_justificativas'].queryset = qs
        self.fields['assinatura_planos_trabalho'].queryset = qs
        self.fields['assinatura_ordens_servico'].queryset = qs
        self.fields['coordenador_adm_plano_trabalho'].queryset = qs
        self.fields['coordenador_adm_plano_trabalho'].empty_label = '---------'
        if self.instance and self.instance.pk:
            if self.instance.cep:
                self.initial['cep'] = format_cep(self.instance.cep)
            if self.instance.telefone:
                self.initial['telefone'] = format_telefone(self.instance.telefone)
            for field_name, tipo in [
                ('assinatura_oficio', AssinaturaConfiguracao.TIPO_OFICIO),
                ('assinatura_justificativas', AssinaturaConfiguracao.TIPO_JUSTIFICATIVA),
                ('assinatura_planos_trabalho', AssinaturaConfiguracao.TIPO_PLANO_TRABALHO),
                ('assinatura_ordens_servico', AssinaturaConfiguracao.TIPO_ORDEM_SERVICO),
            ]:
                rec = self.instance.assinaturas.filter(tipo=tipo, ordem=1).first()
                self.fields[field_name].initial = rec.viajante_id if rec and rec.viajante_id else None

    def clean_divisao(self):
        value = self.cleaned_data.get('divisao') or ''
        return value.strip().upper()

    def clean_unidade(self):
        value = self.cleaned_data.get('unidade') or ''
        return value.strip().upper()

    def clean_sigla_orgao(self):
        value = self.cleaned_data.get('sigla_orgao') or ''
        return value.strip().upper()

    def clean_cep(self):
        value = self.cleaned_data.get('cep') or ''
        cep_limpo = only_digits(value)
        if not cep_limpo:
            return ''
        if len(cep_limpo) != 8:
            raise forms.ValidationError('CEP deve ter 8 dígitos.')
        return format_cep(cep_limpo)

    def clean_uf(self):
        value = (self.cleaned_data.get('uf') or '').strip().upper()
        if value and len(value) != 2:
            raise forms.ValidationError('UF deve ter 2 letras.')
        return value

    def clean_telefone(self):
        value = self.cleaned_data.get('telefone') or ''
        digits = re.sub(r'\D', '', value)
        if not digits:
            return ''
        if len(digits) not in (10, 11):
            raise forms.ValidationError('Telefone deve ter 10 ou 11 dígitos.')
        return digits
