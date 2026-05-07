"""URL patterns for the scheduler app."""

from django.urls import path

from . import views

app_name = "scheduler"

urlpatterns = [
    path("", views.scheduler_queue, name="queue"),
    path("<uuid:case_id>/", views.scheduler_confirm, name="confirm"),
    path("<uuid:case_id>/submit/", views.scheduler_submit, name="submit"),
]
