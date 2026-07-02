from django import forms
from django.core.exceptions import ValidationError
from .models import Document
import os

class SecureDocumentForm(forms.ModelForm):
    # Sensitive field which will be encrypted at rest in the model
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Notas confidenciales adicionales (cifradas en reposo)...'}),
        required=False,
        label="Notas Confidenciales"
    )

    class Meta:
        model = Document
        fields = ['title', 'description', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Título del documento o evidencia'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Descripción del contenido...'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            return file

        # 1. Enforce file size limit (e.g., Max 10MB)
        max_size = 10 * 1024 * 1024 # 10MB
        if file.size > max_size:
            raise ValidationError("El tamaño del archivo supera el límite de 10 MB.")

        # 2. Enforce extension whitelist (prevent uploading executable/executable-related scripts)
        allowed_extensions = ['.pdf', '.zip', '.png', '.jpg', '.jpeg', '.docx', '.xlsx', '.txt', '.csv', '.json']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_extensions:
            raise ValidationError(f"Extensión de archivo no permitida. Permitidos: {', '.join(allowed_extensions)}")

        return file
        #Hola
