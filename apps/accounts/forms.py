"""Forms for account authentication and role selection."""

from django import forms


class LoginForm(forms.Form):
    """Formulário de login com username e senha."""

    username = forms.CharField(
        label="Usuário",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "nome de usuário", "autofocus": True}),
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
