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
        fields = ["username", "email", "password", "roles"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        field_attrs = {"class": "form-control"}
        self.fields["username"].widget.attrs.update(field_attrs)
        self.fields["email"].widget.attrs.update(field_attrs)

    def save(self, commit: bool = True) -> Any:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserUpdateForm(forms.ModelForm):  # type: ignore[type-arg]
    """Formulário para editar usuário (email e papéis apenas).

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
        fields = ["email", "roles"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"class": "form-control"})
        # Armazena username para exibição readonly
        if self.instance and self.instance.pk:
            self._username: str = self.instance.username

    @property
    def username(self) -> str:
        """Retorna o username do usuário (readonly)."""
        return getattr(self, "_username", "")
