from django.db import models


class Level(models.Model):
    code = models.CharField(max_length=10, unique=True, help_text="e.g. A1, B2, C1")
    order = models.PositiveIntegerField(default=0)

    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    description_ar = models.TextField()
    description_en = models.TextField()
    duration_ar = models.CharField(max_length=100)
    duration_en = models.CharField(max_length=100)

    price_group = models.PositiveIntegerField(help_text="Price in EGP for group sessions")
    price_private = models.PositiveIntegerField(help_text="Price in EGP for private sessions")

    class Meta:
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.code} — {self.name_ar}"

    def localized(self, lang, mode):
        return {
            "code": self.code,
            "name": self.name_ar if lang == "ar" else self.name_en,
            "desc": self.description_ar if lang == "ar" else self.description_en,
            "duration": self.duration_ar if lang == "ar" else self.duration_en,
            "price": self.price_group if mode == "group" else self.price_private,
        }
