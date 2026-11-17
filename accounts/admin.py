from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "full_name", "role", "terms_version", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    ordering = ("email",)
    readonly_fields = ("terms_accepted_at", "terms_version")
    fieldsets = UserAdmin.fieldsets + (
        ("RevisorPlus", {"fields": ("role", "full_name")}),
        ("Agreement", {"fields": ("terms_accepted_at", "terms_version")}),
    )
