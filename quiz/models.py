from django.db import models


class Question(models.Model):
    order = models.PositiveIntegerField(default=0)

    tag_ar = models.CharField(max_length=100, help_text="e.g. قواعد / Grammar")
    tag_en = models.CharField(max_length=100)

    passage_ar = models.TextField(blank=True, help_text="Reading passage, if this is a reading question")
    passage_en = models.TextField(blank=True)

    audio_label_ar = models.CharField(max_length=200, blank=True, help_text="Label shown for listening questions")
    audio_label_en = models.CharField(max_length=200, blank=True)

    text_ar = models.TextField()
    text_en = models.TextField()

    options_ar = models.JSONField(help_text="List of 4 answer strings")
    options_en = models.JSONField(help_text="List of 4 answer strings")

    correct_index = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Q{self.order}: {self.tag_ar}"

    def localized(self, lang):
        return {
            "id": self.pk,
            "tag": self.tag_ar if lang == "ar" else self.tag_en,
            "passage": self.passage_ar if lang == "ar" else self.passage_en,
            "audio": self.audio_label_ar if lang == "ar" else self.audio_label_en,
            "text": self.text_ar if lang == "ar" else self.text_en,
            "options": self.options_ar if lang == "ar" else self.options_en,
        }
