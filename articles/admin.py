from django.contrib import admin

from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("order", "title_ar", "title_en", "category_ar", "created_at")
    prepopulated_fields = {"slug": ("title_en",)}
    ordering = ("order", "-created_at")
