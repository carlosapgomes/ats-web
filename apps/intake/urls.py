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
        "<uuid:case_id>/attachments/<uuid:attachment_id>/suppress/",
        views.suppress_attachment,
        name="suppress_attachment",
    ),
    path("<uuid:case_id>/pdf/", views.serve_pdf, name="serve_pdf"),
    path("<uuid:case_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
    path("<uuid:case_id>/lock/renew/", views.nir_lock_renew, name="nir_lock_renew"),
    path("<uuid:case_id>/lock/release/", views.nir_lock_release, name="nir_lock_release"),
    # Post-schedule intercurrence
    path("closed-cases/", views.closed_cases_search, name="closed_cases_search"),
    path("closed-cases/<uuid:case_id>/issue/", views.post_schedule_issue_open, name="post_schedule_issue_open"),
]
