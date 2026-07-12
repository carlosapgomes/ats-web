"""URL patterns for the doctor app."""

from django.urls import path

from . import views

app_name = "doctor"

urlpatterns = [
    path("", views.doctor_queue, name="queue"),
    path("partials/queue/", views.doctor_queue_partial, name="queue_partial"),
    path("decided/<uuid:case_id>/", views.doctor_decided_detail, name="decided_detail"),
    path("<uuid:case_id>/", views.doctor_decision, name="decision"),
    path("<uuid:case_id>/submit/", views.doctor_submit, name="submit"),
    path("<uuid:case_id>/lock/renew/", views.doctor_lock_renew, name="lock_renew"),
    path("<uuid:case_id>/lock/release/", views.doctor_lock_release, name="lock_release"),
    path("<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf"),
    path("<uuid:case_id>/pdf-viewer/", views.pdf_viewer, name="pdf_viewer"),
    path("cases/<uuid:case_id>/attachments/<uuid:attachment_id>/", views.serve_attachment, name="serve_attachment"),
    path(
        "cases/<uuid:case_id>/attachments/<uuid:attachment_id>/viewer/",
        views.attachment_pdf_viewer,
        name="attachment_pdf_viewer",
    ),
]
