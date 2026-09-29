from django.contrib import admin

from .models import TeamMember


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "role_ar", "is_owner", "order")
    ordering = ("-is_owner", "order")
