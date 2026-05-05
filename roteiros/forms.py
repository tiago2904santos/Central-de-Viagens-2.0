from django import forms

from .models import Roteiro


class RoteiroForm(forms.ModelForm):
    """Formulário do roteiro (sede, saída/retorno e observações) — alinhado ao legacy `RoteiroEventoForm`."""

    class Meta:
        model = Roteiro
        fields = [
            "origem_estado",
            "origem_cidade",
            "saida_dt",
            "retorno_saida_dt",
            "observacoes",
        ]
        widgets = {
            "origem_estado": forms.Select(attrs={"class": ""}),
            "origem_cidade": forms.Select(attrs={"class": ""}),
            "saida_dt": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "retorno_saida_dt": forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["saida_dt"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
        self.fields["retorno_saida_dt"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"]

    def clean_observacoes(self):
        val = self.cleaned_data.get("observacoes") or ""
        return val.strip().upper()

    def clean(self):
        data = super().clean()
        o_estado = data.get("origem_estado")
        o_cidade = data.get("origem_cidade")
        if o_estado and o_cidade and o_cidade.estado_id != o_estado.id:
            self.add_error("origem_cidade", "A cidade sede deve pertencer ao estado selecionado.")
        return data
