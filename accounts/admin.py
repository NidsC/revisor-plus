from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("email", "full_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")
    ordering = ("email",)
    fieldsets = UserAdmin.fieldsets + (
        ("RevisorPlus", {"fields": ("role", "full_name")}),
    )
