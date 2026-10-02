import re

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

VIDEO_EXTENSIONS = ["mp4", "webm", "mov"]
VIDEO_MAX_MB = 50

_YOUTUBE_ID = re.compile(
    r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})"
)


def youtube_id(url):
    match = _YOUTUBE_ID.search(url or "")
    return match.group(1) if match else ""


def split_list(text):
    """Split a comma / newline separated field into clean items."""
    return [p.strip() for p in re.split(r"[,\n،]", text or "") if p.strip()]


WEEKDAYS = [
    (0, "الاثنين"), (1, "الثلاثاء"), (2, "الأربعاء"), (3, "الخميس"),
    (4, "الجمعة"), (5, "السبت"), (6, "الأحد"),
]


class TeamMember(models.Model):
    slug = models.SlugField(max_length=255, unique=True, blank=True, allow_unicode=True)
    order = models.PositiveIntegerField(default=0)
    is_owner = models.BooleanField(default=False)

    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150, blank=True)

    role_ar = models.CharField(max_length=150)
    role_en = models.CharField(max_length=150, blank=True)

    specialties_ar = models.TextField(blank=True)
    specialties_en = models.TextField(blank=True)

    bio_ar = models.TextField(blank=True)
    bio_en = models.TextField(blank=True)

    youtube_url = models.URLField(blank=True)
    photo = models.ImageField(upload_to="team/", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_owner", "order", "created_at"]

    def __str__(self):
        return self.name_ar

    def clean(self):
        if self.youtube_url and not youtube_id(self.youtube_url):
            raise ValidationError({"youtube_url": "رابط يوتيوب غير صالح."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name_en or self.name_ar, allow_unicode=True) or "member"
            slug, n = base, 2
            while TeamMember.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def localized(self, lang):
        """Arabic is the master copy: empty English fields fall back to it."""
        def pick(ar, en):
            return ar if lang == "ar" else (en or ar)

        return {
            "slug": self.slug,
            "is_owner": self.is_owner,
            "name": pick(self.name_ar, self.name_en),
            "role": pick(self.role_ar, self.role_en),
            "specialties": split_list(pick(self.specialties_ar, self.specialties_en)),
            "bio": pick(self.bio_ar, self.bio_en),
            "photo_url": self.photo.url if self.photo else "",
            "video_id": youtube_id(self.youtube_url),
        }


class TeamReview(models.Model):
    """A student review of a team member: written, YouTube link, or uploaded video."""

    member = models.ForeignKey(TeamMember, on_delete=models.CASCADE, related_name="reviews")
    order = models.PositiveIntegerField(default=0)
    student_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True)
    youtube_url = models.URLField(blank=True)
    video_file = models.FileField(
        upload_to="team/reviews/", blank=True,
        validators=[FileExtensionValidator(VIDEO_EXTENSIONS)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return f"{self.student_name} → {self.member}"

    def clean(self):
        if self.youtube_url and not youtube_id(self.youtube_url):
            raise ValidationError({"youtube_url": "رابط يوتيوب غير صالح."})
        if not (self.text.strip() or self.youtube_url or self.video_file):
            raise ValidationError("أضف نص التقييم أو فيديو (رابط يوتيوب أو ملف).")

    def as_dict(self):
        return {
            "student_name": self.student_name,
            "rating": self.rating,
            "stars": range(self.rating),
            "text": self.text,
            "video_id": youtube_id(self.youtube_url),
            "video_url": self.video_file.url if self.video_file else "",
        }


class TeacherAvailability(models.Model):
    """A weekly window in which a teacher can take sessions."""

    member = models.ForeignKey(TeamMember, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.member} {self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "وقت النهاية يجب أن يكون بعد وقت البداية."})
