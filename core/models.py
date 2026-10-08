from urllib.parse import quote

from django.db import models

from accounts.phone import validate_whatsapp, whatsapp_digits


class SiteSettings(models.Model):
    """Site-wide settings edited from the dashboard (one row)."""

    whatsapp_number = models.CharField(
        max_length=30, blank=True, validators=[validate_whatsapp],
        help_text="The academy's WhatsApp number. Leave empty to hide the floating button.")
    whatsapp_message = models.CharField(
        max_length=200, blank=True, help_text="Optional text pre-filled in the visitor's chat.")

    # What each course type includes, shown to visitors before they sign up. One feature per line;
    # empty falls back to the defaults in core/translations.py.
    features_group_ar = models.TextField(blank=True)
    features_group_en = models.TextField(blank=True)
    features_semi_private_ar = models.TextField(blank=True)
    features_semi_private_en = models.TextField(blank=True)
    features_private_ar = models.TextField(blank=True)
    features_private_en = models.TextField(blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def plan_features(self, lang):
        """{mode: [feature, ...]} for Group, Semi private and Private in this language.

        The text edited in the dashboard wins; a plan left empty shows the default list.
        """
        from .translations import get_translations
        defaults = get_translations(lang)["courses"]["features"]
        result = {}
        for mode in ("group", "semi_private", "private"):
            text = getattr(self, f"features_{mode}_{'en' if lang == 'en' else 'ar'}")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            result[mode] = lines or list(defaults[mode])
        return result

    @property
    def whatsapp_url(self):
        """wa.me link that opens a chat with the academy, or '' when no usable number is set."""
        digits = whatsapp_digits(self.whatsapp_number)
        if not digits:
            return ""
        url = f"https://wa.me/{digits}"
        return f"{url}?text={quote(self.whatsapp_message)}" if self.whatsapp_message.strip() else url
