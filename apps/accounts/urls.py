"""URL patterns for accounts app."""

from django.urls import path

from . import views
from .password_reset_views import (
    CustomPasswordResetCompleteView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetDoneView,
    RateLimitedPasswordResetView,
)

urlpatterns = [
    path("", views.home_view, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("switch-role/", views.switch_role_view, name="switch_role"),
    # Password reset
    path(
        "password-reset/",
        RateLimitedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        CustomPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        CustomPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        CustomPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
