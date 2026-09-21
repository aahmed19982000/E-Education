from django.db import models
from django.utils.text import slugify


class Article(models.Model):
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    category_ar = models.CharField(max_length=100)
    category_en = models.CharField(max_length=100)

    title_ar = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255)

    excerpt_ar = models.TextField()
    excerpt_en = models.TextField()

    body_ar = models.TextField(blank=True)
    body_en = models.TextField(blank=True)

    read_time_ar = models.CharField(max_length=50)
    read_time_en = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.title_ar

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title_en or self.title_ar, allow_unicode=True)
        super().save(*args, **kwargs)

    def localized(self, lang):
        return {
            "id": self.pk,
            "slug": self.slug,
            "category": self.category_ar if lang == "ar" else self.category_en,
            "title": self.title_ar if lang == "ar" else self.title_en,
            "excerpt": self.excerpt_ar if lang == "ar" else self.excerpt_en,
            "body": self.body_ar if lang == "ar" else self.body_en,
            "read_time": self.read_time_ar if lang == "ar" else self.read_time_en,
        }
