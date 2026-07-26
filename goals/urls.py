from django.urls import path

from . import views

app_name = "goals"

urlpatterns = [
    path("goal/", views.detail, name="detail"),
    path("goal/set/", views.setup, name="setup"),
    path("goal/skip/", views.skip, name="skip"),
    # Tutors set a target for one of their own pupils; ownership is enforced in
    # the view via tutoring._owned_student.
    path("goal/set/<int:student_id>/", views.setup, name="setup_for"),
]
