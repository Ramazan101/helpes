from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

admin.site.site_header = "Help Desk — Администрирование"
admin.site.site_title = "Help Desk"
admin.site.index_title = "Управление системой заявок"


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "full_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Профиль Help Desk", {"fields": ("full_name", "role")}),
    )
