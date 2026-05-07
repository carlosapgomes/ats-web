"""URL patterns for the doctor app."""

from django.urls import path

from . import views

app_name = "doctor"

urlpatterns = [
    path("", views.doctor_queue, name="queue"),
    path("<uuid:case_id>/", views.doctor_decision, name="decision"),
    path("<uuid:case_id>/submit/", views.doctor_submit, name="submit"),
]
