from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_index, name="index"),
    path("summaries/", views.dashboard_summaries, name="summaries"),
    path("<uuid:case_id>/attachments/<uuid:attachment_id>/", views.dashboard_case_attachment, name="case_attachment"),
    path(
        "<uuid:case_id>/attachments/<uuid:attachment_id>/pdf-viewer/",
        views.dashboard_attachment_pdf_viewer,
        name="attachment_pdf_viewer",
    ),
    path(
        "<uuid:case_id>/attachments/<uuid:attachment_id>/image-viewer/",
        views.dashboard_attachment_image_viewer,
        name="attachment_image_viewer",
    ),
    path("<uuid:case_id>/", views.dashboard_case_detail, name="case_detail"),
    path("<uuid:case_id>/pdf/", views.dashboard_case_pdf, name="case_pdf"),
    path("<uuid:case_id>/pdf-viewer/", views.dashboard_pdf_viewer, name="pdf_viewer"),
    path("<uuid:case_id>/administrative-close/", views.dashboard_administrative_close, name="administrative_close"),
]
