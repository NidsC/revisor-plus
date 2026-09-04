from django.contrib import admin

from .models import School, SchoolOnboardingState, StudentTargetSchool


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "urn",
        "postcode",
        "town",
        "phase",
        "establishment_type",
        "status",
    )
    list_filter = ("status", "phase", "admissions_policy", "gender")
    search_fields = ("name", "urn", "postcode", "town")
    ordering = ("name",)


@admin.register(StudentTargetSchool)
class StudentTargetSchoolAdmin(admin.ModelAdmin):
    list_display = ("user", "school", "created_at")
    search_fields = ("user__username", "user__email", "school__name", "school__urn")
    autocomplete_fields = ("school",)


@admin.register(SchoolOnboardingState)
class SchoolOnboardingStateAdmin(admin.ModelAdmin):
    list_display = ("user", "completed_at", "skipped_at", "last_postcode", "updated_at")
    search_fields = ("user__username", "user__email", "last_postcode")
