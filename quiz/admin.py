from django.contrib import admin

from .models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("order", "tag_ar", "text_ar", "correct_index")
    ordering = ("order",)
