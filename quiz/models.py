from django.core.validators import FileExtensionValidator
from django.db import models

AUDIO_EXTENSIONS = ["mp3", "wav", "ogg", "oga", "m4a", "aac", "webm"]
AUDIO_MAX_MB = 20
MIN_OPTIONS = 2
MAX_OPTIONS = 6


class Question(models.Model):
    KIND_STANDARD = "standard"
    KIND_READING = "reading"
    KIND_LISTENING = "listening"

    order = models.PositiveIntegerField(default=0)

    tag_ar = models.CharField(max_length=100, help_text="e.g. قواعد / Grammar")
    tag_en = models.CharField(max_length=100, blank=True)

    passage_ar = models.TextField(blank=True, help_text="Reading passage, if this is a reading question")
    passage_en = models.TextField(blank=True)

    audio_file = models.FileField(
        upload_to="quiz/audio/",
        blank=True,
        validators=[FileExtensionValidator(AUDIO_EXTENSIONS)],
        help_text="Audio clip for listening questions",
    )
    audio_label_ar = models.CharField(max_length=200, blank=True, help_text="Label shown for listening questions")
    audio_label_en = models.CharField(max_length=200, blank=True)

    text_ar = models.TextField()
    text_en = models.TextField(blank=True)

    options_ar = models.JSONField(help_text="List of answer strings")
    options_en = models.JSONField(default=list, blank=True, help_text="List of answer strings (optional; falls back to Arabic)")

    correct_index = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Q{self.order}: {self.tag_ar}"

    @property
    def kind(self):
        if self.audio_file or self.audio_label_ar or self.audio_label_en:
            return self.KIND_LISTENING
        if self.passage_ar or self.passage_en:
            return self.KIND_READING
        return self.KIND_STANDARD

    def localized(self, lang):
        """Return the question in `lang`; any blank English field falls back to Arabic."""
        def pick(ar, en):
            return en if lang == "en" and en else ar

        options_en = self.options_en or []
        options = [pick(ar, options_en[i] if i < len(options_en) else "") for i, ar in enumerate(self.options_ar)]
        return {
            "id": self.pk,
            "tag": pick(self.tag_ar, self.tag_en),
            "passage": pick(self.passage_ar, self.passage_en),
            "audio": pick(self.audio_label_ar, self.audio_label_en),
            "audio_url": self.audio_file.url if self.audio_file else "",
            "text": pick(self.text_ar, self.text_en),
            "options": options,
        }
