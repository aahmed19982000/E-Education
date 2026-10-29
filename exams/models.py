"""Exams set per course level: one after each session, and one at the end of the level.

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

from courses.models import Cohort, CourseLevel, private_storage
from quiz.models import AUDIO_EXTENSIONS


class Exam(models.Model):
    KIND_SESSION = "session"
    KIND_LEVEL = "level"
    KIND_CHOICES = [(KIND_SESSION, "امتحان الجلسة"), (KIND_LEVEL, "اختبار نهاية المستوى")]

    # The questions belong to a course level, so every group at that level gets the same exam.
    level = models.ForeignKey(CourseLevel, on_delete=models.CASCADE, related_name="exams")
    # Which session of the level this follows (1, 2, ...); empty for the end-of-level exam.
    number = models.PositiveSmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_SESSION)
    title = models.CharField(max_length=200, blank=True)
    instructions = models.TextField(blank=True)
    is_published = models.BooleanField(default=False, help_text="Students only see published exams")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["level", "kind", "number"]
        constraints = [
            models.UniqueConstraint(fields=["level", "number"], condition=Q(kind="session"), name="one_session_exam_per_level_number"),
            models.UniqueConstraint(fields=["level"], condition=Q(kind="level"), name="one_final_exam_per_level"),
        ]

    def __str__(self):
        return f"{self.level} / {self.display_title}"

    def clean(self):
        if self.kind == self.KIND_SESSION and not self.number:
            raise ValidationError({"number": "امتحان الجلسة لازم يكون له رقم جلسة."})

    @property
    def display_title(self):
        if self.title:
            return self.title
        if self.kind == self.KIND_LEVEL:
            return "اختبار نهاية المستوى"
        return f"امتحان الجلسة {self.number}" if self.number else "امتحان"

    @property
    def course(self):
        return self.level.course

    @staticmethod
    def _lesson_end(lesson):
        return lesson.starts_at + datetime.timedelta(minutes=lesson.duration_minutes)

    def lesson_for(self, cohort):
        """The session of this group the exam follows (None for the end-of-level exam)."""
        return cohort.lessons.filter(number=self.number).first() if self.kind == self.KIND_SESSION else None

    # Timing differs per group because every group has its own session dates.
    def opens_at(self, cohort):
        """When the group's students may start: after the session ends (or after the group's last session)."""
        if self.kind == self.KIND_LEVEL:
            last = cohort.lessons.order_by("-starts_at").first()
            return self._lesson_end(last) if last else None
        lesson = self.lesson_for(cohort)
        return self._lesson_end(lesson) if lesson else None

    def deadline(self, cohort):
        """A session exam is due before the group's next session starts; the level exam has no deadline."""
        lesson = self.lesson_for(cohort)
        if lesson is None:
            return None
        nxt = cohort.lessons.filter(starts_at__gt=lesson.starts_at).order_by("starts_at").first()
        return nxt.starts_at if nxt else None

    def is_open(self, cohort, now=None):
        opens = self.opens_at(cohort)
        return self.is_published and opens is not None and (now or timezone.now()) >= opens

    def total_points(self):
        return sum((q.points for q in self.questions.all()), Decimal(0))


class ExamQuestion(models.Model):
    KIND_MCQ = "mcq"
    KIND_VOICE = "voice"
    KIND_TEXT = "text"
    KIND_CHOICES = [(KIND_MCQ, "اختيار من متعدد"), (KIND_VOICE, "إجابة صوتية"), (KIND_TEXT, "إجابة كتابية")]

    # What the question shows before it is asked, like the placement test: nothing extra, a reading
    # passage, or an audio clip. Derived from the fields below (see `content`).
    CONTENT_STANDARD = "standard"
    CONTENT_READING = "reading"
    CONTENT_LISTENING = "listening"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=6, choices=KIND_CHOICES, default=KIND_MCQ)
    passage = models.TextField(blank=True, help_text="Reading passage, for a reading question")
    audio_file = models.FileField(upload_to="exams/audio/", blank=True,
                                  validators=[FileExtensionValidator(AUDIO_EXTENSIONS)],
                                  help_text="Audio clip, for a listening question")
    audio_label = models.CharField(max_length=200, blank=True, help_text="Label shown above the audio clip")
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

    @property
    def content(self):
        if self.audio_file or self.audio_label:
            return self.CONTENT_LISTENING
        if self.passage:
            return self.CONTENT_READING
        return self.CONTENT_STANDARD

    # Choices and the correct answer are validated by the dashboard form that builds them.


class Submission(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exam_submissions")
    # The group the student was in when they handed in (its teacher marks the answers).
    cohort = models.ForeignKey(Cohort, null=True, blank=True, on_delete=models.SET_NULL, related_name="exam_submissions")
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
        if graded:
            from courses.certificates import issue_if_eligible
            issue_if_eligible(self)


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
