"""Root URL configuration for ATS Web."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import URLPattern, URLResolver, include, path

urlpatterns: list[URLPattern | URLResolver] = [
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("cases/", include("apps.intake.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("doctor/", include("apps.doctor.urls")),
    path("scheduler/", include("apps.scheduler.urls")),
    path("admin-ui/", include("apps.admin_ui.urls")),
]

# Serve media/static files in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
