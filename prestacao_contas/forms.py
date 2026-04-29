from django import forms

from eventos.services.plano_trabalho_domain import build_atividades_formatada, get_atividades_catalogo

from .models import RelatorioTecnicoPrestacao, TextoPadraoDocumento


class RelatorioTecnicoPrestacaoForm(forms.ModelForm):
    atividades_codigos = forms.MultipleChoiceField(
        required=False,
        choices=[],
        widget=forms.CheckboxSelectMultiple,
    )
    conclusao_modelo = forms.ModelChoiceField(
        required=False,
        queryset=TextoPadraoDocumento.objects.none(),
        empty_label="Selecione texto pronto",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Conclusao (texto pronto)",
    )
    medidas_modelo = forms.ModelChoiceField(
        required=False,
        queryset=TextoPadraoDocumento.objects.none(),
        empty_label="Selecione texto pronto",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Medidas (texto pronto)",
    )
    info_modelo = forms.ModelChoiceField(
        required=False,
        queryset=TextoPadraoDocumento.objects.none(),
        empty_label="Selecione texto pronto",
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Informacoes complementares (texto pronto)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["atividades_codigos"].choices = [
            (item["codigo"], item["nome"]) for item in get_atividades_catalogo()
        ]
        if self.instance and self.instance.atividade_codigos:
            self.initial["atividades_codigos"] = [c.strip() for c in self.instance.atividade_codigos.split(",") if c.strip()]
        self.fields["conclusao_modelo"].queryset = TextoPadraoDocumento.objects.filter(
            categoria=TextoPadraoDocumento.CATEGORIA_RT_CONCLUSAO, ativo=True
        ).order_by("ordem", "titulo")
        self.fields["medidas_modelo"].queryset = TextoPadraoDocumento.objects.filter(
            categoria=TextoPadraoDocumento.CATEGORIA_RT_MEDIDAS, ativo=True
        ).order_by("ordem", "titulo")
        self.fields["info_modelo"].queryset = TextoPadraoDocumento.objects.filter(
            categoria=TextoPadraoDocumento.CATEGORIA_RT_INFO, ativo=True
        ).order_by("ordem", "titulo")
        if not self.is_bound:
            for model_field, text_field, categoria in (
                ("conclusao_modelo", "conclusao", TextoPadraoDocumento.CATEGORIA_RT_CONCLUSAO),
                ("medidas_modelo", "medidas", TextoPadraoDocumento.CATEGORIA_RT_MEDIDAS),
                ("info_modelo", "informacoes_complementares", TextoPadraoDocumento.CATEGORIA_RT_INFO),
            ):
                if not (self.initial.get(text_field) or "").strip():
                    padrao = TextoPadraoDocumento.objects.filter(categoria=categoria, ativo=True, is_padrao=True).first()
                    if padrao:
                        self.initial[model_field] = padrao.pk
                        self.initial[text_field] = padrao.texto
        for field_name in ("conclusao_modelo", "medidas_modelo", "info_modelo"):
            field = self.fields[field_name]
            field.choices = [("", field.empty_label or "Selecione texto pronto")] + [
                (str(obj.pk), obj.titulo) for obj in field.queryset
            ]
        for name, field in self.fields.items():
            css = "form-control"
            if name in {"atividade", "conclusao", "medidas", "informacoes_complementares", "motivo"}:
                css = "form-control"
            if name not in {"atividades_codigos", "conclusao_modelo", "medidas_modelo", "info_modelo"}:
                field.widget.attrs["class"] = css
        self.fields["valor_translado"].widget.attrs.update({"class": "form-control", "step": "0.01"})
        self.fields["valor_passagem"].widget.attrs.update({"class": "form-control", "step": "0.01"})
        self.fields["teve_translado"].widget.attrs.update({"class": "form-check-input"})
        self.fields["teve_passagem"].widget.attrs.update({"class": "form-check-input"})

    class Meta:
        model = RelatorioTecnicoPrestacao
        fields = [
            "diaria",
            "combustivel",
            "teve_translado",
            "valor_translado",
            "translado",
            "teve_passagem",
            "valor_passagem",
            "passagem",
            "motivo",
            "atividade_codigos",
            "atividade",
            "conclusao_modelo",
            "conclusao",
            "medidas_modelo",
            "medidas",
            "info_modelo",
            "informacoes_complementares",
        ]
        widgets = {
            "motivo": forms.Textarea(attrs={"rows": 3}),
            "atividade": forms.Textarea(attrs={"rows": 4}),
            "conclusao": forms.Textarea(attrs={"rows": 3}),
            "medidas": forms.Textarea(attrs={"rows": 3}),
            "informacoes_complementares": forms.Textarea(attrs={"rows": 3}),
            "diaria": forms.TextInput(attrs={"readonly": "readonly"}),
            "combustivel": forms.TextInput(attrs={"readonly": "readonly"}),
            "translado": forms.TextInput(attrs={"readonly": "readonly"}),
            "passagem": forms.TextInput(attrs={"readonly": "readonly"}),
            "motivo": forms.Textarea(attrs={"rows": 4, "readonly": "readonly"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("conclusao_modelo") and not (cleaned.get("conclusao") or "").strip():
            cleaned["conclusao"] = cleaned["conclusao_modelo"].texto
        if cleaned.get("medidas_modelo") and not (cleaned.get("medidas") or "").strip():
            cleaned["medidas"] = cleaned["medidas_modelo"].texto
        if cleaned.get("info_modelo") and not (cleaned.get("informacoes_complementares") or "").strip():
            cleaned["informacoes_complementares"] = cleaned["info_modelo"].texto

        codigos = cleaned.get("atividades_codigos") or []
        cleaned["atividade"] = build_atividades_formatada(",".join(codigos))
        cleaned["atividade_codigos"] = ",".join(codigos)

        if cleaned.get("teve_translado"):
            valor = cleaned.get("valor_translado")
            if valor is None:
                self.add_error("valor_translado", "Informe o valor de translado.")
            cleaned["translado"] = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if valor else ""
        else:
            cleaned["valor_translado"] = None
            cleaned["translado"] = "Nao houve"

        if cleaned.get("teve_passagem"):
            valor = cleaned.get("valor_passagem")
            if valor is None:
                self.add_error("valor_passagem", "Informe o valor de passagem.")
            cleaned["passagem"] = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if valor else ""
        else:
            cleaned["valor_passagem"] = None
            cleaned["passagem"] = "Nao houve"
        return cleaned


class TextoPadraoDocumentoForm(forms.ModelForm):
    class Meta:
        model = TextoPadraoDocumento
        fields = ["categoria", "titulo", "texto", "is_padrao", "ativo", "ordem"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "texto": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "is_padrao": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ativo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "ordem": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }
