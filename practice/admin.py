from django.contrib import admin

from .models import Attempt, TestSession


@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ("student", "mode", "subtopic", "started_at", "finished_at")
    list_filter = ("mode",)


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "question", "subtopic", "is_correct", "source", "created_at")
    list_filter = ("is_correct", "source", "subtopic__section")
