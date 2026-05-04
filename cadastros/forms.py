from django import forms
from django.db.models import Q

from .models import Cidade
from .models import Motorista
from .models import Servidor
from .models import Unidade
from .models import Viatura


def _format_cpf_display(value):
    if not value:
        return ""
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return str(value).strip()


def _format_placa_display(value):
    if not value:
        return ""
    s = "".join(c for c in str(value).upper() if c.isalnum())
    if len(s) == 7:
        return f"{s[:3]}-{s[3:]}"
    return str(value).strip().upper()


class BaseCadastroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")


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


class ServidorForm(BaseCadastroForm):
    class Meta:
        model = Servidor
        fields = ["nome", "matricula", "cargo", "cpf", "unidade"]
        widgets = {
            "cpf": forms.TextInput(
                attrs={
                    "placeholder": "000.000.000-00",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].widget.attrs["class"] = "form-select"
        if self.instance.pk and self.instance.cpf:
            self.initial["cpf"] = _format_cpf_display(self.instance.cpf)

    def clean_nome(self):
        raw = self.cleaned_data.get("nome", "")
        nome = " ".join(raw.strip().split())
        if not nome:
            raise forms.ValidationError("Este campo é obrigatório.")
        return nome

    def clean_matricula(self):
        v = self.cleaned_data.get("matricula", "")
        return " ".join(v.strip().split()) if v else ""

    def clean_cargo(self):
        v = self.cleaned_data.get("cargo", "")
        return " ".join(v.strip().split()) if v else ""

    def clean_cpf(self):
        v = self.cleaned_data.get("cpf", "")
        if not v:
            return ""
        return "".join(c for c in v if c.isdigit())


class MotoristaForm(BaseCadastroForm):
    class Meta:
        model = Motorista
        fields = ["servidor", "cnh", "categoria_cnh"]
        widgets = {
            "cnh": forms.TextInput(attrs={"placeholder": "Número da CNH", "autocomplete": "off"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servidor"].widget.attrs["class"] = "form-select"
        self.fields["servidor"].queryset = self._servidor_queryset()

    def _servidor_queryset(self):
        qs = Servidor.objects.select_related("unidade").order_by("nome")
        if self.instance.pk:
            current_id = self.instance.servidor_id
            return qs.filter(Q(pk=current_id) | Q(motorista__isnull=True)).distinct()
        return qs.filter(motorista__isnull=True)

    def clean_cnh(self):
        v = self.cleaned_data.get("cnh", "")
        return " ".join(v.strip().split()) if v else ""

    def clean_categoria_cnh(self):
        v = self.cleaned_data.get("categoria_cnh", "")
        return v.strip().upper() if v else ""


class ViaturaForm(BaseCadastroForm):
    class Meta:
        model = Viatura
        fields = ["placa", "modelo", "marca", "tipo", "combustivel", "unidade"]
        widgets = {
            "placa": forms.TextInput(
                attrs={"placeholder": "ABC-1D23", "autocomplete": "off"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].widget.attrs["class"] = "form-select"
        if self.instance.pk and self.instance.placa:
            self.initial["placa"] = _format_placa_display(self.instance.placa)

    def clean_placa(self):
        raw = self.cleaned_data.get("placa", "")
        s = "".join(c for c in raw.upper() if c.isalnum())
        if not s:
            raise forms.ValidationError("Este campo é obrigatório.")
        return s

    def clean_modelo(self):
        v = self.cleaned_data.get("modelo", "")
        return " ".join(v.strip().split()) if v else ""

    def clean_marca(self):
        v = self.cleaned_data.get("marca", "")
        return " ".join(v.strip().split()) if v else ""

    def clean_tipo(self):
        v = self.cleaned_data.get("tipo", "")
        return " ".join(v.strip().split()) if v else ""

    def clean_combustivel(self):
        v = self.cleaned_data.get("combustivel", "")
        return " ".join(v.strip().split()) if v else ""
