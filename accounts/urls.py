from django.urls import path

from . import views

app_name = "family"

urlpatterns = [
    path("", views.home, name="home"),
    path("add-child/", views.add_child, name="add_child"),
    path("child/<int:pupil_id>/", views.child, name="child"),
    path("child/<int:pupil_id>/reset-password/", views.reset_child_password, name="reset_child_password"),
]
