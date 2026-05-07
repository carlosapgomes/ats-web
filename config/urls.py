"""Root URL configuration for ATS Web."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("cases/", include("apps.intake.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("doctor/", include("apps.doctor.urls")),
    path("scheduler/", include("apps.scheduler.urls")),
    path("admin-ui/", include("apps.admin_ui.urls")),
]
