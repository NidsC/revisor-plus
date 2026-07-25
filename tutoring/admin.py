from django.contrib import admin

from .models import TutorStudent


@admin.register(TutorStudent)
class TutorStudentAdmin(admin.ModelAdmin):
    list_display = ("tutor", "student", "active", "created_at")
    list_filter = ("active",)
