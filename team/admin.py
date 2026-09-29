from django.contrib import admin

from .models import TeamMember, TeamReview


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en", "role_ar", "is_owner", "order")
    ordering = ("-is_owner", "order")


@admin.register(TeamReview)
class TeamReviewAdmin(admin.ModelAdmin):
    list_display = ("student_name", "member", "rating", "order")
