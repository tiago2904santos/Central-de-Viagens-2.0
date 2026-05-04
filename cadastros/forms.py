import re

from django import forms

from core.utils.masks import (
    RG_NAO_POSSUI_CANONICAL,
    RG_NAO_POSSUI_DISPLAY,
    format_cpf,
    format_cep,
    format_placa,
    format_rg,
    format_telefone,
    only_digits,
    validar_cpf_digitos,
)

from .models import AssinaturaConfiguracao
from .models import Cargo
from .models import Cidade
from .models import Combustivel
from .models import ConfiguracaoSistema
from .models import Estado
from .models import Servidor
from .models import Unidade
from .models import Viatura

PLACA_RE = re.compile(r"^[A-Z]{3}(?:\d{4}|\d[A-Z]\d{2})$")


class BaseCadastroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            attrs = getattr(field.widget, "attrs", None)
            if attrs is None:
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                attrs.setdefault("class", "app-card-toggle__input sr-only")
                attrs.setdefault("role", "switch")
                continue
            attrs.setdefault("class", "form-control")
            if isinstance(field, forms.CharField):
                attrs.setdefault("data-mask", "upper")


class UnidadeForm(BaseCadastroForm):
    class Meta:
        model = Unidade
        fields = ["nome", "sigla"]

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def clean_sigla(self):
        return self.cleaned_data.get("sigla", "").strip().upper()


class EstadoForm(BaseCadastroForm):
    class Meta:
        model = Estado
        fields = ["nome", "sigla", "codigo_ibge"]

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def clean_sigla(self):
        sigla = self.cleaned_data["sigla"].strip().upper()
        if len(sigla) != 2:
            raise forms.ValidationError("Sigla deve ter 2 caracteres.")
        return sigla


class CidadeForm(BaseCadastroForm):
    class Meta:
        model = Cidade
        fields = ["nome", "estado", "capital", "codigo_ibge", "latitude", "longitude"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].queryset = Estado.objects.order_by("nome")
        self.fields["estado"].empty_label = "Selecione"
        self.fields["estado"].widget.attrs["class"] = "form-select"
        for fname in ("latitude", "longitude"):
            if fname in self.fields:
                self.fields[fname].required = False
        if "codigo_ibge" in self.fields:
            self.fields["codigo_ibge"].required = False

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()


_TOGGLE_WIDGET = forms.CheckboxInput(
    attrs={
        "class": "app-card-toggle__input sr-only",
        "role": "switch",
    },
)


class CargoForm(BaseCadastroForm):
    class Meta:
        model = Cargo
        fields = ["nome", "is_padrao"]
        widgets = {
            "is_padrao": _TOGGLE_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_padrao"].required = False
        self.fields["is_padrao"].label = "Cargo padrão"

    def clean_nome(self):
        nome = " ".join(self.cleaned_data.get("nome", "").strip().split()).upper()
        if not nome:
            raise forms.ValidationError("Este campo é obrigatório.")
        qs = Cargo.objects.filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cargo com este nome.")
        return nome


class CombustivelForm(BaseCadastroForm):
    class Meta:
        model = Combustivel
        fields = ["nome", "is_padrao"]
        widgets = {
            "is_padrao": _TOGGLE_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_padrao"].required = False
        self.fields["is_padrao"].label = "Combustível padrão"

    def clean_nome(self):
        nome = " ".join(self.cleaned_data.get("nome", "").strip().split()).upper()
        if not nome:
            raise forms.ValidationError("Este campo é obrigatório.")
        qs = Combustivel.objects.filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um combustível com este nome.")
        return nome


class ServidorForm(BaseCadastroForm):
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        widget=forms.TextInput(
            attrs={
                "placeholder": "000.000.000-00",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "cpf",
                "maxlength": "14",
                "class": "form-control",
            },
        ),
    )
    rg = forms.CharField(
        label="RG",
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "00.000.000-0",
                "autocomplete": "off",
                "data-mask": "rg",
                "class": "form-control",
            },
        ),
    )
    telefone = forms.CharField(
        label="Telefone",
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "(00) 00000-0000",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "telefone",
                "class": "form-control",
            },
        ),
    )
    sem_rg = forms.BooleanField(
        label="Não possui RG",
        required=False,
        widget=_TOGGLE_WIDGET,
    )

    class Meta:
        model = Servidor
        fields = ["nome", "cargo", "cpf", "sem_rg", "rg", "telefone", "unidade"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].required = True
        self.fields["cargo"].empty_label = "Selecione"
        self.fields["cargo"].widget.attrs["class"] = "form-select"
        self.fields["cargo"].queryset = Cargo.objects.order_by("nome")
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].widget.attrs["class"] = "form-select"
        self.fields["unidade"].queryset = Unidade.objects.order_by("nome")

        if not self.instance.pk and not self.data:
            padrao = Cargo.objects.filter(is_padrao=True).first()
            if padrao:
                self.initial.setdefault("cargo", padrao.pk)

        if self.instance.pk and not self.data:
            self.initial["sem_rg"] = self.instance.sem_rg
            if self.instance.cpf:
                self.initial["cpf"] = format_cpf(self.instance.cpf)
            if self.instance.telefone:
                self.initial["telefone"] = format_telefone(self.instance.telefone)
            if self.instance.sem_rg or self.instance.rg == RG_NAO_POSSUI_CANONICAL:
                self.initial["rg"] = RG_NAO_POSSUI_DISPLAY
            elif self.instance.rg and self.instance.rg.isdigit():
                self.initial["rg"] = format_rg(self.instance.rg)

    def clean_nome(self):
        nome = " ".join(self.cleaned_data.get("nome", "").strip().split()).upper()
        if not nome:
            raise forms.ValidationError("Este campo é obrigatório.")
        qs = Servidor.objects.filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um servidor com este nome.")
        return nome

    def clean_cpf(self):
        digits = only_digits(self.cleaned_data.get("cpf", ""))
        if not digits:
            raise forms.ValidationError("Informe o CPF.")
        if len(digits) != 11:
            raise forms.ValidationError("CPF deve conter 11 dígitos.")
        if not validar_cpf_digitos(digits):
            raise forms.ValidationError("CPF inválido.")
        qs = Servidor.objects.filter(cpf=digits)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cadastro com este CPF.")
        return digits

    def clean_rg(self):
        if self.cleaned_data.get("sem_rg"):
            return RG_NAO_POSSUI_CANONICAL
        raw = "".join(c for c in self.cleaned_data.get("rg", "").upper() if c.isalnum())
        if raw.upper() in {RG_NAO_POSSUI_CANONICAL.replace(" ", ""), "NAOPOSSUIRG"}:
            return RG_NAO_POSSUI_CANONICAL
        if raw:
            qs = Servidor.objects.filter(rg=raw)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Já existe um cadastro com este RG.")
        return raw

    def clean_telefone(self):
        digits = only_digits(self.cleaned_data.get("telefone", ""))
        if not digits:
            return ""
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Telefone deve ter 10 ou 11 dígitos.")
        qs = Servidor.objects.filter(telefone=digits)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cadastro com este telefone.")
        return digits


class ViaturaForm(BaseCadastroForm):
    class Meta:
        model = Viatura
        fields = ["placa", "modelo", "combustivel", "tipo", "motoristas"]
        widgets = {
            "placa": forms.TextInput(
                attrs={
                    "placeholder": "AAA1234 ou AAA1A23",
                    "autocomplete": "off",
                    "data-mask": "placa",
                    "class": "form-control",
                },
            ),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "motoristas": forms.SelectMultiple(
                attrs={
                    "class": "form-select",
                    "size": "6",
                    "aria-label": "Motoristas",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["combustivel"].required = True
        self.fields["combustivel"].empty_label = "Selecione"
        self.fields["combustivel"].widget.attrs["class"] = "form-select"
        self.fields["combustivel"].queryset = Combustivel.objects.order_by("nome")
        self.fields["tipo"].required = True
        self.fields["motoristas"].required = False
        self.fields["motoristas"].queryset = Servidor.objects.order_by("nome")
        self.fields["motoristas"].label = "Motoristas"
        if not self.instance.pk and not self.data:
            padrao = Combustivel.objects.filter(is_padrao=True).first()
            if padrao:
                self.initial.setdefault("combustivel", padrao.pk)
            self.initial.setdefault("tipo", Viatura.TIPO_DESCARACTERIZADA)
        if self.instance.pk:
            self.initial["placa"] = format_placa(self.instance.placa)

    def clean_placa(self):
        raw = "".join(c for c in self.cleaned_data.get("placa", "").upper() if c.isalnum())
        if not PLACA_RE.match(raw):
            raise forms.ValidationError("Placa deve estar no formato AAA1234 ou AAA1A23.")
        qs = Viatura.objects.filter(placa=raw)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe uma viatura com esta placa.")
        return raw

    def clean_modelo(self):
        modelo = " ".join(self.cleaned_data.get("modelo", "").strip().split()).upper()
        if not modelo:
            raise forms.ValidationError("Informe o modelo.")
        return modelo


class ConfiguracaoSistemaForm(forms.ModelForm):
    """Singleton institucional + assinantes por tipo documental, espelhando o legacy."""

    assinatura_oficio_1 = forms.ModelChoiceField(
        queryset=Servidor.objects.none(),
        required=False,
        empty_label="---------",
        label="Assinatura 1",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assinatura_oficio_2 = forms.ModelChoiceField(
        queryset=Servidor.objects.none(),
        required=False,
        empty_label="---------",
        label="Assinatura 2",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assinatura_justificativas = forms.ModelChoiceField(
        queryset=Servidor.objects.none(),
        required=False,
        empty_label="---------",
        label="Assinante",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assinatura_planos_trabalho = forms.ModelChoiceField(
        queryset=Servidor.objects.none(),
        required=False,
        empty_label="---------",
        label="Assinante",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assinatura_ordens_servico = forms.ModelChoiceField(
        queryset=Servidor.objects.none(),
        required=False,
        empty_label="---------",
        label="Assinante",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assinatura_termo_autorizacao = forms.ModelChoiceField(
        queryset=Servidor.objects.none(),
        required=False,
        empty_label="---------",
        label="Assinante",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = ConfiguracaoSistema
        fields = [
            "cidade_sede_padrao",
            "prazo_justificativa_dias",
            "nome_orgao",
            "sigla_orgao",
            "divisao",
            "unidade",
            "sede",
            "nome_chefia",
            "cargo_chefia",
            "coordenador_adm_plano_trabalho",
            "cep",
            "logradouro",
            "bairro",
            "cidade_endereco",
            "uf",
            "numero",
            "telefone",
            "email",
            "pt_ultimo_numero",
            "pt_ano",
        ]
        widgets = {
            "cidade_sede_padrao": forms.Select(attrs={"class": "form-select"}),
            "prazo_justificativa_dias": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "nome_orgao": forms.TextInput(attrs={"class": "form-control"}),
            "sigla_orgao": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "divisao": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "unidade": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "sede": forms.TextInput(attrs={"class": "form-control"}),
            "nome_chefia": forms.TextInput(attrs={"class": "form-control"}),
            "cargo_chefia": forms.TextInput(attrs={"class": "form-control"}),
            "coordenador_adm_plano_trabalho": forms.Select(attrs={"class": "form-select"}),
            "cep": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "maxlength": "9",
                    "placeholder": "00000-000",
                    "data-mask": "cep",
                    "inputmode": "numeric",
                },
            ),
            "logradouro": forms.TextInput(attrs={"class": "form-control"}),
            "bairro": forms.TextInput(attrs={"class": "form-control"}),
            "cidade_endereco": forms.TextInput(attrs={"class": "form-control"}),
            "uf": forms.TextInput(attrs={"class": "form-control", "maxlength": 2, "data-mask": "upper"}),
            "numero": forms.TextInput(attrs={"class": "form-control"}),
            "telefone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "telefone",
                    "inputmode": "numeric",
                },
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "pt_ultimo_numero": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "pt_ano": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Servidor.objects.order_by("nome")
        self.fields["coordenador_adm_plano_trabalho"].queryset = qs
        self.fields["coordenador_adm_plano_trabalho"].empty_label = "---------"
        self.fields["coordenador_adm_plano_trabalho"].required = False
        self.fields["cidade_sede_padrao"].queryset = Cidade.objects.select_related("estado").order_by(
            "estado__sigla",
            "nome",
        )
        self.fields["cidade_sede_padrao"].required = False
        self.fields["cidade_sede_padrao"].empty_label = "---------"
        self.fields["cidade_sede_padrao"].disabled = True
        self.fields["cidade_sede_padrao"].help_text = "Resolvida automaticamente pelo endereço informado."

        for fname in (
            "assinatura_oficio_1",
            "assinatura_oficio_2",
            "assinatura_justificativas",
            "assinatura_planos_trabalho",
            "assinatura_ordens_servico",
            "assinatura_termo_autorizacao",
        ):
            self.fields[fname].queryset = qs

        if self.instance and self.instance.pk:
            if self.instance.cep:
                self.initial.setdefault("cep", format_cep(self.instance.cep))
            if self.instance.telefone:
                self.initial.setdefault("telefone", format_telefone(self.instance.telefone))

            mapping = [
                ("assinatura_oficio_1", AssinaturaConfiguracao.TIPO_OFICIO, 1),
                ("assinatura_oficio_2", AssinaturaConfiguracao.TIPO_OFICIO, 2),
                ("assinatura_justificativas", AssinaturaConfiguracao.TIPO_JUSTIFICATIVA, 1),
                ("assinatura_planos_trabalho", AssinaturaConfiguracao.TIPO_PLANO_TRABALHO, 1),
                ("assinatura_ordens_servico", AssinaturaConfiguracao.TIPO_ORDEM_SERVICO, 1),
                ("assinatura_termo_autorizacao", AssinaturaConfiguracao.TIPO_TERMO_AUTORIZACAO, 1),
            ]
            for field_name, tipo, ordem in mapping:
                rec = self.instance.assinaturas.filter(tipo=tipo, ordem=ordem).first()
                if rec and rec.servidor_id:
                    self.fields[field_name].initial = rec.servidor_id

    def clean_nome_orgao(self):
        return " ".join((self.cleaned_data.get("nome_orgao") or "").strip().split()).upper()

    def clean_divisao(self):
        return (self.cleaned_data.get("divisao") or "").strip().upper()

    def clean_unidade(self):
        return (self.cleaned_data.get("unidade") or "").strip().upper()

    def clean_sigla_orgao(self):
        return (self.cleaned_data.get("sigla_orgao") or "").strip().upper()

    def clean_cep(self):
        value = self.cleaned_data.get("cep") or ""
        cep_limpo = only_digits(value)
        if not cep_limpo:
            return ""
        if len(cep_limpo) != 8:
            raise forms.ValidationError("CEP deve ter 8 dígitos.")
        return cep_limpo

    def clean_uf(self):
        value = (self.cleaned_data.get("uf") or "").strip().upper()
        if value and len(value) != 2:
            raise forms.ValidationError("UF deve ter 2 letras.")
        return value

    def clean_telefone(self):
        digits = only_digits(self.cleaned_data.get("telefone", ""))
        if not digits:
            return ""
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Telefone deve ter 10 ou 11 dígitos.")
        return digits

