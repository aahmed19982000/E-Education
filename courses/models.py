import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from team.models import WEEKDAYS, TeamMember

RESERVED_SLUGS = {"mine", "checkout", "lesson", "attachment"}
ATTACHMENT_EXTENSIONS = ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "zip", "png", "jpg", "jpeg", "mp3"]


def private_storage():
    """Attachments live outside MEDIA_ROOT so /media/ can never serve them without the access check."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


class Course(models.Model):
    AUDIENCE_STUDENTS = "students"
    AUDIENCE_TEACHERS = "teachers"
    AUDIENCE_CHOICES = [(AUDIENCE_STUDENTS, "طلاب / أشخاص عاديون"), (AUDIENCE_TEACHERS, "مدرّسون")]

    slug = models.SlugField(max_length=255, unique=True, blank=True, allow_unicode=True)
    title_ar = models.CharField(max_length=200)
    title_en = models.CharField(max_length=200, blank=True)
    description_ar = models.TextField(blank=True)
    description_en = models.TextField(blank=True)

    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default=AUDIENCE_STUDENTS)
    offers_group = models.BooleanField(default=True)
    offers_private = models.BooleanField(default=True)
    price_group = models.PositiveIntegerField(null=True, blank=True, help_text="EGP")
    price_private = models.PositiveIntegerField(null=True, blank=True, help_text="EGP")

    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title_ar

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title_en or self.title_ar, allow_unicode=True) or "course"
            slug, n = base, 2
            # "mine" / "checkout" / "lesson" / "attachment" are fixed URLs, not courses.
            while slug in RESERVED_SLUGS or Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def localized(self, lang):
        def pick(ar, en):
            return en if lang == "en" and en else ar
        return {
            "slug": self.slug, "audience": self.audience,
            "modes": self.allowed_modes(),
            "from_price": min((p for p in (self.price_for(m) for m in self.allowed_modes()) if p is not None), default=None),
            "title": pick(self.title_ar, self.title_en),
            "description": pick(self.description_ar, self.description_en),
        }

    def allowed_modes(self):
        modes = []
        if self.offers_group:
            modes.append("group")
        if self.offers_private:
            modes.append("private")
        return modes

    def price_for(self, mode):
        """The course's own price for a mode (courses are not tied to a level)."""
        return self.price_private if mode == "private" else self.price_group


class Cohort(models.Model):
    """A teacher + schedule + students for one course.

    Times are not fixed per course: each group (or private student, a cohort of
    one) has its own teacher and weekly times agreed with the admin.
    """

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="cohorts")
    name = models.CharField(max_length=150, blank=True, help_text="e.g. مجموعة السبت والثلاثاء")
    mode = models.CharField(max_length=10, choices=[("group", "جروب"), ("private", "خصوصي")], default="group")
    teacher = models.ForeignKey(TeamMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="cohorts")
    start_date = models.DateField(null=True, blank=True, help_text="First day sessions are generated from")
    weeks = models.PositiveSmallIntegerField(default=8, validators=[MinValueValidator(1)],
                                             help_text="How many weeks of sessions to generate")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course} — {self.name or self.get_mode_display()} #{self.pk}"

    def generate_lessons(self):
        """Create the sessions for every weekly slot; returns how many were new.

        Safe to run again: a slot/time that already has a session is skipped, so
        manual edits to existing sessions are never overwritten.
        """
        if not self.start_date:
            return 0
        created = 0
        tz = timezone.get_current_timezone()
        existing = set(self.lessons.values_list("starts_at", flat=True))
        end = self.start_date + datetime.timedelta(weeks=self.weeks)
        for slot in self.slots.all():
            offset = (slot.weekday - self.start_date.weekday()) % 7
            day = self.start_date + datetime.timedelta(days=offset)
            while day < end:
                starts_at = timezone.make_aware(datetime.datetime.combine(day, slot.start_time), tz)
                if starts_at not in existing:
                    Lesson.objects.create(
                        cohort=self, slot=slot, starts_at=starts_at,
                        duration_minutes=slot.duration_minutes, title_ar="", title_en="",
                    )
                    existing.add(starts_at)
                    created += 1
                day += datetime.timedelta(days=7)
        self._renumber()
        return created

    def _renumber(self):
        for i, lesson in enumerate(self.lessons.order_by("starts_at", "pk"), start=1):
            if lesson.number != i:
                Lesson.objects.filter(pk=lesson.pk).update(number=i)


class CohortSlot(models.Model):
    """One recurring weekly session time of a cohort."""

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="slots")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60, validators=[MinValueValidator(5)])

    class Meta:
        ordering = ["weekday", "start_time"]
        unique_together = [("cohort", "weekday", "start_time")]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start_time:%H:%M}"


class Lesson(models.Model):
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="lessons")
    slot = models.ForeignKey(CohortSlot, null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons")
    number = models.PositiveIntegerField(default=0)
    title_ar = models.CharField(max_length=200, blank=True)
    title_en = models.CharField(max_length=200, blank=True)
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60, validators=[MinValueValidator(5)])

    zoom_url = models.URLField(blank=True)
    recording_url = models.URLField(blank=True)
    notes_ar = models.TextField(blank=True)
    notes_en = models.TextField(blank=True)

    class Meta:
        ordering = ["starts_at", "pk"]
        unique_together = [("cohort", "starts_at")]

    def __str__(self):
        return f"{self.cohort.course} #{self.number}"

    @property
    def course(self):
        return self.cohort.course

    @property
    def display_title_ar(self):
        return self.title_ar or f"الجلسة {self.number}"

    def localized(self, lang):
        def pick(ar, en):
            return en if lang == "en" and en else ar
        default = f"Session {self.number}" if lang == "en" else f"الجلسة {self.number}"
        return {
            "pk": self.pk, "number": self.number,
            "title": pick(self.title_ar, self.title_en) or default,
            "starts_at": self.starts_at, "duration": self.duration_minutes,
            "notes": pick(self.notes_ar, self.notes_en),
        }

    @property
    def is_past(self):
        return self.starts_at + datetime.timedelta(minutes=self.duration_minutes) < timezone.now()


class LessonAttachment(models.Model):
    KIND_FILE = "file"
    KIND_HOMEWORK = "homework"
    KIND_CHOICES = [(KIND_FILE, "ملف"), (KIND_HOMEWORK, "واجب")]

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attachments")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_FILE)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to="courses/attachments/", storage=private_storage, validators=[FileExtensionValidator(ATTACHMENT_EXTENSIONS)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind", "created_at"]

    def __str__(self):
        return self.title


class Enrollment(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [(STATUS_ACTIVE, "نشط"), (STATUS_CANCELLED, "ملغي")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    # Empty until the admin places the student in a group (teacher + times).
    cohort = models.ForeignKey(Cohort, null=True, blank=True, on_delete=models.SET_NULL, related_name="enrollments")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user", "course")]

    def __str__(self):
        return f"{self.user} → {self.course}"

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    def clean(self):
        if self.cohort_id and self.cohort.course_id != self.course_id:
            raise ValidationError({"cohort": "المجموعة تابعة لكورس آخر."})

    def progress(self):
        """(attended, total sessions, percent) over the student's own cohort."""
        if not self.cohort_id:
            return 0, 0, 0
        total = self.cohort.lessons.count()
        attended = self.attendance.filter(status=Attendance.PRESENT).count()
        return attended, total, round(attended / total * 100) if total else 0


class Attendance(models.Model):
    PRESENT = "present"
    ABSENT = "absent"
    STATUS_CHOICES = [(PRESENT, "حاضر"), (ABSENT, "غائب")]

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="attendance")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PRESENT)

    class Meta:
        unique_together = [("lesson", "enrollment")]

    def __str__(self):
        return f"{self.enrollment} / {self.lesson}: {self.status}"


class EnrollmentRequest(models.Model):
    """A visitor's request to join a course, filled in before (or without) paying.

    Admin follows every request up: unpaid ones are contacted to be won back,
    paid ones to pick a teacher, agree session times and send the level test.
    """

    MODE_GROUP = "group"
    MODE_PRIVATE = "private"
    MODE_CHOICES = [(MODE_GROUP, "جروب"), (MODE_PRIVATE, "خصوصي")]

    STATUS_NEW = "new"
    STATUS_CONTACTED = "contacted"
    STATUS_TEACHER_ASSIGNED = "teacher_assigned"
    STATUS_ENROLLED = "enrolled"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_NEW, "جديد"), (STATUS_CONTACTED, "تم التواصل"),
        (STATUS_TEACHER_ASSIGNED, "تم اختيار المدرس والمواعيد"),
        (STATUS_ENROLLED, "تم التسجيل في الكورس"), (STATUS_CLOSED, "مغلق"),
    ]

    PAY_ONLINE = "online"
    PAY_CONTACT = "contact"
    PAY_METHOD_CHOICES = [(PAY_ONLINE, "دفع أونلاين"), (PAY_CONTACT, "التواصل معي لترتيب الدفع")]

    PAYMENT_UNPAID = "unpaid"
    PAYMENT_PAID = "paid"
    PAYMENT_CHOICES = [(PAYMENT_UNPAID, "لم يدفع"), (PAYMENT_PAID, "دفع")]

    KIND_STUDENT = "student"
    KIND_TEACHER = "teacher"
    KIND_CHOICES = [(KIND_STUDENT, "طالب"), (KIND_TEACHER, "مدرّس")]

    # A teacher request is a booking for the teachers' workshop: it has no course.
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=KIND_STUDENT)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, related_name="requests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="enrollment_requests")
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_GROUP)
    preferred_times = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_UNPAID)
    payment_method = models.CharField(max_length=10, choices=PAY_METHOD_CHOICES, default=PAY_CONTACT)
    assigned_teacher = models.ForeignKey(TeamMember, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} → {self.course}"

    @property
    def is_paid(self):
        return self.payment_status == self.PAYMENT_PAID

    @property
    def price(self):
        return self.course.price_for(self.mode) if self.course else None
