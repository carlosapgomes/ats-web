"""Forms for account authentication and role selection."""

from django import forms


class LoginForm(forms.Form):
    """Formulário de login com email e senha."""

    username = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "seu@email.com", "autofocus": True}),
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Sua senha"}),
    )


class RoleSelectForm(forms.Form):
    """Formulário para seleção de papel ativo."""

    role = forms.CharField(
        max_length=20,
        widget=forms.HiddenInput(),
    )
