"""Forms for admin_ui user management."""

from typing import Any

from django import forms
from django.contrib.auth import get_user_model

from apps.accounts.models import Role

User = get_user_model()


class UserCreateForm(forms.ModelForm):  # type: ignore[type-arg]
    """Formulário para criar novo usuário com papéis."""

    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        required=True,
    )
    roles = forms.ModelMultipleChoiceField(
        label="Papéis",
        queryset=Role.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "roles", "professional_council", "professional_council_number"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        field_attrs = {"class": "form-control"}
        self.fields["username"].widget.attrs.update(field_attrs)
        self.fields["email"].widget.attrs.update(field_attrs)
        self.fields["professional_council"].widget.attrs.update({"class": "form-select"})
        self.fields["professional_council_number"].widget.attrs.update(field_attrs)

    def save(self, commit: bool = True) -> Any:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
        return user


PROMPT_NAME_CHOICES = [
    ("llm1_system", "LLM1 - System Prompt"),
    ("llm1_user", "LLM1 - User Prompt"),
    ("llm2_system", "LLM2 - System Prompt"),
    ("llm2_user", "LLM2 - User Prompt"),
]


class PromptCreateForm(forms.Form):  # type: ignore[type-arg]
    """Formulário para criar nova versão de prompt."""

    name = forms.ChoiceField(
        label="Nome do Prompt",
        choices=PROMPT_NAME_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    content = forms.CharField(
        label="Conteúdo",
        widget=forms.Textarea(
            attrs={
                "class": "form-control font-monospace",
                "rows": 20,
                "placeholder": "Digite o conteúdo do prompt...",
            }
        ),
        required=True,
    )


class UserUpdateForm(forms.ModelForm):  # type: ignore[type-arg]
    """Formulário para editar usuário (email, papéis e conselho profissional).

    Username é exibido como readonly (não editável).
    """

    roles = forms.ModelMultipleChoiceField(
        label="Papéis",
        queryset=Role.objects.all().order_by("name"),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ["email", "roles", "professional_council", "professional_council_number"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"class": "form-control"})
        self.fields["professional_council"].widget.attrs.update({"class": "form-select"})
        self.fields["professional_council_number"].widget.attrs.update({"class": "form-control"})
        # Armazena username para exibição readonly
        if self.instance and self.instance.pk:
            self._username: str = self.instance.username

    @property
    def username(self) -> str:
        """Retorna o username do usuário (readonly)."""
        return getattr(self, "_username", "")
