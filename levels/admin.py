from django.contrib import admin

from .models import Level


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("order", "code", "name_ar", "name_en", "price_group", "price_private")
    list_editable = ("code", "name_ar", "name_en", "price_group", "price_private")
    ordering = ("order",)
