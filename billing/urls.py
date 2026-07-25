from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("billing/", views.pricing, name="pricing"),
    path("billing/checkout/", views.checkout, name="checkout"),
    path("billing/success/", views.success, name="success"),
    path("billing/cancel/", views.cancel, name="cancel"),
]
