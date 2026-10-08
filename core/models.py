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

    class Meta:
        verbose_name = verbose_name_plural = "Site settings"

    def __str__(self):
        return "Site settings"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def whatsapp_url(self):
        """wa.me link that opens a chat with the academy, or '' when no usable number is set."""
        digits = whatsapp_digits(self.whatsapp_number)
        if not digits:
            return ""
        url = f"https://wa.me/{digits}"
        return f"{url}?text={quote(self.whatsapp_message)}" if self.whatsapp_message.strip() else url
