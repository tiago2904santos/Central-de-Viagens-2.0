from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from .models import DiarioBordo, DiarioBordoTrecho


class DiarioIdentificacaoForm(forms.ModelForm):
    class Meta:
        model = DiarioBordo
        fields = ["oficio", "e_protocolo", "divisao", "unidade_cabecalho", "roteiro", "prestacao", "status"]
        widgets = {
            "oficio": forms.Select(attrs={"class": "form-select"}),
            "roteiro": forms.Select(attrs={"class": "form-select"}),
            "prestacao": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "e_protocolo": forms.TextInput(attrs={"class": "form-control"}),
            "divisao": forms.TextInput(attrs={"class": "form-control"}),
            "unidade_cabecalho": forms.TextInput(attrs={"class": "form-control"}),
        }


class DiarioVeiculoResponsavelForm(forms.ModelForm):
    class Meta:
        model = DiarioBordo
        fields = [
            "veiculo",
            "tipo_veiculo",
            "combustivel",
            "placa_oficial",
            "placa_reservada",
            "motorista",
            "nome_responsavel",
            "rg_responsavel",
        ]
        widgets = {
            "veiculo": forms.Select(attrs={"class": "form-select"}),
            "motorista": forms.Select(attrs={"class": "form-select"}),
            "tipo_veiculo": forms.TextInput(attrs={"class": "form-control"}),
            "combustivel": forms.TextInput(attrs={"class": "form-control"}),
            "placa_oficial": forms.TextInput(attrs={"class": "form-control"}),
            "placa_reservada": forms.TextInput(attrs={"class": "form-control"}),
            "nome_responsavel": forms.TextInput(attrs={"class": "form-control"}),
            "rg_responsavel": forms.TextInput(attrs={"class": "form-control"}),
        }


class DiarioTrechoForm(forms.ModelForm):
    class Meta:
        model = DiarioBordoTrecho
        fields = [
            "ordem",
            "data_saida",
            "hora_saida",
            "km_inicial",
            "data_chegada",
            "hora_chegada",
            "km_final",
            "origem",
            "destino",
            "necessidade_abastecimento",
            "observacao",
        ]
        widgets = {
            "ordem": forms.HiddenInput(),
            "data_saida": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "hora_saida": forms.TimeInput(format="%H:%M", attrs={"class": "form-control", "type": "time"}),
            "km_inicial": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "data_chegada": forms.DateInput(format="%Y-%m-%d", attrs={"class": "form-control", "type": "date"}),
            "hora_chegada": forms.TimeInput(format="%H:%M", attrs={"class": "form-control", "type": "time"}),
            "km_final": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "origem": forms.TextInput(attrs={"class": "form-control"}),
            "destino": forms.TextInput(attrs={"class": "form-control"}),
            "necessidade_abastecimento": forms.Select(
                choices=((False, "Não"), (True, "Sim")),
                attrs={"class": "form-select"},
            ),
            "observacao": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        km_inicial = cleaned.get("km_inicial")
        km_final = cleaned.get("km_final")
        if km_inicial is not None and km_final is not None and km_final < km_inicial:
            self.add_error("km_final", "KM final não pode ser menor que KM inicial.")
        saida_data = cleaned.get("data_saida")
        saida_hora = cleaned.get("hora_saida")
        chegada_data = cleaned.get("data_chegada")
        chegada_hora = cleaned.get("hora_chegada")
        origem = (cleaned.get("origem") or "").strip()
        destino = (cleaned.get("destino") or "").strip()
        if not origem:
            self.add_error("origem", "Origem não pode ficar vazia.")
        if not destino:
            self.add_error("destino", "Destino não pode ficar vazio.")
        if saida_data and chegada_data and chegada_data < saida_data:
            self.add_error("data_chegada", "Data de chegada não pode ser anterior à data de saída.")
        if saida_data and saida_hora and chegada_data and chegada_hora:
            if (chegada_data, chegada_hora) < (saida_data, saida_hora):
                self.add_error("hora_chegada", "Chegada não pode ser anterior à saída.")
        return cleaned


DiarioTrechoFormSet = inlineformset_factory(
    DiarioBordo,
    DiarioBordoTrecho,
    form=DiarioTrechoForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class DiarioAssinadoForm(forms.ModelForm):
    class Meta:
        model = DiarioBordo
        fields = ["arquivo_assinado"]
        widgets = {
            "arquivo_assinado": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "application/pdf"}),
        }

    def clean_arquivo_assinado(self):
        arquivo = self.cleaned_data.get("arquivo_assinado")
        if arquivo and not arquivo.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Envie o arquivo assinado em PDF.")
        return arquivo
