from django.contrib import admin
from .models import UserProfile, SecurityAuditLog

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'two_factor_enabled', 'updated_at')
    list_filter = ('role', 'two_factor_enabled')
    search_fields = ('user__username', 'user__email')

@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'severity', 'action', 'user', 'ip_address')
    list_filter = ('severity', 'action')
    search_fields = ('details', 'user__username', 'ip_address')
    readonly_fields = ('timestamp', 'action', 'user', 'ip_address', 'user_agent', 'details', 'severity')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent auditing logs deletion to satisfy A09:2021
        return False
