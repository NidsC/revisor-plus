from django.urls import path

from . import views

app_name = "family"

urlpatterns = [
    path("", views.home, name="home"),
    path("add-child/", views.add_child, name="add_child"),
    path("child/<int:pupil_id>/", views.child, {"parent_page": "overview"}, name="child"),
    path("child/<int:pupil_id>/subjects/", views.child, {"parent_page": "subjects"}, name="child_subjects"),
    path("child/<int:pupil_id>/homework/", views.child, {"parent_page": "homework"}, name="child_homework"),
    path("child/<int:pupil_id>/messages/", views.child, {"parent_page": "messages"}, name="child_messages"),
    path("child/<int:pupil_id>/subject/<str:code>/", views.child_subject, name="child_subject"),
    path("child/<int:pupil_id>/reset-password/", views.reset_child_password, name="reset_child_password"),
]
