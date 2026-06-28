"""Profile and password change views (Slice 002).

Uses Django native PasswordChangeView with custom templates
and session preservation via update_session_auth_hash.
"""

from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import render
from django.urls import reverse


@login_required
def profile_view(request):  # type: ignore[no-untyped-def]
    """Render the profile page with basic user data."""
    user = request.user
    roles = list(user.roles.values_list("name", flat=True))
    active_role = request.session.get("active_role", "")
    return render(
        request,
        "accounts/profile.html",
        {
            "user_roles": roles,
            "active_role": active_role,
        },
    )


class HospitalPasswordChangeForm(PasswordChangeForm):
    """PasswordChangeForm com widgets aderentes ao estilo Bootstrap do app.

    Adiciona a classe 'form-control' aos campos de senha para que os inputs
    usem as bordas e cantos arredondados do tema, harmonizando com o botão
    de mostrar/ocultar senha renderizado ao lado no input-group.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        for field_name in ("old_password", "new_password1", "new_password2"):
            self.fields[field_name].widget.attrs.setdefault("class", "")
            classes = self.fields[field_name].widget.attrs["class"]
            if "form-control" not in classes:
                self.fields[field_name].widget.attrs["class"] = (classes + " form-control").strip()


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    """PasswordChangeView with custom template and session preservation.

    Django's PasswordChangeView automatically calls
    update_session_auth_hash() on successful password change,
    preserving the current session.
    """

    template_name = "accounts/password_change_form.html"
    form_class = HospitalPasswordChangeForm
    success_url = "password_change_done"

    def get_success_url(self) -> str:
        """Return the resolved URL for success redirect."""
        return reverse(self.success_url)
