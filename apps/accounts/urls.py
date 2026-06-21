"""URL patterns for accounts app."""

from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .password_reset_views import (
    CustomPasswordResetCompleteView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetDoneView,
    RateLimitedPasswordResetView,
)
from .profile_views import CustomPasswordChangeView, profile_view

urlpatterns = [
    path("", views.home_view, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("switch-role/", views.switch_role_view, name="switch_role"),
    # Notifications
    path("notifications/", views.notifications_list, name="notifications"),
    path(
        "notifications/<uuid:notification_id>/open/",
        views.notification_open,
        name="notification_open",
    ),
    path(
        "notifications/<uuid:notification_id>/read/",
        views.notification_mark_read,
        name="notification_mark_read",
    ),
    path(
        "notifications/mark-all-read/",
        views.notifications_mark_all_read,
        name="notifications_mark_all_read",
    ),
    path(
        "notifications/unread-count/",
        views.notifications_unread_count,
        name="notifications_unread_count",
    ),
    # Profile and password change
    path("profile/", profile_view, name="profile"),
    path(
        "password-change/",
        CustomPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="accounts/password_change_done.html"),
        name="password_change_done",
    ),
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
