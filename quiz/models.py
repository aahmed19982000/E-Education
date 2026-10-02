from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models

AUDIO_EXTENSIONS = ["mp3", "wav", "ogg", "oga", "m4a", "aac", "webm"]
AUDIO_MAX_MB = 20
MIN_OPTIONS = 2
MAX_OPTIONS = 6


class Category(models.Model):
    """Question category shown above each quiz question (e.g. قواعد / Grammar)."""

    name_ar = models.CharField(max_length=100, unique=True)
    name_en = models.CharField(max_length=100, blank=True, help_text="Optional; falls back to Arabic")

    class Meta:
        ordering = ["name_ar"]
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name_ar

    def localized_name(self, lang):
        return self.name_en if lang == "en" and self.name_en else self.name_ar


class Question(models.Model):
    KIND_STANDARD = "standard"
    KIND_READING = "reading"
    KIND_LISTENING = "listening"

    order = models.PositiveIntegerField(default=0)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="questions")

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

    points = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Marks for this question (used when grading per question)",
    )

    time_limit_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Seconds allowed for this question. Empty = use the default from quiz settings.",
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Q{self.order}: {self.category}"

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
            "tag": self.category.localized_name(lang),
            "passage": pick(self.passage_ar, self.passage_en),
            "audio": pick(self.audio_label_ar, self.audio_label_en),
            "audio_url": self.audio_file.url if self.audio_file else "",
            "text": pick(self.text_ar, self.text_en),
            "options": options,
        }


class QuizSettings(models.Model):
    """Single-row settings for the level test (always pk=1; use QuizSettings.load())."""

    MODE_PER_QUESTION = "per_question"
    MODE_TOTAL = "total"
    MODE_CHOICES = [
        (MODE_PER_QUESTION, "درجة لكل سؤال"),
        (MODE_TOTAL, "درجة كلية للاختبار"),
    ]

    grading_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_TOTAL)
    total_marks = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal("100"),
        validators=[MinValueValidator(Decimal("1"))],
        help_text="Whole-test marks, split equally across questions (total mode)",
    )

    exam_time_minutes = models.PositiveIntegerField(
        default=0, help_text="Time limit for the whole test in minutes (0 = no limit)",
    )
    question_time_seconds = models.PositiveIntegerField(
        default=0, help_text="Default time per question in seconds (0 = no limit)",
    )

    class Meta:
        verbose_name = "Quiz settings"
        verbose_name_plural = "Quiz settings"

    def __str__(self):
        return "Quiz settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_per_question(self):
        return self.grading_mode == self.MODE_PER_QUESTION

    def question_limit(self, question):
        """Seconds allowed for `question`, or None for no limit."""
        seconds = question.time_limit_seconds if question.time_limit_seconds is not None else self.question_time_seconds
        return seconds or None


class PlacementResult(models.Model):
    """A signed-in student's level-test result, shown on their first course session."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="placement_results")
    percent = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.percent}%"
