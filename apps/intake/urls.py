from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("", views.intake_home, name="home"),
    path("my-cases/", views.my_cases, name="my_cases"),
    path("my-cases/partial/", views.my_cases_partial, name="my_cases_partial"),
    path("<uuid:case_id>/", views.case_detail, name="case_detail"),
    path("<uuid:case_id>/attachments/<uuid:attachment_id>/", views.serve_attachment, name="serve_attachment"),
    path(
        "<uuid:case_id>/attachments/<uuid:attachment_id>/viewer/",
        views.attachment_pdf_viewer,
        name="attachment_pdf_viewer",
    ),
    path(
        "<uuid:case_id>/attachments/<uuid:attachment_id>/image-viewer/",
        views.attachment_image_viewer,
        name="attachment_image_viewer",
    ),
    path(
        "<uuid:case_id>/attachments/<uuid:attachment_id>/suppress/",
        views.suppress_attachment,
        name="suppress_attachment",
    ),
    path(
        "<uuid:case_id>/attachments/supplemental/add/",
        views.add_supplemental_attachment,
        name="supplemental_attachment_add",
    ),
    path("<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf"),
    path("<uuid:case_id>/pdf-viewer/", views.pdf_viewer, name="pdf_viewer"),
    path("<uuid:case_id>/corrected-resubmission/", views.corrected_resubmission, name="corrected_resubmission"),
    path("<uuid:case_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
    path("<uuid:case_id>/lock/renew/", views.nir_lock_renew, name="nir_lock_renew"),
    path("<uuid:case_id>/lock/release/", views.nir_lock_release, name="nir_lock_release"),
    # Post-schedule intercurrence
    path("closed-cases/", views.closed_cases_search, name="closed_cases_search"),
    path("closed-cases/<uuid:case_id>/", views.closed_case_detail, name="closed_case_detail"),
    path("closed-cases/<uuid:case_id>/pdf/", views.closed_case_pdf, name="closed_case_pdf"),
    path("closed-cases/<uuid:case_id>/pdf-viewer/", views.closed_case_pdf_viewer, name="closed_case_pdf_viewer"),
    path(
        "closed-cases/<uuid:case_id>/attachments/<uuid:attachment_id>/",
        views.closed_case_attachment,
        name="closed_case_attachment",
    ),
    path(
        "closed-cases/<uuid:case_id>/attachments/<uuid:attachment_id>/viewer/",
        views.closed_case_attachment_pdf_viewer,
        name="closed_case_attachment_pdf_viewer",
    ),
    path(
        "closed-cases/<uuid:case_id>/attachments/<uuid:attachment_id>/image-viewer/",
        views.closed_case_attachment_image_viewer,
        name="closed_case_attachment_image_viewer",
    ),
    path("closed-cases/<uuid:case_id>/issue/", views.post_schedule_issue_open, name="post_schedule_issue_open"),
    path("<uuid:case_id>/communication/", views.post_case_communication, name="post_case_communication"),
]
