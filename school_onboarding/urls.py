from django.urls import path

from . import views

app_name = "school_onboarding"

urlpatterns = [
    path("", views.onboarding, name="onboarding"),
    path("api/search/", views.search_schools, name="search"),
    path("api/save/", views.save_selection, name="save"),
    path("api/skip/", views.skip_onboarding, name="skip"),
]
