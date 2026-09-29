import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

_YOUTUBE_ID = re.compile(
    r"(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})"
)


def youtube_id(url):
    match = _YOUTUBE_ID.search(url or "")
    return match.group(1) if match else ""


def split_list(text):
    """Split a comma / newline separated field into clean items."""
    return [p.strip() for p in re.split(r"[,\n،]", text or "") if p.strip()]


class TeamMember(models.Model):
    slug = models.SlugField(max_length=255, unique=True, blank=True, allow_unicode=True)
    order = models.PositiveIntegerField(default=0)
    is_owner = models.BooleanField(default=False)

    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)

    role_ar = models.CharField(max_length=150)
    role_en = models.CharField(max_length=150)

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
        ar = lang == "ar"
        video = youtube_id(self.youtube_url)
        return {
            "slug": self.slug,
            "is_owner": self.is_owner,
            "name": self.name_ar if ar else self.name_en,
            "role": self.role_ar if ar else self.role_en,
            "specialties": split_list(self.specialties_ar if ar else self.specialties_en),
            "bio": self.bio_ar if ar else self.bio_en,
            "photo_url": self.photo.url if self.photo else "",
            "video_id": video,
        }
