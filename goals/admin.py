from django.contrib import admin

from .models import Goal, School, SectionTarget


class SectionTargetInline(admin.TabularInline):
    model = SectionTarget
    extra = 0


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "area", "admissions_body", "test_window", "verified", "active")
    list_filter = ("verified", "active", "area")
    search_fields = ("name", "area", "admissions_body")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("papers",)
    fieldsets = (
        (None, {"fields": ("name", "slug", "area", "active")}),
        ("Assessment", {"fields": ("admissions_body", "papers", "test_window")}),
        ("How selection works", {
            "fields": ("requirement_note", "source_url", "source_year", "verified"),
            "description": "Describe selection in words. Do NOT record a pass mark "
                           "unless the school itself publishes one — most do not, "
                           "because cutoffs are rank-based and move every year. Tick "
                           "'verified' only once these details have been checked "
                           "against the school's own admissions material.",
        }),
    )


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("student", "target_label", "exam_date", "target_overall",
                    "target_hours", "set_by", "is_active")
    list_filter = ("is_active", "set_by", "school")
    search_fields = ("student__email", "student__full_name", "school__name")
    autocomplete_fields = ("school",)
    inlines = [SectionTargetInline]
