from django import forms

from .models import Cidade
from .models import Unidade


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
