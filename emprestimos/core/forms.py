from django import forms
from .models import Parcela, Emprestimo

class ParcelaAdminForm(forms.ModelForm):
    comprovante_upload = forms.FileField(required=False, label="Comprovante")

    class Meta:
        model = Parcela
        fields = '__all__'  # isso inclui todos os campos da model, exceto esse extra

    def save(self, commit=True):
        instance = super().save(commit=False)

        upload = self.cleaned_data.get('comprovante_upload')
        if upload:
            instance.comprovante = upload.read()
            instance.tipo_comprovante = upload.content_type

        if commit:
            instance.save()
        return instance

class EmprestimoAdminForm(forms.ModelForm):
    comprovante_upload = forms.FileField(required=False, label="Comprovante")

    class Meta:
        model = Emprestimo
        fields = '__all__'  # isso inclui todos os campos da model, exceto esse extra

    def save(self, commit=True):
        instance = super().save(commit=False)

        upload = self.cleaned_data.get('comprovante_upload')
        if upload:
            instance.comprovante = upload.read()
            instance.tipo_comprovante = upload.content_type

        if commit:
            instance.save()
        return instance