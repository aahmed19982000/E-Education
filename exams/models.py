"""Exams a teacher sets for a group: one after each session, and one at the end of the level.

Multiple-choice answers are marked automatically; recorded/uploaded voice answers and written
answers wait for the teacher to give them marks. A student must hand a session exam in before the
next session starts, otherwise it shows as late.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from courses.models import Cohort, Lesson, private_storage
from quiz.models import AUDIO_EXTENSIONS


class Exam(models.Model):
    KIND_SESSION = "session"
    KIND_LEVEL = "level"
    KIND_CHOICES = [(KIND_SESSION, "امتحان الجلسة"), (KIND_LEVEL, "اختبار نهاية المستوى")]

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="exams")
    # Set for a session exam; empty for the end-of-level exam (it belongs to the whole group).
    lesson = models.OneToOneField(Lesson, null=True, blank=True, on_delete=models.CASCADE, related_name="exam")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_SESSION)
    title = models.CharField(max_length=200, blank=True)
    instructions = models.TextField(blank=True)
    is_published = models.BooleanField(default=False, help_text="Students only see published exams")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["cohort"], condition=Q(kind="level"), name="one_level_exam_per_cohort"),
        ]

    def __str__(self):
        return self.display_title

    def clean(self):
        if self.kind == self.KIND_SESSION and not self.lesson_id:
            raise ValidationError({"lesson": "امتحان الجلسة لازم يكون مرتبطًا بجلسة."})
        if self.lesson_id and self.lesson.cohort_id != self.cohort_id:
            raise ValidationError({"lesson": "الجلسة تابعة لمجموعة أخرى."})

    @property
    def display_title(self):
        if self.title:
            return self.title
        if self.kind == self.KIND_LEVEL:
            return "اختبار نهاية المستوى"
        return f"امتحان الجلسة {self.lesson.number}" if self.lesson_id else "امتحان"

    @property
    def course(self):
        return self.cohort.course

    def _lesson_end(self, lesson):
        return lesson.starts_at + datetime.timedelta(minutes=lesson.duration_minutes)

    @property
    def opens_at(self):
        """When students may start: after the session ends (or after the group's last session)."""
        if self.kind == self.KIND_LEVEL:
            last = self.cohort.lessons.order_by("-starts_at").first()
            return self._lesson_end(last) if last else None
        return self._lesson_end(self.lesson) if self.lesson_id else None

    @property
    def deadline(self):
        """A session exam is due before the next session starts; the level exam has no deadline."""
        if self.kind != self.KIND_SESSION or not self.lesson_id:
            return None
        nxt = self.cohort.lessons.filter(starts_at__gt=self.lesson.starts_at).order_by("starts_at").first()
        return nxt.starts_at if nxt else None

    def is_open(self, now=None):
        opens = self.opens_at
        return self.is_published and opens is not None and (now or timezone.now()) >= opens

    def total_points(self):
        return sum((q.points for q in self.questions.all()), Decimal(0))


class ExamQuestion(models.Model):
    KIND_MCQ = "mcq"
    KIND_VOICE = "voice"
    KIND_TEXT = "text"
    KIND_CHOICES = [(KIND_MCQ, "اختيار من متعدد"), (KIND_VOICE, "إجابة صوتية"), (KIND_TEXT, "إجابة كتابية")]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=6, choices=KIND_CHOICES, default=KIND_MCQ)
    text = models.TextField()
    options = models.JSONField(default=list, blank=True, help_text="Answer choices (multiple choice only)")
    correct_index = models.PositiveSmallIntegerField(null=True, blank=True)
    points = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("1"), validators=[MinValueValidator(Decimal("0"))])

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return self.text[:60]

    @property
    def is_auto(self):
        return self.kind == self.KIND_MCQ

    # Choices and the correct answer are validated by the dashboard form that builds them.


class Submission(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_submissions")
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False)
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = [("exam", "user")]
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.user} → {self.exam}"

    def earned(self):
        return sum((a.points_awarded or Decimal(0) for a in self.answers.all()), Decimal(0))

    def total(self):
        return self.exam.total_points()

    @property
    def percent(self):
        total = self.total()
        return round(self.earned() / total * 100) if total else 0

    def pending_count(self):
        """Answers waiting for the teacher's marks."""
        return sum(1 for a in self.answers.all() if a.points_awarded is None)

    @property
    def is_graded(self):
        return self.pending_count() == 0

    def refresh_graded(self):
        graded = self.is_graded
        if graded and not self.graded_at:
            self.graded_at = timezone.now()
        elif not graded:
            self.graded_at = None
        self.save(update_fields=["graded_at"])


class Answer(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE, related_name="answers")
    choice_index = models.PositiveSmallIntegerField(null=True, blank=True)
    text = models.TextField(blank=True)
    audio_file = models.FileField(upload_to="exams/answers/", storage=private_storage, blank=True,
                                  validators=[FileExtensionValidator(AUDIO_EXTENSIONS)])
    points_awarded = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = [("submission", "question")]
        ordering = ["question__order", "question__pk"]

    def __str__(self):
        return f"{self.submission} / {self.question}"
