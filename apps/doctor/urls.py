"""URL patterns for the doctor app."""

from django.urls import path

from . import views

app_name = "doctor"

urlpatterns = [
    path("", views.doctor_queue, name="queue"),
    path("partials/queue/", views.doctor_queue_partial, name="queue_partial"),
    path("<uuid:case_id>/", views.doctor_decision, name="decision"),
    path("<uuid:case_id>/submit/", views.doctor_submit, name="submit"),
    path("<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf"),
]
