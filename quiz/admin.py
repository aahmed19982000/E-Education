from django.contrib import admin

from .models import Category, Question, QuizSettings


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("order", "category", "text_ar", "correct_index", "points")
    list_select_related = ("category",)
    ordering = ("order",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_ar", "name_en")


admin.site.register(QuizSettings)
