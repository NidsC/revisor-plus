from django.urls import path

from . import views

app_name = "practice"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("practice/", views.choose, name="choose"),
    path("practice/subject/<str:code>/", views.subject_detail, name="subject_detail"),
    path("practice/start/<int:subtopic_id>/", views.start, name="start"),
    path("practice/question/", views.question, name="question"),
    path("practice/answer/", views.answer, name="answer"),
    path("practice/next/", views.next_q, name="next"),
    path("practice/pause/", views.pause, name="pause"),
    path("practice/resume/<int:session_id>/", views.resume, name="resume"),
    path("practice/summary/", views.summary, name="summary"),
    path("mocks/", views.mock_choose, name="mock_choose"),
    path("mocks/start/<int:section_id>/", views.mock_start, name="mock_start"),
    path("mocks/targeted/", views.mock_start_targeted, name="mock_start_targeted"),
    path("mocks/result/", views.mock_result, name="mock_result"),
]
