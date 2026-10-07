from django.urls import path

from . import api

app_name = "vocab"

urlpatterns = [
    path("api/me/", api.me, name="api_me"),
    path("api/round/", api.round_view, name="api_round"),
    path("api/round/<int:round_id>/", api.round_detail, name="api_round_detail"),
    path("api/answer/", api.answer, name="api_answer"),
]
