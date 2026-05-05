from django import forms

from cadastros.models import Cidade

from .models import Roteiro


class RoteiroForm(forms.ModelForm):
    class Meta:
        model = Roteiro
        fields = [
            "nome",
            "descricao",
            "origem",
            "destino",
            "data_inicio",
            "data_fim",
            "observacoes",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "origem": forms.Select(attrs={"class": "form-select"}),
            "destino": forms.Select(attrs={"class": "form-select"}),
            "data_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "data_fim": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cidades = Cidade.objects.select_related("estado").order_by("estado__sigla", "nome")
        self.fields["origem"].queryset = cidades
        self.fields["destino"].queryset = cidades
        self.fields["origem"].empty_label = "Selecione a origem"
        self.fields["destino"].empty_label = "Selecione o destino principal"
        self.fields["descricao"].required = False
        self.fields["observacoes"].required = False

    def clean_nome(self):
        return " ".join((self.cleaned_data.get("nome") or "").strip().split())
