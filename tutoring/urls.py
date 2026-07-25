from django.urls import path

from . import views

app_name = "tutoring"

urlpatterns = [
    path("tutor/", views.dashboard, name="dashboard"),
    path("tutor/student/<int:student_id>/", views.student_detail, name="student_detail"),
    path("tutor/student/<int:student_id>/assign/", views.assign_homework, name="assign"),
]
