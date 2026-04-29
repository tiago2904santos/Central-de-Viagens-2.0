from django import forms

from .models import RelatorioTecnicoPrestacao


class RelatorioTecnicoPrestacaoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-control"
            if name in {"atividade", "conclusao", "medidas", "informacoes_complementares", "motivo"}:
                css = "form-control"
            field.widget.attrs["class"] = css

    class Meta:
        model = RelatorioTecnicoPrestacao
        fields = [
            "nome_servidor",
            "rg_servidor",
            "cargo_servidor",
            "diaria",
            "translado",
            "passagem",
            "motivo",
            "atividade",
            "conclusao",
            "medidas",
            "informacoes_complementares",
        ]
        widgets = {
            "motivo": forms.Textarea(attrs={"rows": 3}),
            "atividade": forms.Textarea(attrs={"rows": 4}),
            "conclusao": forms.Textarea(attrs={"rows": 3}),
            "medidas": forms.Textarea(attrs={"rows": 3}),
            "informacoes_complementares": forms.Textarea(attrs={"rows": 3}),
        }
