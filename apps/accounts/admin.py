from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import LoginAttempt, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ['full_name']
    list_display = ('full_name', 'phone', 'role', 'is_active', 'is_staff')
    search_fields = ('full_name', 'phone')
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ("Shaxsiy ma'lumot", {'fields': ('full_name', 'role')}),
        ('Ruxsatlar', {'fields': ('is_active', 'is_staff', 'is_superuser', 'must_change_password', 'groups', 'user_permissions')}),
        ('Sanalar', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {'fields': ('phone', 'full_name', 'role', 'password1', 'password2')}),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ('phone', 'failed_count', 'locked_until', 'updated_at')
