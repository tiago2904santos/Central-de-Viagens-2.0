import re

from django import forms

from .models import Cargo
from .models import Cidade
from .models import Combustivel
from .models import Servidor
from .models import Unidade
from .models import Viatura

PLACA_RE = re.compile(r"^[A-Z]{3}(?:\d{4}|\d[A-Z]\d{2})$")


def _format_cpf_display(value):
    digits = "".join(c for c in (value or "") if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return digits


def _format_rg_display(value):
    raw = "".join(c for c in (value or "").upper() if c.isalnum())
    if len(raw) >= 8:
        base = raw[:8]
        suffix = raw[8:9]
        masked = f"{base[:2]}.{base[2:5]}.{base[5:8]}"
        return f"{masked}-{suffix}" if suffix else masked
    return raw


def _format_placa_display(value):
    raw = "".join(c for c in (value or "").upper() if c.isalnum())
    return raw


class BaseCadastroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            attrs = getattr(field.widget, "attrs", None)
            if attrs is None:
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


class CidadeForm(BaseCadastroForm):
    class Meta:
        model = Cidade
        fields = ["nome", "uf"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["uf"].initial = self.fields["uf"].initial or "PR"

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def clean_uf(self):
        uf = self.cleaned_data["uf"].strip().upper()
        if len(uf) != 2:
            raise forms.ValidationError("UF deve ter 2 caracteres.")
        return uf


class CargoForm(BaseCadastroForm):
    class Meta:
        model = Cargo
        fields = ["nome"]

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
        fields = ["nome"]

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
    cpf = forms.CharField(required=False, max_length=14)
    rg = forms.CharField(required=False, max_length=20)

    class Meta:
        model = Servidor
        fields = ["nome", "cargo", "cpf", "rg", "unidade"]
        widgets = {
            "cpf": forms.TextInput(
                attrs={
                    "placeholder": "000.000.000-00",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                    "data-mask": "cpf",
                    "maxlength": "14",
                }
            ),
            "rg": forms.TextInput(
                attrs={
                    "placeholder": "00.000.000-0",
                    "autocomplete": "off",
                    "data-mask": "rg",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cpf"].widget = forms.TextInput(
            attrs={
                "placeholder": "000.000.000-00",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "cpf",
                "maxlength": "14",
                "class": "form-control",
            }
        )
        self.fields["rg"].widget = forms.TextInput(
            attrs={
                "placeholder": "00.000.000-0",
                "autocomplete": "off",
                "data-mask": "rg",
                "class": "form-control",
            }
        )
        self.fields["cargo"].required = True
        self.fields["cargo"].empty_label = "Selecione"
        self.fields["cargo"].widget.attrs["class"] = "form-select"
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].widget.attrs["class"] = "form-select"
        if self.instance.pk:
            self.initial["cpf"] = _format_cpf_display(self.instance.cpf)
            self.initial["rg"] = _format_rg_display(self.instance.rg)

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
        digits = "".join(c for c in self.cleaned_data.get("cpf", "") if c.isdigit())
        if digits and len(digits) != 11:
            raise forms.ValidationError("CPF deve conter 11 dígitos.")
        return digits

    def clean_rg(self):
        raw = "".join(c for c in self.cleaned_data.get("rg", "").upper() if c.isalnum())
        return raw


class ViaturaForm(BaseCadastroForm):
    class Meta:
        model = Viatura
        fields = ["placa", "modelo", "combustivel", "tipo"]
        widgets = {
            "placa": forms.TextInput(
                attrs={
                    "placeholder": "AAA1234 ou AAA1A23",
                    "autocomplete": "off",
                    "data-mask": "placa",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["combustivel"].required = True
        self.fields["combustivel"].empty_label = "Selecione"
        self.fields["combustivel"].widget.attrs["class"] = "form-select"
        self.fields["tipo"].required = True
        self.fields["tipo"].widget.attrs["class"] = "form-select"
        if self.instance.pk:
            self.initial["placa"] = _format_placa_display(self.instance.placa)

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
        return " ".join(self.cleaned_data.get("modelo", "").strip().split())
