from django.contrib import admin

from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("student", "tutor", "subtopic", "due_date", "status")
    list_filter = ("status", "subtopic__section")
