from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

class UserRegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150, 
        required=True, 
        label="Nombre de Usuario",
        error_messages={'required': 'El nombre de usuario es obligatorio.'}
    )
    email = forms.EmailField(
        required=True, 
        label="Correo Electrónico",
        error_messages={'required': 'El correo electrónico es obligatorio.'}
    )
    password = forms.CharField(
        widget=forms.PasswordInput(), 
        required=True, 
        label="Contraseña",
        error_messages={'required': 'La contraseña es obligatoria.'}
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(), 
        required=True, 
        label="Confirmar Contraseña",
        error_messages={'required': 'Debes confirmar la contraseña.'}
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("El nombre de usuario ya está registrado.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Las contraseñas no coinciden.")

        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                # Add validation errors to password field
                for message in e.messages:
                    self.add_error('password', message)
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    two_factor = forms.BooleanField(required=False, label="Habilitar 2FA")

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        error_messages = {
            'email': {
                'required': 'El correo electrónico es obligatorio.',
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['two_factor'].initial = self.instance.profile.two_factor_enabled

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if not email:
            raise ValidationError("El correo electrónico es obligatorio.")
        # Ensure email is unique except for the current user
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError("Este correo electrónico ya está registrado por otro usuario.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if hasattr(user, 'profile'):
            user.profile.two_factor_enabled = self.cleaned_data.get('two_factor', False)
            if commit:
                user.profile.save()
        return user


class UserLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150, 
        required=True, 
        label="Usuario",
        error_messages={'required': 'El nombre de usuario es obligatorio.'}
    )
    password = forms.CharField(
        widget=forms.PasswordInput(), 
        required=True, 
        label="Contraseña",
        error_messages={'required': 'La contraseña es obligatoria.'}
    )
