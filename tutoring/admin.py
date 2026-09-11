from django.contrib import admin

from .models import TutorMessage, TutorStudent


@admin.register(TutorStudent)
class TutorStudentAdmin(admin.ModelAdmin):
    list_display = ("tutor", "student", "active", "created_at")
    list_filter = ("active",)


@admin.register(TutorMessage)
class TutorMessageAdmin(admin.ModelAdmin):
    list_display = ("link", "sender", "created_at", "read_at")
    list_filter = ("created_at", "read_at")
    search_fields = ("body", "sender__email", "link__student__email", "link__tutor__email")
