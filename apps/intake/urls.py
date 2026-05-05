from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("", views.intake_home, name="home"),
    path("my-cases/", views.my_cases, name="my_cases"),
    path("<uuid:case_id>/", views.case_detail, name="case_detail"),
    path("<uuid:case_id>/confirm/", views.confirm_receipt, name="confirm_receipt"),
]
