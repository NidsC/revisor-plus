from django.contrib import admin
from django.urls import include, path

from pages import views as pages_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", pages_views.landing, name="landing"),
    path("after-login/", pages_views.after_login, name="after_login"),
    path("privacy/", pages_views.privacy, name="privacy"),
    path("terms/", pages_views.terms, name="terms"),
    path("family/", include("accounts.urls")),
    path("", include("practice.urls")),
    path("", include("tutoring.urls")),
    path("", include("billing.urls")),
    path("", include("goals.urls")),
    path("vocab/", include("vocab.urls")),
]
